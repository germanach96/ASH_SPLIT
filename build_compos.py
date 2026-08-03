"""Saca la tabla de componentes comprados y quien los consume.

Uso:  python3 build_compos.py

Escribe:
    Ashford components by planner.xlsx   una fila por comprado
    venn_compos.svg                       el Venn de cinco planners

La hoja lleva, por cada comprado, el nivel que ocupa en la piramide y un 1 o un
0 por planner segun lo consuma o no. El nivel es el mismo que usa el visor: el
camino mas largo desde lo que ya no consume nadie, asi que un comprado que entre
tanto en un producto final como en un bulk sale con el nivel mas profundo de los
dos, que es donde se le ve en el dibujo.
"""

import json
from collections import Counter, defaultdict, deque

import pandas as pd

import venn5

XLSX = "Ashford split 2.xlsx"
REPARTO = "ownership_proposal.json"
SALIDA = "Ashford components by planner.xlsx"
SVG = "venn_compos.svg"

OWNERS = ["Sr planner 1", "Sr planner 2", "Jr planner 1", "Jr planner 2", "Intern"]
COLOR = ["#7c3aed", "#db2777", "#65a30d", "#d97706", "#334155"]


def datos():
    """(comprados ordenados, nivel, consumidores) con lo que hace falta aqui."""
    bom = pd.read_excel(XLSX, sheet_name="BOM", dtype=str)
    rate = pd.read_excel(XLSX, sheet_name="RATE", dtype=str)
    owner = {k: int(v) for k, v in json.load(open(REPARTO)).items()}

    codigos = sorted(set(bom.ParentID) | set(bom.ComponentID))
    hijos, padres = defaultdict(list), defaultdict(list)
    for a, b in zip(bom.ParentID, bom.ComponentID):
        hijos[a].append(b)
        padres[b].append(a)
    con_ruta = set(rate.ProductID)

    # Nivel = camino mas largo desde las raices, igual que la piramide del visor.
    grado = {c: len(padres[c]) for c in codigos}
    nivel = dict.fromkeys(codigos, 0)
    cola = deque(c for c in codigos if grado[c] == 0)
    vistos = 0
    while cola:
        x = cola.popleft()
        vistos += 1
        for h in hijos[x]:
            nivel[h] = max(nivel[h], nivel[x] + 1)
            grado[h] -= 1
            if grado[h] == 0:
                cola.append(h)
    assert vistos == len(codigos), "hay un ciclo en la BOM"

    comprados = [c for c in codigos if c not in con_ruta]
    # Quien lo consume: el dueno de cada padre directo. Un comprado cuelga
    # siempre de codigos con ruta, asi que no hace falta subir mas.
    consume = {c: {owner[p] for p in padres[c] if p in owner} for c in comprados}
    return comprados, nivel, consume, padres


def main():
    comprados, nivel, consume, padres = datos()

    filas = []
    for c in comprados:
        quienes = consume[c]
        filas.append({
            "Component": c,
            "Level": nivel[c],
            "Used by": len(quienes),
            "Parents": len(padres[c]),
            **{OWNERS[o]: (1 if o in quienes else 0) for o in range(5)},
        })
    df = pd.DataFrame(filas).sort_values(["Level", "Used by", "Component"],
                                         ascending=[True, False, True])

    with pd.ExcelWriter(SALIDA, engine="openpyxl") as xl:
        df.to_excel(xl, sheet_name="Components", index=False)
        hoja = xl.sheets["Components"]
        hoja.freeze_panes = "A2"
        for col, ancho in zip("ABCDEFGHI", (16, 8, 9, 9, 14, 14, 14, 14, 10)):
            hoja.column_dimensions[col].width = ancho
        hoja.auto_filter.ref = hoja.dimensions

        # Una segunda hoja con el recuento de cada region del Venn, que es lo
        # que hay detras del dibujo.
        regiones = Counter(frozenset(consume[c]) for c in comprados)
        res = [{"Planners": ", ".join(OWNERS[o] for o in sorted(g)) or "(nobody)",
                "How many": len(g), "Components": n}
               for g, n in regiones.items()]
        (pd.DataFrame(res).sort_values(["How many", "Components"], ascending=[True, False])
           .to_excel(xl, sheet_name="Shared by", index=False))
        xl.sheets["Shared by"].column_dimensions["A"].width = 56
        xl.sheets["Shared by"].column_dimensions["B"].width = 11
        xl.sheets["Shared by"].column_dimensions["C"].width = 13

    # El Venn: cada region es la combinacion exacta de planners que lo consumen.
    cuentas = Counter()
    for c in comprados:
        cuentas[sum(1 << o for o in consume[c])] += 1
    totales = [sum(1 for c in comprados if o in consume[c]) for o in range(5)]
    open(SVG, "w").write(venn5.svg(cuentas, OWNERS, COLOR, totales))

    print(f"{SALIDA}: {len(df)} comprados")
    print(f"  niveles: {dict(sorted(Counter(nivel[c] for c in comprados).items()))}")
    print(f"  solo un planner: {sum(1 for c in comprados if len(consume[c]) == 1)}"
          f" | compartidos: {sum(1 for c in comprados if len(consume[c]) > 1)}")
    for o in range(5):
        print(f"    {OWNERS[o]:16} consume {totales[o]:>5}")
    print(f"{SVG}: {len(cuentas)} regiones con codigos de las 31 posibles")


if __name__ == "__main__":
    main()

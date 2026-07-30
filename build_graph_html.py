"""Genera el visor interactivo del arbol de producto de Ashford.

Uso:  python3 build_graph_html.py

Lee 'Ashford split 2.xlsx' (pestanas BOM y RATE ya limpias), calcula el grafo y
lo incrusta en graph_template.html para producir un unico HTML autocontenido:

    ashford_bom_graph.html

El grafo se guarda en formato CSR (offsets + indices) y solo con la direccion
padre -> hijo; los padres se reconstruyen en el navegador para no duplicar las
48.756 aristas en el fichero.

La clasificacion FG / BLK / WIP / CMP se deriva en el navegador a partir de las
maquinas de RATE; aqui solo se calcula para elegir el codigo de arranque y para
el resumen que se imprime.
"""

import json
from collections import Counter, defaultdict

import pandas as pd

XLSX = "Ashford split 2.xlsx"
TEMPLATE = "graph_template.html"
SALIDA = "ashford_bom_graph.html"


def main():
    bom = pd.read_excel(XLSX, sheet_name="BOM", dtype=str)
    rate = pd.read_excel(XLSX, sheet_name="RATE", dtype=str)

    codes = sorted(set(bom.ParentID) | set(bom.ComponentID))
    idx = {c: i for i, c in enumerate(codes)}

    hijos = defaultdict(set)
    for padre, comp in zip(bom.ParentID, bom.ComponentID):
        hijos[idx[padre]].add(idx[comp])
    ch_off, ch_idx = [0], []
    for i in range(len(codes)):
        ch_idx.extend(sorted(hijos.get(i, ())))
        ch_off.append(len(ch_idx))

    # RATE -> maquinas por codigo. Tener maquina es lo que hace "producible" a
    # un nodo, y por tanto lo que decide su color en el grafo.
    maquinas = sorted(rate.MachineId.unique())
    midx = {m: i for i, m in enumerate(maquinas)}
    ops = rate.drop_duplicates("MachineId").set_index("MachineId").OperationNo
    machine_ops = [ops[m] for m in maquinas]

    por_codigo = defaultdict(set)
    for maq, prod in zip(rate.MachineId, rate.ProductID):
        if prod in idx:
            por_codigo[idx[prod]].add(midx[maq])
    mach_off, mach_idx = [0], []
    for i in range(len(codes)):
        mach_idx.extend(sorted(por_codigo.get(i, ())))
        mach_off.append(len(mach_idx))

    # Codigo de arranque: el arbol mas representativo, para que la primera
    # pantalla muestre las cuatro clases y varios niveles. Se prefiere que
    # aparezcan todas las clases, luego profundidad, luego cantidad de bulks.
    consumidos = set(bom.ComponentID)
    raices = [idx[c] for c in sorted(set(bom.ParentID) - consumidos)]
    es_bulk = [m.startswith("P05M") for m in maquinas]

    def clase(i):
        """CMP sin maquina; BLK si sale en alguna P05M; si no, FG o WIP."""
        if mach_off[i + 1] == mach_off[i]:
            return "CMP"
        if any(es_bulk[m] for m in mach_idx[mach_off[i]:mach_off[i + 1]]):
            return "BLK"
        return "WIP" if codes[i] in consumidos else "FG"

    def explorar(raiz):
        prof = {raiz: 0}
        pila, maxp = [raiz], 0
        while pila:
            x = pila.pop()
            for m in hijos.get(x, ()):
                if prof.get(m, -1) < prof[x] + 1:
                    prof[m] = prof[x] + 1
                    maxp = max(maxp, prof[m])
                    pila.append(m)
        return maxp, prof.keys()

    def puntuar(i):
        maxp, alcance = explorar(i)
        clases = {clase(n) for n in alcance}
        bulks = sum(1 for n in alcance if clase(n) == "BLK")
        return (len(clases), maxp, bulks, -abs(len(alcance) - 34))

    inicio = max(raices, key=puntuar)

    datos = {
        "codes": codes,
        "ch_off": ch_off,
        "ch_idx": ch_idx,
        "machines": maquinas,
        "machine_ops": machine_ops,
        "mach_off": mach_off,
        "mach_idx": mach_idx,
        "start": inicio,
    }

    plantilla = open(TEMPLATE, encoding="utf-8").read()
    marcador = "/*__DATA__*/"
    assert marcador in plantilla, f"falta el marcador {marcador} en {TEMPLATE}"
    html = plantilla.replace(marcador, json.dumps(datos, separators=(",", ":")))
    open(SALIDA, "w", encoding="utf-8").write(html)

    reparto = Counter(clase(i) for i in range(len(codes)))

    print(f"{SALIDA} — {len(html) / 1024:.0f} KB")
    print(f"  {len(codes)} nodos | {len(ch_idx)} aristas | {len(maquinas)} maquinas")
    print("  " + " | ".join(f"{reparto[c]} {c}" for c in ("FG", "BLK", "WIP", "CMP")))
    print(f"  arranque: {codes[inicio]} ({len(hijos[inicio])} componentes directos)")


if __name__ == "__main__":
    main()

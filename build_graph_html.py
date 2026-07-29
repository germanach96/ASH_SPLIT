"""Genera el visor interactivo del arbol de producto de Ashford.

Uso:  python3 build_graph_html.py

Lee 'Ashford split 2.xlsx' (pestanas BOM y RATE ya limpias), calcula el grafo y
lo incrusta en graph_template.html para producir un unico HTML autocontenido:

    ashford_bom_graph.html

El grafo se guarda en formato CSR (offsets + indices) y solo con la direccion
padre -> hijo; los padres se reconstruyen en el navegador para no duplicar las
48.756 aristas en el fichero.
"""

import json
from collections import defaultdict

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

    # Producto final de arranque: el arbol mas representativo, para que la
    # primera pantalla muestre los tres tipos de nodo y varios niveles. Se
    # prefiere profundidad, luego cantidad de componentes fabricados.
    consumidos = set(bom.ComponentID)
    finales = [idx[c] for c in sorted(set(bom.ParentID) - consumidos)]

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
        tipos = {2 if mach_off[n + 1] == mach_off[n] else (1 if codes[n] in consumidos else 0)
                 for n in alcance}
        fabricados = sum(1 for n in alcance
                         if mach_off[n + 1] > mach_off[n] and codes[n] in consumidos)
        return (len(tipos), maxp, fabricados, -abs(len(alcance) - 34))

    inicio = max(finales, key=puntuar)

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

    tipos = [0, 0, 0]
    for i in range(len(codes)):
        producible = mach_off[i + 1] > mach_off[i]
        consumido = codes[i] in consumidos
        tipos[2 if not producible else (1 if consumido else 0)] += 1

    print(f"{SALIDA} — {len(html) / 1024:.0f} KB")
    print(f"  {len(codes)} nodos | {len(ch_idx)} aristas | {len(maquinas)} maquinas")
    print(f"  {tipos[0]} productos finales | {tipos[1]} fabricados | {tipos[2]} comprados")
    print(f"  arranque: {codes[inicio]} ({len(hijos[inicio])} componentes directos)")


if __name__ == "__main__":
    main()

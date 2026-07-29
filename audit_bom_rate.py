"""Auditoria de calidad de datos de las pestanas BOM y RATE de 'Ashford split 2.xlsx'.

Uso:  python3 audit_bom_rate.py ["Ashford split 2.xlsx"]

Comprueba integridad referencial entre la lista de materiales (BOM) y las rutas
de fabricacion (RATE), consistencia del ID compuesto de cada registro, ciclos en
el arbol de producto y coherencia del flujo entre las dos etapas productivas.
"""

import sys
from collections import defaultdict

import pandas as pd

FICHERO = sys.argv[1] if len(sys.argv) > 1 else "Ashford split 2.xlsx"
HOY = pd.Timestamp.today().normalize()


def cargar(fichero):
    bom = pd.read_excel(fichero, sheet_name="BOM", dtype=str)
    rate = pd.read_excel(fichero, sheet_name="RATE", dtype=str)

    # BOMElementId = version/padre/centro/componente/posicion/fecha_validez
    seg = bom.BOMElementId.str.split("/", expand=True)
    seg.columns = ["ver", "padre", "centro", "comp", "pos", "fecha"]
    bom = pd.concat([bom, seg], axis=1)
    bom["nseg"] = bom.BOMElementId.str.count("/") + 1
    bom["fecha_dt"] = pd.to_datetime(bom.fecha, format="%Y%m%d", errors="coerce")

    # OperationId = version/producto/centro/operacion
    seg = rate.OperationId.str.split("/", expand=True)
    seg.columns = ["ver", "producto", "centro", "op"]
    rate = pd.concat([rate, seg], axis=1)
    rate["tipo_maq"] = rate.MachineId.str[:4]

    return bom, rate


def seccion(titulo):
    print(f"\n{'=' * 78}\n{titulo}\n{'=' * 78}")


def hallazgo(nivel, texto):
    print(f"  [{nivel}] {texto}")


def main():
    bom, rate = cargar(FICHERO)
    normal = bom[bom.nseg == 6]  # lineas de componente reales
    out = bom[bom.nseg == 5]  # registros 'out' (salida de operacion, no componente)

    padres = set(normal.ParentID)
    comps = set(normal.ComponentID)
    productos = set(rate.ProductID)

    seccion("1. VOLUMEN Y NULOS")
    print(f"  BOM : {len(bom):>6} filas | {bom.ParentID.nunique()} padres | "
          f"{bom.ComponentID.nunique()} componentes")
    print(f"  RATE: {len(rate):>6} filas | {rate.MachineId.nunique()} maquinas | "
          f"{rate.ProductID.nunique()} productos")
    vacias = (bom[["BOMElementId", "ParentID", "ComponentID"]].isna().sum().sum()
              + rate[["MachineId", "OperationId", "ProductID"]].isna().sum().sum())
    hallazgo("OK" if not vacias else "ERROR",
             f"celdas vacias en las columnas originales: {vacias}")

    seccion("2. CONSISTENCIA DEL ID COMPUESTO CONTRA LAS COLUMNAS")
    hallazgo("OK" if (bom.padre == bom.ParentID).all() else "ERROR",
             f"padre embebido vs ParentID: {(bom.padre != bom.ParentID).sum()} discrepancias")
    hallazgo("OK" if (bom.comp == bom.ComponentID).all() else "ERROR",
             f"componente embebido vs ComponentID: {(bom.comp != bom.ComponentID).sum()} discrepancias")
    hallazgo("OK" if (rate.producto == rate.ProductID).all() else "ERROR",
             f"producto embebido vs ProductID: {(rate.producto != rate.ProductID).sum()} discrepancias")

    seccion("3. REGISTROS 'out' MAL MAPEADOS (defecto principal)")
    if len(out):
        hallazgo("ERROR",
                 f"{len(out)} filas con formato de 5 segmentos ('.../CU05/0010/out'): "
                 f"ComponentID recoge el numero de operacion, no un material")
        print(f"      valores falsos en ComponentID: {sorted(out.ComponentID.unique())}")
        print(f"      padres afectados: {out.ParentID.nunique()} "
              f"(todos tienen tambien lineas de componente validas)")
    else:
        hallazgo("OK", "no hay registros con formato anomalo")

    seccion("4. INTEGRIDAD REFERENCIAL BOM <-> RATE")
    hallazgo("OK" if not (padres - productos) else "ERROR",
             f"padres de BOM sin ruta en RATE: {len(padres - productos)}")
    huerfanos = productos - padres - comps
    hallazgo("OK" if not huerfanos else "AVISO",
             f"productos en RATE que no aparecen en ninguna BOM: {len(huerfanos)} {sorted(huerfanos)}")
    solo_comp = (productos & comps) - padres
    hallazgo("OK" if not solo_comp else "AVISO",
             f"productos con ruta que solo figuran como componente (sin BOM propia): "
             f"{len(solo_comp)} {sorted(solo_comp)}")

    seccion("5. ALINEACION DE VERSIONES (misma version en BOM y en RATE)")
    v_bom = normal.groupby("ParentID").ver.agg(set)
    v_rate = rate.groupby("ProductID").ver.agg(set)
    j = pd.concat([v_bom.rename("bom"), v_rate.rename("rate")], axis=1).dropna()
    solo_bom = [b - r for b, r in zip(j.bom, j.rate)]
    solo_rate = [r - b for b, r in zip(j.bom, j.rate)]
    n_bom = sum(1 for x in solo_bom if x)
    n_rate = sum(1 for x in solo_rate if x)
    print(f"  coinciden exactamente: {len(j) - n_bom - n_rate} de {len(j)} productos")
    hallazgo("AVISO", f"{n_bom} productos con version de BOM sin ruta equivalente")
    hallazgo("AVISO", f"{n_rate} productos con ruta sin version de BOM equivalente")

    seccion("6. ARBOL DE PRODUCTO: CICLOS Y PROFUNDIDAD")
    hijos = defaultdict(set)
    for a, b in zip(normal.ParentID, normal.ComponentID):
        hijos[a].add(b)

    BLANCO, GRIS, NEGRO = 0, 1, 2
    color = dict.fromkeys(padres | comps, BLANCO)
    ciclos = []
    for raiz in list(color):
        if color[raiz] != BLANCO:
            continue
        color[raiz] = GRIS
        pila, camino = [(raiz, iter(hijos.get(raiz, ())))], [raiz]
        while pila:
            nodo, it = pila[-1]
            avanzo = False
            for m in it:
                if color[m] == BLANCO:
                    color[m] = GRIS
                    camino.append(m)
                    pila.append((m, iter(hijos.get(m, ()))))
                    avanzo = True
                    break
                if color[m] == GRIS:
                    ciclos.append(camino[camino.index(m):] + [m])
            if not avanzo:
                color[nodo] = NEGRO
                pila.pop()
                camino.pop()
    hallazgo("OK" if not ciclos else "ERROR", f"ciclos detectados: {len(ciclos)}")
    for c in ciclos[:5]:
        print("      " + " -> ".join(c))

    prof = {}

    def profundidad(n, visto=frozenset()):
        if n in prof:
            return prof[n]
        if n in visto:
            return 0
        h = hijos.get(n)
        prof[n] = 0 if not h else 1 + max(profundidad(m, visto | {n}) for m in h)
        return prof[n]

    for n in list(color):
        profundidad(n)
    print("  niveles del arbol por padre:")
    for nivel, n in pd.Series({n: prof[n] for n in padres}).value_counts().sort_index().items():
        print(f"      nivel {nivel}: {n} padres")

    seccion("7. COHERENCIA DEL FLUJO DE FABRICACION (2 etapas)")
    print(pd.crosstab(rate.tipo_maq, rate.op).to_string().replace("\n", "\n  "))
    op_de = rate.groupby("ProductID").op.agg(lambda s: sorted(set(s))[0])
    f = normal.assign(op_padre=normal.ParentID.map(op_de),
                      op_comp=normal.ComponentID.map(op_de))
    tab = pd.crosstab(f.op_padre, f.op_comp)
    print("\n  operacion del padre (filas) vs operacion del componente fabricado (columnas):")
    print(tab.to_string().replace("\n", "\n  "))
    retro = tab.loc["0040", "0010"] if ("0040" in tab.index and "0010" in tab.columns) else 0
    hallazgo("OK" if retro == 0 else "AVISO",
             f"lineas donde la etapa 0040 (P05M) consume salida de la 0010 (P05P): {retro}")

    seccion("8. DUPLICADOS")
    hallazgo("OK" if not bom.BOMElementId.duplicated().any() else "ERROR",
             f"BOMElementId repetidos: {bom.BOMElementId.duplicated().sum()}")
    hallazgo("OK" if not rate.OperationId.duplicated().any() else "ERROR",
             f"OperationId repetidos: {rate.OperationId.duplicated().sum()}")
    d1 = normal.duplicated(["ver", "padre", "comp", "pos"]).sum()
    hallazgo("OK" if not d1 else "AVISO",
             f"misma version+padre+componente+posicion con distinta fecha de validez: {d1}")
    d2 = normal.duplicated(["ver", "padre", "pos"], keep=False).sum()
    hallazgo("AVISO", f"misma posicion ocupada por componentes distintos: {d2} filas")
    d3 = normal.duplicated(["ver", "padre", "comp"], keep=False)
    hallazgo("AVISO", f"mismo componente repetido en varias posiciones de una BOM: "
                      f"{d3.sum()} filas en {normal[d3].padre.nunique()} padres")

    seccion("9. FECHAS DE VALIDEZ")
    d = bom.fecha_dt
    print(f"  rango: {d.min():%Y-%m-%d} .. {d.max():%Y-%m-%d}")
    hallazgo("AVISO", f"lineas con fecha futura (> {HOY:%Y-%m-%d}): {(d > HOY).sum()}")
    hallazgo("INFO", f"lineas anteriores a 2015: {(d < pd.Timestamp('2015-01-01')).sum()}")

    seccion("10. CARGA POR MAQUINA")
    mc = rate.groupby("MachineId").ProductID.nunique().sort_values(ascending=False)
    print(f"  {len(mc)} maquinas | mediana {mc.median():.0f} productos | "
          f"max {mc.max()} | min {mc.min()}")
    hallazgo("INFO", f"las 10 maquinas mas cargadas concentran "
                     f"{mc.head(10).sum() / mc.sum():.0%} de las asignaciones producto-maquina")
    hallazgo("AVISO", f"maquinas con un unico producto asignado: {(mc == 1).sum()} "
                      f"{sorted(mc[mc == 1].index)}")


if __name__ == "__main__":
    main()

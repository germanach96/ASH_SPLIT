"""Propone un reparto del ownership de los codigos entre los cinco planners.

Uso:  python3 propose_split.py

Escribe ownership_proposal.json (codigo -> indice de owner) e imprime las
metricas del reparto.

El reparto no sale de optimizar un grafo: sale de como esta organizada la
planta. Cada planner es dueno de un grupo de lineas de packing, y todo lo demas
cuelga de ahi:

  1. Las lineas de packing se reparten por familia de producto.
  2. Cada codigo de packing va con el dueno de su linea. Si corre en lineas de
     dos duenos, va con el de la linea mas pequena, que asi queda entera.
  3. Cada bulk va con el planner que mas lo consume en sus lineas de packing.
  4. Un comprado va con su dueno solo si es uno solo; si lo consumen varios se
     queda sin asignar, porque en la practica no se gestiona por planner.

Los grupos de lineas salen de la fluidity real: mirando que codigos pueden
correr en dos lineas a la vez, las lineas se separan en cinco bloques sin un
solo codigo compartido entre ellos.
"""

import json
from collections import Counter, defaultdict

import pandas as pd

XLSX = "Ashford split 2.xlsx"
NOMBRES = "machine_names.tsv"
SALIDA = "ownership_proposal.json"

OWNERS = ["Sr planner 1", "Sr planner 2", "Jr planner 1", "Jr planner 2", "Intern"]

# Que lineas de packing lleva cada uno. Los bloques salen de la fluidity: no hay
# ni un codigo que corra en lineas de dos bloques distintos.
LINEAS = {
    # Liquidos, foundations al completo, mas la 516. La 516 es una Kugler y sus
    # bulks alimentan al bloque Kugler 100 veces y a foundations ninguna, asi
    # que llega aqui con un traspaso de bulk permanente; se pone donde se pidio.
    "Sr planner 1": ["P05P0521", "P05P0518", "P05P0513", "P05P0509", "P05P0519",
                     "P05P0516"],
    # Liquidos, el bloque Kugler. 501-510, 502-506 y 501-502 son los enlaces
    # fuertes, y la 507 cuelga de el con solo 4 codigos.
    #
    # La 520 Romaco entra aqui. No tiene fluidity con nadie, y de sus 79 codigos
    # 59 se alimentan de mouldings y de Kugler a la vez; con ella en Kugler el
    # traspaso pendiente es hacia mouldings, que es una linea sola (la 416).
    "Sr planner 2": ["P05P0501", "P05P0502", "P05P0506", "P05P0507", "P05P0510",
                     "P05P0520"],
    # Powders: las lineas 600 de envasado y las 300 de pressing, donde se hacen
    # los wips que ellas mismas consumen.
    "Jr planner 1": ["P05P0602", "P05P0603", "P05P0612",
                     "P05P0306", "P05P0321", "P05P0322", "P05P0324",
                     "P05P0325", "P05P0326", "P05P0327", "P05P0329"],
    # Mouldings, las lineas 400.
    "Jr planner 2": ["P05P0402", "P05P0410", "P05P0416", "P05P0417"],
    # Una sola linea, sin fluidity con ninguna otra: la carga mas contenida y la
    # que menos coordinacion exige, que es lo que toca para el intern.
    "Intern": ["P05P0701"],
}


def main():
    bom = pd.read_excel(XLSX, sheet_name="BOM", dtype=str)
    rate = pd.read_excel(XLSX, sheet_name="RATE", dtype=str)
    nombres = pd.read_csv(NOMBRES, sep="\t", dtype=str)
    nombre_maq = dict(zip(nombres.MachineId, nombres.Description))

    codigos = sorted(set(bom.ParentID) | set(bom.ComponentID))
    hijos, padres = defaultdict(set), defaultdict(set)
    for a, b in zip(bom.ParentID, bom.ComponentID):
        hijos[a].add(b)
        padres[b].add(a)
    maq = defaultdict(set)
    for m, p in zip(rate.MachineId, rate.ProductID):
        maq[p].add(m)
    # Ordenados a proposito: recorrer conjuntos de cadenas deja el resultado a
    # merced del hash del proceso, y el reparto tiene que salir igual siempre.
    hijos = {k: sorted(v) for k, v in hijos.items()}
    padres = {k: sorted(v) for k, v in padres.items()}
    maq = {k: sorted(v) for k, v in maq.items()}

    linea_de = {m: o for o, ms in LINEAS.items() for m in ms}
    packing = [m for m in rate.MachineId.unique() if m.startswith("P05P")]
    faltan = sorted(set(packing) - set(linea_de))
    assert not faltan, f"lineas de packing sin grupo: {faltan}"

    owner = {}

    # ---- 1. cada codigo de packing, con el dueno de su linea ----
    # Un codigo que corre en lineas de dos duenos hay que romperlo por algun
    # lado: va con el dueno de la linea mas pequena, que asi queda entera y la
    # que se parte es la grande, que lo nota menos.
    tam_linea = Counter(m for c in codigos for m in maq.get(c, ()) if m in linea_de)
    conflicto = 0
    for c in codigos:
        lineas = [m for m in maq.get(c, ()) if m in linea_de]
        if not lineas:
            continue
        if len({linea_de[m] for m in lineas}) > 1:
            conflicto += 1
        elegida = min(lineas, key=lambda m: (tam_linea[m], m))
        owner[c] = OWNERS.index(linea_de[elegida])
    print(f"1. packing: {len(owner)} codigos"
          + (f" ({conflicto} en lineas de dos duenos)" if conflicto else " (ninguno en dos bloques)"))

    # ---- 2. cada bulk, con quien mas lo consume en sus lineas de packing ----
    # Se sube por toda la cadena, no solo al padre directo: un bulk puede
    # alimentar a otro bulk y solo aparecer en packing dos niveles mas arriba.
    por_maquina = defaultdict(list)
    for c in codigos:
        for m in maq.get(c, ()):
            por_maquina[m].append(c)
    def mas_lo_usa(c, cuenta):
        """El que mas lo consume. Si empatan, el que ya lleve mas de su vaso."""
        top = max(cuenta.values())
        empatados = sorted(o for o in cuenta if cuenta[o] == top)
        if len(empatados) == 1:
            return empatados[0]
        vaso = Counter(owner[o] for m in maq[c] for o in por_maquina[m] if o in owner)
        return max(empatados, key=lambda o: (vaso.get(o, 0), -o))

    bulks = [c for c in codigos if c not in owner and maq.get(c)]
    sin_rastro = []
    for c in bulks:
        pila, visto, cuenta = [c], {c}, Counter()
        while pila:
            x = pila.pop()
            for p in padres.get(x, ()):
                if p in visto:
                    continue
                visto.add(p)
                if p in owner:
                    cuenta[owner[p]] += 1
                else:
                    pila.append(p)
        if cuenta:
            owner[c] = mas_lo_usa(c, cuenta)
        else:
            sin_rastro.append(c)
    print(f"2. making : {len(bulks) - len(sin_rastro)} bulks por consumo en packing")

    # Los que no llegan a packing son los que se venden a granel: no hay linea
    # aguas arriba de la que colgarlos, asi que van con quien lleve el resto de
    # su propia maquina de making.
    huerfanos = 0
    for _ in range(3):                     # unas pocas pasadas: se apoyan entre si
        for c in list(sin_rastro):
            cuenta = Counter(owner[o] for m in maq[c]
                             for o in por_maquina[m] if o in owner)
            if cuenta:
                owner[c] = mas_lo_usa(c, cuenta)
    huerfanos = sum(1 for c in sin_rastro if c not in owner)
    print(f"          {len(sin_rastro) - huerfanos} a granel por mayoria de su maquina"
          + (f", {huerfanos} sin resolver" if huerfanos else ""))

    # ---- 3. comprados: solo si tienen un unico dueno ----
    comprados = [c for c in codigos if not maq.get(c)]
    unico = compartido = 0
    for c in comprados:
        duenos = {owner[p] for p in padres.get(c, ()) if p in owner}
        if len(duenos) == 1:
            owner[c] = duenos.pop()
            unico += 1
        else:
            compartido += 1
    print(f"3. compos : {unico} con un solo dueno, {compartido} compartidos que se dejan vacios")

    # ---- metricas ----
    consumidos = {b for a in hijos for b in hijos[a]}

    def clase(c):
        ms = maq.get(c)
        if not ms:
            return "CMP"
        if any(m.startswith("P05M") for m in ms):
            return "BLK"
        return "WIP" if c in consumidos else "FG"

    print(f"\n{'':16} {'total':>6} {'FG':>5} {'BLK':>5} {'WIP':>5} {'CMP':>6}  lineas")
    for o, nom in enumerate(OWNERS):
        suyos = [c for c in codigos if owner.get(c) == o]
        k = Counter(clase(c) for c in suyos)
        ls = ", ".join(nombre_maq.get(m, m) for m in LINEAS[nom])
        print(f"{nom:16} {len(suyos):>6} {k['FG']:>5} {k['BLK']:>5} {k['WIP']:>5} {k['CMP']:>6}  {ls}")
    print(f"{'sin asignar':16} {sum(1 for c in codigos if c not in owner):>6}"
          f" {'':>5} {'':>5} {'':>5} {compartido:>6}  compos que consumen varios planners")

    # maquinas de un solo dueno
    por_maq = defaultdict(set)
    for c, o in owner.items():
        for m in maq.get(c, ()):
            por_maq[m].add(o)
    partidas = sorted(m for m, os in por_maq.items() if len(os) > 1)
    print(f"\nmaquinas de un solo planner: {len(por_maq) - len(partidas)} de {len(por_maq)}")
    if partidas:
        print("  compartidas: " + ", ".join(f"{nombre_maq.get(m, m)}({len(por_maq[m])})" for m in partidas))
    p05p = [m for m in partidas if m.startswith("P05P")]
    print(f"  de ellas lineas de packing: {len(p05p)}" + (f" -> {p05p}" if p05p else " (ninguna)"))

    # bulks: cada uno tiene que ser del planner que lo usa
    # Se recalcula sobre el reparto final, sin reutilizar nada del paso 2, para
    # que sea una comprobacion de verdad y no un eco de la regla.
    es_packing = {c for c in codigos if any(m.startswith("P05P") for m in maq.get(c, ()))}
    solo_making = [c for c in codigos if maq.get(c) and c not in es_packing]
    usan = {}
    for c in solo_making:
        pila, visto, cuenta = [c], {c}, Counter()
        while pila:
            x = pila.pop()
            for p in padres.get(x, ()):
                if p in visto:
                    continue
                visto.add(p)
                if p in es_packing:
                    cuenta[owner[p]] += 1
                else:
                    pila.append(p)
        usan[c] = cuenta
    reparto_bulk = Counter(len(usan[c]) for c in solo_making)
    ajeno = [c for c in solo_making if usan[c] and owner.get(c) not in usan[c]]
    compartidos = [c for c in solo_making if len(usan[c]) > 1]
    print(f"\nbulks: {len(solo_making)} en total")
    print(f"  {reparto_bulk[1]} los usa un solo planner y son suyos")
    print(f"  {reparto_bulk[0]} se venden a granel, no los consume ninguna linea")
    print(f"  {len(compartidos)} los usan dos o tres planners a la vez")
    print(f"  {len(ajeno)} en manos de quien no los usa"
          + ("  <- deberia ser 0" if ajeno else ""))
    # Un bulk que usan k planners deja k-1 sin el, se ponga donde se ponga: ese
    # es el suelo con el que hay que comparar lo que sale.
    suelo = sum(len(usan[c]) - 1 for c in compartidos)
    fuera = sum(1 for c in solo_making for o in usan[c] if owner.get(c) != o)
    print(f"  traspasos pendientes: {fuera} (minimo posible con estas lineas: {suelo})")
    for o, nom in enumerate(OWNERS):
        usa = [c for c in solo_making if o in usan[c]]
        print(f"    {nom:16} usa {len(usa):>4}, son suyos {sum(1 for c in usa if owner.get(c) == o):>4}")

    # cadenas completas entre producibles
    finales = [c for c in codigos if maq.get(c) and c not in consumidos]
    enteras = 0
    for f in finales:
        pila, visto, duenos = [f], {f}, {owner.get(f)}
        while pila:
            x = pila.pop()
            for h in hijos.get(x, ()):
                if maq.get(h) and h not in visto:
                    visto.add(h)
                    duenos.add(owner.get(h))
                    pila.append(h)
        if len(duenos) == 1:
            enteras += 1
    print(f"\ncadenas de producto final con un solo dueno: {enteras} de {len(finales)} "
          f"({enteras / len(finales):.0%})")

    json.dump(owner, open(SALIDA, "w"), separators=(",", ":"))
    print(f"{SALIDA}: {len(owner)} codigos asignados de {len(codigos)}")


if __name__ == "__main__":
    main()

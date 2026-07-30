"""Propone un reparto del ownership de los codigos entre los cinco planners.

Uso:  python3 propose_split.py

Escribe ownership_proposal.json (codigo -> indice de owner) e imprime las
metricas del reparto.

El reparto no sale de optimizar un grafo: sale de como esta organizada la
planta. Cada planner es dueno de un grupo de lineas de packing, y todo lo demas
cuelga de ahi:

  1. Las lineas de packing se reparten por familia de producto.
  2. Cada codigo de packing va con el dueno de su linea.
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
    # Liquidos, foundations. Dentro de foundations hay dos nucleos de fluidity
    # que no comparten ni un codigo: 521-518-513 por un lado y 509-519 por otro.
    # Se separan por ahi, que no cuesta nada en fluidity, y las 509-519 pasan al
    # intern: dejar foundations entera cargaba a este planner con 698 codigos de
    # packing frente a los 171 del intern.
    "Sr planner 1": ["P05P0521", "P05P0518", "P05P0513"],
    # Liquidos, el bloque Kugler. 501-510, 502-506 y 501-502 son los enlaces
    # fuertes; 507 y 516 cuelgan de el con poca fluidity pero son de la familia.
    "Sr planner 2": ["P05P0501", "P05P0502", "P05P0506", "P05P0507", "P05P0510", "P05P0516"],
    # Powders: las lineas 600 de envasado y las 300 de pressing, donde se hacen
    # los wips que ellas mismas consumen.
    "Jr planner 1": ["P05P0602", "P05P0603", "P05P0612",
                     "P05P0306", "P05P0321", "P05P0322", "P05P0324",
                     "P05P0325", "P05P0326", "P05P0327", "P05P0329"],
    # Mouldings, las lineas 400. Se le suma la 520 Romaco: de sus 79 codigos, 59
    # se alimentan de mouldings y de Kugler a la vez, asi que romper por un lado
    # o por otro cuesta casi lo mismo (70 cadenas frente a 68). Se decide por
    # carga, que en mouldings es la mitad que en Kugler, y por dejar la cadena
    # 416 -> 520 en una sola mano.
    "Jr planner 2": ["P05P0402", "P05P0410", "P05P0416", "P05P0417", "P05P0520"],
    # Tres lineas de liquidos sin fluidity entre ellas ni con nadie mas, que es
    # la carga mas llevadera del reparto.
    "Intern": ["P05P0509", "P05P0519", "P05P0701"],
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

    linea_de = {m: o for o, ms in LINEAS.items() for m in ms}
    packing = [m for m in rate.MachineId.unique() if m.startswith("P05P")]
    faltan = sorted(set(packing) - set(linea_de))
    assert not faltan, f"lineas de packing sin grupo: {faltan}"

    owner = {}

    # ---- 1. cada codigo de packing, con el dueno de su linea ----
    conflicto = 0
    for c in codigos:
        duenos = {linea_de[m] for m in maq.get(c, ()) if m in linea_de}
        if not duenos:
            continue
        if len(duenos) > 1:
            conflicto += 1
        owner[c] = OWNERS.index(sorted(duenos)[0])
    print(f"1. packing: {len(owner)} codigos"
          + (f" ({conflicto} en lineas de dos duenos)" if conflicto else " (ninguno en dos bloques)"))

    # ---- 2. cada bulk, con quien mas lo consume en sus lineas de packing ----
    # Se sube por toda la cadena, no solo al padre directo: un bulk puede
    # alimentar a otro bulk y solo aparecer en packing dos niveles mas arriba.
    por_maquina = defaultdict(list)
    for c in codigos:
        for m in maq.get(c, ()):
            por_maquina[m].append(c)
    bulks = [c for c in codigos if c not in owner and maq.get(c)]
    sin_rastro = []
    for c in bulks:
        pila, visto, cuenta = [c], {c}, Counter()
        while pila:
            x = pila.pop()
            for p in padres[x]:
                if p in visto:
                    continue
                visto.add(p)
                if p in owner:
                    cuenta[owner[p]] += 1
                else:
                    pila.append(p)
        if cuenta:
            owner[c] = cuenta.most_common(1)[0][0]
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
                owner[c] = cuenta.most_common(1)[0][0]
    huerfanos = sum(1 for c in sin_rastro if c not in owner)
    print(f"          {len(sin_rastro) - huerfanos} a granel por mayoria de su maquina"
          + (f", {huerfanos} sin resolver" if huerfanos else ""))

    # ---- 3. comprados: solo si tienen un unico dueno ----
    comprados = [c for c in codigos if not maq.get(c)]
    unico = compartido = 0
    for c in comprados:
        duenos = {owner[p] for p in padres[c] if p in owner}
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

    # cadenas completas entre producibles
    finales = [c for c in codigos if maq.get(c) and c not in consumidos]
    enteras = 0
    for f in finales:
        pila, visto, duenos = [f], {f}, {owner.get(f)}
        while pila:
            x = pila.pop()
            for h in hijos[x]:
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

"""Propone un reparto del ownership de los codigos entre los cinco planners.

Uso:  python3 propose_split.py

Escribe ownership_proposal.json (codigo -> indice de owner) e imprime las
metricas del reparto.

Dos objetivos tiran en direcciones opuestas y no se pueden satisfacer los dos:

  * Que cada planner tenga sus cadenas de principio a fin, sin depender de
    bulks de otro.
  * Que no compartan maquina, para no pisarse en la programacion.

Son incompatibles porque un producto final se envasa en una P05P y su bulk se
fabrica en una P05M, asi que toda cadena cruza de maquina por construccion.
Unir por maquina compartida da 21 grupos, pero unir por maquina Y cadena da un
unico grupo con los 3.925 producibles: no hay corte limpio.

De modo que esto es una particion equilibrada de grafo con dos costes a la vez.
Se optimiza por busqueda local sobre los codigos producibles y despues se
reparten los comprados, que por naturaleza se comparten.
"""

import json
import sys
from collections import Counter, defaultdict

import pandas as pd

XLSX = "Ashford split 2.xlsx"
SALIDA = "ownership_proposal.json"

OWNERS = ["Sr planner 1", "Sr planner 2", "Jr planner 1", "Jr planner 2", "Intern"]
# Cuanta carga se lleva cada uno. El intern la mitad que un planner.
CARGA = [1.0, 1.0, 1.0, 1.0, 0.5]

# Cuanto pesa cada tipo de roce. Compartir una maquina obliga a coordinarse
# todos los dias; un eslabon de cadena roto es un traspaso por articulo. De ahi
# que una maquina partida pese mas que un enlace, pero no infinitamente: si
# pesara demasiado, las cadenas se romperian todas.
PESO_MAQUINA = int(sys.argv[1]) if len(sys.argv) > 1 else 25
PESO_ENLACE = 1

VUELTAS = 40          # pasadas de busqueda local
HOLGURA = 1.06        # cuanto puede pasarse un owner de su cuota


def cargar():
    bom = pd.read_excel(XLSX, sheet_name="BOM", dtype=str)
    rate = pd.read_excel(XLSX, sheet_name="RATE", dtype=str)

    codigos = sorted(set(bom.ParentID) | set(bom.ComponentID))
    idx = {c: i for i, c in enumerate(codigos)}

    hijos = defaultdict(set)
    padres = defaultdict(set)
    for a, b in zip(bom.ParentID, bom.ComponentID):
        hijos[idx[a]].add(idx[b])
        padres[idx[b]].add(idx[a])

    maquinas = sorted(rate.MachineId.unique())
    midx = {m: i for i, m in enumerate(maquinas)}
    maq_de = defaultdict(set)
    for m, p in zip(rate.MachineId, rate.ProductID):
        if p in idx:
            maq_de[idx[p]].add(midx[m])

    return codigos, idx, hijos, padres, maquinas, maq_de


def main():
    codigos, idx, hijos, padres, maquinas, maq_de = cargar()
    n = len(codigos)
    producibles = [i for i in range(n) if maq_de[i]]
    comprados = [i for i in range(n) if not maq_de[i]]
    codigos_de_maq = defaultdict(list)
    for i in producibles:
        for m in maq_de[i]:
            codigos_de_maq[m].append(i)

    # Enlaces entre producibles: son las cadenas que interesa no partir.
    enlaces = defaultdict(set)
    for i in producibles:
        for j in hijos[i] | padres[i]:
            if maq_de[j]:
                enlaces[i].add(j)

    cuota = [len(producibles) * c / sum(CARGA) for c in CARGA]
    tope = [c * HOLGURA for c in cuota]

    # ---- arranque: hacer crecer cinco regiones por la cadena ----
    # Sembrar por grupos de maquina condena el reparto: las P05M y las P05P son
    # disjuntas, asi que un owner se queda con los bulks y otro con los productos
    # finales, que es lo contrario de tener la cadena entera. Se siembra por la
    # cadena y las maquinas se arreglan despues en la busqueda local.
    orden = sorted(producibles, key=lambda i: -len(enlaces[i]))
    semillas, vistos = [], set()
    for i in orden:                       # semillas lejanas entre si
        if len(semillas) == len(OWNERS):
            break
        if i in vistos:
            continue
        semillas.append(i)
        cerca, frente = {i}, [i]
        for _ in range(3):                # reservar su vecindario
            nuevo = []
            for x in frente:
                for j in enlaces[x]:
                    if j not in cerca:
                        cerca.add(j)
                        nuevo.append(j)
            frente = nuevo
        vistos |= cerca

    owner = {}
    carga = [0.0] * len(OWNERS)
    frentes = []
    for o, s in enumerate(semillas):
        owner[s] = o
        carga[o] += 1
        frentes.append([s])
    # crecer en rondas, cada owner tira de sus vecinos hasta llenar su cuota
    sueltos = True
    while sueltos:
        sueltos = False
        for o in sorted(range(len(OWNERS)), key=lambda o: carga[o] / cuota[o]):
            if carga[o] >= cuota[o]:
                continue
            nuevo = []
            for x in frentes[o]:
                for j in enlaces[x]:
                    if j not in owner and carga[o] < cuota[o]:
                        owner[j] = o
                        carga[o] += 1
                        nuevo.append(j)
            if nuevo:
                frentes[o] = nuevo
                sueltos = True
            elif carga[o] < cuota[o]:     # region agotada: saltar a otro sitio
                libre = next((i for i in orden if i not in owner), None)
                if libre is not None:
                    owner[libre] = o
                    carga[o] += 1
                    frentes[o] = [libre]
                    sueltos = True
    for i in producibles:                 # lo que quede, al que tenga hueco
        if i not in owner:
            o = max(range(len(OWNERS)), key=lambda o: cuota[o] - carga[o])
            owner[i] = o
            carga[o] += 1

    # ---- coste ----
    def maquinas_partidas():
        return sum(len({owner[i] for i in cs}) - 1 for cs in codigos_de_maq.values())

    def enlaces_rotos():
        return sum(1 for i in producibles for j in enlaces[i] if owner[i] != owner[j]) // 2

    def coste():
        return PESO_MAQUINA * maquinas_partidas() + PESO_ENLACE * enlaces_rotos()

    print(f"arranque: {maquinas_partidas()} maquinas partidas, {enlaces_rotos()} enlaces rotos")

    # ---- busqueda local ----
    # Dos escalas de movimiento. Mover un codigo suelto arregla las cadenas pero
    # nunca consolida una maquina, porque hace falta que se muevan todos sus
    # codigos a la vez; el movimiento de maquina entera es el que recorre el
    # compromiso entre no partir maquinas y no partir cadenas.
    def mover_maquina(m):
        cs = codigos_de_maq[m]
        duenos = {owner[i] for i in cs}
        if len(duenos) < 2:
            return False
        mejor, mejor_d = None, 0
        for o in duenos:
            fuera = [i for i in cs if owner[i] != o]
            if carga[o] + len(fuera) > tope[o]:
                continue
            d = 0
            for i in fuera:                       # cadenas que gana y pierde
                d += PESO_ENLACE * (sum(1 for j in enlaces[i] if owner[j] == owner[i])
                                    - sum(1 for j in enlaces[i] if owner[j] == o))
            antes = {i: owner[i] for i in fuera}  # maquinas antes y despues
            tocadas = {mm for i in fuera for mm in maq_de[i]}
            prev = sum(len({owner[x] for x in codigos_de_maq[mm]}) - 1 for mm in tocadas)
            for i in fuera:
                owner[i] = o
            post = sum(len({owner[x] for x in codigos_de_maq[mm]}) - 1 for mm in tocadas)
            for i, o0 in antes.items():
                owner[i] = o0
            d += PESO_MAQUINA * (post - prev)
            if d < mejor_d:
                mejor, mejor_d = o, d
        if mejor is None:
            return False
        for i in cs:
            if owner[i] != mejor:
                carga[owner[i]] -= 1
                carga[mejor] += 1
                owner[i] = mejor
        return True

    for vuelta in range(VUELTAS):
        movidos = 0
        for m in sorted(codigos_de_maq, key=lambda m: -len(codigos_de_maq[m])):
            if mover_maquina(m):
                movidos += 1
        for i in producibles:
            actual = owner[i]
            mejor, mejor_delta = actual, 0
            for o in range(len(OWNERS)):
                if o == actual or carga[o] + 1 > tope[o]:
                    continue
                # enlaces: cuantos vecinos gana o pierde
                gana = sum(1 for j in enlaces[i] if owner[j] == o)
                pierde = sum(1 for j in enlaces[i] if owner[j] == actual)
                d = PESO_ENLACE * (pierde - gana)
                # maquinas: cuantos owners distintos tocan sus maquinas antes y despues
                for m in maq_de[i]:
                    otros = Counter(owner[x] for x in codigos_de_maq[m] if x != i)
                    antes = len(set(otros) | {actual}) - 1
                    despues = len(set(otros) | {o}) - 1
                    d += PESO_MAQUINA * (despues - antes)
                if d < mejor_delta:
                    mejor, mejor_delta = o, d
            if mejor != actual:
                carga[actual] -= 1
                carga[mejor] += 1
                owner[i] = mejor
                movidos += 1
        if not movidos:
            print(f"estable en la vuelta {vuelta}")
            break
    print(f"tras optimizar: {maquinas_partidas()} maquinas partidas, {enlaces_rotos()} enlaces rotos")

    # ---- comprados: al que mas los consume ----
    # Se comparten por naturaleza, asi que se asignan por mayoria y se cuenta
    # cuantos quedan repartidos entre varios.
    compartidos = 0
    for i in comprados:
        duenos = Counter(owner[p] for p in padres[i] if p in owner)
        if not duenos:
            continue
        if len(duenos) > 1:
            compartidos += 1
        owner[i] = duenos.most_common(1)[0][0]

    # ---- metricas ----
    consumidos = {j for i in range(n) for j in hijos[i]}

    def clase(i):
        if not maq_de[i]:
            return "CMP"
        if any(maquinas[m].startswith("P05M") for m in maq_de[i]):
            return "BLK"
        return "WIP" if i in consumidos else "FG"

    print(f"\n{'':16} {'total':>6} {'FG':>6} {'BLK':>5} {'WIP':>5} {'CMP':>6} {'maquinas':>9}")
    for o, nombre in enumerate(OWNERS):
        suyos = [i for i in range(n) if owner.get(i) == o]
        c = Counter(clase(i) for i in suyos)
        maqs = {m for i in suyos for m in maq_de[i]}
        print(f"{nombre:16} {len(suyos):>6} {c['FG']:>6} {c['BLK']:>5} {c['WIP']:>5} {c['CMP']:>6} {len(maqs):>9}")

    partidas = [maquinas[m] for m, cs in codigos_de_maq.items() if len({owner[i] for i in cs}) > 1]
    print(f"\nmaquinas compartidas entre planners: {len(partidas)} de {len(maquinas)}"
          + (f" -> {', '.join(partidas[:8])}{'...' if len(partidas) > 8 else ''}" if partidas else ""))

    # cadenas completas: un producto final y todos sus producibles aguas abajo
    finales = [i for i in producibles if i not in consumidos]
    enteras = 0
    for f in finales:
        pila, visto, duenos = [f], {f}, {owner[f]}
        while pila:
            x = pila.pop()
            for j in hijos[x]:
                if maq_de[j] and j not in visto:
                    visto.add(j)
                    duenos.add(owner[j])
                    pila.append(j)
        if len(duenos) == 1:
            enteras += 1
    print(f"cadenas de producto final con un solo dueno: {enteras} de {len(finales)} ({enteras/len(finales):.0%})")
    dentro = sum(1 for i in producibles for j in enlaces[i] if owner[i] == owner[j]) // 2
    total_en = sum(len(enlaces[i]) for i in producibles) // 2
    print(f"enlaces de cadena dentro del mismo planner: {dentro} de {total_en} ({dentro/total_en:.0%})")
    print(f"comprados que consumen varios planners: {compartidos} de {len(comprados)} "
          f"({compartidos/len(comprados):.0%}) — inevitable, el grafo es una sola pieza")

    fuera = {codigos[i]: o for i, o in owner.items()}
    json.dump(fuera, open(SALIDA, "w"), separators=(",", ":"))
    print(f"\n{SALIDA}: {len(fuera)} codigos asignados de {n}")


if __name__ == "__main__":
    main()

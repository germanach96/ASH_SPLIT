# Propuesta de reparto del ownership

Generada por `propose_split.py`, incrustada en `ashford_bom_graph_proposal.html`.

```
python3 propose_split.py 25
python3 build_graph_html.py --owners ownership_proposal.json \
        --out ashford_bom_graph_proposal.html --key ashford-ownership-proposal-v1
```

El `25` es el peso que se le da a no partir una máquina frente a no partir una
cadena. Cambiarlo mueve el reparto por la frontera de abajo.

## Lo primero: los dos objetivos son incompatibles

No es una limitación del algoritmo, es la forma de los datos.

Un producto final se envasa en una **P05P** y su bulk se fabrica en una **P05M**.
Los dos conjuntos de máquinas son disjuntos, así que **toda cadena cruza de
máquina por construcción**. En números:

- Agrupando solo por máquina compartida salen **21 grupos**, el mayor con 941
  códigos. Cero fluidity compartida es alcanzable.
- Agrupando por máquina **y** cadena sale **un único grupo con los 3.925
  producibles**. No hay ningún corte limpio.

De modo que cero máquinas compartidas y cadenas enteras no pueden darse a la
vez. Hay que elegir un punto intermedio.

## La frontera

| Peso máquina | Máquinas compartidas | Cadenas con un solo dueño | Enlaces de cadena internos |
|---:|---:|---:|---:|
| 0 | 52 / 63 | 98 % | 99 % |
| 5 | 40 / 63 | 96 % | 98 % |
| **25** | **19 / 63** | **82 %** | **90 %** |
| 60 | 15 / 63 | 71 % | 86 % |
| 150 | 12 / 63 | 58 % | 77 % |

Elegido **25**, que es el codo: bajar de 52 a 19 máquinas compartidas cuesta 16
puntos de integridad de cadena, y a partir de ahí cada máquina que se recupera
cuesta mucho más. De 25 a 150 se ganan 7 máquinas y se pierden 24 puntos.

## El reparto

| | Total | FG | BLK | WIP | CMP | Máquinas |
|---|---:|---:|---:|---:|---:|---:|
| Sr planner 1 | 1.495 | 487 | 354 | 30 | 624 | 28 |
| Sr planner 2 | 1.799 | 546 | 323 | 55 | 875 | 23 |
| Jr planner 1 | 1.385 | 498 | 268 | 81 | 538 | 24 |
| Jr planner 2 | 1.548 | 496 | 255 | 70 | 727 | 34 |
| Intern | 949 | 352 | 110 | 0 | 487 | 23 |

El intern lleva media carga de códigos producibles respecto a un planner, y
ningún WIP: se queda con cadenas más cortas y autocontenidas. La cuota se aplica
sobre los producibles; los comprados caen después con quien más los consume, y
son el trabajo más ligero.

Resultados:

- **82 %** de los productos finales tienen toda su cadena de producibles en un
  solo planner: 2.079 de 2.532.
- **90 %** de los enlaces de cadena quedan dentro del mismo planner.
- **44 de 63 máquinas** son de un solo planner.
- **18 %** de los comprados los consumen varios planners. Es inevitable: el
  grafo no dirigido es una sola pieza, precisamente por las materias primas
  compartidas.

## Las 19 máquinas que quedan compartidas

No son un residuo del algoritmo, son los caballos de batalla de la planta:

| Máquina | Nombre | Planners | Códigos |
|---|---|---:|---:|
| P05P0521 | 521 Kalix | 5 | 477 |
| P05P0501 | 501 Kugler | 5 | 356 |
| P05P0502 | 502 Kugler | 5 | 333 |
| P05M0565 | EKATO200ATEX | 5 | 307 |
| P05M0573 | EKATO500ATEX | 5 | 291 |
| P05M0568 | BECOMIX 2000L | 5 | 280 |
| P05P0510 | 510 High Speed Kugler | 5 | 262 |
| P05M0566 | EKATO320ATEX | 5 | 242 |
| P05P0509 | 509 Bottle Foundation Line | 5 | 215 |
| P05P0506 | 506 Kugler | 5 | 196 |
| P05M0562 | EKATO200 | 5 | 187 |
| P05M0575 | BECOMIX 25L | 5 | 121 |
| P05M0557 | BECO1200 | 5 | 80 |
| P05P0416 | 416 MM360 | 4 | 259 |
| P05P0701 | 701 Liquids Prestige | 4 | 171 |
| P05M0567 | BECO5 | 4 | 92 |
| P05M0463 | BUHLER4 | 4 | 45 |
| P05M0462 | BUHLER3 | 4 | 45 |
| P05M0466 | K60 BEAD MILL | 3 | 33 |

Dárselas a un solo planner significaría darle un cuarto de la fábrica. La
lectura práctica es que **el ownership exclusivo funciona para el equipo
especializado, y estas diecinueve son infraestructura compartida**: tienen que
programarse en común, con independencia de quién sea dueño de cada código.

## Cómo está montado el algoritmo

1. **Siembra por cadena.** Cinco semillas alejadas entre sí en el grafo de
   producibles, y cada una crece por sus vecinos hasta llenar su cuota.
   Sembrar por grupos de máquina no funciona: las P05M y las P05P son disjuntas,
   así que un owner se queda con todos los bulks y otro con todos los productos
   finales — lo contrario de tener la cadena entera. Ese fue el primer intento y
   daba 15 % de cadenas completas.
2. **Búsqueda local a dos escalas.** Mover un código suelto arregla cadenas pero
   nunca consolida una máquina, porque para eso tienen que moverse todos sus
   códigos a la vez. El movimiento de máquina entera es el que recorre el
   compromiso; sin él la búsqueda se quedaba clavada en 52 máquinas compartidas.
3. **Comprados al final**, con quien más los consume.

## Qué hacer con esto

Es un punto de partida, no un veredicto. Ábrelo, mira las zonas que no te
convenzan y muévelas con el propio visor: `Select related` para coger una cadena
entera, o el rectángulo para una zona, y `Assign to` para reasignarla. Los
cambios se guardan solos.

La copia usa su **propia clave de almacenamiento**, así que trabajar sobre ella
no toca lo que hagas en `ashford_bom_graph.html`, que sigue en blanco.

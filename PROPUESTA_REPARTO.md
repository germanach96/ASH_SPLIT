# Propuesta de reparto del ownership

Generada por `propose_split.py`, incrustada en `ashford_bom_graph_proposal.html`.

```
python3 propose_split.py
python3 build_graph_html.py --owners ownership_proposal.json \
        --out ashford_bom_graph_proposal.html --key ashford-ownership-proposal-v1
```

El reparto no sale de optimizar un grafo, sale de cómo está organizada la
planta. Cada planner es dueño de un grupo de líneas de packing y todo lo demás
cuelga de ahí.

## Las reglas

1. Las líneas de packing se reparten por familia de producto.
2. Cada código de packing va con el dueño de su línea. Si corre en líneas de dos
   dueños, va con el de la **línea más pequeña**, que así queda entera.
3. Cada bulk va con el planner que más lo consume en sus líneas de packing,
   subiendo por toda la cadena y no solo al padre directo. Si dos empatan, se
   queda con quien ya lleve más códigos de su mismo vaso. Los que se venden a
   granel y no llegan a ninguna línea van con quien lleve el resto de su máquina
   de making.
4. Un comprado va con su dueño solo si es uno solo. Si lo consumen varios se
   queda **sin asignar**, porque en la práctica no se gestiona por planner.

## El reparto

| | Líneas | Producibles | FG | BLK | WIP | CMP |
|---|---|---:|---:|---:|---:|---:|
| **Sr planner 1** | 521 Kalix, 518 IWK, 513 Kalix Tube Filler, 509 Bottle Foundation, 519 PKB, **516 Kugler** | 1.104 | 745 | 359 | 0 | 777 |
| **Sr planner 2** | 501, 502, 506, 507, 510 Kugler, 520 Romaco | 1.522 | 879 | 549 | 94 | 1.097 |
| **Jr planner 1** | 602, 603, 612 · 306, 321, 322, 324, 325, 326, 327, 329 | 382 | 159 | 83 | 140 | 170 |
| **Jr planner 2** | 402, 410, 416, 417 | 662 | 425 | 235 | 2 | 646 |
| **Intern** | 701 Liquids Prestige | 255 | 171 | 84 | 0 | 257 |
| Sin asignar | | | | | | 304 |

De las 63 máquinas, **48 son de un solo planner**. El **86 %** de los productos
finales tienen toda su cadena de producibles en un solo planner: 2.172 de 2.532.

## Los bulks: cada uno con quien lo usa

De los 1.310 bulks:

| | |
|---:|---|
| **1.098** | los usa un solo planner, y son suyos |
| **161** | se venden a granel, no los consume ninguna línea de packing |
| **51** | los usan **dos o tres planners a la vez** |

**Ningún bulk está en manos de quien no lo usa.** Los 51 compartidos son los
únicos que dejan a alguien programando con bulk ajeno, y ahí no hay reparto que
valga: un bulk que usan dos planners deja fuera a uno se ponga donde se ponga.
Los traspasos pendientes son **52, que es exactamente el mínimo posible** con
estas líneas.

| | Bulks que usa | Suyos |
|---|---:|---:|
| Sr planner 1 | 358 | 344 |
| Sr planner 2 | 456 | 426 |
| Jr planner 1 | 69 | 69 |
| Jr planner 2 | 233 | 226 |
| Intern | 85 | 84 |

Reducir esos 52 no se hace tocando bulks, se hace moviendo líneas: son bulks que
alimentan a dos líneas de dueños distintos.

## Los bloques de fluidity

Qué líneas se pueden separar no es una opinión, es un dato. Agrupando por
códigos que pueden correr en dos líneas a la vez, las 28 líneas de packing se
parten en bloques que **no comparten ni un solo código**:

| Códigos | Familia | Líneas |
|---:|---|---|
| 941 | liquids | 501, 502, 506, 507, 510, 516 Kugler |
| 477 | liquids | 513 Kalix Tube Filler, 518 IWK, 521 Kalix |
| 312 | mouldings | 402 Weckerle, 416 MM360 |
| 221 | liquids | 509 Bottle Foundation, 519 PKB |
| 171 | liquids | 701 Liquids Prestige |
| 79 | liquids | 520 Romaco |
| 70 | powders | 321, 322 Book Press |
| 69 | powders | 612 Manual Line |
| 58 | mouldings | 417 MM360 |
| 57 | mouldings | 410 Weckerle Tester |
| 49 | powders | 324 Book Press |
| 44 | powders | 325, 326 Vetraco, 329 Camwell |
| 40 | powders | 602, 603 Robot Line |
| 27 | powders | 306 Kemwall, 327 Robot Vetraco |

El único bloque partido a mano es el de Kugler: la 516 sale de él y se va con
foundations, con el coste que se detalla abajo. Los otros trece van enteros.

## La 516, con el Sr planner 1

Va donde se pidió. El precio, medido:

- **La 510 deja de ser de un solo dueño.** Hay 6 códigos que corren en la 516 y
  en la 510 a la vez (`33330025002`, `99350239342`, `99350239344`, `99350240225`,
  `99350240443`, `99350240444`). Se quedan con la 516 para que la línea pequeña
  esté entera, así que la 510 queda 256 / 6 entre Sr planner 2 y Sr planner 1.
  Es la **única línea de packing partida** de las 28.
- **Los bulks compartidos suben de 41 a 51.** Sus bulks (EKATO1000, BECOMIX 2000L,
  BECO5, EKATO500ATEX, EKATO200) alimentan al bloque Kugler 100 veces y a
  foundations ninguna, así que el 516 arrastra un traspaso permanente: de los 27
  bulks que alimentan la 516, 18 son del Sr planner 1 y 9 de otros.

A cambio, iguala mucho la carga: el Sr planner 1 pasa de 1.020 a 1.104
producibles y el Sr planner 2 baja de 1.605 a 1.522.

## La 520 Romaco, con Kugler

No tiene fluidity con nadie. De sus 79 códigos, **59 se alimentan de mouldings y
de Kugler a la vez**, así que el traspaso existe se ponga donde se ponga. Con
ella en Kugler, lo que queda pendiente es hacia mouldings, que por ese lado es
una sola línea, la 416.

## El desequilibrio

| | Producibles |
|---|---:|
| Sr planner 2 (Kugler + 520) | 1.522 |
| Sr planner 1 (foundations + 516) | 1.104 |
| Jr planner 2 (mouldings) | 662 |
| Jr planner 1 (powders) | 382 |
| Intern (701) | 255 |

Con la 516 en foundations los dos Sr quedan mucho más parejos que antes. Los dos
llevan el 63 % de los producibles, que tiene sentido, y el intern la carga más
contenida y la que menos coordinación exige: una línea sola sin fluidity con
ninguna otra.

Lo que sigue sin tener arreglo limpio es Kugler: es el bloque más grande del
packing de la planta y no se parte sin romper fluidity. Su costura más débil está
entre **501+510+507** y **502+506**, y cortarla rompería la fluidity de decenas
de códigos. Es la única palanca real que queda.

## El reparto sale siempre igual

`propose_split.py` recorre la BOM ordenando cada lista de padres e hijos y
rompe los empates con una regla explícita, no con el orden en que caen los
conjuntos. Dos ejecuciones dan el mismo `ownership_proposal.json`.

## Cómo ajustarlo

En el visor, **la forma dice qué es un código y el color de quién es**: círculo
para un FG, rombo para un bulk, triángulo para un WIP y cuadrado para un
comprado. Un código hueco es uno que no tiene dueño.

Picando un planner en el panel de **Ownership** el mapa se queda solo con sus
códigos y con los comprados que no son de nadie porque los comparte con el
resto; picando otra vez vuelve la fábrica entera. El **+** de cada fila lo añade
a la selección sin cambiar la vista.

Para mover cosas: `Select related` coge una cadena entera, el rectángulo coge una
zona y `Assign to` la reasigna. Los cambios se guardan solos.

La copia usa su propia clave de almacenamiento, así que trabajar sobre ella no
toca `ashford_bom_graph.html`, que sigue en blanco.

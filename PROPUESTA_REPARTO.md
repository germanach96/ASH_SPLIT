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
2. Cada código de packing va con el dueño de su línea.
3. Cada bulk va con el planner que más lo consume en sus líneas de packing,
   subiendo por toda la cadena y no solo al padre directo. Los que se venden a
   granel y no llegan a ninguna línea van con quien lleve el resto de su máquina
   de making.
4. Un comprado va con su dueño solo si es uno solo. Si lo consumen varios se
   queda **sin asignar**, porque en la práctica no se gestiona por planner.

## El reparto

| | Líneas | Producibles | FG | BLK | WIP | CMP |
|---|---|---:|---:|---:|---:|---:|
| **Sr planner 1** | 521 Kalix, 518 IWK, 513 Kalix Tube Filler, 509 Bottle Foundation, 519 PKB | 1.020 | 698 | 322 | 0 | 639 |
| **Sr planner 2** | 501, 502, 506, 507, 510, 516 Kugler, 520 Romaco | 1.605 | 926 | 585 | 94 | 1.260 |
| **Jr planner 1** | 602, 603, 612 · 306, 321, 322, 324, 325, 326, 327, 329 | 382 | 159 | 83 | 140 | 170 |
| **Jr planner 2** | 402, 410, 416, 417 | 663 | 425 | 236 | 2 | 647 |
| **Intern** | 701 Liquids Prestige | 255 | 171 | 84 | 0 | 257 |
| Sin asignar | | | | | | 278 |

**Las 28 líneas de packing tienen un solo dueño.** De las 63 máquinas, 49 son de
un solo planner; las 14 compartidas son todas de making, ninguna de packing.

El **86 %** de los productos finales tienen toda su cadena de producibles en un
solo planner: 2.173 de 2.532.

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

Ningún bloque queda partido entre dos planners.

## La 516: por qué se queda en Kugler

Moverla a foundations cuesta muy poco en fluidity, **6 códigos** con la 510. Pero
la fluidity no es lo único que la ata:

- Sus bulks (EKATO1000, BECOMIX 2000L, BECO5, EKATO500ATEX, EKATO200) alimentan
  a las líneas del bloque Kugler **100 veces**.
- A las líneas de foundations (521, 518, 513, 509, 519), **ninguna**.

En foundations quedaría descolgada: una línea suelta cuyo bulk lo programa otro
planner todos los días. Se queda con Kugler.

Si aun así la quieres en foundations, es mover `"P05P0516"` de una lista a otra
en `LINEAS` dentro de `propose_split.py`. Mueve 47 códigos de packing, así que
tampoco arregla el desequilibrio.

## La 520 Romaco, con Kugler

No tiene fluidity con nadie. De sus 79 códigos, **59 se alimentan de mouldings y
de Kugler a la vez**, así que el traspaso existe se ponga donde se ponga. Con
ella en Kugler, lo que queda pendiente es hacia mouldings, que por ese lado es
una sola línea, la 416.

## El desequilibrio

| | Producibles |
|---|---:|
| Sr planner 2 (Kugler + 520) | 1.605 |
| Sr planner 1 (foundations) | 1.020 |
| Jr planner 2 (mouldings) | 663 |
| Jr planner 1 (powders) | 382 |
| Intern (701) | 255 |

**Seis a uno entre el mayor y el menor.** Los dos Sr llevan el 62 % de los
producibles, que tiene sentido, y el intern la carga más contenida y la que menos
coordinación exige, que es una línea sola sin fluidity con nadie.

Lo que sigue sin tener arreglo limpio es Kugler: es el 36 % de todo el packing de
la planta en un bloque que no se parte sin romper fluidity. Su costura más débil
está entre **501+510+516+507** (597 códigos) y **502+506** (428), y cortarla
rompería la fluidity de **84 códigos**. Es la única palanca real que queda.

## Cómo ajustarlo

Ábrelo y muévelo con el propio visor: `Select related` para coger una cadena
entera, el rectángulo para una zona, y `Assign to` para reasignarla. Los cambios
se guardan solos.

La copia usa su propia clave de almacenamiento, así que trabajar sobre ella no
toca `ashford_bom_graph.html`, que sigue en blanco.

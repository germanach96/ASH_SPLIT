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
   subiendo por toda la cadena y no solo al padre directo.
4. Un comprado va con su dueño solo si es uno solo. Si lo consumen varios se
   queda **sin asignar**, porque en la práctica no se gestiona por planner.

## Los bloques de fluidity

Antes de repartir hay que saber qué no se puede partir. Mirando qué códigos
pueden correr en dos líneas a la vez, las 28 líneas de packing se separan en
bloques que **no comparten ni un solo código** entre sí:

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

Los enlaces fuertes dentro del bloque Kugler son 501–510 (124 códigos),
502–506 (101) y 501–502 (63). La 507 y la 516 cuelgan de él con muy poca
fluidity, 2 y 6 códigos, pero son de la misma familia y se dejan dentro.

## El reparto

| | Líneas | Producibles | FG | BLK | WIP | CMP |
|---|---|---:|---:|---:|---:|---:|
| **Sr planner 1** | 521 Kalix, 518 IWK, 513 Kalix Tube Filler | 690 | 477 | 213 | 0 | 249 |
| **Sr planner 2** | 501, 502, 506, 507, 510, 516 Kugler | 1.530 | 847 | 589 | 94 | 1.168 |
| **Jr planner 1** | 602, 603, 612 · 306, 321, 322, 324, 325, 326, 327, 329 | 382 | 159 | 83 | 140 | 170 |
| **Jr planner 2** | 402, 410, 416, 417 · 520 Romaco | 742 | 504 | 236 | 2 | 739 |
| **Intern** | 509 Bottle Foundation, 519 PKB, 701 Prestige | 581 | 392 | 189 | 0 | 631 |
| Sin asignar | | | | | | 294 |

**Las 28 líneas de packing tienen un solo dueño.** De las 63 máquinas, 49 son de
un solo planner; las 14 compartidas son todas de making, ninguna de packing.

El 77 % de los productos finales tienen toda su cadena de producibles en un solo
planner.

## Las tres decisiones que dejaste abiertas

**La 520 Romaco va con mouldings.** Es una línea de kits: de sus 79 códigos, 59
se alimentan de mouldings **y** de Kugler a la vez. Romperla por un lado cuesta
70 cadenas y por el otro 68, así que en cadenas da igual. Se decide por carga
—mouldings es la mitad que Kugler— y por dejar la cadena 416 → 520 en una sola
mano, que es como la planteaste.

**La 507 se queda en Kugler.** Solo comparte 4 códigos con el bloque (2 con la
501 y 2 con la 510), pero es de la familia y no hay ningún sitio mejor.

**Powders y mouldings van a Jr planners distintos.** Juntarlos en uno liberaba un
planner para líquidos, pero líquidos no se puede partir en cuatro sin romper el
bloque Kugler, así que no compensaba.

## Un cambio sobre tu esquema, y por qué

Describiste foundations como un grupo: 521, 509, 519, 518 y 513. Dentro tiene
**dos núcleos que no comparten ni un código**: 521–518–513 por un lado y
509–519 por otro. Se separan por ahí, que no cuesta nada en fluidity, y las
509–519 pasan al intern.

Dejando foundations entera, ese planner se llevaba 698 códigos de packing y el
intern se quedaba con 171. Si prefieres el grupo completo, es mover dos líneas
en `LINEAS` dentro de `propose_split.py`, o dos selecciones en el propio visor.

## Lo que no cuadra: el desequilibrio

| | Producibles |
|---|---:|
| Sr planner 2 (Kugler) | 1.530 |
| Jr planner 2 (mouldings) | 742 |
| Sr planner 1 (foundations) | 690 |
| Intern | 581 |
| Jr planner 1 (powders) | 382 |

**Cuatro a uno entre el mayor y el menor.** No es un fallo del reparto, es que el
bloque Kugler es el 36 % de todo el packing de la planta y no se puede partir sin
romper fluidity.

Si quieres equilibrarlo, la costura más débil de Kugler está entre
**501+510+516+507** (597 códigos) y **502+506** (428). Partir por ahí rompe la
fluidity de **84 códigos** que pueden correr a los dos lados. Es la única palanca
real que hay, y es tu decisión si esos 84 valen el equilibrio.

## Cómo ajustarlo

Ábrelo y muévelo con el propio visor: `Select related` para coger una cadena
entera, el rectángulo para una zona, y `Assign to` para reasignarla. Los cambios
se guardan solos.

La copia usa su propia clave de almacenamiento, así que trabajar sobre ella no
toca `ashford_bom_graph.html`, que sigue en blanco.

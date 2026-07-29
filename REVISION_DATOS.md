# Revisión de datos — `Ashford split 2.xlsx` (BOM + RATE)

Auditoría reproducible: `python3 audit_bom_rate.py`

## Veredicto

**Sí, los datos tienen sentido.** Son un extracto limpio de maestro de datos (con
toda la pinta de venir de SAP: centro `CU05`, versiones de lista `V0xx`/`Z0xx`,
posiciones en múltiplos de 5, operaciones `0010`/`0040`). La integridad
referencial entre las dos pestañas es prácticamente perfecta y la estructura de
producto es consistente.

Hay **un defecto real de extracción** (109 filas) y una lista de detalles menores
que conviene decidir antes de usar el fichero para calcular capacidad o costes.

## Qué es cada cosa

`BOMElementId` es una clave compuesta que se descompone limpiamente en 6 partes,
y sus segmentos **coinciden al 100 %** con las columnas `ParentID` / `ComponentID`
(0 discrepancias en 90.621 filas):

```
V060 / 99200005407 / CU05 / TRM020642 / 175 / 20240126
 ^          ^          ^        ^         ^       ^
versión   padre     centro  componente posición fecha validez
```

`OperationId` se descompone igual en 4 partes, también con 0 discrepancias:

```
V004 / 1ZH084A / CU05 / 0040
 ^        ^        ^      ^
versión producto centro operación
```

| | BOM | RATE |
|---|---|---|
| Filas | 90.621 | 6.390 |
| Padres / productos | 3.925 | 3.927 |
| Componentes | 4.646 | — |
| Máquinas | — | 63 |
| Celdas vacías | 0 | 0 |
| Claves duplicadas | 0 | 0 |

## Lo que cuadra bien

**Integridad referencial BOM ↔ RATE — cobertura del 100 %.**
Los **3.925** padres de la BOM tienen ruta en RATE. Cero excepciones. Es el
indicador más fuerte de que ambos extractos salieron del mismo sistema y del
mismo corte.

**El árbol de producto es acíclico.** Cero ciclos en 90.621 aristas — ningún
producto se consume a sí mismo, ni directa ni indirectamente. En una BOM real de
este tamaño esto no se da por hecho.

**Profundidad razonable:** 1–5 niveles (763 / 1.754 / 1.152 / 173 / 83 padres),
1.393 semielaborados (son padre e hijo a la vez), 3.253 materias primas compradas
(nunca son padre), 2.532 productos de cabecera (nunca se consumen).

**Tamaños de lista plausibles:** mediana de 10 componentes distintos por padre
(rango 1–34), mediana de 12 líneas (máx. 140 contando todas las versiones).

**La fábrica se organiza en dos etapas y el dato lo refleja sin excepciones:**

| Prefijo máquina | Nº máquinas | Operación | Filas |
|---|---|---|---|
| `P05M` | 35 | `0040` | 2.979 |
| `P05P` | 28 | `0010` | 3.411 |

La correspondencia es perfecta: ninguna máquina hace las dos operaciones, y
ningún producto pasa por las dos. **Y el flujo va en un solo sentido**: los
padres de la etapa `0040` (P05M) nunca consumen salida de la etapa `0010`
(P05P) — 0 líneas de 10.681. `0040` alimenta a `0010`, nunca al revés.

```
op del padre \ op del componente     0010     0040
0010  (P05P)                          461    2.978
0040  (P05M)                            0    7.242   <- 0 = sin retroceso
```

**Versiones alineadas:** 3.918 de 3.925 productos tienen exactamente el mismo
juego de versiones en BOM y en RATE.

## Problemas encontrados

### 1. ERROR — 109 filas donde `ComponentID` no es un material

Son las únicas filas con 5 segmentos en lugar de 6, y acaban en `/out`:

```
V005/99350284792/CU05/0010/out   ->  ComponentID = "0010"   (mal)
V009/99350275442/CU05/0010/out   ->  ComponentID = "0010"   (mal)
V/99350194385/CU05/0010/out      ->  ComponentID = "0010"   (mal)
```

Al partir por `/` sin comprobar el número de segmentos, el **número de
operación** ha caído en la columna del componente. `"0010"` y `"0040"` aparecen
así como si fueran materiales, cuando no lo son (`0010` no es padre de nada, y
no aparece como componente en ninguna fila bien formada).

Son registros de **salida** de operación (co-producto / rendimiento), no líneas
de consumo. Lo confirma que los 109 padres afectados **ya tienen sus líneas de
componente normales aparte**, están los 109 en RATE, y sus 109 pares
(producto, versión) no tienen ruta asociada — precisamente el desajuste del
punto 4 de abajo.

**Acción:** eliminarlas de la BOM, o separarlas a su propia tabla de salidas. Si
se dejan, aparecerán dos materiales fantasma en cualquier explosión de BOM.

### 2. AVISO — 2 productos en RATE sin BOM propia

| Producto | Máquina | Situación |
|---|---|---|
| `99040009087` | P05M0465 | No aparece en ninguna BOM, ni como padre ni como componente |
| `99200033777` | P05M0565 | Se fabrica y lo consumen 2 padres, pero no tiene lista de materiales |

El segundo es el más raro: se produce y se consume, pero no declara de qué está
hecho. Vale la pena preguntar si es una BOM que falta o un artículo tipo servicio.

### 3. AVISO — 8 líneas duplicadas que solo se diferencian por la fecha de validez

Misma versión, mismo padre, mismo componente, misma posición, dos fechas:

```
V010/99350235815/CU05/99200024075/10/20261001
V010/99350235815/CU05/99200024075/10/20260901   <- misma posicion 10
```

Afecta a 4 padres (`993502358 15/16/18/19`) × 2 versiones. Si el extracto
pretendía ser una foto a una fecha concreta, sobra una de las dos; si es
histórico, falta una columna de fecha-hasta para poder filtrar.

### 4. AVISO — 7 productos con ruta sin versión de BOM equivalente

`99240355442/43/44/45/46/48/51`: tienen ruta `V010` y `V020`, pero solo BOM
`V010`. O falta la BOM de la V020, o la ruta V020 está obsoleta.

### 5. AVISO — 316 filas con la misma posición ocupada por componentes distintos

Dentro de una misma versión, una posición debería identificar una línea:

```
V010/99200005400/CU05/TRM020632/105/20211213
V010/99200005400/CU05/TRM020630/105/20211213   <- ambas en la posicion 105
```

Es legal en SAP, pero suele indicar líneas alternativas o una migración a medias.
Importa porque la posición deja de servir como clave de línea.

### 6. INFO — Repetición del mismo componente en varias posiciones (8.412 filas, 888 padres)

```
V020/1JE001A/CU05/R0029/200/20110701
V020/1JE001A/CU05/R0029/320/20210519   <- mismo material, otra posicion
```

Normal en fabricación (el mismo material se consume en dos puntos del proceso),
pero **hay que sumar cantidades al explotar la BOM, no quedarse con la primera
coincidencia**. Es la causa de que haya 41.756 pares (padre, componente)
repetidos en el fichero.

### 7. INFO — Fechas de validez

Rango 2011-07-01 a 2027-06-01. Hay **120 líneas con fecha futura** (posteriores a
hoy) y **1.224 anteriores a 2015**. Las futuras son cambios de ingeniería ya
planificados: si se explota la BOM sin filtrar por fecha, se mezclan estructuras
que aún no están vigentes con otras que ya no lo están.

### 8. INFO — Códigos de versión atípicos

`V0V0` (11 filas, todas del padre `99300013912`) y `V` (1 fila, la del `/out`).
`V0V0` es **consistente entre BOM y RATE** para ese producto, así que parece un
código real del sistema por raro que suene, no un error de tecleo.

### 9. INFO — Concentración de carga

Las 10 máquinas más cargadas concentran el **49 %** de las asignaciones
producto-máquina (`P05P0521` sola tiene 477 productos). En el otro extremo,
3 máquinas tienen un único producto: `P05M0460`, `P05M0555`, `P05P0322`.
No es un error de datos, pero si el objetivo del "split" es repartir carga, ahí
está el desequilibrio.

### 10. INFO — Codificación de materiales

Conviven cuatro esquemas: numérico de 11 dígitos (6.745 códigos, el grueso),
`TRM######` (134), tipo `1ZH084A` (27) y `R####` / `SHWR0200A`. Coherente con
materias primas y utillaje que vienen de otro sistema. Los componentes más
reutilizados (`99260051959` en 2.484 padres, `99400004141` en 2.473) son
claramente consumibles genéricos — embalaje o similar.

## Resumen de acciones sugeridas

| Prioridad | Acción |
|---|---|
| Alta | Quitar o reclasificar las 109 filas `/out`; `ComponentID` `0010`/`0040` no son materiales |
| Alta | Al explotar la BOM, agrupar por (padre, componente) **sumando**, no deduplicando |
| Alta | Decidir la fecha de corte y filtrar por fecha de validez antes de calcular |
| Media | Aclarar `99040009087` y `99200033777` (ruta sin BOM) |
| Media | Resolver los 7 productos con ruta V020 sin BOM V020 |
| Media | Elegir versión por producto — el 42 % de los padres tiene más de una |
| Baja | Revisar las 8 duplicadas por fecha y las 316 colisiones de posición |

## Nota sobre las versiones

1.669 padres tienen más de una versión de lista. En **1.549** de ellos todas las
versiones llevan exactamente los mismos componentes (cambia la posición o la
fecha), y en **120** los componentes difieren de verdad. Para cualquier cálculo
hay que fijar una regla de selección de versión; si no, se cuentan los mismos
materiales varias veces.

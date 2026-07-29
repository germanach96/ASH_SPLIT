# Revisión y limpieza de datos — `Ashford split 2.xlsx` (BOM + RATE)

| Script | Qué hace |
|---|---|
| `audit_bom_rate.py` | Audita el **extracto original** (ver cabecera del fichero para recuperarlo) |
| `clean_bom_rate.py` | Aplica la limpieza descrita abajo y reescribe el xlsx |

## Estado actual del fichero

El fichero es una **foto de master data**, no un histórico. Se ha colapsado a
relaciones puras entre códigos: **la BOM ya no distingue versión, posición ni
fecha de validez**; RATE sí conserva la distinción de máquina.

### Pestaña `BOM` — 48.756 filas

| Columna | Contenido |
|---|---|
| `ParentID` | Código del producto que consume |
| `ComponentID` | Código del componente consumido |

Una fila = una relación padre-hijo única. 3.925 padres, 4.644 componentes.

### Pestaña `RATE` — 6.122 filas

| Columna | Contenido |
|---|---|
| `MachineId` | Máquina |
| `ProductID` | Producto fabricado |
| `OperationNo` | Etapa: `0040` (máquinas `P05M`) o `0010` (máquinas `P05P`) |

Una fila = una combinación producto-máquina única. 3.925 productos, 63 máquinas.

`OperationNo` es nueva: la operación venía embebida en el `OperationId` compuesto
y está determinada al 100 % por la máquina, así que se ha extraído a su propia
columna y se ha descartado la versión de ruta.

**Los 3.925 padres de la BOM son exactamente los 3.925 productos de RATE.**
El script lo verifica con un `assert` antes de escribir.

## Cambios aplicados, problema a problema

### 1. Registros `/out` mal mapeados — **109 filas eliminadas**

Eran las únicas con 5 segmentos en el id (`V005/99350284792/CU05/0010/out`).
Al partir por `/` el número de operación cayó en `ComponentID`, metiendo `0010`
y `0040` como materiales fantasma. Eran registros de salida de operación, no
líneas de consumo. Eliminadas; los 109 padres conservan sus líneas normales.

### 2. Productos en RATE sin BOM propia — **2 filas eliminadas**

`99040009087` (no aparecía en ninguna BOM) y `99200033777` (se fabricaba y lo
consumían 2 padres, pero sin lista propia).

> **Consecuencia a tener en cuenta:** `99200033777` sigue siendo componente de
> 2 padres en la BOM, pero ya no tiene ruta. A efectos de cálculo pasa a
> comportarse como material comprado en lugar de fabricado.

### 3. Duplicados por fecha de validez — **resueltos**

Las 8 líneas que solo se diferenciaban por la fecha (4 padres `993502358xx`)
desaparecen al colapsar: la fecha ya no forma parte de la clave.

### 4. Rutas V020 sin BOM V020 — **sin cambios**

Los 7 productos `99240355442…` ya no plantean problema: al desaparecer la
versión de la BOM, la relación de códigos es única y las rutas V010/V020 se
conservan en RATE porque apuntan a máquinas distintas.

### 5. Colisiones de posición — **resueltas**

Las 316 filas con la misma posición ocupada por componentes distintos dejan de
importar: la posición ya no está en el fichero.

### 6. Componentes repetidos y multiversión — **colapsados**

Las 8.412 repeticiones del mismo componente en varias posiciones y los 41.756
pares (padre, componente) duplicados por versión se reducen a una arista única.
De 90.621 filas a **48.756**. Ya no hace falta ninguna regla de selección de
versión ni riesgo de contar el mismo material varias veces.

### 7. Fechas de validez — **eliminadas**

Las 120 líneas de vigencia futura y las 1.224 anteriores a 2015 dejan de ser
relevantes. No hay fecha de corte que decidir.

## Verificación posterior a la limpieza

| Comprobación | Resultado |
|---|---|
| Celdas vacías | 0 |
| Aristas padre-hijo duplicadas | 0 |
| Pares producto-máquina duplicados | 0 |
| Autorreferencias (padre = componente) | 0 |
| Ciclos en el árbol de producto | 0 |
| Materiales fantasma `0010` / `0040` | 0 |
| Padres de BOM = productos de RATE | sí (3.925) |

**La estructura de dos etapas sobrevive intacta.** Las 35 máquinas `P05M` siguen
haciendo solo la operación `0040` y las 28 `P05P` solo la `0010`, y el flujo
sigue yendo en un único sentido — **0 líneas** donde la etapa `0040` consuma
salida de la `0010`:

```
op del padre \ op del componente     0010     0040
0010  (P05P)                          319    2.278
0040  (P05M)                            0    3.041   <- 0 = sin retroceso
```

Reparto de máquinas por producto: 2.400 productos en 1 máquina, 1.149 en 2,
250 en 3, 52 en 4, 26 en 5 y 48 en 7. Mediana de 10 componentes por padre
(rango 1–34).

## Lo que no se ha tocado

La concentración de carga sigue igual: las 10 máquinas más cargadas acumulan
cerca de la mitad de las asignaciones producto-máquina (`P05P0521` es la más
cargada), mientras `P05M0460`, `P05M0555` y `P05P0322` tienen un solo producto.
No es un problema de datos, pero es el desequilibrio de partida si el objetivo
del *split* es repartir carga.

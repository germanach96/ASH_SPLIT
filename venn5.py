"""Venn de cinco conjuntos, en SVG y con los numeros dentro de cada region.

Con cinco conjuntos hacen falta elipses: con circulos no existe un Venn de 5 que
tenga las 31 regiones. Se usa la construccion clasica de cinco elipses iguales
giradas 72 grados entre si, comprobada aqui mismo: RASTER cuenta las 31.

La gracia esta en colocar las etiquetas. En vez de estimarlo a ojo se rasteriza
el dibujo, se saca cada region y se pone el numero en su punto mas interior, el
que queda mas lejos del borde. Asi ninguna etiqueta se sale de su region ni pisa
una linea, por pequena que sea la region.
"""

import numpy as np
from scipy import ndimage

# (centro x, centro y, ancho, alto, giro en grados) en un lienzo de 0..1
ELIPSES = [
    (0.428, 0.449, 0.87, 0.50, 155.0),
    (0.469, 0.543, 0.87, 0.50, 82.0),
    (0.558, 0.523, 0.87, 0.50, 10.0),
    (0.578, 0.432, 0.87, 0.50, 118.0),
    (0.489, 0.383, 0.87, 0.50, 46.0),
]
RASTER = 900


def _codigo_de_region(g=RASTER):
    """Para cada pixel, la mascara de bits de las elipses que lo contienen."""
    ys, xs = np.mgrid[0:g, 0:g]
    X, Y = (xs + .5) / g, 1 - (ys + .5) / g
    code = np.zeros((g, g), np.int32)
    for k, (cx, cy, w, h, ang) in enumerate(ELIPSES):
        r = np.deg2rad(ang)
        u = (X - cx) * np.cos(r) + (Y - cy) * np.sin(r)
        v = -(X - cx) * np.sin(r) + (Y - cy) * np.cos(r)
        code |= (((u / (w / 2)) ** 2 + (v / (h / 2)) ** 2 <= 1)).astype(np.int32) << k
    return code


def anclas():
    """{mascara: (x, y, holgura)} con el punto mas interior de cada region.

    La holgura es la distancia al borde en unidades del lienzo, que sirve para
    no escribir un numero mas grande de lo que cabe.
    """
    code = _codigo_de_region()
    g = code.shape[0]
    out = {}
    for m in range(1, 32):
        region = code == m
        if not region.any():
            continue
        # Si la region viene partida en trozos, el numero va en el mayor.
        etiquetas, n = ndimage.label(region)
        if n > 1:
            mayor = 1 + np.argmax(ndimage.sum(region, etiquetas, range(1, n + 1)))
            region = etiquetas == mayor
        dist = ndimage.distance_transform_edt(np.pad(region, 1))[1:-1, 1:-1]
        iy, ix = np.unravel_index(np.argmax(dist), dist.shape)
        out[m] = ((ix + .5) / g, 1 - (iy + .5) / g, dist[iy, ix] / g)
    return out


def svg(cuentas, nombres, colores, totales=None, ancho=760):
    """El diagrama entero.

    cuentas -- {mascara de bits: numero de codigos en esa region exacta}
    nombres -- los cinco nombres, en el orden de los bits
    colores -- los cinco colores
    totales -- opcional, {indice: total del conjunto} para la etiqueta
    """
    A = anclas()
    faltan = [m for m in cuentas if m not in A]
    assert not faltan, f"regiones sin sitio en el dibujo: {faltan}"

    # Los nombres van fuera de las elipses, asi que el lienzo lleva un margen.
    # Ojo: px y py mueven un punto y por tanto llevan el margen dentro; una
    # longitud (un radio) solo se escala. Mezclarlos dibujaba las elipses un 46 %
    # mas grandes que las regiones sobre las que se colocan los numeros.
    MARGEN = 0.17
    P = ancho / (1 + 2 * MARGEN)
    def esc(v): return round(v * P, 1)
    def px(x): return round((x + MARGEN) * P, 1)
    def py(y): return round((1 - y + MARGEN) * P, 1)

    partes = [f'<svg viewBox="0 0 {ancho} {ancho}" width="{ancho}" height="{ancho}" '
              f'font-family="Helvetica, Arial, sans-serif">']

    for k, (cx, cy, w, h, ang) in enumerate(ELIPSES):
        partes.append(
            f'<ellipse cx="{px(cx)}" cy="{py(cy)}" rx="{esc(w / 2)}" ry="{esc(h / 2)}" '
            f'transform="rotate({-ang} {px(cx)} {py(cy)})" '
            f'fill="{colores[k]}" fill-opacity="0.10" stroke="{colores[k]}" '
            f'stroke-width="1.6" stroke-opacity="0.85"/>')

    for m in range(1, 32):
        n = cuentas.get(m, 0)
        x, y, holgura = A[m]
        # El numero no puede ser mas ancho que el hueco: el radio libre da el
        # tope, y los de cuatro cifras necesitan mas sitio que los de una.
        cifras = max(1, len(str(n)))
        tope = holgura * P * 2 / (cifras * 0.62)
        fs = max(7.5, min(20 if bin(m).count("1") == 1 else 15, tope))
        peso = "600" if bin(m).count("1") == 1 else "400"
        color = "#9aa2aa" if n == 0 else "#1a1d21"
        # Un borde blanco por debajo: hay numeros que caen encima de una linea.
        partes.append(
            f'<text x="{px(x)}" y="{py(y)}" font-size="{fs:.1f}" font-weight="{peso}" '
            f'fill="{color}" stroke="#fff" stroke-width="3" paint-order="stroke" '
            f'text-anchor="middle" dominant-baseline="central">{n}</text>')

    # Cada nombre justo por fuera de su propio petalo. El petalo es la region
    # que solo toca a esa elipse, asi que se sale desde su numero hacia fuera y
    # el nombre no puede quedar junto al petalo de otro.
    for k in range(5):
        ax, ay, _ = A[1 << k]
        dx, dy = ax - 0.5, ay - 0.5
        n = np.hypot(dx, dy) or 1
        ex, ey = ax + dx / n * 0.24, ay + dy / n * 0.24
        anchor = "middle" if abs(dx / n) < 0.35 else ("start" if dx > 0 else "end")
        etiqueta = nombres[k] if totales is None else f"{nombres[k]} · {totales[k]}"
        # Los dos nombres de los lados se salian del lienzo. Se mide el ancho a
        # ojo de buen cubero (0,55 em por letra en Helvetica) y se mete dentro.
        fs, X = 13.5, px(ex)
        ancho_txt = len(etiqueta) * fs * 0.55
        izq = X - (0 if anchor == "start" else ancho_txt if anchor == "end" else ancho_txt / 2)
        X += max(0, 3 - izq) - max(0, izq + ancho_txt - (ancho - 3))
        partes.append(
            f'<text x="{X:.1f}" y="{py(ey)}" font-size="{fs}" font-weight="600" '
            f'fill="{colores[k]}" stroke="#fff" stroke-width="3.5" paint-order="stroke" '
            f'text-anchor="{anchor}" dominant-baseline="central">{etiqueta}</text>')

    partes.append("</svg>")
    return "".join(partes)

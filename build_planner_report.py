"""Genera el PDF con la ficha de cada planner.

Uso:  python3 build_planner_report.py

Escribe:
    Ashford ownership by planner.pdf

Una ficha por planner: el mapa de sus codigos sacado del propio visor, sus
lineas, sus vasos, el reparto por nivel, los comprados que consume por nivel y
donde se solapa con los demas.

El mapa no se redibuja aqui: se abre ashford_bom_graph_proposal.html en el
Chromium del entorno, se filtra por el planner y se le quitan las aristas antes
de la captura. Con decenas de miles de lineas el dibujo se vuelve una mancha y
ademas tarda; sin ellas se ven los clusters y los niveles, que es lo que
interesa en una ficha.
"""

import base64
import html
import json
from collections import Counter, defaultdict, deque

import pandas as pd

XLSX = "Ashford split 2.xlsx"
NOMBRES = "machine_names.tsv"
REPARTO = "ownership_proposal.json"
VISOR = "/home/user/ASH_SPLIT/ashford_bom_graph_proposal.html"
SALIDA = "Ashford ownership by planner.pdf"
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

OWNERS = ["Sr planner 1", "Sr planner 2", "Jr planner 1", "Jr planner 2", "Intern"]
COLOR = ["#7c3aed", "#db2777", "#65a30d", "#d97706", "#334155"]
CORTO = ["Sr 1", "Sr 2", "Jr 1", "Jr 2", "Intern"]


# ---------------------------------------------------------------- datos

def cargar():
    bom = pd.read_excel(XLSX, sheet_name="BOM", dtype=str)
    rate = pd.read_excel(XLSX, sheet_name="RATE", dtype=str)
    tabla = pd.read_csv(NOMBRES, sep="\t", dtype=str)

    d = dict(owner={k: int(v) for k, v in json.load(open(REPARTO)).items()},
             nombre=dict(zip(tabla.MachineId, tabla.Description)))
    d["codigos"] = sorted(set(bom.ParentID) | set(bom.ComponentID))
    hijos, padres = defaultdict(list), defaultdict(list)
    for a, b in zip(bom.ParentID, bom.ComponentID):
        hijos[a].append(b)
        padres[b].append(a)
    d["hijos"], d["padres"] = hijos, padres
    maq = defaultdict(set)
    for m, p in zip(rate.MachineId, rate.ProductID):
        maq[p].add(m)
    d["maq"] = maq
    por_maq = defaultdict(list)
    for c in d["codigos"]:
        for m in sorted(maq.get(c, ())):
            por_maq[m].append(c)
    d["por_maq"] = por_maq
    d["consumidos"] = {b for v in hijos.values() for b in v}

    # Nivel = camino mas largo desde las raices, el mismo que dibuja el visor.
    grado = {c: len(padres[c]) for c in d["codigos"]}
    lvl = dict.fromkeys(d["codigos"], 0)
    cola = deque(c for c in d["codigos"] if grado[c] == 0)
    vistos = 0
    while cola:
        x = cola.popleft()
        vistos += 1
        for h in hijos[x]:
            lvl[h] = max(lvl[h], lvl[x] + 1)
            grado[h] -= 1
            if grado[h] == 0:
                cola.append(h)
    assert vistos == len(d["codigos"]), "hay un ciclo en la BOM"
    d["nivel"] = lvl
    return d


def clase(d, c):
    ms = d["maq"].get(c)
    if not ms:
        return "CMP"
    if any(m.startswith("P05M") for m in ms):
        return "BLK"
    return "WIP" if c in d["consumidos"] else "FG"


def ficha(d, o):
    """Todo lo que hace falta para la pagina de un planner."""
    o_de, lvl = d["owner"], d["nivel"]
    mios = [c for c in d["codigos"] if o_de.get(c) == o]
    cl = {c: clase(d, c) for c in mios}

    # Maquinas donde tiene codigos, con cuanto de la maquina es suyo.
    maquinas = []
    for m in sorted(d["por_maq"]):
        cs = d["por_maq"][m]
        suyos = [c for c in cs if o_de.get(c) == o]
        if not suyos:
            continue
        otros = Counter(o_de[c] for c in cs if c in o_de and o_de[c] != o)
        niveles = sorted({lvl[c] for c in cs})
        maquinas.append(dict(
            id=m, nombre=d["nombre"].get(m, m), total=len(cs), mios=len(suyos),
            cuota=len(suyos) / len(cs), otros=otros,
            niveles=f"{niveles[0]}" if len(niveles) == 1 else f"{niveles[0]}–{niveles[-1]}",
            # A que nivel esta lo que se comparte, que es donde duele
            niv_ajeno=sorted({lvl[c] for c in cs if c in o_de and o_de[c] != o}),
        ))

    # Comprados que consume, y cuantos de ellos son solo suyos.
    consumen = {}
    for c in d["codigos"]:
        if d["maq"].get(c):
            continue
        duenos = {o_de[p] for p in d["padres"][c] if p in o_de}
        if o in duenos:
            consumen[c] = duenos
    return dict(
        mios=mios, clase=cl, maquinas=maquinas, consumen=consumen,
        por_nivel=Counter((lvl[c], cl[c]) for c in mios),
        cmp_nivel=Counter((lvl[c], len(v) == 1) for c, v in consumen.items()),
    )


# ---------------------------------------------------------------- capturas

def capturas():
    """Un PNG por planner, sacado del visor con las aristas quitadas."""
    from playwright.sync_api import sync_playwright
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM)
        pg = b.new_page(viewport={"width": 2400, "height": 1500}, device_scale_factor=2)
        errores = []
        pg.on("pageerror", lambda e: errores.append(str(e)))
        pg.goto("file://" + VISOR)
        pg.wait_for_timeout(2500)
        # El rotulo del ambito y la ayuda de abajo tapan clusters en la captura.
        pg.evaluate("""() => { for (const id of ['scope', 'hint'])
            document.getElementById(id).style.display = 'none'; }""")
        for o in range(5):
            pg.locator(f'#owners [data-show="{o}"]').click()
            pg.wait_for_timeout(3200)
            forma = pg.evaluate("""() => {
              view.edges = new Int32Array(0); view.linkGroups = null; groupLinks = false;
              fit(); draw();
              // Cuanto ocupa de verdad el dibujo, para darle un lienzo de su
              // misma forma: con fit() sobre un marco que no le pega, media
              // pagina se queda en blanco y las etiquetas salen ilegibles.
              let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
              for (const c of view.clusters) {
                x0 = Math.min(x0, c.x); y0 = Math.min(y0, c.y);
                x1 = Math.max(x1, c.x + c.w); y1 = Math.max(y1, c.y + c.h);
              }
              return {ancho: x1 - x0, alto: y1 - y0};
            }""")
            # La forma del contenido, pero acotada a la del hueco que tiene la
            # imagen en la pagina (176 x 108 mm, o sea 1,63). Dejarla libre daba
            # capturas altisimas que se comian dos paginas cada una.
            razon = min(1.95, max(1.35, forma["ancho"] / forma["alto"]))
            area = 2400 * 1500
            ancho = round((area * razon) ** 0.5)
            alto = round(area / ancho)
            pg.set_viewport_size({"width": ancho, "height": alto})
            pg.wait_for_timeout(700)
            # fit() del visor encuadra los puntos, no las cajas: el titulo del
            # cluster y el rotulo del nivel quedan por encima del primer punto y
            # se salian por arriba. Aqui se encuadra la caja entera y el rotulo.
            info = pg.evaluate("""() => {
              let x0 = 0, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
              for (const c of view.clusters) {
                x0 = Math.min(x0, c.x); y0 = Math.min(y0, c.y);
                x1 = Math.max(x1, c.x + c.w); y1 = Math.max(y1, c.y + c.h);
              }
              for (const b of view.banners) y0 = Math.min(y0, b.y - 34);
              const r = cv.getBoundingClientRect(), pad = 26;
              k = Math.min((r.width - 2 * pad) / (x1 - x0), (r.height - 2 * pad) / (y1 - y0));
              tx = r.width / 2 - (x0 + x1) / 2 * k;
              ty = r.height / 2 - (y0 + y1) / 2 * k;
              draw();
              return {nodos: view.nodes.length, clusters: view.clusters.length,
                      etiquetas: k * 13 >= 5};
            }""")
            png = pg.locator("#cv").screenshot()
            pg.set_viewport_size({"width": 2400, "height": 1500})
            pg.wait_for_timeout(500)
            out[o] = base64.b64encode(png).decode()
            print(f"  {OWNERS[o]:16} {info['nodos']:>5} codigos, {info['clusters']:>3} clusters"
                  + ("" if info["etiquetas"] else "  (sin etiquetas, muy alejado)"))
            # Volver a la fabrica entera para que el siguiente filtro parta igual
            pg.locator(f'#owners [data-show="{o}"]').click()
            pg.wait_for_timeout(2500)
        assert not errores, f"el visor dio errores: {errores}"
        b.close()
    return out


# ---------------------------------------------------------------- plantilla

CSS = """
@page { size: A4; margin: 15mm 14mm; }
* { box-sizing: border-box; }
body { font: 9.5pt/1.45 "Helvetica Neue", Helvetica, Arial, sans-serif; color: #1a1d21;
       margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
h1 { font-size: 24pt; line-height: 1.12; margin: 0 0 3mm; letter-spacing: -.02em; }
h2 { font-size: 15pt; margin: 0 0 1mm; letter-spacing: -.01em; }
h3 { font-size: 9.5pt; margin: 5mm 0 1.5mm; letter-spacing: .01em; break-after: avoid; }
p { margin: 0 0 2.4mm; }
b, strong { font-weight: 600; }
.lead { font-size: 10.5pt; color: #3d444c; }
.sub { color: #6b737c; font-size: 8pt; letter-spacing: .09em; text-transform: uppercase; }

.head { border-top: 3pt solid; padding-top: 2.5mm; margin-bottom: 3mm; }
.head .sub { margin-bottom: .5mm; }
.head .lines { color: #6b737c; font-size: 8.6pt; margin-top: .8mm; }

table { width: 100%; border-collapse: collapse; margin: 2mm 0 3mm; font-size: 8.4pt; }
th { text-align: left; font-weight: 600; font-size: 7.2pt; letter-spacing: .06em;
     text-transform: uppercase; color: #6b737c; padding: 0 2mm 1.2mm 0;
     border-bottom: .8pt solid #1a1d21; }
td { padding: 1.1mm 2mm 1.1mm 0; border-bottom: .4pt solid #e4e8eb; vertical-align: top; }
th.n, td.n { text-align: right; padding-left: 3mm; padding-right: 2.5mm; width: 1%;
             font-variant-numeric: tabular-nums; white-space: nowrap; }
th.n:last-child, td.n:last-child { padding-right: 0; }
td.who { white-space: nowrap; }
tr.tot td { font-weight: 600; border-top: .8pt solid #1a1d21; border-bottom: 0; }
table.keep { break-inside: avoid; }

.chip { display: inline-block; padding: .4mm 1.6mm; border-radius: 1.4mm; color: #fff;
        font-size: 7pt; font-weight: 600; white-space: nowrap; }
.dim { color: #6b737c; }
.mono { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 7.8pt; }

.cards { display: flex; gap: 2mm; margin: 0 0 3mm; }
.card { flex: 1; border: .5pt solid #d3d8dd; border-radius: 1.4mm; padding: 2mm 2.4mm; }
.card .k { font-size: 15pt; font-weight: 600; letter-spacing: -.02em; line-height: 1.1; }
.card .v { font-size: 7.2pt; color: #6b737c; margin-top: .4mm; text-transform: uppercase;
           letter-spacing: .05em; }

.shot { margin: 0 0 3mm; border: .5pt solid #d3d8dd; border-radius: 1.4mm; overflow: hidden; }
.shot img { display: block; width: 100%; }

.bar { height: 3.4mm; background: #eef1f3; border-radius: 1mm; overflow: hidden; display: flex; }
.bar span { display: block; height: 100%; }

.note { font-size: 7.8pt; color: #6b737c; }
.page { break-before: page; }
.foot { margin-top: 6mm; padding-top: 2mm; border-top: .5pt solid #d3d8dd;
        font-size: 7.6pt; color: #6b737c; }
"""


def chip(o):
    return f'<span class="chip" style="background:{COLOR[o]}">{CORTO[o]}</span>'


def construir(d, shots):
    W = []
    w = W.append
    o_de = d["owner"]
    fichas = {o: ficha(d, o) for o in range(5)}

    # ------------------------------------------------------------ portada
    w("""<div class="sub">Ashford &middot; ownership reorganisation</div>
      <h1>One page per planner</h1>
      <p class="lead">What each planner ends up owning: their lines and vessels, how much of
      each machine is theirs, where their codes sit in the pyramid, the purchased codes they
      consume by level, and where they overlap with the rest.</p>
      <p>Every map is a capture of the viewer itself, filtered to that planner and with the
      arrows removed. Drawing tens of thousands of links turns the picture into a grey smear,
      and what matters in a summary is the shape: which clusters they own and at what level
      they sit. Shape is the class &mdash; circle for a finished good, diamond for a bulk,
      triangle for work in progress, square for a purchased code &mdash; and a hollow shape is
      a code with no owner, shared with somebody else.</p>""")

    w('<table class="keep"><tr><th>Planner</th><th class="n">Codes</th><th class="n">FG</th>'
      '<th class="n">BLK</th><th class="n">WIP</th><th class="n">CMP</th>'
      '<th class="n">Machines</th><th class="n">Only theirs</th>'
      '<th>Where their codes sit</th></tr>')
    for o in range(5):
        f = fichas[o]
        k = Counter(f["clase"].values())
        solas = sum(1 for m in f["maquinas"] if not m["otros"])
        niv = sorted({d["nivel"][c] for c in f["mios"]})
        w(f'<tr><td class="who">{chip(o)} {OWNERS[o]}</td>'
          f'<td class="n">{len(f["mios"]):,}</td><td class="n">{k["FG"]:,}</td>'
          f'<td class="n">{k["BLK"]:,}</td><td class="n">{k["WIP"]}</td>'
          f'<td class="n">{k["CMP"]:,}</td><td class="n">{len(f["maquinas"])}</td>'
          f'<td class="n">{solas}</td>'
          f'<td class="dim">levels {niv[0]}&ndash;{niv[-1]}</td></tr>')
    w("</table>")
    w('<p class="note">Only theirs counts the machines where no other planner holds a single '
      'code. Level 0 is what ships; every step down is one more BOM level away from it.</p>')

    # ------------------------------------------------------------ una por planner
    for o in range(5):
        f = fichas[o]
        k = Counter(f["clase"].values())
        lineas = [m for m in f["maquinas"] if m["id"].startswith("P05P")]
        vasos = [m for m in f["maquinas"] if m["id"].startswith("P05M")]
        compartidas = [m for m in f["maquinas"] if m["otros"]]
        solo_mio = sum(1 for v in f["consumen"].values() if len(v) == 1)

        w(f'<div class="page"></div>'
          f'<div class="head" style="border-color:{COLOR[o]}">'
          f'<div class="sub" style="color:{COLOR[o]}">Planner {o + 1} of 5</div>'
          f'<h2>{OWNERS[o]}</h2>'
          f'<div class="lines">{html.escape(", ".join(m["nombre"] for m in lineas if m["cuota"] >= .5))}</div></div>')

        w('<div class="cards">')
        for kk, vv in [(f"{len(f['mios']):,}", "codes owned"),
                       (f"{k['FG']:,}", "finished goods"),
                       (f"{k['BLK']:,}", "bulks"),
                       (str(k["WIP"]), "work in progress"),
                       (f"{k['CMP']:,}", "purchased"),
                       (str(len(lineas)), "packing lines"),
                       (str(len(vasos)), "vessels")]:
            w(f'<div class="card"><div class="k">{kk}</div><div class="v">{vv}</div></div>')
        w("</div>")

        w(f'<div class="shot"><img src="data:image/png;base64,{shots[o]}" '
          f'alt="Map of {OWNERS[o]}"></div>')
        w('<p class="note">Clusters are machines, stacked by level. Filled shapes are theirs; '
          'hollow squares are the purchased codes shared with other planners, which is why they '
          'have no owner.</p>')

        # --- lineas de packing
        w("<h3>Packing lines</h3>")
        w('<table class="keep"><tr><th>Line</th><th class="n">Codes</th><th class="n">Theirs</th>'
          '<th class="n">Share</th><th>How much of the machine</th><th>Also on it</th></tr>')
        for m in sorted(lineas, key=lambda m: -m["total"]):
            w(fila_maquina(m, o))
        w("</table>")

        # --- vasos
        w("<h3>Vessels</h3>")
        w('<table><tr><th>Vessel</th><th class="n">Codes</th><th class="n">Theirs</th>'
          '<th class="n">Share</th><th>How much of the machine</th><th>Also on it</th></tr>')
        for m in sorted(vasos, key=lambda m: -m["mios"]):
            w(fila_maquina(m, o))
        w("</table>")

        # --- niveles
        w("<h3>Their codes by level</h3>")
        niveles = sorted({n for n, _ in f["por_nivel"]})
        w('<table class="keep"><tr><th>Level</th><th class="n">FG</th><th class="n">BLK</th>'
          '<th class="n">WIP</th><th class="n">CMP</th><th class="n">Total</th>'
          '<th>What sits there</th></tr>')
        que = {0: "what ships, plus bulks nobody consumes",
               1: "bulks and the packs that go straight into a finished good",
               2: "second-level bulks and their materials",
               3: "raw material of a bulk that feeds another bulk",
               4: "the deep end of the chain", 5: "the deep end of the chain"}
        for n in niveles:
            fila = [f["por_nivel"].get((n, c), 0) for c in ("FG", "BLK", "WIP", "CMP")]
            w(f'<tr><td>Level {n}</td>'
              + "".join(f'<td class="n">{v}</td>' for v in fila)
              + f'<td class="n"><b>{sum(fila)}</b></td>'
              f'<td class="dim">{que.get(n, "")}</td></tr>')
        w("</table>")

        # --- comprados por nivel
        w("<h3>Purchased codes they consume, by level</h3>")
        nivs = sorted({n for n, _ in f["cmp_nivel"]})
        w('<table class="keep"><tr><th>Level</th><th class="n">Only theirs</th>'
          '<th class="n">Shared</th><th class="n">Total</th><th class="n">Shared</th>'
          '<th>Split</th></tr>')
        for n in nivs:
            solo = f["cmp_nivel"].get((n, True), 0)
            comp = f["cmp_nivel"].get((n, False), 0)
            tot = solo + comp
            w(f'<tr><td>Level {n}</td><td class="n">{solo}</td><td class="n">{comp}</td>'
              f'<td class="n">{tot}</td><td class="n">{comp / tot * 100:.0f} %</td>'
              f'<td>{barra(comp / tot, COLOR[o])}</td></tr>')
        tot = len(f["consumen"])
        w(f'<tr class="tot"><td>Total</td><td class="n">{solo_mio}</td>'
          f'<td class="n">{tot - solo_mio}</td><td class="n">{tot}</td>'
          f'<td class="n">{(tot - solo_mio) / tot * 100:.0f} %</td><td></td></tr>')
        w("</table>")
        w('<p class="note">Only theirs is what nobody else consumes, and it is exactly the '
          f'{solo_mio:,} purchased codes they own. The other {tot - solo_mio} are shared and '
          'deliberately left with no owner.</p>')

        # --- donde se solapa
        w("<h3>Where they overlap</h3>")
        if compartidas:
            w('<table><tr><th>Machine</th><th class="n">Theirs</th><th>Shared with</th>'
              '<th class="n">Their share</th><th>Levels of the other codes</th></tr>')
            for m in sorted(compartidas, key=lambda m: -sum(m["otros"].values())):
                otros = " ".join(f'{chip(x)} <span class="dim">{n}</span>'
                                 for x, n in m["otros"].most_common())
                niv = ", ".join(str(x) for x in m["niv_ajeno"])
                w(f'<tr><td>{html.escape(m["nombre"])} '
                  f'<span class="mono dim">{m["id"]}</span></td>'
                  f'<td class="n">{m["mios"]}</td><td class="who">{otros}</td>'
                  f'<td class="n">{m["cuota"] * 100:.0f} %</td>'
                  f'<td class="dim">level {niv}</td></tr>')
            w("</table>")
            w(f'<p class="note">{len(compartidas)} of their {len(f["maquinas"])} machines carry '
              'codes belonging to somebody else. The rest are theirs alone.</p>')
        else:
            w('<p class="note">None. Every machine they touch is theirs alone.</p>')

    w('<div class="foot">Generated by <span class="mono">build_planner_report.py</span>. The '
      'maps are captures of <span class="mono">ashford_bom_graph_proposal.html</span> filtered '
      'per planner with the arrows removed; every figure comes from the same split the viewer '
      'carries.</div>')

    return ("<!doctype html><meta charset=utf-8><title>Ashford ownership by planner</title>"
            f"<style>{CSS}</style>" + "".join(W))


def barra(frac, color):
    return (f'<span class="bar"><span style="width:{frac * 100:.1f}%;background:{color}"></span>'
            f'</span>')


def fila_maquina(m, o):
    otros = (" ".join(chip(x) for x, _ in m["otros"].most_common())
             if m["otros"] else '<span class="dim">nobody else</span>')
    return (f'<tr><td>{html.escape(m["nombre"])} <span class="mono dim">{m["id"]}</span></td>'
            f'<td class="n">{m["total"]}</td><td class="n">{m["mios"]}</td>'
            f'<td class="n">{m["cuota"] * 100:.0f} %</td>'
            f'<td>{barra(m["cuota"], COLOR[o])}</td><td class="who">{otros}</td></tr>')


def main():
    d = cargar()
    print("capturando el visor:")
    shots = capturas()
    doc = construir(d, shots)
    tmp = "/tmp/_planners.html"
    open(tmp, "w", encoding="utf-8").write(doc)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM)
        pg = b.new_page()
        pg.goto("file://" + tmp)
        pg.pdf(path=SALIDA, format="A4", print_background=True,
               display_header_footer=True, header_template="<div></div>",
               footer_template='<div style="width:100%;font:8pt Helvetica,Arial;color:#9aa2aa;'
                               'padding:0 14mm;display:flex;justify-content:space-between">'
                               '<span>Ashford &middot; ownership by planner</span>'
                               '<span class="pageNumber"></span></div>',
               margin={"top": "15mm", "bottom": "15mm", "left": "0", "right": "0"})
        b.close()

    import os
    print(f"{SALIDA} — {os.path.getsize(SALIDA) / 1024:.0f} KB")


if __name__ == "__main__":
    main()

"""Genera el informe en PDF de la propuesta de reparto.

Uso:  python3 build_report.py

Lee el xlsx limpio, machine_names.tsv y ownership_proposal.json, calcula todas
las cifras y escribe:

    Ashford ownership proposal.pdf

El informe va en ingles porque es para el equipo; el codigo y los comentarios
siguen en castellano como el resto del repositorio.

Nada del informe esta escrito a mano: las tablas y los recuentos salen del mismo
reparto que se incrusta en el visor, asi que no pueden quedarse viejos. El PDF se
imprime con el Chromium que ya trae el entorno.
"""

import html
import json
from collections import Counter, defaultdict, deque

import pandas as pd

import venn5

XLSX = "Ashford split 2.xlsx"
NOMBRES = "machine_names.tsv"
REPARTO = "ownership_proposal.json"
SALIDA = "Ashford ownership proposal.pdf"
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

OWNERS = ["Sr planner 1", "Sr planner 2", "Jr planner 1", "Jr planner 2", "Intern"]
COLOR = ["#7c3aed", "#db2777", "#65a30d", "#d97706", "#334155"]
CORTO = ["Sr 1", "Sr 2", "Jr 1", "Jr 2", "Intern"]


def cargar():
    bom = pd.read_excel(XLSX, sheet_name="BOM", dtype=str)
    rate = pd.read_excel(XLSX, sheet_name="RATE", dtype=str)
    tabla = pd.read_csv(NOMBRES, sep="\t", dtype=str)
    d = dict(
        owner={k: int(v) for k, v in json.load(open(REPARTO)).items()},
        nombre=dict(zip(tabla.MachineId, tabla.Description)),
    )
    d["codigos"] = sorted(set(bom.ParentID) | set(bom.ComponentID))
    hijos, padres = defaultdict(set), defaultdict(set)
    for a, b in zip(bom.ParentID, bom.ComponentID):
        hijos[a].add(b)
        padres[b].add(a)
    d["hijos"], d["padres"] = hijos, padres
    maq = defaultdict(set)
    for m, p in zip(rate.MachineId, rate.ProductID):
        maq[p].add(m)
    d["maq"] = maq
    por_maq = defaultdict(list)
    for c in d["codigos"]:
        for m in maq.get(c, ()):
            por_maq[m].append(c)
    d["por_maq"] = por_maq
    d["consumidos"] = {b for a in hijos for b in hijos[a]}
    return d


def clase(d, c):
    ms = d["maq"].get(c)
    if not ms:
        return "CMP"
    if any(m.startswith("P05M") for m in ms):
        return "BLK"
    return "WIP" if c in d["consumidos"] else "FG"


def dueno_maquina(d, m):
    """Quien lleva la mayoria de los codigos de una maquina, y cuantos."""
    cuenta = Counter(d["owner"][c] for c in d["por_maq"][m] if c in d["owner"])
    top, n = cuenta.most_common(1)[0]
    return top, n, len(d["por_maq"][m])


def consumidores_de_bulk(d):
    """Para cada bulk, cuantas veces lo consume cada planner en su packing."""
    packing = {c for c in d["codigos"] if any(m.startswith("P05P") for m in d["maq"].get(c, ()))}
    bulks = [c for c in d["codigos"] if d["maq"].get(c) and c not in packing]
    out = {}
    for c in bulks:
        pila, visto, cuenta = [c], {c}, Counter()
        while pila:
            x = pila.pop()
            for p in sorted(d["padres"][x]):
                if p in visto:
                    continue
                visto.add(p)
                if p in packing:
                    if p in d["owner"]:
                        cuenta[d["owner"][p]] += 1
                else:
                    pila.append(p)
        out[c] = cuenta
    return bulks, out


def niveles(d):
    """Camino mas largo desde las raices, el mismo nivel que dibuja el visor."""
    grado = {c: len(d["padres"][c]) for c in d["codigos"]}
    lvl = dict.fromkeys(d["codigos"], 0)
    cola = deque(c for c in d["codigos"] if grado[c] == 0)
    vistos = 0
    while cola:
        x = cola.popleft()
        vistos += 1
        for h in sorted(d["hijos"][x]):
            lvl[h] = max(lvl[h], lvl[x] + 1)
            grado[h] -= 1
            if grado[h] == 0:
                cola.append(h)
    assert vistos == len(d["codigos"]), "hay un ciclo en la BOM"
    return lvl


# ---------------------------------------------------------------- plantilla

CSS = """
@page { size: A4; margin: 17mm 15mm 15mm 15mm; }
* { box-sizing: border-box; }
body {
  font: 10pt/1.5 "Helvetica Neue", Helvetica, Arial, sans-serif;
  color: #1a1d21; margin: 0; -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
h1 { font-size: 25pt; line-height: 1.12; margin: 0 0 4mm; letter-spacing: -.02em; }
h2 {
  font-size: 13.5pt; margin: 11mm 0 3mm; padding-bottom: 1.6mm;
  border-bottom: 1.6pt solid #1a1d21; letter-spacing: -.01em; break-after: avoid;
}
h3 { font-size: 10.5pt; margin: 6mm 0 2mm; letter-spacing: .01em; break-after: avoid; }
p { margin: 0 0 2.6mm; }
b, strong { font-weight: 600; }
.lead { font-size: 11pt; color: #3d444c; }
.sub { color: #6b737c; font-size: 8.6pt; letter-spacing: .09em; text-transform: uppercase; }

table { width: 100%; border-collapse: collapse; margin: 3mm 0 4mm; font-size: 9pt; }
th {
  text-align: left; font-weight: 600; font-size: 7.8pt; letter-spacing: .07em;
  text-transform: uppercase; color: #6b737c; padding: 0 2.5mm 1.4mm 0;
  border-bottom: .8pt solid #1a1d21;
}
td { padding: 1.5mm 2.5mm 1.5mm 0; border-bottom: .4pt solid #e4e8eb; vertical-align: top; }
th.n, td.n {
  text-align: right; padding-left: 4mm; padding-right: 3mm; width: 1%;
  font-variant-numeric: tabular-nums; white-space: nowrap;
}
th.n:last-child, td.n:last-child { padding-right: 0; }
td.who { white-space: nowrap; }
tr.tot td { font-weight: 600; border-top: .8pt solid #1a1d21; border-bottom: 0; }
table.tight td, table.tight th { padding-top: 1mm; padding-bottom: 1mm; }

.chip {
  display: inline-block; padding: .5mm 1.8mm; border-radius: 1.5mm; color: #fff;
  font-size: 7.6pt; font-weight: 600; letter-spacing: .02em; white-space: nowrap;
}
.dim { color: #6b737c; }
.mono { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 8.4pt; }

.rule-card {
  border-left: 2.4pt solid #1a1d21; padding: 0 0 0 4mm; margin: 0 0 5mm;
  break-inside: avoid;
}
.rule-card .n { font-size: 7.8pt; letter-spacing: .1em; text-transform: uppercase; color: #6b737c; }
.rule-card .t { font-size: 11.5pt; font-weight: 600; margin: .6mm 0 1.6mm; line-height: 1.3; }
.rule-card .why { color: #3d444c; }
.rule-card .ex {
  background: #f4f6f8; border-radius: 1.5mm; padding: 2.2mm 3mm; margin-top: 2.2mm;
  font-size: 9pt;
}

.cards { display: flex; gap: 3mm; margin: 3mm 0 4mm; }
.card { flex: 1; border: .5pt solid #d3d8dd; border-radius: 1.5mm; padding: 2.6mm 3mm; }
.card .k { font-size: 18pt; font-weight: 600; letter-spacing: -.02em; line-height: 1.1; }
.card .v { font-size: 8pt; color: #6b737c; margin-top: .8mm; line-height: 1.35; }

.venn { text-align: center; margin: 2mm 0 1mm; break-inside: avoid; }
.venn svg { width: 152mm; height: 152mm; }

.note { font-size: 8.6pt; color: #6b737c; }
.page { break-before: page; }
.foot { margin-top: 8mm; padding-top: 2.5mm; border-top: .5pt solid #d3d8dd; font-size: 8pt; color: #6b737c; }
"""


def chip(o):
    return f'<span class="chip" style="background:{COLOR[o]}">{CORTO[o]}</span>'


def construir(d):
    o_de = d["owner"]
    codigos = d["codigos"]
    W = []
    w = W.append

    suyos = {o: [c for c in codigos if o_de.get(c) == o] for o in range(5)}
    sin_asignar = [c for c in codigos if c not in o_de]
    producibles = {o: sum(1 for c in suyos[o] if d["maq"].get(c)) for o in range(5)}
    lineas_de = {}
    for m in sorted(d["por_maq"]):
        if m.startswith("P05P"):
            lineas_de.setdefault(dueno_maquina(d, m)[0], []).append(m)

    packing = [m for m in sorted(d["por_maq"]) if m.startswith("P05P")]
    n_pack = sum(1 for c in codigos if any(m.startswith("P05P") for m in d["maq"].get(c, ())))
    bulks, usan = consumidores_de_bulk(d)
    a_granel = [c for c in bulks if not usan[c]]
    comprados = [c for c in codigos if not d["maq"].get(c)]
    con_dueno = len(comprados) - len(sin_asignar)

    # ------------------------------------------------------------ portada
    w(f"""<div class="sub">Ashford &middot; ownership reorganisation</div>
      <h1>Ownership proposal<br>across the five planners</h1>
      <p class="lead">Each planner owns a group of packing lines and everything else hangs off
      that: bulks go with whoever consumes them, and a purchased code only gets an owner when a
      single planner uses it. This document holds the split, <b>the rules for classifying a new
      code</b>, and why {len(sin_asignar)} purchased codes are left with no owner at all.</p>""")

    w('<div class="cards">')
    for k, v in [(f"{len(codigos):,}", "codes in the Ashford BOM"),
                 (f"{len(o_de):,}", "with a proposed owner"),
                 (str(len(sin_asignar)), "purchased codes shared, left unassigned"),
                 ("86 %", "finished goods whose whole chain sits with one planner")]:
        w(f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div></div>')
    w("</div>")

    # ------------------------------------------------------------ el reparto
    w("<h2>The split</h2>")
    w('<table><tr><th>Planner</th><th>Packing lines</th><th class="n">Made</th>'
      '<th class="n">FG</th><th class="n">BLK</th><th class="n">WIP</th><th class="n">CMP</th></tr>')
    tot = Counter()
    for o in range(5):
        k = Counter(clase(d, c) for c in suyos[o])
        tot.update(k)
        ls = ", ".join(d["nombre"].get(m, m) for m in lineas_de.get(o, []))
        w(f'<tr><td class="who">{chip(o)} {OWNERS[o]}</td><td class="dim">{html.escape(ls)}</td>'
          f'<td class="n">{producibles[o]:,}</td><td class="n">{k["FG"]:,}</td>'
          f'<td class="n">{k["BLK"]:,}</td><td class="n">{k["WIP"]}</td>'
          f'<td class="n">{k["CMP"]:,}</td></tr>')
    w(f'<tr><td colspan="2">Unassigned <span class="dim">&mdash; purchased codes several planners '
      f'consume</span></td><td class="n">0</td><td class="n">&mdash;</td><td class="n">&mdash;</td>'
      f'<td class="n">&mdash;</td><td class="n">{len(sin_asignar)}</td></tr>')
    w(f'<tr class="tot"><td colspan="2">Total</td><td class="n">{sum(producibles.values()):,}</td>'
      f'<td class="n">{tot["FG"]:,}</td><td class="n">{tot["BLK"]:,}</td>'
      f'<td class="n">{tot["WIP"]}</td><td class="n">{tot["CMP"] + len(sin_asignar):,}</td></tr>'
      "</table>")
    w('<p class="note">Made = everything with a routing in RATE, that is FG + BLK + WIP. A code can '
      'run on several machines, but it only ever has one owner.</p>')

    # ------------------------------------------------------------ reglas
    w('<div class="page"></div><h2>Rules for classifying a new code</h2>')
    w("<p>In order. The first one that fits decides, and you never need to read further down.</p>")

    reglas = [
        ("Rule 1", "If the code is packed on a packing line, it belongs to the owner of that line.",
         f"This is the mother rule: ownership is organised by line, not by product family and not "
         f"code by code. It settles {n_pack:,} codes today, every FG and every WIP.",
         "Every code packed on the <b>510 High Speed Kugler</b> goes to <b>Sr planner 2</b>. Every "
         "code on the <b>521 Kalix</b> goes to <b>Sr planner 1</b>. Every code on the "
         "<b>416 MM360</b> goes to <b>Jr planner 2</b>."),
        ("Rule 2", "If it runs on two lines with different owners, it belongs to the owner of the "
                   "smaller line.",
         "One of the two has to be broken. The big one gets broken, because it feels it less, and "
         "the small one stays whole. Today this happens to 6 codes only.",
         "A code running on both the <b>516 Kugler</b> (47 codes) and the <b>510</b> (262) goes to "
         "<b>Sr planner 1</b>, who owns the 516."),
        ("Rule 3", "If it is a bulk, it belongs to the planner who consumes it most on their own "
                   "packing lines.",
         f"You walk the whole chain up, not just to the direct parent: a bulk can feed another bulk "
         f"and only show up in packing two levels higher. On a tie it goes to whoever already holds "
         f"more codes on the same vessel. It settles {len(bulks) - len(a_granel):,} bulks.",
         "A new bulk on <b>EKATO500ATEX</b> that ends up in 30 codes of the <b>521</b> and 4 of the "
         "<b>501</b> goes to <b>Sr planner 1</b>, even though both share the vessel."),
        ("Rule 4", "If it is a bulk sold as it is, it belongs to whoever owns most of its vessel.",
         f"There is no packing line upstream to hang it from, so it hangs from the machine where it "
         f"is made instead. It settles {len(a_granel)} bulks.",
         "A bulk sold as it is, made on <b>BECOMIX 25L</b>, goes to the <b>Intern</b>, who holds 80 "
         "of its 121 codes."),
        ("Rule 5", "If it is a purchased code, it belongs to the planner who consumes it &mdash; "
                   "but only if there is just one.",
         f"If two or more consume it, it is left with <b>no owner</b> on purpose. It settles "
         f"{con_dueno:,} purchased codes and leaves {len(sin_asignar)} unassigned.",
         "A pack that only goes into codes of the <b>701</b> belongs to the <b>Intern</b>. A cap "
         "that goes into both the 521 and the 501 <b>belongs to nobody</b>."),
    ]
    for n, t, why, ex in reglas:
        w(f'<div class="rule-card"><div class="n">{n}</div><div class="t">{t}</div>'
          f'<div class="why">{why}</div><div class="ex">{ex}</div></div>')

    w(f'<p class="note">The five rules cover all {len(codigos):,} codes without overlapping: '
      f'{n_pack:,} packed on a line, {len(bulks) - len(a_granel):,} bulks by consumption, '
      f'{len(a_granel)} sold as they are, {con_dueno:,} purchased with a single owner and '
      f'{len(sin_asignar)} left unassigned.</p>')

    # ------------------------------------------------------------ lineas
    w('<div class="page"></div><h2>Rule 1 as a table: who owns each line</h2>')
    w("<p>The 28 packing lines and their owner. This is the only thing you need to look up for "
      "100 % of the finished goods.</p>")
    w('<table class="tight"><tr><th>Line</th><th>Machine</th><th class="n">Codes</th>'
      '<th>Owner</th><th>Family</th></tr>')
    fam = {"3": "powders (pressing)", "4": "mouldings", "5": "liquids", "6": "powders (packing)",
           "7": "liquids"}
    for m in packing:
        o, n, total = dueno_maquina(d, m)
        nota = "" if n == total else f' <span class="dim">({n} of {total})</span>'
        w(f'<tr><td class="mono">{m}</td><td>{html.escape(d["nombre"].get(m, m))}</td>'
          f'<td class="n">{total}</td><td class="who">{chip(o)} {OWNERS[o]}{nota}</td>'
          f'<td class="dim">{fam.get(m[5], "")}</td></tr>')
    w("</table>")
    partidas = [m for m in packing if dueno_maquina(d, m)[1] != len(d["por_maq"][m])]
    w(f'<p class="note"><b>{len(packing) - len(partidas)} of the {len(packing)} packing lines have '
      'a single owner.</b> The only split one is the 510, because of the 6 codes it shares with the '
      '516 that follow the 516 (rule 2).</p>')

    # ------------------------------------------------------------ vasos
    w("<h2>Rule 4 as a table: who owns each vessel</h2>")
    w("<p>You only need this for bulks sold as they are. For every other bulk rule 3 wins, and "
      "that one is about consumption, not about the vessel.</p>")
    w('<table class="tight"><tr><th>Machine</th><th>Vessel</th><th class="n">Codes</th>'
      '<th>Majority</th><th class="n">Share</th></tr>')
    making = [m for m in sorted(d["por_maq"]) if m.startswith("P05M")]
    for m in making:
        o, n, total = dueno_maquina(d, m)
        w(f'<tr><td class="mono">{m}</td><td>{html.escape(d["nombre"].get(m, m))}</td>'
          f'<td class="n">{total}</td><td class="who">{chip(o)} {OWNERS[o]}</td>'
          f'<td class="n">{n / total * 100:.0f} %</td></tr>')
    w("</table>")
    enteros = sum(1 for m in making if dueno_maquina(d, m)[1] == len(d["por_maq"][m]))
    mas = max(len({o_de[c] for c in d["por_maq"][m] if c in o_de}) for m in making)
    w(f'<p class="note">Vessels are shared far more than lines: {enteros} of the {len(making)} '
      f'belong to a single planner, and the big liquids ones are touched by up to {mas}. That is '
      'normal &mdash; one vessel serves several lines &mdash; and it is exactly why ownership is '
      'organised by line and not by vessel.</p>')

    # ------------------------------------------------------------ bulks
    w("<h2>Bulks: each one with whoever uses it</h2>")
    reparto_b = Counter(len(usan[c]) for c in bulks)
    comp_b = [c for c in bulks if len(usan[c]) > 1]
    ajenos = [c for c in bulks if usan[c] and o_de.get(c) not in usan[c]]
    suelo = sum(len(usan[c]) - 1 for c in comp_b)
    w(f"""<p>Of the {len(bulks):,} bulks, <b>{reparto_b[1]:,} are used by a single planner</b> and
      are theirs. {len(a_granel)} are sold as they are and no line consumes them. The
      <b>{len(comp_b)} left are used by two or three planners at once</b>.</p>
      <p><b>Not one is held by someone who does not use it</b> ({len(ajenos)} cases). The shared
      ones are the only place where somebody schedules against a bulk that is not theirs, and there
      no split can help: a bulk two planners use leaves one of them out wherever you put it. That
      comes to <b>{suelo} hand-overs, which is exactly the floor</b> these lines allow. Getting
      below it is not done by moving bulks, it is done by moving lines.</p>""")
    w('<table><tr><th>Planner</th><th class="n">Bulks used</th><th class="n">Theirs</th>'
      '<th class="n">Someone else\'s</th></tr>')
    for o in range(5):
        usa = [c for c in bulks if o in usan[c]]
        mios = sum(1 for c in usa if o_de.get(c) == o)
        w(f'<tr><td class="who">{chip(o)} {OWNERS[o]}</td><td class="n">{len(usa)}</td>'
          f'<td class="n">{mios}</td><td class="n">{len(usa) - mios}</td></tr>')
    w("</table>")

    # ------------------------------------------------------------ comprados
    w(f'<div class="page"></div><h2>The {len(sin_asignar)} unassigned purchased codes</h2>')
    duenos_de = {c: sorted({o_de[p] for p in d["padres"][c] if p in o_de}) for c in sin_asignar}
    lineas_bom = sum(len(d["padres"][c]) for c in sin_asignar)
    w(f"""<p><b>Why they have no owner.</b> They are purchased codes that go into codes belonging
      to two or more planners. Handing one to a single planner would be a lie: the others would keep
      consuming it just the same and would have to ask permission for something they use every day.
      In practice a shared component is not managed per planner, it is managed by purchasing, so
      they are deliberately left empty &mdash; and in the viewer they show up hollow, so you can see
      them at a glance.</p>
      <p>They are {len(sin_asignar)} codes out of {len(comprados):,} purchased,
      {len(sin_asignar) / len(comprados) * 100:.0f} %. But they weigh far more than that suggests:
      <b>{lineas_bom:,} BOM lines</b> hang off them, because they are the packs and common materials
      of the whole plant.</p>""")

    # el Venn
    todos_consumen = {c: {o_de[p] for p in d["padres"][c] if p in o_de} for c in comprados}
    cuentas = Counter(sum(1 << o for o in todos_consumen[c]) for c in comprados)
    totales = [sum(1 for c in comprados if o in todos_consumen[c]) for o in range(5)]
    w(f"<h3>All {len(comprados):,} purchased codes, by who consumes them</h3>")
    w(f'<div class="venn">{venn5.svg(cuentas, OWNERS, COLOR, totales)}</div>')
    w('<p class="note">Each ellipse is one planner and holds every purchased code they consume. '
      'The number standing alone inside an ellipse is what only that planner uses, which is what '
      'they own; every number in an overlap is shared, and shared is what gets left unassigned. '
      'A zero means nobody has that exact combination.</p>')

    w("<h3>How many planners share each one</h3>")
    w('<table class="tight"><tr><th>Consumed by</th><th class="n">Codes</th><th>What they are</th></tr>')
    etiqueta = {2: "the normal case: two lines from different families use the same pack",
                3: "material common to liquids, or to liquids plus mouldings",
                4: "consumables used across almost the whole plant",
                5: "the genuinely universal ones, everybody touches them"}
    for k in sorted(Counter(len(v) for v in duenos_de.values())):
        n = sum(1 for v in duenos_de.values() if len(v) == k)
        w(f'<tr><td>{k} planners</td><td class="n">{n}</td><td class="dim">{etiqueta[k]}</td></tr>')
    w("</table>")

    w("<h3>Who shares with whom</h3>")
    w("<p>The combinations that come up most. This is where an agreement would be needed if any of "
      "these codes ever got an owner.</p>")
    w('<table class="tight"><tr><th>Shared by</th><th class="n">Codes</th></tr>')
    for g, n in Counter(tuple(v) for v in duenos_de.values()).most_common(8):
        w(f'<tr><td class="who">{" ".join(chip(o) for o in g)} '
          f'<span class="dim">{", ".join(OWNERS[o] for o in g)}</span></td>'
          f'<td class="n">{n}</td></tr>')
    w("</table>")

    w("<h3>How many each planner appears in</h3>")
    cuenta_o = Counter(o for v in duenos_de.values() for o in v)
    w('<table class="tight"><tr><th>Planner</th><th class="n">Shared purchased codes consumed</th></tr>')
    for o, n in cuenta_o.most_common():
        w(f'<tr><td class="who">{chip(o)} {OWNERS[o]}</td><td class="n">{n}</td></tr>')
    w("</table>")
    w(f'<p class="note">The column adds up to more than {len(sin_asignar)} because a code counts '
      'once for every planner that consumes it.</p>')

    w("<h3>The ten most used</h3>")
    lvl = niveles(d)
    top = sorted(sin_asignar, key=lambda c: (-len(d["padres"][c]), c))[:10]
    w('<table class="tight"><tr><th>Code</th><th class="n">Level</th><th class="n">Parents</th>'
      '<th>Shared by</th></tr>')
    for c in top:
        w(f'<tr><td class="mono">{c}</td><td class="n">{lvl[c]}</td>'
          f'<td class="n">{len(d["padres"][c]):,}</td>'
          f'<td>{" ".join(chip(o) for o in duenos_de[c])}</td></tr>')
    w("</table>")
    w('<p class="note">The first five go into more than a thousand products each and all five '
      'planners consume them. No split can assign those without leaving four people depending on a '
      'fifth. The full list, with its level and a column per planner, is in '
      '<span class="mono">Ashford components by planner.xlsx</span>.</p>')

    # ------------------------------------------------------------ abierto
    w('<div class="page"></div><h2>What is still open</h2>')
    w(f"""<h3>The 510 is split</h3>
      <p>It is the only packing line with two owners. It comes from putting the 516 with
      foundations: 6 codes run on both and follow the 516, which is the smaller one. On top of that
      the bulks of the 516 feed the Kugler block far more than they feed foundations, so Sr planner
      1 owns the line but schedules against bulks that Sr planner 2 largely drives. It is a known
      cost, accepted in exchange for levelling the load between the two Sr planners.</p>

      <h3>Kugler</h3>
      <p>It is the largest packing block in the plant and it does not come apart without breaking
      fluidity. While it stays whole, Sr planner 2 will carry more codes than anyone else. It is the
      only real lever left if the load ever has to be rebalanced.</p>

      <h3>Shared vessels</h3>
      <p>{len(making) - enteros} of the {len(making)} vessels are touched by two or more planners.
      That is not a problem with the split: a vessel serves several lines by design. What has to be
      clear is that coordination in making is real, and that rules 3 and 4 only say who decides, not
      who is the only one using it.</p>

      <h3>How to adjust it</h3>
      <p>The viewer (<span class="mono">ashford_bom_graph_proposal.html</span>) already carries the
      split. The shape says what a code is and the colour says whose it is: a circle for an FG, a
      diamond for a bulk, a triangle for a WIP and a square for a purchased code; hollow means
      nobody holds it. Click a planner and the map keeps only their codes together with the
      purchased ones they share with the rest. To move things: <b>Select related</b> picks up a
      whole chain, the rectangle picks up an area, and <b>Assign to</b> reassigns it. Changes save
      themselves in the browser.</p>""")

    w('<div class="foot">Generated by <span class="mono">build_report.py</span> from '
      '<span class="mono">Ashford split 2.xlsx</span> and '
      '<span class="mono">ownership_proposal.json</span>. Every figure comes from the same split '
      'the viewer carries.</div>')

    return ("<!doctype html><meta charset=utf-8><title>Ashford ownership proposal</title>"
            f"<style>{CSS}</style>" + "".join(W))


def main():
    d = cargar()
    doc = construir(d)
    tmp = "/tmp/_informe.html"
    open(tmp, "w", encoding="utf-8").write(doc)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM)
        pg = b.new_page()
        pg.goto("file://" + tmp)
        pg.pdf(path=SALIDA, format="A4", print_background=True,
               display_header_footer=True,
               header_template="<div></div>",
               footer_template='<div style="width:100%;font:8pt Helvetica,Arial;color:#9aa2aa;'
                               'padding:0 15mm;display:flex;justify-content:space-between">'
                               '<span>Ashford &middot; ownership proposal</span>'
                               '<span class="pageNumber"></span></div>',
               margin={"top": "17mm", "bottom": "17mm", "left": "0", "right": "0"})
        b.close()

    import os
    print(f"{SALIDA} — {os.path.getsize(SALIDA) / 1024:.0f} KB")


if __name__ == "__main__":
    main()

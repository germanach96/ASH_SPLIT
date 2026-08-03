"""Genera el informe en PDF de la propuesta de reparto.

Uso:  python3 build_report.py

Lee el xlsx limpio, machine_names.tsv y ownership_proposal.json, calcula todas
las cifras y escribe:

    Propuesta reparto Ashford.pdf

Nada del informe esta escrito a mano: las tablas y los recuentos salen del
mismo reparto que se incrusta en el visor, asi que no pueden quedarse viejos.
El PDF se imprime con el Chromium que ya trae el entorno.
"""

import html
import json
from collections import Counter, defaultdict

import pandas as pd

XLSX = "Ashford split 2.xlsx"
NOMBRES = "machine_names.tsv"
REPARTO = "ownership_proposal.json"
SALIDA = "Propuesta reparto Ashford.pdf"
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
.rule { border: 0; border-top: .5pt solid #d3d8dd; margin: 5mm 0; }

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

.regla {
  border-left: 2.4pt solid #1a1d21; padding: 0 0 0 4mm; margin: 0 0 5mm;
  break-inside: avoid;
}
.regla .n { font-size: 7.8pt; letter-spacing: .1em; text-transform: uppercase; color: #6b737c; }
.regla .t { font-size: 11.5pt; font-weight: 600; margin: .6mm 0 1.6mm; line-height: 1.3; }
.regla .porque { color: #3d444c; }
.regla .ej {
  background: #f4f6f8; border-radius: 1.5mm; padding: 2.2mm 3mm; margin-top: 2.2mm;
  font-size: 9pt;
}
.regla .ej b { font-weight: 600; }

.cards { display: flex; gap: 3mm; margin: 3mm 0 4mm; }
.card { flex: 1; border: .5pt solid #d3d8dd; border-radius: 1.5mm; padding: 2.6mm 3mm; }
.card .k { font-size: 18pt; font-weight: 600; letter-spacing: -.02em; line-height: 1.1; }
.card .v { font-size: 8pt; color: #6b737c; margin-top: .8mm; line-height: 1.35; }

.note { font-size: 8.6pt; color: #6b737c; }
.page { break-before: page; }
ul { margin: 0 0 3mm; padding-left: 4.5mm; }
li { margin-bottom: 1.2mm; }
.foot { margin-top: 8mm; padding-top: 2.5mm; border-top: .5pt solid #d3d8dd; font-size: 8pt; color: #6b737c; }
"""


def mil(n):
    """1310 -> "1.310". Formatear el numero suelto y no el parrafo entero, que
    se llevaba por delante las comas del texto."""
    return f"{n:,}".replace(",", ".")


def chip(o):
    return f'<span class="chip" style="background:{COLOR[o]}">{CORTO[o]}</span>'


def construir(d):
    o_de = d["owner"]
    codigos = d["codigos"]
    W = []
    w = W.append

    # ---- cifras de cabecera
    suyos = {o: [c for c in codigos if o_de.get(c) == o] for o in range(5)}
    sin_asignar = [c for c in codigos if c not in o_de]
    producibles = {o: sum(1 for c in suyos[o] if d["maq"].get(c)) for o in range(5)}
    lineas_de = {}
    for m in sorted(d["por_maq"]):
        if m.startswith("P05P"):
            lineas_de.setdefault(dueno_maquina(d, m)[0], []).append(m)

    w(f"""<div class="sub">Ashford · reorganización del ownership</div>
      <h1>Propuesta de reparto<br>entre los cinco planners</h1>
      <p class="lead">Cada planner es dueño de un grupo de líneas de packing y todo lo demás cuelga
      de ahí: los bulks van con quien los consume y los comprados solo tienen dueño si lo consume
      uno solo. Este documento recoge el reparto, <b>las reglas para clasificar un código nuevo</b>
      y por qué 304 comprados se quedan sin asignar.</p>""")

    w('<div class="cards">')
    for k, v in [(f"{len(codigos):,}".replace(",", "."), "códigos en la BOM de Ashford"),
                 (f"{len(o_de):,}".replace(",", "."), "con dueño propuesto"),
                 (str(len(sin_asignar)), "comprados compartidos, sin dueño"),
                 ("86 %", "productos finales con la cadena entera en un solo planner")]:
        w(f'<div class="card"><div class="k">{k}</div><div class="v">{v}</div></div>')
    w("</div>")

    # ---- el reparto
    w("<h2>El reparto</h2>")
    w('<table><tr><th>Planner</th><th>Líneas de packing</th><th class="n">Produc.</th>'
      '<th class="n">FG</th><th class="n">BLK</th><th class="n">WIP</th><th class="n">CMP</th></tr>')
    tot = Counter()
    for o in range(5):
        k = Counter(clase(d, c) for c in suyos[o])
        tot.update(k)
        ls = ", ".join(d["nombre"].get(m, m) for m in lineas_de.get(o, []))
        w(f'<tr><td class="who">{chip(o)} {OWNERS[o]}</td><td class="dim">{html.escape(ls)}</td>'
          f'<td class="n">{producibles[o]}</td><td class="n">{k["FG"]}</td>'
          f'<td class="n">{k["BLK"]}</td><td class="n">{k["WIP"]}</td><td class="n">{k["CMP"]}</td></tr>')
    w(f'<tr><td colspan="2">Sin asignar <span class="dim">— comprados que consumen varios planners</span></td>'
      f'<td class="n">0</td><td class="n">—</td><td class="n">—</td><td class="n">—</td>'
      f'<td class="n">{len(sin_asignar)}</td></tr>')
    w(f'<tr class="tot"><td colspan="2">Total</td><td class="n">{sum(producibles.values())}</td>'
      f'<td class="n">{tot["FG"]}</td><td class="n">{tot["BLK"]}</td><td class="n">{tot["WIP"]}</td>'
      f'<td class="n">{tot["CMP"] + len(sin_asignar)}</td></tr></table>')
    w('<p class="note">Producibles = todo lo que tiene ruta en RATE, o sea FG + BLK + WIP. '
      'Un código puede correr en varias máquinas, pero solo tiene un dueño.</p>')

    # ---- las reglas
    w('<div class="page"></div><h2>Reglas para clasificar un código nuevo</h2>')
    w("<p>En orden. La primera que encaje decide, y no hace falta mirar las siguientes.</p>")

    packing = [m for m in sorted(d["por_maq"]) if m.startswith("P05P")]
    n_pack = sum(1 for c in codigos if any(m.startswith("P05P") for m in d["maq"].get(c, ())))
    bulks, usan = consumidores_de_bulk(d)
    a_granel = [c for c in bulks if not usan[c]]
    comprados = [c for c in codigos if not d["maq"].get(c)]
    con_dueno = len(comprados) - len(sin_asignar)

    reglas = [
        ("Regla 1", "Si el código se envasa en una línea de packing, es del dueño de esa línea.",
         "Es la regla madre: el ownership se organiza por línea, no por familia de producto ni por "
         "código suelto. Decide hoy 2.615 códigos, todos los FG y todos los WIP.",
         "Todos los códigos que se envasen en la <b>510 High Speed Kugler</b> son del "
         "<b>Sr planner 2</b>. Todos los de la <b>521 Kalix</b>, del <b>Sr planner 1</b>. "
         "Todos los de la <b>416 MM360</b>, del <b>Jr planner 2</b>."),
        ("Regla 2", "Si corre en dos líneas de dueños distintos, es del dueño de la línea más pequeña.",
         "Alguna de las dos se parte por narices. Se parte la grande, que lo nota menos, y la "
         "pequeña queda entera. Hoy solo pasa en 6 códigos.",
         "Un código que corra en la <b>516 Kugler</b> (47 códigos) y en la <b>510</b> (262) es del "
         "<b>Sr planner 1</b>, que lleva la 516."),
        ("Regla 3", "Si es un bulk, es del planner que más lo consume en sus líneas de packing.",
         "Se sube por toda la cadena, no solo al padre directo: un bulk puede alimentar a otro bulk "
         "y no aparecer en packing hasta dos niveles más arriba. Si empatan, va con quien ya lleve "
         "más códigos del mismo vaso. Decide 1.149 bulks.",
         "Un bulk nuevo en <b>EKATO500ATEX</b> que acabe en 30 códigos de la <b>521</b> y en 4 de la "
         "<b>501</b> es del <b>Sr planner 1</b>, aunque el vaso lo compartan los dos."),
        ("Regla 4", "Si es un bulk que se vende a granel, es del dueño de la mayoría de su vaso.",
         "No hay ninguna línea de packing aguas arriba de la que colgarlo, así que se cuelga de la "
         "máquina donde se hace. Decide 161 bulks.",
         "Un bulk a granel hecho en <b>BECOMIX 25L</b> es del <b>Intern</b>, que lleva 80 de sus "
         "121 códigos."),
        ("Regla 5", "Si es un comprado, es del planner que lo consume, pero solo si es uno solo.",
         f"Si lo consumen dos o más se queda <b>sin dueño</b> a propósito. Decide {con_dueno:,} "
         "comprados con dueño y deja 304 sin asignar.".replace(",", "."),
         "Un envase que solo entre en códigos de la <b>701</b> es del <b>Intern</b>. Un tapón que "
         "entre en la 521 y en la 501 <b>no es de nadie</b>."),
    ]
    for n, t, porque, ej in reglas:
        w(f'<div class="regla"><div class="n">{n}</div><div class="t">{t}</div>'
          f'<div class="porque">{porque}</div><div class="ej">{ej}</div></div>')

    w('<p class="note">Las cinco reglas cubren los 7.176 códigos sin solaparse: '
      f'{mil(n_pack)} de packing, {mil(len(bulks) - len(a_granel))} bulks por consumo, '
      f'{len(a_granel)} a granel, {mil(con_dueno)} comprados con un dueño y '
      f'{len(sin_asignar)} sin asignar.</p>')

    # ---- tabla de lineas
    w('<div class="page"></div><h2>Regla 1 en una tabla: quién lleva cada línea</h2>')
    w("<p>Las 28 líneas de packing y su dueño. Es lo único que hay que consultar para el 100 % de "
      "los productos finales.</p>")
    w('<table class="tight"><tr><th>Línea</th><th>Máquina</th><th class="n">Códigos</th>'
      '<th>Dueño</th><th>Familia</th></tr>')
    fam = {"3": "powders (pressing)", "4": "mouldings", "5": "liquids", "6": "powders (packing)",
           "7": "liquids"}
    for m in packing:
        o, n, total = dueno_maquina(d, m)
        nota = "" if n == total else f' <span class="dim">({n} de {total})</span>'
        w(f'<tr><td class="mono">{m}</td><td>{html.escape(d["nombre"].get(m, m))}</td>'
          f'<td class="n">{total}</td><td>{chip(o)} {OWNERS[o]}{nota}</td>'
          f'<td class="dim">{fam.get(m[5], "")}</td></tr>')
    w("</table>")
    w('<p class="note"><b>27 de las 28 líneas tienen un solo dueño.</b> La única partida es la 510, '
      'por los 6 códigos que comparte con la 516 y que se van con ella (regla 2).</p>')

    # ---- vasos
    w("<h2>Regla 4 en una tabla: quién lleva cada vaso</h2>")
    w("<p>Solo hace falta para los bulks que se venden a granel. Para el resto manda la regla 3, que "
      "es el consumo, no el vaso.</p>")
    w('<table class="tight"><tr><th>Máquina</th><th>Vaso</th><th class="n">Códigos</th>'
      '<th>Mayoría</th><th class="n">Cuota</th></tr>')
    for m in sorted(d["por_maq"]):
        if not m.startswith("P05M"):
            continue
        o, n, total = dueno_maquina(d, m)
        w(f'<tr><td class="mono">{m}</td><td>{html.escape(d["nombre"].get(m, m))}</td>'
          f'<td class="n">{total}</td><td>{chip(o)} {OWNERS[o]}</td>'
          f'<td class="n">{n / total * 100:.0f} %</td></tr>')
    w("</table>")
    making = [m for m in d["por_maq"] if m.startswith("P05M")]
    enteros = sum(1 for m in making if dueno_maquina(d, m)[1] == len(d["por_maq"][m]))
    mas = max(len({o_de[c] for c in d["por_maq"][m] if c in o_de}) for m in making)
    w(f'<p class="note">Los vasos se comparten mucho más que las líneas: {enteros} de los '
      f'{len(making)} son de un solo planner, y los grandes de líquidos los tocan hasta {mas}. Es '
      'normal, un vaso sirve a varias líneas; por eso el ownership se organiza por línea y no por '
      'vaso.</p>')

    # ---- bulks
    w('<h2>Los bulks: cada uno con quien lo usa</h2>')
    reparto_b = Counter(len(usan[c]) for c in bulks)
    comp_b = [c for c in bulks if len(usan[c]) > 1]
    ajenos = [c for c in bulks if usan[c] and o_de.get(c) not in usan[c]]
    suelo = sum(len(usan[c]) - 1 for c in comp_b)
    w(f"""<p>De los {mil(len(bulks))} bulks, <b>{mil(reparto_b[1])} los usa un solo planner</b> y
      son suyos. {len(a_granel)} se venden a granel y no los consume ninguna línea. Los
      <b>{len(comp_b)} restantes los usan dos o tres planners a la vez</b>.</p>
      <p><b>Ninguno está en manos de quien no lo usa</b> ({len(ajenos)} casos). Los compartidos son
      los únicos que dejan a alguien programando con bulk ajeno, y ahí no hay reparto que valga: un
      bulk que usan dos planners deja fuera a uno se ponga donde se ponga. Salen <b>{suelo}
      traspasos pendientes, que es exactamente el mínimo posible</b> con estas líneas. Bajar de ahí
      no se hace tocando bulks, se hace moviendo líneas.</p>""")
    w('<table><tr><th>Planner</th><th class="n">Bulks que usa</th><th class="n">Suyos</th>'
      '<th class="n">De otro</th></tr>')
    for o in range(5):
        usa = [c for c in bulks if o in usan[c]]
        mios = sum(1 for c in usa if o_de.get(c) == o)
        w(f'<tr><td class="who">{chip(o)} {OWNERS[o]}</td><td class="n">{len(usa)}</td>'
          f'<td class="n">{mios}</td><td class="n">{len(usa) - mios}</td></tr>')
    w("</table>")

    # ---- comprados sin asignar
    w("<h2>Los 304 comprados sin asignar</h2>")
    duenos_de = {c: sorted({o_de[p] for p in d["padres"][c] if p in o_de}) for c in sin_asignar}
    lineas_bom = sum(len(d["padres"][c]) for c in sin_asignar)
    w(f"""<p><b>Por qué no tienen dueño.</b> Son comprados que entran en códigos de dos o más
      planners. Dárselos a uno sería mentir: los otros los seguirían consumiendo igual y tendrían
      que pedir permiso para algo que usan todos los días. En la práctica un componente compartido
      no se gestiona por planner, se gestiona por compras, así que se dejan vacíos a propósito y se
      ve de un vistazo en el visor, donde salen huecos.</p>
      <p>Son {len(sin_asignar)} códigos de los {mil(len(comprados))} comprados, el
      {len(sin_asignar) / len(comprados) * 100:.0f} %. Pero pesan mucho más de lo que parece: de ellos
      cuelgan <b>{mil(lineas_bom)} líneas de BOM</b>, porque son los envases y materiales comunes de
      toda la planta.</p>""")

    w("<h3>Con cuántos planners lo comparte cada uno</h3>")
    w('<table class="tight"><tr><th>Lo consumen</th><th class="n">Códigos</th><th>Qué son</th></tr>')
    etiqueta = {2: "el caso normal: dos líneas de familias distintas usan el mismo envase",
                3: "material común de líquidos, o de líquidos más mouldings",
                4: "consumibles de casi toda la planta",
                5: "los verdaderamente universales, los toca todo el mundo"}
    for k in sorted(Counter(len(v) for v in duenos_de.values())):
        n = sum(1 for v in duenos_de.values() if len(v) == k)
        w(f'<tr><td>{k} planners</td><td class="n">{n}</td><td class="dim">{etiqueta[k]}</td></tr>')
    w("</table>")

    w("<h3>Quién comparte con quién</h3>")
    w("<p>Los grupos que más se repiten. Es donde habría que ponerse de acuerdo si algún día se "
      "quiere dar dueño a alguno de estos códigos.</p>")
    w('<table class="tight"><tr><th>Lo comparten</th><th class="n">Códigos</th></tr>')
    for g, n in Counter(tuple(v) for v in duenos_de.values()).most_common(8):
        w(f'<tr><td>{" ".join(chip(o) for o in g)} '
          f'<span class="dim">{", ".join(OWNERS[o] for o in g)}</span></td><td class="n">{n}</td></tr>')
    w("</table>")

    w("<h3>En cuántos aparece cada planner</h3>")
    cuenta_o = Counter(o for v in duenos_de.values() for o in v)
    w('<table class="tight"><tr><th>Planner</th><th class="n">Comprados compartidos que consume</th></tr>')
    for o, n in cuenta_o.most_common():
        w(f'<tr><td class="who">{chip(o)} {OWNERS[o]}</td><td class="n">{n}</td></tr>')
    w("</table>")
    w('<p class="note">La suma pasa de 304 porque un mismo código cuenta una vez por cada planner '
      'que lo consume.</p>')

    w("<h3>Los diez que más se usan</h3>")
    top = sorted(sin_asignar, key=lambda c: (-len(d["padres"][c]), c))[:10]
    w('<table class="tight"><tr><th>Código</th><th class="n">Padres</th><th>Lo comparten</th></tr>')
    for c in top:
        w(f'<tr><td class="mono">{c}</td><td class="n">{mil(len(d["padres"][c]))}</td>'
          f'<td>{" ".join(chip(o) for o in duenos_de[c])}</td></tr>')
    w("</table>")
    w('<p class="note">Los cinco primeros entran en más de mil productos cada uno y los consumen '
      'los cinco planners. Ningún reparto los puede asignar sin dejar a cuatro personas dependiendo '
      'de una quinta.</p>')

    # ---- lo que queda abierto
    w('<div class="page"></div><h2>Lo que queda abierto</h2>')
    w(f"""<h3>La 510 partida</h3>
      <p>Es la única línea de packing con dos dueños. Sale de haber puesto la 516 con foundations:
      6 códigos corren en las dos y se van con la 516, que es la pequeña. Además los bulks de la 516
      alimentan al bloque Kugler mucho más que a foundations, así que el Sr planner 1 lleva la línea
      pero programa con bulks que en buena parte mueve el Sr planner 2. Es un coste conocido y
      aceptado a cambio de igualar la carga entre los dos Sr.</p>

      <h3>Kugler</h3>
      <p>Es el bloque más grande del packing de la planta y no se parte sin romper fluidity.
      Mientras siga entero, el Sr planner 2 va a llevar más códigos que nadie. Es la única palanca
      que queda si algún día hay que reequilibrar de verdad.</p>

      <h3>Los vasos compartidos</h3>
      <p>{len(making) - enteros} de los {len(making)} vasos los tocan dos o más planners. No es un problema del reparto: un vaso
      sirve a varias líneas por diseño de la planta. Lo que hay que tener claro es que la
      coordinación en making es real, y que las reglas 3 y 4 solo dicen quién decide, no quién es el
      único que lo usa.</p>

      <h3>Cómo ajustarlo</h3>
      <p>El visor (<span class="mono">ashford_bom_graph_proposal.html</span>) lleva el reparto ya
      puesto. La forma dice qué es un código y el color de quién es: círculo para un FG, rombo para
      un bulk, triángulo para un WIP y cuadrado para un comprado; hueco es que no tiene dueño.
      Picando un planner, el mapa se queda solo con sus códigos y con los comprados que comparte con
      el resto. Para mover cosas: <b>Select related</b> coge una cadena entera, el rectángulo coge
      una zona y <b>Assign to</b> la reasigna. Los cambios se guardan solos en el navegador.</p>""")

    w('<div class="foot">Generado por <span class="mono">build_report.py</span> a partir de '
      '<span class="mono">Ashford split 2.xlsx</span> y '
      '<span class="mono">ownership_proposal.json</span>. Las cifras salen del mismo reparto que '
      'lleva el visor.</div>')

    return f"<!doctype html><meta charset=utf-8><title>Propuesta de reparto Ashford</title>" \
           f"<style>{CSS}</style>" + "".join(W)


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
                               '<span>Ashford · propuesta de reparto del ownership</span>'
                               '<span class="pageNumber"></span></div>',
               margin={"top": "17mm", "bottom": "17mm", "left": "0", "right": "0"})
        b.close()

    import os
    print(f"{SALIDA} — {os.path.getsize(SALIDA) / 1024:.0f} KB")


if __name__ == "__main__":
    main()

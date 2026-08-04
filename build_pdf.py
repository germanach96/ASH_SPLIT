"""Genera el informe completo en PDF.

Uso:  python3 build_pdf.py

Escribe:
    Ashford ownership proposal.pdf

Junta las dos partes en un unico documento y no en dos PDF pegados: asi la
numeracion de pagina y el pie corren seguidos de principio a fin, cosa que no
pasa si se concatenan dos ficheros ya impresos.

    1. La propuesta            build_report.py
    2. Ficha por planner       build_planner_report.py

Las dos partes comparten hoja de estilos. La segunda va dentro de un
<div class="planner"> porque sus tablas llevan mas columnas y necesitan medio
punto menos de letra; el resto del diseno es el mismo.
"""

import build_planner_report as parte2
import build_report as parte1

SALIDA = "Ashford ownership proposal.pdf"
CHROMIUM = "/opt/pw-browsers/chromium-1194/chrome-linux/chrome"

# Lo que la ficha de planner anade sobre la hoja de la propuesta.
CSS_PLANNER = """
.planner { font-size: 9.5pt; }
.planner table { font-size: 8.4pt; }
.planner th { font-size: 7.2pt; padding-right: 2mm; }
.planner td { padding: 1.1mm 2mm 1.1mm 0; }
.planner th.n, .planner td.n { padding-left: 3mm; padding-right: 2.5mm; }
.planner th.n:last-child, .planner td.n:last-child { padding-right: 0; }
.planner h2 { font-size: 15pt; margin: 0 0 1mm; padding-bottom: 0; border-bottom: 0; }
.planner h3 { font-size: 9.5pt; margin: 5mm 0 1.5mm; }
.planner .chip { font-size: 7pt; padding: .4mm 1.6mm; }
.planner .mono { font-size: 7.8pt; }
.planner .note { font-size: 7.8pt; }
.planner .card { padding: 2mm 2.4mm; }
.planner .card .k { font-size: 15pt; }
.planner .card .v { font-size: 7.2pt; text-transform: uppercase; letter-spacing: .05em; }
.planner .cards { gap: 2mm; }

.head { border-top: 3pt solid; padding-top: 2.5mm; margin-bottom: 3mm; }
.head .sub { margin-bottom: .5mm; }
.head .lines { color: #6b737c; font-size: 8.6pt; margin-top: .8mm; }
.shot { margin: 0 0 3mm; border: .5pt solid #d3d8dd; border-radius: 1.4mm; overflow: hidden; }
.shot img { display: block; width: 100%; }
.bar { height: 3.4mm; background: #eef1f3; border-radius: 1mm; overflow: hidden; display: flex; }
.bar span { display: block; height: 100%; }
"""


def main():
    d1 = parte1.cargar()
    d2 = parte2.cargar()
    print("capturando el visor:")
    shots = parte2.capturas()

    doc = ("<!doctype html><meta charset=utf-8><title>Ashford ownership proposal</title>"
           f"<style>{parte1.CSS}{CSS_PLANNER}</style>"
           + parte1.construir(d1)
           + '<div class="page"></div>'      # la segunda parte abre pagina
           + parte2.construir(d2, shots))
    tmp = "/tmp/_informe.html"
    open(tmp, "w", encoding="utf-8").write(doc)

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM)
        pg = b.new_page()
        pg.goto("file://" + tmp)
        pg.pdf(path=SALIDA, format="A4", print_background=True,
               display_header_footer=True, header_template="<div></div>",
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

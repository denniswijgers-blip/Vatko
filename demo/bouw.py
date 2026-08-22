import io, os

HIER = os.path.dirname(os.path.abspath(__file__))

# De volgorde is geen smaakkwestie. Alles wordt aan elkaar geplakt tot
# één bestand, dus wat onderaan staat mag rekenen op wat erboven staat.
# Vandaar de nummers in de mapnamen: dat IS de bouwvolgorde.
#
#   1-kern      rekenen, zonder kennis van schermen of gegevens
#   2-logica    boeken, meten, uitgaand, optimaliseren
#   3-import    klantbestanden inlezen
#   4-schermen  wat de gebruiker ziet
#   5-schil     menu, klikken, toetsen - en als allerlaatste de start
#
# Alleen de laatste twee regels van 5-schil/toetsen.js voeren bij het
# laden echt iets uit. Al het andere zijn definities, dus binnen een map
# maakt de volgorde niet uit.
BRON = [
    ("1-kern",     ["kern.js", "grafiek.js"]),
    ("2-logica",   ["data.js", "gebruikers.js", "app.js", "uitgaand.js",
                    "optimalisatie.js", "simulatie.js", "scan.js"]),
    ("3-import",   ["import.js"]),
    ("4-schermen", ["ui.js", "ui2.js", "ui3.js", "ui4.js", "ui5.js",
                    "ui6.js", "ui7.js"]),
    ("5-schil",    ["menu.js", "schil.js", "tekenen.js", "klikken.js",
                    "toetsen.js"]),
]

def lees(*delen):
    pad = os.path.join(HIER, *delen)
    if not os.path.exists(pad):
        raise SystemExit(f"Bestand ontbreekt: {os.path.join(*delen)}\n"
                         f"Staat het ergens anders, of mist er een naam in BRON?")
    return io.open(pad, encoding="utf-8").read()

css = lees("stijl.css")
js  = "\n".join(lees("bron", map_, bestand)
                for map_, bestanden in BRON for bestand in bestanden)

FONTS = ('<link rel="preconnect" href="https://fonts.googleapis.com">\n'
         '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
         '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=Archivo:wdth,wght@62.5..125,400..700&'
         'family=IBM+Plex+Mono:wght@400;500&display=swap">')

BODY = """<div id="nav"></div>
<main>
  <header id="balkboven"></header>
  <div id="inhoud"></div>
</main>
<div id="palet" hidden>
  <div class="palet-doos" role="dialog" aria-label="Snel zoeken">
    <div class="palet-invoer">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
           stroke-linecap="round" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>
      <input id="paletInvoer" autocomplete="off" spellcheck="false"
             placeholder="Zoek een artikel, locatie, order of scherm\u2026">
      <kbd>esc</kbd>
    </div>
    <div id="paletUit" class="palet-uit"></div>
    <div class="palet-voet">
      <span><kbd>&uarr;</kbd><kbd>&darr;</kbd> kiezen</span>
      <span><kbd>&crarr;</kbd> openen</span>
      <span><kbd>esc</kbd> sluiten</span>
    </div>
  </div>
</div>
<div id="balk" class="vlag" hidden></div>"""

# --- versie voor de Artifact (zonder doctype/html/head/body) -----------
artifact = f"""<title>Vakto Warehouse</title>
{FONTS}
<style>
{css}</style>
{BODY}
<script>
{js}</script>"""
io.open(os.path.join(HIER, "artifact.html"), "w", encoding="utf-8").write(artifact)

# --- losstaande versie voor offline gebruik ---------------------------
los = f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vakto Warehouse</title>
{FONTS}
<style>
{css}</style>
</head>
<body>
{BODY}
<script>
{js}</script>
</body>
</html>"""
io.open(os.path.join(HIER, "vakto-demo.html"), "w", encoding="utf-8").write(los)

print("artifact.html   ", len(artifact)//1024, "kB")
print("vakto-demo.html ", len(los)//1024, "kB")

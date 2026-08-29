"""Locatie-etiketten met een streepjescode (R-SCAN-08).

Code 39, want die leest elke handscanner zonder dat je er iets voor hoeft
in te stellen. Bij een klant met onbekende apparatuur is dat meer waard
dan de dichtheid van een modernere code.

Dit bestand raakt geen database en weet niets van schermen: er gaat tekst
in en er komt een tekening uit. Dat is met opzet, want dit is het soort
code waar een fout niet opvalt — een etiket dat er goed uitziet en niet
scant, merk je pas als er iemand met een scanner voor de stelling staat.
Daarom staat de codering hier, met een test die de streepjes natelt.
"""

from __future__ import annotations

from html import escape

# Elk teken is negen strepen: vijf zwart en vier wit, om en om, waarvan
# er precies drie breed zijn. Vandaar de naam "3 van 9".
C39: dict[str, str] = {
    "0": "nnnwwnwnn", "1": "wnnwnnnnw", "2": "nnwwnnnnw", "3": "wnwwnnnnn",
    "4": "nnnwwnnnw", "5": "wnnwwnnnn", "6": "nnwwwnnnn", "7": "nnnwnnwnw",
    "8": "wnnwnnwnn", "9": "nnwwnnwnn",
    "A": "wnnnnwnnw", "B": "nnwnnwnnw", "C": "wnwnnwnnn", "D": "nnnnwwnnw",
    "E": "wnnnwwnnn", "F": "nnwnwwnnn", "G": "nnnnnwwnw", "H": "wnnnnwwnn",
    "I": "nnwnnwwnn", "J": "nnnnwwwnn", "K": "wnnnnnnww", "L": "nnwnnnnww",
    "M": "wnwnnnnwn", "N": "nnnnwnnww", "O": "wnnnwnnwn", "P": "nnwnwnnwn",
    "Q": "nnnnnnwww", "R": "wnnnnnwwn", "S": "nnwnnnwwn", "T": "nnnnwnwwn",
    "U": "wwnnnnnnw", "V": "nwwnnnnnw", "W": "wwwnnnnnn", "X": "nwnnwnnnw",
    "Y": "wwnnwnnnn", "Z": "nwwnwnnnn",
    "-": "nwnnnnwnw", ".": "wwnnnnwnn", " ": "nwwnnnwnn", "*": "nwnnwnwnn",
}

SMAL, BREED = 1, 3          # R-SCAN-08. De verhouding is 1 : 3.
RUSTZONE = 10               # wit aan weerskanten, anders vindt hij het begin niet
HOOGTE = 30


def schoon(tekst) -> str:
    """Wat er van een code overblijft dat Code 39 aankan.

    Alles buiten de tekenset wordt een streepje. Weigeren zou netter
    lijken, maar dan drukt hij voor een locatie met een rare code
    helemaal geen etiket af — en dan staat er straks één vak zonder
    label, precies het vak waar niemand aan denkt.
    """
    return "".join(c if c in C39 and c != "*" else "-"
                   for c in str(tekst).upper())


def strepen(tekst) -> list[tuple[int, bool]]:
    """De streepjes als (breedte, zwart), inclusief de sterren eromheen.

    Los van het tekenen, zodat een test de codering kan natellen zonder
    door SVG heen te hoeven lezen.
    """
    uit: list[tuple[int, bool]] = []
    for teken in "*" + schoon(tekst) + "*":
        patroon = C39[teken]
        for i, breedte in enumerate(patroon):
            uit.append((BREED if breedte == "w" else SMAL, i % 2 == 0))
        uit.append((SMAL, False))       # scheiding tussen twee tekens
    return uit[:-1]                     # behalve na de laatste


def svg(tekst) -> str:
    """De streepjescode als SVG.

    Als SVG en niet als reeks blokjes: een streepjescode moet zijn
    breedteverhoudingen exact houden. Wordt hij ergens uitgerekt of
    samengedrukt, dan piept de scanner en denkt de klant dat het systeem
    niet werkt.
    """
    x = RUSTZONE
    blokken = []
    for breedte, zwart in strepen(tekst):
        if zwart:
            blokken.append(f'<rect x="{x}" y="0" width="{breedte}" '
                           f'height="{HOOGTE}"/>')
        x += breedte
    breed = x + RUSTZONE
    return (f'<svg class="c39" viewBox="0 0 {breed} {HOOGTE}" '
            f'preserveAspectRatio="none" width="100%" height="34" role="img" '
            f'aria-label="streepjescode {escape(str(tekst))}">'
            f'<rect x="0" y="0" width="{breed}" height="{HOOGTE}" '
            f'fill="#fff"/><g fill="#000">{"".join(blokken)}</g></svg>')

"""Instellingen — alles wat per klant verschilt (R-BASIS-04).

Deze klasse weet niets van een database. Je vult hem met een dict, en
straks laadt de serverlaag die dict uit de tabel `setting`. Zo blijft de
rekenkern testbaar zonder PostgreSQL.
"""

from __future__ import annotations
from typing import Mapping

# De standaardwaarden. Gelijk aan hoofdstuk 14 van de specificatie en aan
# seed_config.sql — die twee moeten altijd hetzelfde zeggen.
STANDAARD: dict[str, str] = {
    "putaway.fill_factor":          "0.85",
    "putaway.prefer_smallest_fit":  "true",
    "putaway.te_ruim_onder":        "0.20",
    "drift.alert_threshold_pct":    "15",
    "drift.remeasure_after_days":   "180",
    "opt.samenvoegen":              "true",
    "opt.dekking_dagen":            "3",
    "opt.hardloper_per_dag":        "6",
    "opt.venster_dagen":            "30",
    "opt.max_open_teltaken":        "12",
    "opt.drempel_afwijking_pct":    "60",
    "opstart.onbekend_aanmaken":    "false",
    "uit.max_colli_gewicht_g":      "25000",
    "ui.rows_per_page":             "60",
    "sessie.duur_uren":             "12",
    "inlog.max_pogingen":           "10",
    "inlog.badge_voor_scanner":     "true",
}

# R-INST-01. Wat voor soort waarde er in mag, en tussen welke grenzen.
#
# Dit staat hier en niet in de database, om dezelfde reden als de rest van
# de rekenkern: een waarde toetsen is rekenwerk en moet zonder PostgreSQL
# na te testen zijn. De database bewaakt dat de sleutel bestaat; Python
# bewaakt dat de waarde ergens op slaat.
#
# De ondergrenzen zijn geen willekeur. Een vulfactor boven 1 zegt dat er
# meer in een vak gaat dan erin past; een telinterval van nul dagen zet
# elke locatie elke dag op de lijst. Zulke waarden vallen niet meteen om
# — ze geven maandenlang stilletjes onzin, en dat is erger.
SOORT: dict[str, tuple[str, float | None, float | None]] = {
    #  sleutel                      soort     min      max
    "putaway.fill_factor":         ("komma",  0.1,     1.0),
    "putaway.prefer_smallest_fit": ("janee",  None,    None),
    "putaway.te_ruim_onder":       ("komma",  0.0,     1.0),
    "drift.alert_threshold_pct":   ("komma",  1,       100),
    "drift.remeasure_after_days":  ("geheel", 1,       3650),
    "opt.samenvoegen":             ("janee",  None,    None),
    "opt.dekking_dagen":           ("komma",  0.5,     90),
    "opt.hardloper_per_dag":       ("komma",  0.1,     10000),
    "opt.venster_dagen":           ("geheel", 1,       365),
    "opt.max_open_teltaken":       ("geheel", 1,       500),
    "opt.drempel_afwijking_pct":   ("komma",  1,       500),
    "opstart.onbekend_aanmaken":   ("janee",  None,    None),
    "uit.max_colli_gewicht_g":     ("geheel", 100,     2_000_000),
    "ui.rows_per_page":            ("geheel", 5,       5000),
    "sessie.duur_uren":            ("geheel", 1,       168),
    "inlog.max_pogingen":          ("geheel", 3,       1000),
    "inlog.badge_voor_scanner":    ("janee",  None,    None),
}

SOORTNAAM = {"komma": "een getal", "geheel": "een heel getal",
             "janee": "ja of nee"}


def toets(sleutel: str, waarde: str) -> str | None:
    """R-INST-01. Geeft terug wat er mis is, of None als het goed is.

    Bewaren en dan bij de eerstvolgende berekening omvallen is het
    slechtste van twee werelden: de fout komt dan boven water op een
    moment dat niemand nog weet dat er iets is gewijzigd.
    """
    if sleutel not in SOORT:
        return (f"{sleutel} is geen bestaande instelling. Een sleutel die de "
                f"code niet kent doet niets.")
    soort, laag, hoog = SOORT[sleutel]
    tekst = (waarde or "").strip()

    if soort == "janee":
        if tekst.lower() not in ("true", "false"):
            return "Vul true of false in."
        return None

    try:
        getal = float(tekst.replace(",", "."))
    except ValueError:
        return f"Vul {SOORTNAAM[soort]} in."
    if soort == "geheel" and getal != int(getal):
        return "Vul een heel getal in, zonder komma."
    if laag is not None and getal < laag:
        return f"Dit moet {_net(laag)} of hoger zijn."
    if hoog is not None and getal > hoog:
        return f"Dit moet {_net(hoog)} of lager zijn."
    return None


def _net(n) -> str:
    return str(int(n)) if float(n) == int(n) else str(n)


def opgeschoond(sleutel: str, waarde: str) -> str:
    """De waarde zoals hij in de kolom hoort te staan.

    Een komma wordt een punt, en `TRUE` wordt `true`. Anders staat er na
    één keer opslaan `0,85` in de tabel en valt `float()` erover.
    """
    tekst = (waarde or "").strip()
    soort, _laag, _hoog = SOORT.get(sleutel, ("tekst", None, None))
    if soort == "janee":
        return tekst.lower()
    if soort in ("komma", "geheel"):
        getal = float(tekst.replace(",", "."))
        return str(int(getal)) if soort == "geheel" else _net(getal)
    return tekst


# De punten van het inslagvoorstel (R-INS-04).
WEGING: dict[str, int] = {
    "benutting":            500,
    "zelfde_artikel":       400,
    "picklocatie_aanvul":   600,
    "hele_partij_past":     200,
    "deelvulling_max":      150,
    "te_ruim_straf":       -550,
}


class Instellingen:
    """Leest instellingen als tekst en zet ze om bij het opvragen.

    Waarom als tekst opslaan? Omdat een instellingentabel met kolommen
    voor int, float, bool en tekst na drie klanten onwerkbaar is. Eén
    kolom, omzetten bij het lezen.
    """

    def __init__(self, waarden: Mapping[str, str] | None = None,
                 weging: Mapping[str, int] | None = None) -> None:
        self._w: dict[str, str] = dict(STANDAARD)
        if waarden:
            self._w.update(waarden)
        self.weging: dict[str, int] = dict(WEGING)
        if weging:
            self.weging.update(weging)

    def tekst(self, sleutel: str) -> str:
        try:
            return self._w[sleutel]
        except KeyError:
            raise KeyError(
                f"Onbekende instelling {sleutel!r}. "
                f"Zet hem in STANDAARD én in seed_config.sql, anders lopen "
                f"de twee uit elkaar."
            ) from None

    def getal(self, sleutel: str) -> float:
        return float(self.tekst(sleutel))

    def geheel(self, sleutel: str) -> int:
        return int(float(self.tekst(sleutel)))

    def aan(self, sleutel: str) -> bool:
        return self.tekst(sleutel).strip().lower() == "true"

    def zet(self, sleutel: str, waarde) -> None:
        self._w[sleutel] = "true" if waarde is True else \
                           "false" if waarde is False else str(waarde)

    def __repr__(self) -> str:  # pragma: no cover
        return f"Instellingen({len(self._w)} sleutels)"

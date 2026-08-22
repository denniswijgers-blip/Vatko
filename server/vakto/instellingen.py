"""Instellingen — alles wat per klant verschilt (R-BASIS-04).

Deze klasse weet niets van een database. Je vult hem met een dict, en
straks laadt de serverlaag die dict uit de tabel `setting`. Zo blijft de
rekenkern testbaar zonder PostgreSQL.
"""

from __future__ import annotations
from typing import Mapping

# De standaardwaarden. Gelijk aan hoofdstuk 12 van de specificatie en aan
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
}

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

"""Afronden zoals JavaScript het doet.

Dit lijkt muggenzifterij en is het niet. Python's ingebouwde round()
rondt 112,5 af naar 112 (bankiersafronding: naar het dichtstbijzijnde
even getal), JavaScript rondt naar 113. In het scoren van een
inslagvoorstel komt precies zo'n half getal voor: de deelvullingsterm
150 x (30/40) is exact 112,5.

Zonder deze functie geeft de Python-versie een score van 437 waar de
browserversie 438 geeft, en dan zoek je een avond naar een fout die er
niet is. Testgeval T-07 valt hierop om.
"""

import math


def rond(x: float) -> int:
    """Rond af naar het dichtstbijzijnde gehele getal, halve naar boven.

    Gelijk aan Math.round() in JavaScript, ook voor negatieve getallen:
    rond(-506.5) == -506, niet -507.
    """
    return math.floor(x + 0.5)

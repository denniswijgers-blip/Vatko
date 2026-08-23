/* Leest de meldingen en overgangen van de scanmodus af uit de DRAAIENDE
   browserversie, zodat de Python-tests van stap 8 pariteit bewijzen in
   plaats van een mening te herhalen (afspraak 2).

   De teksten doen er hier meer toe dan gewoonlijk: dit is het enige
   scherm dat iemand met handschoenen aan gebruikt, en "Verkeerde
   locatie. Je staat bij X, je moet naar Y." is het verschil tussen
   doorlopen en stilstaan.

       node test/scan-vectoren.mjs

   Draait de browser niet vanzelf, zet dan CHROME op het pad van je
   chromium. */
import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const DEMO = 'file://' + join(dirname(fileURLToPath(import.meta.url)), '..', 'vakto-demo.html');
const opties = process.env.CHROME ? { executablePath: process.env.CHROME } : {};

const b = await chromium.launch(opties);
const p = await b.newPage();
await p.goto(DEMO);
await p.waitForSelector('#inhoud h1');

const uit = await p.evaluate(() => {
  /* De echte demodatabase, met een order die vrijgegeven is. Zo staan er
     pickregels klaar en hoeven we niets na te bouwen. */
  const order = DB.orders.find(o => o.status === 'NIEUW')
             || maakOrder(DB, Date.now());
  reserveer(DB, order);
  geefVrij(DB, order);

  scanStart('PICKEN');
  const regel = scan.regel;
  const doelLoc = DB.locaties[regel.locationId];
  const doelArt = DB.artikelen[regel.productId];
  const andereLoc = DB.locaties.find(l => l.id !== doelLoc.id && l.actief);
  const andereArt = DB.artikelen.find(a => a.id !== doelArt.id);

  const stap = (code) => {
    verwerkScan(code);
    return { stap: scan.stap, bericht: scan.bericht, soort: scan.berichtSoort };
  };

  const picken = {
    beginstap: scan.stap,
    artikelTeVroeg: stap(doelArt.barcode || doelArt.sku),
    onbekend:       stap('87999999999'),
    verkeerdeLoc:   stap(andereLoc.code),
    goedeLoc:       stap(doelLoc.code),
    verkeerdArt:    stap(andereArt.barcode || andereArt.sku),
    goedArt:        stap(doelArt.barcode || doelArt.sku),
    voorgesteld:    scan.aantal,
    open:           regel.qty - regel.gepickt,
  };

  /* volledig afmelden */
  const volledig = (() => {
    const n = scan.aantal;
    scanBevestig(n);
    return { bericht: scan.bericht, soort: scan.berichtSoort, aantal: n };
  })();

  /* manco: loop de volgende regel af en meld er één te weinig */
  const manco = (() => {
    const r = scan.regel;
    if (!r) return null;
    verwerkScan(DB.locaties[r.locationId].code);
    verwerkScan(DB.artikelen[r.productId].barcode || DB.artikelen[r.productId].sku);
    const gevraagd = scan.aantal;
    scanBevestig(Math.max(0, gevraagd - 1));
    return { bericht: scan.bericht, soort: scan.berichtSoort, gevraagd };
  })();

  /* overslaan zet de regel achteraan, het is geen manco */
  const overslaan = (() => {
    const job = scan.job;
    if (!job || !scan.regel) return null;
    const voor = job.regels.map(r => r.nr);
    const nr = scan.regel.nr;
    scanOverslaan();
    return { bericht: scan.bericht, voor, na: job.regels.map(r => r.nr), overgeslagen: nr };
  })();

  /* --- tellen ------------------------------------------------------- */
  scanStart('TELLEN');
  const telLoc = DB.voorraad.find(s => s.qty > 0);
  const tLoc = DB.locaties[telLoc.locationId], tArt = DB.artikelen[telLoc.productId];
  const tellen = {
    beginstap: scan.stap,
    artikelTeVroeg: stap(tArt.barcode || tArt.sku),
    locatie:        stap(tLoc.code),
    artikel:        stap(tArt.barcode || tArt.sku),
    voorgesteld:    scan.aantal,
    werkelijk:      telLoc.qty,
  };
  const telVerschil = (() => {
    scanBevestig(telLoc.qty - 2);
    return { bericht: scan.bericht, soort: scan.berichtSoort };
  })();

  /* --- inslag ------------------------------------------------------- */
  scanStart('INSLAG');
  const gemeten = DB.artikelen.find(a => DB.artikelNu(a.id).L);
  const inslag = {
    beginstap: scan.stap,
    locatieTeVroeg: stap(tLoc.code),
    artikel:        stap(gemeten.barcode || gemeten.sku),
    voorgesteld:    scan.aantal,
  };
  scanBevestig(6);
  const naAantal = { stap: scan.stap, bericht: scan.bericht };
  const voorstel = voorstelInslag(DB, gemeten.id, 6, 4);
  const verkeerdVak = DB.locaties.find(l => l.actief && !voorstel.some(v => v.loc.id === l.id));
  const inslagFout = verkeerdVak ? stap(verkeerdVak.code) : null;
  const inslagGoed = stap(voorstel[0].loc.code);

  /* --- een badge werkt altijd --------------------------------------- */
  scanStart('PICKEN');
  const badge = DB.gebruikers[1];
  const metBadge = stap(badge.badge);

  return { picken, volledig, manco, overslaan, tellen, telVerschil,
           inslag, naAantal, inslagFout, inslagGoed,
           badge: { ...metBadge, naam: badge.naam } };
});

console.log(JSON.stringify(uit, null, 2));
await b.close();

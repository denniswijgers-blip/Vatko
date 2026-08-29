/* Leest de uitkomsten van de zelfcontrole en de optimalisatie af uit de
   DRAAIENDE browserversie, zodat de Python-tests van stap 6 pariteit
   bewijzen in plaats van een mening te herhalen (afspraak 2).

   Zelfde opzet als meet-vectoren.mjs en uitgaand-vectoren.mjs. Bouw
   eerst de demo (python3 bouw.py) en draai dan:

       node test/zelfcontrole-vectoren.mjs

   De uitvoer is JSON. Wat eruit komt staat in
   server/tests/test_zelfcontrole.py en test_optimalisatie.py, met de
   naam van het scenario erbij.

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
  const DAG = 86400000;

  /* --- een klein magazijn dat je in je hoofd kunt houden -------------
     01-01-1  picklocatie 300x400x220, 12 kg
     02-01-1  bulk        1200x800x1500, 900 kg
     03-01-1  bulk        1200x800x1500, 900 kg
     Artikel 1: 120x90x45 mm, 180 g. Daar passen er 30 van op 01-01-1. */
  function nieuweDb(opties = {}) {
    /* Let op: locaties en artikelen zijn ARRAYS met de id als index,
       precies zoals data.js ze opbouwt. voorstelInslag loopt eroverheen. */
    const db = {
      groepen: [], artikelen: [], locaties: [], voorraad: [], taken: [],
      orders: [], boekingen: [], drift: [], log: [], reserveringen: [],
      pickjobs: [], _laatste: {}, metingen: [],
      artikelNu(id) { const a = this.artikelen[id], m = this._laatste[id];
        return m ? { ...a, L: m.L, W: m.W, H: m.H, G: m.G } : { ...a }; },
    };
    db.groepen.push({ id: 0, naam: 'Testgroep', telint: opties.telint ?? 180 });
    db.artikelen.push({ id: 0, sku: 'ZC-1', oms: 'Testartikel', groepId: 0,
                        minQty: opties.minQty ?? null, maxQty: opties.maxQty ?? null,
                        stapelbaar: 1, vraag: 1 });
    db.metingen.push({ productId: 0, at: Date.now() - 40 * DAG, bron: 'RECEIPT',
                       L: opties.L ?? 120, W: opties.W ?? 90, H: opties.H ?? 45,
                       G: opties.G ?? 180 });
    db._laatste[0] = db.metingen[0];
    db.locaties.push({ id: 0, code: '01-01-1', typeId: 0, zoneId: 0, actief: 1,
                       aisle: 1, bay: 1, level: 1, seq: 1000110,
                       L: 300, W: 400, H: 220, maxG: 12000,
                       geteldOp: opties.geteldOp ?? null });
    db.locaties.push({ id: 1, code: '02-01-1', typeId: 1, zoneId: 0, actief: 1,
                       aisle: 2, bay: 1, level: 1, seq: 2999810,
                       L: 1200, W: 800, H: 1500, maxG: 900000, geteldOp: Date.now() });
    db.locaties.push({ id: 2, code: '03-01-1', typeId: 1, zoneId: 0, actief: 1,
                       aisle: 3, bay: 1, level: 1, seq: 3000110,
                       L: 1200, W: 800, H: 1500, maxG: 900000, geteldOp: Date.now() });
    for (const [loc, qty] of (opties.voorraad || []))
      db.voorraad.push({ productId: 0, locationId: loc, qty, res: 0 });
    return db;
  }

  const taakBeeld = t => ({ soort: t.soort, prio: t.prio, van: t.van, naar: t.naar,
                            qty: t.qty, aanleiding: t.aanleiding, reden: t.reden,
                            status: t.status, vervallenReden: t.vervallenReden ?? null });

  /* --- 1. R-ZC-04 / R-OPT-03: aanvullen vanuit de drempel ----------- */
  const db1 = nieuweDb({ minQty: 20, maxQty: 40, voorraad: [[0, 5], [1, 500]] });
  maakAanvultaken(db1);
  const drempel = db1.taken.map(taakBeeld);

  /* --- 2. T-17: bijvullen tot boven de drempel laat de taak vervallen */
  db1.voorraad.find(s => s.locationId === 0).qty = 25;
  const r2 = { gesloten: 0, aangemaakt: 0, vervallen: 0, regels: [] };
  hertoets(db1);
  const t17 = db1.taken.map(taakBeeld);

  /* --- 3. R-OPT-03: twee aanleidingen, één taak -------------------- */
  const db3 = nieuweDb({ minQty: 20, maxQty: 40, voorraad: [[0, 5], [1, 500]] });
  db3.orders.push({ id: 0, nummer: 'ORD-1', status: 'NIEUW', prio: 3, regels: [
    { idx: 0, productId: 0, besteld: 28, gereserveerd: 0, gepickt: 0, manco: 0 }] });
  const r3 = { gesloten: 0, aangemaakt: 0, vervallen: 0, regels: [] };
  optVraag(db3, r3, bezetPerLocatie(db3));
  maakAanvultaken(db3);
  const samenEen = db3.taken.map(taakBeeld);

  /* --- 4. R-OPT-01: samenvoegen ------------------------------------ */
  const db4 = nieuweDb({ voorraad: [[0, 12], [1, 8]] });
  const r4 = { gesloten: 0, aangemaakt: 0, vervallen: 0, regels: [] };
  optSamenvoegen(db4, r4);
  const samenvoegen = db4.taken.map(taakBeeld);

  /* nooit een picklocatie leeghalen naar bulk: 40 past niet op 01-01-1 */
  const db4b = nieuweDb({ voorraad: [[0, 25], [1, 40]] });
  optSamenvoegen(db4b, { gesloten: 0, aangemaakt: 0, vervallen: 0, regels: [] });
  const samenvoegenPick = db4b.taken.map(taakBeeld);

  /* --- 5. R-OPT-02: vraagsnelheid ---------------------------------- */
  const db5 = nieuweDb({ voorraad: [[0, 10]] });
  const nu = Date.now();
  db5.boekingen.push({ at: nu - 1 * DAG, soort: 'PICK', productId: 0, qty: 30 });
  db5.boekingen.push({ at: nu - 10 * DAG, soort: 'PICK', productId: 0, qty: 60 });
  db5.boekingen.push({ at: nu - 40 * DAG, soort: 'PICK', productId: 0, qty: 900 });
  db5.boekingen.push({ at: nu - 2 * DAG, soort: 'MOVE', productId: 0, qty: 500 });
  const snel = [...pickSnelheden(db5)].map(([pid, v]) => ({ pid, perDag: v }));

  /* --- 6. R-OPT-04: telplan ---------------------------------------- */
  const db6 = nieuweDb({ telint: 30, geteldOp: nu - 100 * DAG, voorraad: [[0, 10]] });
  const r6 = { gesloten: 0, aangemaakt: 0, vervallen: 0, regels: [] };
  optTellen(db6, r6);
  const telplan = db6.taken.map(taakBeeld);

  /* --- 7. R-OPT-05: drempeladvies ---------------------------------- */
  const db7 = nieuweDb({ minQty: 4, maxQty: 8, voorraad: [[0, 10]] });
  db7.boekingen.push({ at: nu - 1 * DAG, soort: 'PICK', productId: 0, qty: 300 });
  const advies = optDrempelAdvies(db7);

  /* --- 8. T-16: melding gaat vanzelf dicht ------------------------- */
  /* Het artikel wordt groter gemeten: er passen er nog 27 op 01-01-1 in
     plaats van 30, en er liggen er 30. */
  const db8 = nieuweDb({ voorraad: [[0, 30], [1, 100]] });
  db8.metingen.push({ productId: 0, at: nu, bron: 'RECEIPT', L: 140, W: 100, H: 50, G: 210 });
  db8._laatste[0] = db8.metingen[db8.metingen.length - 1];
  db8.drift.push({ id: 0, productId: 0, at: nu, dVol: 44, dGew: 16.7,
                   status: 'OPEN', gevolg: '' });
  hertoets(db8);
  const naMeting = { melding: db8.drift[0].status, gevolg: db8.drift[0].gevolg,
                     taken: db8.taken.map(taakBeeld) };

  /* de overlooptaak uitvoeren: 3 st van 01-01-1 naar 02-01-1 */
  const over = db8.taken.find(t => t.soort === 'OVERLOOP');
  if (over) boek(db8, 0, over.qty, 'MOVE', over.van, over.naar, null, 'Taak');
  if (over) over.status = 'DONE';
  hertoets(db8);
  const naUitvoeren = { melding: db8.drift[0].status, gevolg: db8.drift[0].gevolg,
                        ligt: db8.voorraad.find(s => s.locationId === 0).qty };

  /* --- 9. R-OPT-06: hardloper die alleen in bulk ligt -------------- */
  const db9 = nieuweDb({ voorraad: [[1, 500]] });
  db9.boekingen.push({ at: nu - 1 * DAG, soort: 'PICK', productId: 0, qty: 360 });
  optZonderPicklocatie(db9);
  const zonderPick = db9.zonderPick;

  return { drempel, t17, samenEen, samenvoegen, samenvoegenPick, snel,
           telplan, advies, naMeting, naUitvoeren, zonderPick };
});

console.log(JSON.stringify(uit, null, 2));
await b.close();

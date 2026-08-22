/* Leest de uitkomsten van de uitgaande stroom af uit de DRAAIENDE
   browserversie, zodat de Python-tests van stap 5 pariteit bewijzen in
   plaats van een mening te herhalen (afspraak 2).

   Zelfde opzet als meet-vectoren.mjs: bouw eerst de demo
   (python3 bouw.py) en draai dan:

       node test/uitgaand-vectoren.mjs

   De uitvoer is JSON. Wat eruit komt staat in server/tests/test_uitgaand.py,
   met de naam van het scenario erbij.

   Draait de browser niet vanzelf, zet dan CHROME op het pad van je
   chromium — op een Mac met een verse `npm install playwright` is dat
   niet nodig. */
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
  /* --- R-UIT-03: de looproute, zoals data.js hem uitrekent ---------- */
  const seq = (gang, vak, niveau) => {
    const vakPos = gang % 2 ? vak : 9999 - vak;
    return gang * 1e6 + vakPos * 100 + niveau * 10;
  };
  const looproute = [
    [1, 1, 1], [1, 2, 1], [1, 1, 2],      // oneven gang: vak telt op
    [2, 1, 1], [2, 2, 1],                 // even gang: slangroute
    [3, 4, 3], [4, 4, 3],
  ].map(([g, v, n]) => ({ gang: g, vak: v, niveau: n, seq: seq(g, v, n) }));

  /* --- een kaal magazijntje voor reserveren en picken --------------- */
  function nieuweDb() {
    const db = {
      artikelen: [], locaties: {}, voorraad: [], reserveringen: [],
      orders: [], pickjobs: [], taken: [], log: [], boekingen: [],
      artikelNu(id) { return this.artikelen[id]; },
    };
    db.artikelen[1] = { id: 1, sku: 'UIT-1', L: 120, W: 90, H: 45, G: 180, stapelbaar: 1 };
    /* picklocatie vooraan, twee bulkvakken, en een geblokkeerd QC-vak */
    db.locaties[1] = { id: 1, code: 'U-01-1', typeId: 0, zoneId: 1, actief: 1, seq: seq(1, 1, 1) };
    db.locaties[2] = { id: 2, code: 'U-02-1', typeId: 1, zoneId: 1, actief: 1, seq: seq(2, 1, 1) };
    db.locaties[3] = { id: 3, code: 'U-03-1', typeId: 1, zoneId: 1, actief: 1, seq: seq(3, 1, 1) };
    db.locaties[4] = { id: 4, code: 'U-QC-1', typeId: 3, zoneId: 1, actief: 1, seq: seq(9, 1, 1) };
    db.voorraad.push({ productId: 1, locationId: 1, qty: 10, res: 0 });
    db.voorraad.push({ productId: 1, locationId: 2, qty: 20, res: 0 });
    db.voorraad.push({ productId: 1, locationId: 3, qty: 20, res: 0 });
    db.voorraad.push({ productId: 1, locationId: 4, qty: 50, res: 0 });
    return db;
  }

  function order(db, nummer, besteld) {
    const o = {
      id: db.orders.length, nummer, klant: 'Testklant', prio: 3,
      status: 'NIEUW', at: Date.now(), colli: null, gewicht: null, track: null,
      regels: [{ idx: 0, productId: 1, besteld, gereserveerd: 0, gepickt: 0,
                 verzonden: 0, manco: 0 }],
    };
    db.orders.push(o);
    return o;
  }

  const toewijzingen = (db, o) => db.reserveringen
    .filter(r => r.orderId === o.id)
    .map(r => ({ locatie: db.locaties[r.locationId].code, qty: r.qty }));

  /* --- scenario 1: kandidaatvolgorde en verdeling ------------------- */
  const db1 = nieuweDb();
  const o1 = order(db1, 'ORD-910', 35);
  const status1 = reserveer(db1, o1);

  /* --- scenario 2: T-14, twee orders die samen te veel vragen ------- */
  const o2 = order(db1, 'ORD-911', 40);
  const status2 = reserveer(db1, o2);
  const status2b = reserveer(db1, o2);          // nog een keer proberen

  /* --- scenario 3: T-15, manco ------------------------------------- */
  geefVrij(db1, o1);
  const job = db1.pickjobs.find(j => j.orderId === o1.id);
  const volgorde = job.regels.map(r => db1.locaties[r.locationId].code);
  const pick1 = bevestigPick(db1, job, 1, 10);   // U-01-1 volledig
  const pick2 = bevestigPick(db1, job, 2, 9);    // U-02-1: 9 van 20
  const na2 = db1.voorraad.find(s => s.locationId === 2);
  const teltaak = db1.taken[db1.taken.length - 1];
  const pick3 = bevestigPick(db1, job, 3, 5);    // U-03-1 volledig

  /* --- scenario 4: R-UIT-07, inpakken ------------------------------ */
  const gepakt = [];
  for (const [naam, aantal] of [['een collo', 24], ['precies 25 kg', 138],
                                ['net erover', 139], ['niets gepickt', 0]]) {
    const db = nieuweDb();
    const o = order(db, 'ORD-P', Math.max(1, aantal));
    o.regels[0].gepickt = aantal;
    o.status = 'GEPICKT';
    pakIn(db, o);
    gepakt.push({ naam, gepickt: aantal, colli: o.colli, gewicht: o.gewicht });
  }

  return {
    looproute,
    reserveren: {
      status: status1,
      toewijzingen: toewijzingen(db1, o1),
      gereserveerd: o1.regels[0].gereserveerd,
      res_per_locatie: db1.voorraad.map(s => ({
        locatie: db1.locaties[s.locationId].code, qty: s.qty, res: s.res })),
    },
    t14: {
      status: status2, opnieuw: status2b,
      gereserveerd: o2.regels[0].gereserveerd,
      waarschuwingen: db1.log.filter(r => r.bron === 'reservering').length,
    },
    picken: {
      volgorde, pick1, pick2, pick3,
      qty_na_manco: na2.qty, res_na_manco: na2.res,
      teltaak_reden: teltaak.reden, teltaak_qty: teltaak.qty,
      orderregel: { gepickt: o1.regels[0].gepickt, manco: o1.regels[0].manco },
      orderstatus: o1.status,
    },
    inpakken: gepakt,
  };
});

console.log(JSON.stringify(uit, null, 2));
await b.close();

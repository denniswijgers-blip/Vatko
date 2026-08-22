import {chromium} from 'playwright';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
/* De demo staat één map hoger. Zo werkt de test ook als je hem vanuit
   een andere map start. */
const DEMO = 'file://' + join(dirname(fileURLToPath(import.meta.url)), '..', 'vakto-demo.html');

const b = await chromium.launch();
const p = await b.newPage();
await p.goto(DEMO);
await p.waitForSelector('#inhoud h1');

const uit = await p.evaluate(() => {
  /* Een kaal databankje: alleen wat legMetingVast aanraakt. */
  function nieuweDb(){
    const db = {
      artikelen:{}, locaties:{}, metingen:[], voorraad:[], drift:[], log:[],
      _laatste:{},
      artikelNu(id){ const a=this.artikelen[id], m=this._laatste[id];
        return m ? {...a, L:m.L,W:m.W,H:m.H,G:m.G} : {...a}; },
      herbereken(){ const l={}; for(const m of this.metingen){
        if(!l[m.productId]||m.at>l[m.productId].at) l[m.productId]=m; } this._laatste=l; }
    };
    return db;
  }
  const DAG = 86400000, NU = 1750000000000;

  function scenario(naam, opts){
    const db = nieuweDb();
    db.artikelen[1] = {id:1, sku:"TEST-001", stapelbaar:opts.stapelbaar??1};
    db.locaties[1] = {id:1, code:"01-01-1", typeId:0, actief:1, L:300,W:400,H:220, maxG:12000};
    db.locaties[2] = {id:2, code:"02-03-2", typeId:1, actief:1, L:1200,W:800,H:1400, maxG:800000};
    if(opts.eerste) db.metingen.push({productId:1, at:NU-40*DAG, bron:"RECEIPT", ...opts.eerste});
    db.herbereken();
    for(const s of (opts.voorraad||[])) db.voorraad.push({productId:1, locationId:s.loc, qty:s.qty});
    const a = legMetingVast(db, 1, opts.nieuw.L, opts.nieuw.W, opts.nieuw.H, opts.nieuw.G, "RECEIPT", null);
    /* pas-uitkomsten los erbij, zodat de Python-test ze ook kan nakijken */
    const passen = (db.voorraad||[]).map(s=>{
      const nep={...opts.nieuw, stapelbaar:db.artikelen[1].stapelbaar};
      const f = pasBerekening(nep, db.locaties[s.locationId], 0.85);
      return {loc:db.locaties[s.locationId].code, ligt:s.qty, past:f.qty, limiet:f.limiet};
    });
    return {naam, alert: a && {dVol:a.dVol, dGew:a.dGew, status:a.status, gevolg:a.gevolg}, passen};
  }

  return [
    scenario("groter, past niet meer", {
      eerste:{L:120,W:90,H:45,G:180}, nieuw:{L:140,W:100,H:50,G:210},
      voorraad:[{loc:1, qty:30}]}),
    scenario("groter, geen voorraad", {
      eerste:{L:120,W:90,H:45,G:180}, nieuw:{L:140,W:100,H:50,G:210},
      voorraad:[]}),
    scenario("groter, past nog wel", {
      eerste:{L:120,W:90,H:45,G:180}, nieuw:{L:140,W:100,H:50,G:210},
      voorraad:[{loc:1, qty:10}]}),
    scenario("twee locaties", {
      eerste:{L:120,W:90,H:45,G:180}, nieuw:{L:140,W:100,H:50,G:210},
      voorraad:[{loc:1, qty:30},{loc:2, qty:900}]}),
    scenario("binnen de drempel", {
      eerste:{L:120,W:90,H:45,G:180}, nieuw:{L:124,W:92,H:46,G:186},
      voorraad:[{loc:1, qty:30}]}),
    scenario("eerste meting ooit", {
      eerste:null, nieuw:{L:140,W:100,H:50,G:210}, voorraad:[{loc:1, qty:30}]}),
    scenario("krimpt", {
      eerste:{L:140,W:100,H:50,G:210}, nieuw:{L:120,W:90,H:45,G:180},
      voorraad:[{loc:1, qty:30}]}),
    scenario("alleen gewicht wijkt af", {
      eerste:{L:120,W:90,H:45,G:180}, nieuw:{L:121,W:90,H:45,G:230},
      voorraad:[{loc:1, qty:30}]}),
    scenario("niet stapelbaar", {
      eerste:{L:120,W:90,H:45,G:180}, nieuw:{L:140,W:100,H:50,G:210},
      stapelbaar:0, voorraad:[{loc:1, qty:8}]}),
    scenario("gewicht wordt de grens", {
      eerste:{L:120,W:90,H:45,G:180}, nieuw:{L:120,W:90,H:45,G:900},
      voorraad:[{loc:1, qty:30}]}),
  ];
});
console.log(JSON.stringify(uit, null, 2));
await b.close();

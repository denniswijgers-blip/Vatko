/* =====================================================================
   OPTIMALISATIE

   Alles hier volgt dezelfde regel als de rest van het systeem: het is
   afgeleid uit de toestand van het magazijn, niemand vult het in, en
   zodra de aanleiding weg is vervalt het werk vanzelf.

   Vier dingen waar een magazijn geld op verliest zonder het te merken:

     1. Hetzelfde artikel op drie plekken. Elke plek die je terugwint is
        een plek die je niet hoeft bij te bouwen.
     2. Een picklocatie die leegloopt terwijl er orders op wachten. De
        picker staat er, en dat is het duurste moment van de dag.
     3. Een hardloper met een aanvuldrempel die iemand drie jaar geleden
        heeft ingetypt. Precies dezelfde ziekte als een artikelmaat die
        stil veroudert.
     4. Locaties die al een jaar niet geteld zijn. Niet spannend, wel de
        reden dat je voorraad langzaam wegloopt van de werkelijkheid.
   ===================================================================== */

/* --- pickvraag per dag, uit het journaal ----------------------------
   Cache op het aantal boekingen: zolang er niets geboekt is, verandert
   de snelheid niet en hoeven we niet opnieuw te rekenen.              */
let _snelCache = {n:-1, kaart:null};
function pickSnelheden(db){
  if(_snelCache.n === db.boekingen.length && _snelCache.kaart) return _snelCache.kaart;
  const dagen = Math.max(1, getN("opt.venster_dagen"));
  const vanaf = Date.now() - dagen*86400000;
  const kaart = new Map();
  for(const b of db.boekingen){
    if(b.soort!=="PICK" || b.at < vanaf) continue;
    kaart.set(b.productId, (kaart.get(b.productId)||0) + b.qty);
  }
  for(const [k,v] of kaart) kaart.set(k, v/dagen);
  _snelCache = {n:db.boekingen.length, kaart};
  return kaart;
}

/* --- wat ligt er per locatie, in volume en gewicht ------------------- */
function bezetPerLocatie(db){
  const kaart = new Map();
  for(const s of db.voorraad){
    if(s.qty<=0) continue;
    const m = db.artikelNu(s.productId);
    if(!m || !m.L) continue;
    let b = kaart.get(s.locationId);
    if(!b) kaart.set(s.locationId, b = {vol:0, gew:0,
                                        perArt:new Map(), volPerArt:new Map()});
    const v = s.qty*m.L*m.W*m.H, g = s.qty*m.G;
    b.vol += v; b.gew += g;
    b.perArt.set(s.productId, (b.perArt.get(s.productId)||0) + s.qty);
    b.volPerArt.set(s.productId, (b.volPerArt.get(s.productId)||0) + v);
  }
  return kaart;
}

/* --- de beste bulkbron voor een artikel ------------------------------ */
function bulkBron(db, pid, minAantal=1){
  let beste = null;
  for(const s of db.voorraad){
    if(s.productId!==pid || s.qty<=0) continue;
    const t = LOCTYPES[db.locaties[s.locationId].typeId];
    if(!t.bulk) continue;
    const vrij = s.qty - (s.res||0);
    if(vrij < minAantal) continue;
    if(!beste || vrij > beste.vrij) beste = {rij:s, vrij};
  }
  return beste;
}

/* --- één aanvultaak per artikel per picklocatie ----------------------
   Drie aanleidingen kunnen om hetzelfde vragen. Dan wordt het één taak
   met de zwaarste aanleiding, niet drie taken voor dezelfde loop.     */
function vraagAanvulling(db, r, {pid, naar, qty, prio, aanleiding, reden, bezet}){
  const bestaand = db.taken.find(t=>t.soort==="REPLENISH" && t.status==="TODO"
    && t.productId===pid && t.naar===naar);
  if(bestaand){
    if(qty > bestaand.qty || prio < bestaand.prio){
      bestaand.qty = Math.min(Math.max(bestaand.qty, qty),
                              Math.max(1, ruimteVoor(db, pid, naar, bezet)));
      bestaand.prio = Math.min(bestaand.prio, prio);
      bestaand.aanleiding = aanleiding;
      bestaand.reden = reden;
    }
    return false;
  }
  const bron = bulkBron(db, pid, 1);
  if(!bron) return false;
  /* Nooit meer klaarzetten dan er op de picklocatie past. */
  const past = ruimteVoor(db, pid, naar, bezet);
  const echt = Math.min(qty, bron.vrij, past);
  if(echt <= 0) return false;
  db.taken.push({id:db.taken.length, soort:"REPLENISH", naam:"Picklocatie aanvullen",
    prio, status:"TODO", productId:pid, van:bron.rij.locationId, naar,
    qty:echt, automatisch:true, aanleiding, reden, at:Date.now()});
  r.aangemaakt++;
  return true;
}

/* =====================================================================
   1. SAMENVOEGEN
   ===================================================================== */
function optSamenvoegen(db, r){
  if(!getB("opt.samenvoegen")) return;
  const vul = getN("putaway.fill_factor");
  const bezet = bezetPerLocatie(db);

  const perArt = new Map();
  for(const s of db.voorraad){
    if(s.qty<=0) continue;
    if(!LOCTYPES[db.locaties[s.locationId].typeId].doel) continue;
    (perArt.get(s.productId) || perArt.set(s.productId, []).get(s.productId)).push(s);
  }

  for(const [pid, rijen] of perArt){
    if(rijen.length < 2 || rijen.length > 6) continue;
    /* Gereserveerde voorraad staat al op naam van een order. Daar gaan
       we niet aan zitten: dan klopt de pickopdracht niet meer. */
    if(rijen.some(s=>(s.res||0) > 0)) continue;
    if(db.taken.some(t=>t.soort==="SAMENVOEG" && t.status==="TODO" && t.productId===pid)) continue;

    const p = db.artikelNu(pid);
    if(!p || !p.L) continue;
    const pVol = p.L*p.W*p.H, totaal = rijen.reduce((a,s)=>a+s.qty,0);

    let doel = null;
    for(const s of rijen){
      const loc = db.locaties[s.locationId];
      if(!loc.actief) continue;
      const fit = pasBerekening(p, loc, vul);
      if(!fit.qty) continue;
      const b = bezet.get(loc.id) || {vol:0, gew:0, perArt:new Map(), volPerArt:new Map()};
      const eigenVol = b.volPerArt.get(pid) || 0;
      const eigenStuks = b.perArt.get(pid) || 0;
      const vreemdVol = b.vol - eigenVol;
      const vreemdGew = b.gew - eigenStuks*p.G;
      const ruimte = Math.floor(Math.min(fit.qty,
        ((loc.L*loc.W*loc.H)*vul - vreemdVol)/pVol,
        (loc.maxG - vreemdGew)/p.G));
      if(ruimte < totaal) continue;
      /* Liever de picklocatie houden, en anders de plek waar al het
         meeste ligt: dan hoef je het minst te sjouwen. */
      const score = (LOCTYPES[loc.typeId].pick ? 1e6 : 0) + s.qty;
      if(!doel || score > doel.score) doel = {loc, score};
    }
    if(!doel) continue;

    const bronnen = rijen.filter(s=>s.locationId !== doel.loc.id);
    if(!bronnen.length) continue;
    /* Nooit een picklocatie leeghalen naar bulk: dan staat de picker
       morgen voor een leeg vak. */
    if(!LOCTYPES[doel.loc.typeId].pick &&
       bronnen.some(s=>LOCTYPES[db.locaties[s.locationId].typeId].pick)) continue;

    for(const b of bronnen){
      db.taken.push({id:db.taken.length, soort:"SAMENVOEG", naam:"Voorraad samenvoegen",
        prio:35, status:"TODO", productId:pid, van:b.locationId, naar:doel.loc.id,
        qty:b.qty, automatisch:true, aanleiding:"samenvoegen",
        reden:`${db.locaties[b.locationId].code} komt helemaal vrij; alle ${fmt(totaal)} st passen op ${doel.loc.code}`,
        at:Date.now()});
      r.aangemaakt++;
    }
  }
}

/* =====================================================================
   2. VRAAGGESTUURD AANVULLEN — er wachten orders op
   ===================================================================== */
function optVraag(db, r, bezet){
  const vraag = new Map();
  for(const o of db.orders){
    if(o.status==="VERZONDEN" || o.status==="INGEPAKT") continue;
    for(const rg of o.regels){
      const open = rg.besteld - rg.gepickt;
      if(open > 0) vraag.set(rg.productId, (vraag.get(rg.productId)||0) + open);
    }
  }
  for(const [pid, nodig] of vraag){
    const pickRijen = db.voorraad.filter(s=>s.productId===pid && s.qty>0
      && LOCTYPES[db.locaties[s.locationId].typeId].pick);
    if(!pickRijen.length) continue;
    const opPick = pickRijen.reduce((a,s)=>a+s.qty, 0);
    if(opPick >= nodig) continue;
    const doel = pickRijen[0];
    const p = db.artikelen[pid];
    const tot = Math.max(nodig, p.maxQty || nodig);
    vraagAanvulling(db, r, {pid, naar:doel.locationId, qty:tot - opPick, prio:10,
      bezet, aanleiding:"ordervraag",
      reden:`${fmt(nodig)} st gevraagd door openstaande orders, ${fmt(opPick)} op de picklocatie`});
  }
}

/* =====================================================================
   3. HARDLOPERS — houd de picklocatie vooruit op het verbruik
   ===================================================================== */
function optHardlopers(db, r, bezet){
  const snel = pickSnelheden(db);
  const drempel = getN("opt.hardloper_per_dag");
  const dekking = getN("opt.dekking_dagen");
  for(const [pid, perDag] of snel){
    if(perDag < drempel) continue;
    const pickRijen = db.voorraad.filter(s=>s.productId===pid && s.qty>0
      && LOCTYPES[db.locaties[s.locationId].typeId].pick);
    if(!pickRijen.length) continue;
    const opPick = pickRijen.reduce((a,s)=>a+s.qty, 0);
    const dagenOver = opPick/perDag;
    if(dagenOver >= dekking) continue;
    const doel = pickRijen[0];
    const nodig = Math.ceil(perDag*dekking) - opPick;
    if(nodig <= 0) continue;
    vraagAanvulling(db, r, {pid, naar:doel.locationId, qty:nodig, prio:20,
      bezet, aanleiding:"hardloper",
      reden:`hardloper: ${perDag.toFixed(1)} st per dag, nog ${dagenOver.toFixed(1)} dag(en) op de picklocatie`});
  }
}

/* =====================================================================
   4. TELLEN — per artikelgroep een eigen telinterval
   ===================================================================== */
function optTellen(db, r){
  const max = getN("opt.max_open_teltaken");
  let open = db.taken.filter(t=>t.soort==="CYCLE_COUNT" && t.status==="TODO").length;
  if(open >= max) return;
  const nu = Date.now();
  const kandidaten = [];
  const gezien = new Set();
  for(const s of db.voorraad){
    if(s.qty<=0 || gezien.has(s.locationId)) continue;
    const loc = db.locaties[s.locationId];
    if(!LOCTYPES[loc.typeId].doel || !loc.actief) continue;
    const g = db.groepen[db.artikelen[s.productId].groepId];
    const interval = ((g && g.telint) || 180)*86400000;
    const over = nu - (loc.geteldOp || 0) - interval;
    if(over <= 0) continue;
    gezien.add(s.locationId);
    kandidaten.push({loc, pid:s.productId, qty:s.qty, over, interval});
  }
  /* Het meest over tijd eerst, en bij gelijke stand de snelste groep. */
  kandidaten.sort((a,b)=> (b.over/b.interval) - (a.over/a.interval));
  for(const k of kandidaten){
    if(open >= max) break;
    if(db.taken.some(t=>t.soort==="CYCLE_COUNT" && t.status==="TODO" && t.naar===k.loc.id)) continue;
    const dagen = Math.floor(k.over/86400000);
    db.taken.push({id:db.taken.length, soort:"CYCLE_COUNT", naam:"Locatie tellen",
      prio:45, status:"TODO", productId:k.pid, van:k.loc.id, naar:k.loc.id, qty:k.qty,
      automatisch:true, aanleiding:"telinterval",
      reden:`${dagen} dag(en) over het telinterval van ${Math.round(k.interval/86400000)} dagen`,
      at:Date.now()});
    r.aangemaakt++;
    open++;
  }
}

/* =====================================================================
   5. ADVIES — de aanvuldrempel klopt niet meer
   Geen taak: dit is een besluit. Het systeem rekent het uit en legt het
   voor. Precies zoals bij artikelmaten: een getal dat iemand ooit heeft
   ingetypt veroudert stil, en niemand merkt het.
   ===================================================================== */
function optDrempelAdvies(db){
  const snel = pickSnelheden(db);
  const dekking = getN("opt.dekking_dagen");
  const afw = getN("opt.drempel_afwijking_pct")/100;
  const uit = [];
  for(const [pid, perDag] of snel){
    if(perDag < 0.5) continue;
    const p = db.artikelen[pid];
    if(!p.minQty) continue;
    if(p.drempelAkkoord) continue;
    const zou = Math.max(1, Math.round(perDag*dekking));
    const verschil = Math.abs(zou - p.minQty)/Math.max(1, zou);
    if(verschil < afw) continue;
    uit.push({pid, sku:p.sku, oms:p.oms, perDag, nu:p.minQty, zou,
      maxNu:p.maxQty, maxZou:Math.max(zou*3, zou+1),
      richting: zou > p.minQty ? "omhoog" : "omlaag"});
  }
  uit.sort((a,b)=>b.perDag-a.perDag);
  db.adviezen = uit.slice(0, 40);
  return db.adviezen;
}

/* =====================================================================
   6. HARDLOPERS DIE ALLEEN IN BULK LIGGEN
   Een artikel dat elke dag twaalf keer gepakt wordt en alleen in de
   palletstelling ligt, laat je picker elke keer een eind lopen. Het
   systeem rekent uit welk vak past; wélk vak je ervoor vrijmaakt blijft
   een keuze van de teamleider.
   ===================================================================== */
function optZonderPicklocatie(db){
  const snel = pickSnelheden(db);
  const drempel = getN("opt.hardloper_per_dag");
  const dekking = getN("opt.dekking_dagen");
  const uit = [];
  for(const [pid, perDag] of snel){
    if(perDag < drempel) continue;
    const heeft = db.voorraad.some(s=>s.productId===pid && s.qty>0
      && LOCTYPES[db.locaties[s.locationId].typeId].pick);
    if(heeft) continue;
    if(db.taken.some(t=>t.soort==="PICKPLEK" && t.status==="TODO" && t.productId===pid)) continue;
    const bron = bulkBron(db, pid, 1);
    if(!bron) continue;
    const nodig = Math.max(1, Math.ceil(perDag*dekking));
    const v = voorstelInslag(db, pid, nodig, 8)
      .find(x=>LOCTYPES[x.loc.typeId].pick && x.loc.id !== bron.rij.locationId);
    if(!v) continue;
    uit.push({pid, perDag, van:bron.rij.locationId, naar:v.loc.id,
      qty:Math.max(1, Math.min(nodig, bron.vrij, v.alles ? nodig : v.vrij))});
  }
  db.zonderPick = uit.sort((a,b)=>b.perDag-a.perDag).slice(0, 12);
}

/* --- alles achter elkaar, aangeroepen vanuit de zelfcontrole -------- */
function optimaliseer(db, r){
  const bezet = bezetPerLocatie(db);
  optVraag(db, r, bezet);
  optHardlopers(db, r, bezet);
  optSamenvoegen(db, r);
  optTellen(db, r);
  optDrempelAdvies(db);
  optZonderPicklocatie(db);
}

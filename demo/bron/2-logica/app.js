/* =====================================================================
   VAKTO - schermen
   ===================================================================== */
let DB = null;

/* --- afwijkingen en aanvultaken: het systeem doet dit zelf ----------- */
function legMetingVast(db, productId, L, W, H, G, bron="RECEIPT", notitie=null){
  const drempel = getN("drift.alert_threshold_pct");
  const vorige = db._laatste[productId] || null;
  const meting = {productId, at:Date.now(), bron, L, W, H, G, notitie};
  db.metingen.push(meting);
  db.herbereken();
  if(!vorige) return null;

  const oudVol = vorige.L*vorige.W*vorige.H, nieuwVol = L*W*H;
  const dVol = oudVol ? (nieuwVol-oudVol)/oudVol*100 : 0;
  const dGew = vorige.G ? (G-vorige.G)/vorige.G*100 : 0;
  if(Math.abs(dVol)<drempel && Math.abs(dGew)<drempel) return null;

  /* Het belangrijkste: wat betekent dit voor de voorraad die er NU ligt?
     Zelfde regel als passenNiet() gebruikt bij de zelfcontrole - inclusief
     het overslaan van ontvangst, keuring en verzendgereed. Dat zijn
     doorloopplekken met een nominale maat; een pallet die daar staat
     "past" er niet minder om. Zouden de twee routes hier van elkaar
     verschillen, dan zou een melding zichzelf meteen weer sluiten. */
  const problemen = passenNiet(db, productId).map(x=>
    `${x.loc.code} (ligt ${x.ligt}, past nog ${x.past})`);

  const gevolg = problemen.length ? "Past niet meer op: "+problemen.join(", ")
                                  : "Geen gevolgen voor huidige voorraadlocaties.";
  const pv = rond1(dVol), pg = rond1(dGew);

  /* Een melding is een uitspraak over de huidige toestand, geen regel op
     een takenlijst. Twee open uitspraken over hetzelfde artikel spreken
     elkaar tegen, dus werken we de bestaande bij in plaats van er een
     tweede naast te zetten. Het tijdstip blijft staan: dan zie je hoe
     lang dit al speelt. */
  let alert = db.drift.find(d=>d.productId===productId && d.status==="OPEN");
  if(alert){ alert.dVol=pv; alert.dGew=pg; alert.gevolg=gevolg; }
  else {
    alert = {id:db.drift.length, productId, at:Date.now(),
             dVol:pv, dGew:pg, status:"OPEN", gevolg};
    db.drift.push(alert);
  }
  db.log.unshift({at:Date.now(),niveau:"WARN",bron:"drift",
    bericht:`${db.artikelen[productId].sku}: volume ${pv>0?"+":""}${pv}%, gewicht ${pg>0?"+":""}${pg}%`});
  return alert;
}

function maakAanvultaken(db){
  let n=0;
  /* Eén keer opbouwen, niet per kandidaat: anders loop je de hele
     voorraad zestig keer langs bij elke hertekening van het scherm. */
  const bezet = bezetPerLocatie(db);
  const bulkVan={};
  for(const s of db.voorraad){
    if(s.qty>0 && LOCTYPES[db.locaties[s.locationId].typeId].bulk)
      if(!bulkVan[s.productId] || s.qty>bulkVan[s.productId].qty) bulkVan[s.productId]=s;
  }
  for(const s of db.voorraad){
    const loc = db.locaties[s.locationId];
    if(!LOCTYPES[loc.typeId].pick) continue;
    const p = db.artikelen[s.productId];
    if(!p.minQty || s.qty >= p.minQty) continue;
    if(db.taken.some(t=>t.soort==="REPLENISH"&&t.naar===loc.id&&t.productId===p.id&&t.status==="TODO")) continue;
    const bron = bulkVan[p.id];
    if(!bron) continue;
    /* Ook hier: nooit meer dan er past. Een aanvultaak van 115 stuks
       naar een vak waar er zestig in gaan is geen taak maar een probleem
       dat je op de vloer aflevert. */
    /* bron.vrij en niet bron.qty: wat op naam van een order staat mag
       je niet wegrijden, ook al ligt het er nog (R-ZC-04). */
    const nodig = Math.min((p.maxQty||p.minQty)-s.qty, bron.qty-(bron.res||0),
                           ruimteVoor(db, p.id, loc.id, bezet));
    if(nodig<=0) continue;
    db.taken.push({id:db.taken.length, soort:"REPLENISH", naam:"Picklocatie aanvullen",
      prio:25, status:"TODO", productId:p.id, van:bron.locationId, naar:loc.id,
      qty:nodig, automatisch:true, aanleiding:"drempel",
      reden:`Picklocatie ${loc.code} onder drempel (${s.qty}/${p.minQty})`,
      at:Date.now()});
    n++;
  }
  return n;
}

function boek(db, productId, qty, soort, vanId, naarId, reden, ref){
  if(qty<=0) throw new Error("Aantal moet groter dan 0 zijn");
  if(vanId!==null && vanId!==undefined){
    const r = db.voorraad.find(s=>s.productId===productId && s.locationId===vanId);
    const aanwezig = r?r.qty:0;
    if(aanwezig<qty) throw new Error(`Onvoldoende voorraad op bronlocatie (aanwezig ${aanwezig}, gevraagd ${qty})`);
    r.qty-=qty;
  }
  if(naarId!==null && naarId!==undefined){
    let r = db.voorraad.find(s=>s.productId===productId && s.locationId===naarId);
    if(r) r.qty+=qty; else db.voorraad.push({productId,locationId:naarId,qty});
  }
  /* Voorraad en journaal gaan altijd samen. Geen enkele mutatie zonder regel. */
  db.boekingen.unshift({at:Date.now(),soort,productId,van:vanId??null,naar:naarId??null,
    qty,reden:reden||null,ref:ref||null});
}

/* --- demo opbouwen inclusief de drie situaties ----------------------- */
function startDemo(){
  DB = bouwDemo();
  bouwGebruikers(DB);
  const gem = DB.artikelen.map(a=>DB.artikelNu(a.id)).filter(p=>p.L);
  const metVoorraad = new Set(DB.voorraad.filter(s=>s.qty>10).map(s=>s.productId));

  /* 1+2. Twee leveranciers hebben stilletjes de verpakking gewijzigd. */
  const kandidaten = gem.filter(p=>metVoorraad.has(p.id));
  if(kandidaten[0]) legMetingVast(DB, kandidaten[0].id,
    Math.round(kandidaten[0].L*1.18), Math.round(kandidaten[0].W*1.14),
    Math.round(kandidaten[0].H*1.12), Math.round(kandidaten[0].G*1.19),
    "RECEIPT","Nieuwe verpakking leverancier, niet aangekondigd");
  const k2 = kandidaten[kandidaten.length-1];
  if(k2) legMetingVast(DB, k2.id, Math.round(k2.L*1.18), k2.W, k2.H,
    Math.round(k2.G*1.21), "RECEIPT","Afwijkende partij");

  /* 3. Aanvultaken laat het systeem zelf aanmaken. */
  const n = maakAanvultaken(DB);
  DB.log.unshift({at:Date.now(),niveau:"INFO",bron:"systeem",
    bericht:`Demo opgebouwd: ${n} aanvultaken aangemaakt`});
  return DB;
}


/* =====================================================================
   ZELFCONTROLE

   Het uitgangspunt: een melding is GEEN taakje dat iemand moet afvinken,
   maar een afgeleide van de huidige toestand. Precies zoals beschikbare
   voorraad nooit wordt opgeslagen maar altijd berekend.

   Dus: na elke mutatie toetst Vakto zichzelf opnieuw. Is het probleem
   weg, dan sluit de melding zichzelf. Is het er nog, dan zet het systeem
   het werk klaar dat nodig is om het op te lossen. Is een taak overbodig
   geworden doordat iemand anders het al deed, dan vervalt hij.

   Wat een mens nog wel beslist: "dit is geen fout, meld het niet meer".
   Dat is een oordeel, en oordelen horen bij mensen. Afvinken hoort bij
   het systeem.
   ===================================================================== */
let controle = {at:null, gesloten:0, aangemaakt:0, vervallen:0, regels:[], runs:0};

/* Waar ligt van dit artikel meer dan er volgens de huidige maat past? */
function passenNiet(db, productId){
  const p = db.artikelNu(productId);
  if(!p || !p.L) return [];
  const vul = getN("putaway.fill_factor");
  const uit = [];
  for(const s of db.voorraad){
    if(s.productId!==productId || s.qty<=0) continue;
    const loc = db.locaties[s.locationId];
    if(!LOCTYPES[loc.typeId].doel) continue;
    const fit = pasBerekening(p, loc, vul);
    if(fit.qty!==null && fit.qty < s.qty)
      uit.push({loc, ligt:s.qty, past:fit.qty, teveel:s.qty-fit.qty});
  }
  /* Vaste volgorde. Anders verandert de tekst van een melding bij elke
     herberekening terwijl er niets nieuws te melden is. */
  uit.sort((a,b)=> (a.loc.seq-b.loc.seq) || (a.loc.id-b.loc.id));
  return uit;
}

function noteerControle(db, r, tekst, niveau="INFO"){
  r.regels.unshift({at:Date.now(), tekst});
  if(r.regels.length>30) r.regels.pop();
  db.log.unshift({at:Date.now(), niveau, bron:"zelfcontrole", bericht:tekst});
}

function hertoets(db){
  const r = {gesloten:0, aangemaakt:0, vervallen:0, regels:controle.regels||[]};

  /* --- 1. openstaande afwijkingen opnieuw beoordelen ---------------- */
  for(const d of db.drift){
    if(d.status!=="OPEN") continue;
    const sku = db.artikelen[d.productId].sku;
    const pr = passenNiet(db, d.productId);
    if(!pr.length){
      d.status = "OPGELOST"; d.opgelostOp = Date.now();
      d.gevolg = "Vanzelf opgelost \u2014 de voorraad past weer.";
      r.gesloten++;
      noteerControle(db, r, `${sku}: afwijking vanzelf gesloten, de voorraad past weer`);
      continue;
    }
    d.gevolg = "Past niet meer op: " + pr.map(x=>
      `${x.loc.code} (ligt ${x.ligt}, past nog ${x.past})`).join(", ");

    /* Waar het systeem zelf iets kan: het werk klaarzetten. */
    for(const x of pr){
      if(db.taken.some(t=>t.soort==="OVERLOOP" && t.status==="TODO"
        && t.productId===d.productId && t.van===x.loc.id)) continue;
      const doel = voorstelInslag(db, d.productId, x.teveel, 4)
        .find(v=>v.loc.id!==x.loc.id);
      if(!doel) continue;
      db.taken.push({id:db.taken.length, soort:"OVERLOOP", naam:"Overloop verplaatsen",
        prio:15, status:"TODO", productId:d.productId, van:x.loc.id, naar:doel.loc.id,
        qty:Math.min(x.teveel, doel.alles?x.teveel:doel.vrij), automatisch:true,
        aanleiding:"afwijking",
        reden:`${x.loc.code} zit ${x.teveel} st over de nieuwe maat`, at:Date.now()});
      r.aangemaakt++;
      noteerControle(db, r,
        `${sku}: verplaatstaak aangemaakt, ${x.teveel} st van ${x.loc.code} naar ${doel.loc.code}`);
    }
  }

  /* --- 2. taken die niet meer nodig zijn laten vervallen ------------ */
  const vul = getN("putaway.fill_factor");
  for(const t of db.taken){
    if(t.status!=="TODO") continue;
    const sku = db.artikelen[t.productId].sku;
    let weg = null;
    if(t.soort==="REPLENISH"){
      const doel = db.voorraad.find(s=>s.productId===t.productId && s.locationId===t.naar);
      const p = db.artikelen[t.productId];
      const bron = db.voorraad.find(s=>s.productId===t.productId && s.locationId===t.van);
      if(p.minQty && doel && doel.qty >= p.minQty) weg = "picklocatie is weer op peil";
      else if(!bron || bron.qty <= 0)              weg = "er ligt geen bulkvoorraad meer om mee aan te vullen";
    }
    if(t.soort==="OVERLOOP"){
      const bron = db.voorraad.find(s=>s.productId===t.productId && s.locationId===t.van);
      if(!bron || bron.qty<=0) weg = "de bronlocatie is inmiddels leeg";
      else {
        const fit = pasBerekening(db.artikelNu(t.productId), db.locaties[t.van], vul);
        if(fit.qty!==null && fit.qty >= bron.qty) weg = "het past er inmiddels weer in";
      }
    }
    if(t.soort==="SAMENVOEG"){
      const bron = db.voorraad.find(s=>s.productId===t.productId && s.locationId===t.van);
      const doel = db.voorraad.find(s=>s.productId===t.productId && s.locationId===t.naar);
      if(!bron || bron.qty<=0)          weg = "de bronlocatie is al leeg";
      else if((bron.res||0) > 0 || (doel && (doel.res||0) > 0))
                                        weg = "er is inmiddels voorraad gereserveerd voor een order";
      else if(!doel)                    weg = "op de doellocatie ligt dit artikel niet meer";
    }
    if(t.soort==="PICKPLEK"){
      const heeft = db.voorraad.some(s=>s.productId===t.productId && s.qty>0
        && LOCTYPES[db.locaties[s.locationId].typeId].pick);
      if(heeft) weg = "het artikel heeft inmiddels een picklocatie";
    }
    if(t.soort==="CYCLE_COUNT"){
      const loc = db.locaties[t.naar];
      if(loc.geteldOp && loc.geteldOp > t.at) weg = "de locatie is inmiddels geteld";
      else {
        const s2 = db.voorraad.find(s=>s.locationId===t.naar && s.qty>0);
        if(!s2) weg = "er ligt niets meer op deze locatie";
      }
    }
    if(weg){
      t.status = "VERVALLEN"; t.vervallenOp = Date.now(); t.vervallenReden = weg;
      r.vervallen++;
      noteerControle(db, r, `${sku}: taak vervallen \u2014 ${weg}`);
    }
  }

  /* --- 3. nieuw werk dat uit de toestand volgt ---------------------- */
  const n = maakAanvultaken(db);
  if(n) r.aangemaakt += n;

  /* Samenvoegen, telplan en drempeladvies zijn zwaarder en hoeven niet
     tien keer per seconde. Meldingen en vervallen taken hierboven wel:
     die moeten kloppen op het moment dat je ernaar kijkt. */
  const nu = Date.now();
  if(nu - (hertoets._zwaar||0) > 900){
    hertoets._zwaar = nu;
    optimaliseer(db, r);
  }

  controle = {at:Date.now(), gesloten:r.gesloten, aangemaakt:r.aangemaakt,
              vervallen:r.vervallen, regels:r.regels, runs:(controle.runs||0)+1};
  return r;
}

/* --- afgeleide gegevens ---------------------------------------------- */
const fmt = n => n.toLocaleString("nl-NL");
const dat = t => new Date(t).toLocaleDateString("nl-NL",{day:"2-digit",month:"2-digit",year:"numeric"});
const tijd = t => new Date(t).toLocaleString("nl-NL",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"});
const dagenOud = t => t ? Math.floor((Date.now()-t)/86400000) : null;

function teMeten(db){
  const max = getN("drift.remeasure_after_days");
  return db.artikelen.map(a=>db.artikelNu(a.id)).filter(p=>{
    const d = dagenOud(p.gemetenOp);
    return p.gemetenOp===null || p.bron==="SUPPLIER" || d>max;
  }).map(p=>({...p, reden: p.gemetenOp===null ? "nooit gemeten"
      : p.bron==="SUPPLIER" ? "alleen opgave leverancier"
      : `meting ${dagenOud(p.gemetenOp)} dagen oud`}))
    .sort((a,b)=>(a.gemetenOp||0)-(b.gemetenOp||0));
}

function voorraadOp(db, locId){
  return db.voorraad.filter(s=>s.locationId===locId && s.qty>0);
}
function voorraadVan(db, pid){
  return db.voorraad.filter(s=>s.productId===pid && s.qty>0);
}
function beschikbaar(db, pid){
  return voorraadVan(db,pid).reduce((a,s)=>
    a + (LOCTYPES[db.locaties[s.locationId].typeId].blok ? 0 : s.qty), 0);
}

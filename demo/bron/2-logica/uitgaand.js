/* =====================================================================
   UITGAANDE STROOM
   Order -> reserveren -> vrijgeven -> picken -> inpakken -> verzenden

   De statussen zijn een echte toestandsmachine: een order kan alleen
   langs toegestane overgangen. Geen vrij tekstveld waar iemand "klaar?"
   in typt.
   ===================================================================== */

const ORDERSTATUS = ["NIEUW","GERESERVEERD","WACHT_OP_VOORRAAD","VRIJGEGEVEN",
                     "PICKEN","GEPICKT","INGEPAKT","VERZONDEN"];
const STATUSNAAM = {
  NIEUW:"Nieuw", GERESERVEERD:"Gereserveerd", WACHT_OP_VOORRAAD:"Wacht op voorraad",
  VRIJGEGEVEN:"Vrijgegeven", PICKEN:"Wordt gepickt", GEPICKT:"Gepickt",
  INGEPAKT:"Ingepakt", VERZONDEN:"Verzonden"
};
const STATUSKLEUR = {
  NIEUW:"n", GERESERVEERD:"a", WACHT_OP_VOORRAAD:"r", VRIJGEGEVEN:"a",
  PICKEN:"o", GEPICKT:"g", INGEPAKT:"g", VERZONDEN:"g"
};

const KLANTEN=[
  ["Installatiebedrijf Van Loon","Deventer","NL","DPD"],
  ["Machinefabriek Kessels","Helmond","NL","DHL"],
  ["Techniek Groep Oost","Hengelo","NL","DPD"],
  ["Pompservice Zeeland","Goes","NL","DHL"],
  ["Van Baarle Transporttechniek","Tilburg","NL","EIGEN"],
  ["Hydrauliek Noord","Groningen","NL","DPD"],
  ["Ateliers Vermeulen","Antwerpen","BE","DPD"],
  ["Rheinland Antriebstechnik","Kleve","DE","DHL"],
  ["Bosman Onderhoud","Zwolle","NL","AFHAAL"],
  ["Staalbouw Rijnmond","Rotterdam","NL","EIGEN"],
  ["Servicedienst Brabant","Eindhoven","NL","DPD"],
  ["Motoren De Wit","Alphen aan den Rijn","NL","DHL"]
];
const ORDERSOORTEN=[["WEB","Webshop",3],["SERVICE","Servicedienst",1],
                    ["PROJECT","Projectorder",5],["BALIE","Balieverkoop",2]];

/* --- hulpgetallen ---------------------------------------------------- */
const vrijeVoorraad = (s)=> s.qty - (s.res||0);
function beschikbaarTotaal(db, pid){
  return db.voorraad.filter(s=>s.productId===pid && s.qty>0)
    .filter(s=>!LOCTYPES[db.locaties[s.locationId].typeId].blok)
    .reduce((a,s)=>a+vrijeVoorraad(s),0);
}

/* =====================================================================
   RESERVEREN
   Dit is de plek waar het bij zelfbouwsystemen misgaat. Reserveren
   verplaatst niets: het legt vast WELKE voorraad op WELKE locatie voor
   deze order bestemd is. Zonder dat verkoop je twee keer dezelfde doos.
   ===================================================================== */
function reserveer(db, order){
  if(order.status!=="NIEUW" && order.status!=="WACHT_OP_VOORRAAD") return order.status;
  const gedaan=[];
  let compleet = true;

  for(const r of order.regels){
    let nodig = r.besteld - r.gereserveerd;
    if(nodig<=0) continue;

    /* Voorkeur: picklocatie eerst, dan bulk. Binnen dezelfde soort de
       locatie met de kortste looproute. */
    const kandidaten = db.voorraad
      .filter(s=>s.productId===r.productId && vrijeVoorraad(s)>0)
      .filter(s=>!LOCTYPES[db.locaties[s.locationId].typeId].blok)
      .sort((a,b)=>{
        const la=db.locaties[a.locationId], lb=db.locaties[b.locationId];
        const pa=LOCTYPES[la.typeId].pick?0:1, pb=LOCTYPES[lb.typeId].pick?0:1;
        return pa-pb || la.seq-lb.seq;
      });

    for(const s of kandidaten){
      if(nodig<=0) break;
      const neem = Math.min(nodig, vrijeVoorraad(s));
      s.res = (s.res||0) + neem;
      r.gereserveerd += neem;
      gedaan.push({s, neem});
      db.reserveringen.push({orderId:order.id, regel:r.idx,
        productId:r.productId, locationId:s.locationId, qty:neem, gepickt:0});
      nodig -= neem;
    }
    if(nodig>0) compleet = false;
  }

  order.status = compleet ? "GERESERVEERD" : "WACHT_OP_VOORRAAD";
  if(!compleet && !order.tekortGemeld){
    order.tekortGemeld = true;
    db.log.unshift({at:Date.now(),niveau:"WARN",bron:"reservering",
      bericht:`Order ${order.nummer} kan niet volledig gereserveerd worden`});
  }
  return order.status;
}

/* --- vrijgeven: pas hier gaat er werk de vloer op -------------------- */
function geefVrij(db, order){
  if(order.status!=="GERESERVEERD") return false;
  const regels = db.reserveringen
    .filter(x=>x.orderId===order.id && x.gepickt < x.qty)
    .map(x=>({...x, seq: db.locaties[x.locationId].seq,
                    zone: db.locaties[x.locationId].zoneId}))
    .sort((a,b)=>a.seq-b.seq);      /* looproute, niet ordervolgorde */
  if(!regels.length) return false;

  db.pickjobs.push({id:db.pickjobs.length, orderId:order.id, status:"TODO",
    prio:order.prio, at:Date.now(), regels:regels.map((r,i)=>({...r, nr:i+1,
      gepickt:0, status:"TODO"}))});
  order.status = "VRIJGEGEVEN";
  return true;
}

/* --- picken: het enige punt waar voorraad echt daalt ----------------- */
function bevestigPick(db, job, regelNr, aantal){
  const r = job.regels.find(x=>x.nr===regelNr);
  if(!r || r.status!=="TODO") throw new Error("Regel bestaat niet of is al afgehandeld");
  const s = db.voorraad.find(x=>x.productId===r.productId && x.locationId===r.locationId);
  const order = db.orders[job.orderId];
  const teMax = Math.min(r.qty - r.gepickt, s ? s.qty : 0);
  const neem = Math.max(0, Math.min(aantal, teMax));

  if(neem>0){
    /* De reservering geven we vrij en boek() haalt de voorraad eraf.
       Niet allebei zelf doen: dan boek je dubbel af. */
    s.res = Math.max(0, (s.res||0) - neem);
    boek(db, r.productId, neem, "PICK", r.locationId, null, null, order.nummer);
    r.gepickt += neem;
    order.regels[r.regel].gepickt += neem;
    const res = db.reserveringen.find(x=>x.orderId===order.id && x.regel===r.regel
                                      && x.locationId===r.locationId);
    if(res) res.gepickt += neem;
  }

  if(r.gepickt >= r.qty){
    r.status = "DONE";
  } else {
    /* MANCO. Niet stilletjes doorlopen. Vier dingen tegelijk:
         1. reservering vrijgeven, zodat een ander deze voorraad kan gebruiken
         2. het systeemaantal corrigeren tot wat er echt lag
         3. een teltaak aanmaken, want alleen een mens weet het echte aantal
         4. de orderregel als manco markeren
       Dit is precies het punt waar de meeste zelfbouwsystemen falen. */
    r.status = "MANCO";
    const tekort = r.qty - r.gepickt;
    const or = order.regels[r.regel];
    or.manco = (or.manco||0) + tekort;

    if(s){
      s.res = Math.max(0, (s.res||0) - tekort);
      /* Afboeken kan nooit meer zijn dan wat het systeem denkt te hebben. */
      const afboeken = Math.min(tekort, s.qty);
      if(afboeken > 0)
        boek(db, r.productId, afboeken, "ADJUST", r.locationId, null,
             "MANCO", order.nummer);
    }

    db.taken.push({id:db.taken.length, soort:"CYCLE_COUNT", naam:"Tellen na manco",
      prio:45, status:"TODO", productId:r.productId, van:r.locationId,
      naar:r.locationId, qty:tekort,
      reden:`Manco bij ${order.nummer}: ${tekort} van ${r.qty} niet gevonden op ${db.locaties[r.locationId].code}`,
      at:Date.now()});
    db.log.unshift({at:Date.now(),niveau:"WARN",bron:"picken",
      bericht:`Manco ${tekort}x ${db.artikelen[r.productId].sku} op ${db.locaties[r.locationId].code} (${order.nummer})`});
  }

  if(order.status==="VRIJGEGEVEN") order.status="PICKEN";
  if(job.regels.every(x=>x.status!=="TODO")){
    job.status = "DONE";
    order.status = "GEPICKT";
  }
  return r.status;
}

/* --- inpakken en verzenden ------------------------------------------ */
function pakIn(db, order){
  if(order.status!=="GEPICKT") return false;
  const gewicht = order.regels.reduce((a,r)=>{
    const p=db.artikelNu(r.productId);
    return a + (p.G||0)*r.gepickt;
  },0);
  order.colli = Math.max(1, Math.ceil(gewicht/25000));   /* max 25 kg per doos */
  order.gewicht = gewicht;
  order.status = "INGEPAKT";
  return true;
}
function verzend(db, order){
  if(order.status!=="INGEPAKT") return false;
  order.status = "VERZONDEN";
  order.verzondenOp = Date.now();
  order.track = `3S${String(100000+order.id*7919%899999)}NL`;
  for(const r of order.regels) r.verzonden = r.gepickt;
  return true;
}

/* --- orders aanmaken ------------------------------------------------- */
function maakOrder(db, tijd){
  const [klant,plaats,land,vervoerder] = pick(KLANTEN);
  const [type,typenaam,prio] = pick(ORDERSOORTEN);
  const gem = db.artikelen.map(a=>db.artikelNu(a.id))
    .filter(p=>p.L && beschikbaarTotaal(db,p.id)>3);
  if(!gem.length) return null;
  /* Ook orders zijn scheef verdeeld: dezelfde hardlopers komen elke dag
     terug. Daardoor lopen juist die picklocaties leeg, en dat is precies
     wat het aanvulmechanisme moet opvangen. */
  const kiesArt = wegingSampler(gem, p=>db.artikelen[p.id].vraag || 0.01);
  const nRegels = type==="PROJECT" ? rint(4,9) : type==="WEB" ? rint(1,3) : rint(1,5);
  const regels=[];
  for(let i=0;i<nRegels;i++){
    const p = kiesArt();
    if(!p || regels.some(r=>r.productId===p.id)) continue;
    const max = Math.max(1, Math.min(24, Math.floor(beschikbaarTotaal(db,p.id)*0.4)));
    regels.push({idx:regels.length, productId:p.id, besteld:rint(1,max),
                 gereserveerd:0, gepickt:0, verzonden:0, manco:0});
  }
  if(!regels.length) return null;
  const order = {id:db.orders.length,
    nummer:`ORD-${250000+db.orders.length}`, klant, plaats, land, vervoerder,
    type, typenaam, prio, status:"NIEUW", at:tijd||Date.now(), regels,
    colli:null, gewicht:null, track:null};
  db.orders.push(order);
  return order;
}

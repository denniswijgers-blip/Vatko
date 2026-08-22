/* =====================================================================
   BOUWEN
   Vanaf hier is er geen verschil meer tussen een ingelezen magazijn en
   de demo. Dezelfde structuur, dezelfde rekenregels.
   ===================================================================== */
function koppelAfleiding(db){
  db.herbereken = function(){
    const l = {};
    for(const m of this.metingen){
      if(!l[m.productId] || m.at > l[m.productId].at) l[m.productId] = m;
    }
    this._laatste = l;
  };
  db.artikelNu = function(id){
    const a = this.artikelen[id]; if(!a) return null;
    const m = this._laatste[id];
    return {...a, L:m?m.L:null, W:m?m.W:null, H:m?m.H:null, G:m?m.G:null,
            gemetenOp:m?m.at:null, bron:m?m.bron:null};
  };
  db.herbereken();
  return db;
}

function leegDb(){
  return {zones:[], locaties:[], groepen:[], artikelen:[], metingen:[],
          voorraad:[], boekingen:[], drift:[], taken:[], log:[],
          orders:[], reserveringen:[], pickjobs:[], _laatste:{}, eigen:true};
}

/* Gang, vak en niveau uit een locatiecode halen. Werkt op 01-02-3,
   A.12.4, 1/14/2 en op 011204. Lukt het niet, dan is de volgorde in het
   bestand de looproute - dat is nog altijd beter dan willekeurig. */
function ontleedCode(code, volgnr){
  const delen = String(code).split(/[-_.\/\s]+/).filter(Boolean);
  const nums = delen.map(d=>{ const m = /(\d+)/.exec(d); return m ? +m[1] : null; });
  if(delen.length >= 3 && nums[nums.length-1] !== null && nums[nums.length-2] !== null){
    const niv = nums[nums.length-1], vak = nums[nums.length-2];
    let gang = nums[nums.length-3];
    if(gang === null){
      const s = delen[delen.length-3] || "";
      gang = s ? s.toUpperCase().charCodeAt(0)-64 : 1;
    }
    return {gang, vak, niveau:niv};
  }
  return {gang:1, vak:volgnr+1, niveau:1};
}

function soortNaarType(tekst, code){
  const t = plat(tekst) + " " + plat(code);
  if(/ontvang|receiv|inbound|inkomend|dock/.test(t)) return 2;
  if(/keur|qc|quality|inspect|quarantaine/.test(t))  return 3;
  if(/schade|damage|defect|breuk/.test(t))           return 4;
  if(/expedit|verzend|ship|outbound|uitgaand/.test(t)) return 5;
  if(/bulk|pallet|reserve|voorraadlocatie|stelling/.test(t)) return 1;
  return 0;
}

function bouwEigen(){
  const R = imp.rapport || controleer();
  const db = leegDb();
  const nu = Date.now();

  /* --- zones ------------------------------------------------------- */
  const zoneIndex = new Map();
  const zoneVan = (naam)=>{
    const schoon = (naam||"Magazijn").trim() || "Magazijn";
    const sleutel = schoon.toUpperCase();          /* EXPEDITIE en Expeditie zijn één zone */
    if(!zoneIndex.has(sleutel)){
      zoneIndex.set(sleutel, db.zones.length);
      db.zones.push({id:db.zones.length, code:schoon.slice(0,3).toUpperCase(), naam:schoon});
    }
    return zoneIndex.get(sleutel);
  };

  /* --- locaties ---------------------------------------------------- */
  const locIndex = new Map();
  let i = 0;
  for(const [sleutel, l] of R.locNaam){
    const {gang, vak, niveau} = ontleedCode(l.code, i);
    const vakPos = gang % 2 ? vak : 9999 - vak;      /* snake-route */
    const id = db.locaties.length;
    db.locaties.push({id, code:l.code, zoneId:zoneVan(l.zone),
      typeId:soortNaarType(l.soort, l.code), aisle:gang, bay:vak, level:niveau,
      seq: gang*1e6 + vakPos*100 + niveau*10,
      L:l.L, W:l.W, H:l.H, maxG:l.maxG, actief:1, geschat:l.geschat});
    locIndex.set(sleutel, id);
    i++;
  }
  /* Zonder ontvangst- en expeditielocatie kun je niets ontvangen en
     niets verzenden. Ontbreken ze in het bestand, dan maken we ze. */
  if(!db.locaties.some(l=>l.typeId===2))
    db.locaties.push({id:db.locaties.length, code:"ONTVANGST", zoneId:zoneVan("Expeditie"),
      typeId:2, aisle:0,bay:0,level:0, seq:0, L:8000,W:4000,H:2500,maxG:4e6, actief:1});
  if(!db.locaties.some(l=>l.typeId===5))
    db.locaties.push({id:db.locaties.length, code:"EXP-01", zoneId:zoneVan("Expeditie"),
      typeId:5, aisle:0,bay:0,level:0, seq:0, L:4000,W:2000,H:2000,maxG:2e6, actief:1});
  if(!db.locaties.some(l=>l.typeId===3))
    db.locaties.push({id:db.locaties.length, code:"QC-01", zoneId:zoneVan("Expeditie"),
      typeId:3, aisle:0,bay:0,level:0, seq:0, L:1200,W:800,H:1000,maxG:6e5, actief:1});
  if(!db.locaties.some(l=>l.typeId===4))
    db.locaties.push({id:db.locaties.length, code:"SCHADE", zoneId:zoneVan("Expeditie"),
      typeId:4, aisle:0,bay:0,level:0, seq:0, L:1200,W:800,H:1000,maxG:6e5, actief:1});

  /* --- artikelgroepen en artikelen ---------------------------------- */
  const groepIndex = new Map();
  const groepVan = (naam)=>{
    const s = (naam||"Overig").trim() || "Overig";
    if(!groepIndex.has(s)){
      groepIndex.set(s, db.groepen.length);
      db.groepen.push({id:db.groepen.length, naam:s, telint:180});
    }
    return groepIndex.get(s);
  };
  const artIndex = new Map();
  for(const [sleutel, a] of R.artNaam){
    const id = db.artikelen.length;
    db.artikelen.push({id, sku:a.sku, oms:a.oms, groepId:groepVan(a.groep),
      minQty:a.min, maxQty:a.max || (a.min ? a.min*4 : null),
      stapelbaar:1, barcode:a.barcode || a.sku});
    if(a.L) db.metingen.push({productId:id, at:nu, bron:"SUPPLIER",
      L:a.L, W:a.W, H:a.H, G:a.G, notitie:"Overgenomen uit het aangeleverde bestand"});
    artIndex.set(sleutel, id);
  }
  koppelAfleiding(db);

  /* --- voorraad: mét journaalregel, want dit is ook een mutatie ----- */
  for(const v of (R.voorraadRijen || [])){
    const pid = artIndex.get(v.sku), lid = locIndex.get(v.loc);
    if(pid === undefined || lid === undefined) continue;
    const bestaand = db.voorraad.find(s=>s.productId===pid && s.locationId===lid);
    if(bestaand) bestaand.qty += v.qty;
    else db.voorraad.push({productId:pid, locationId:lid, qty:v.qty});
    db.boekingen.push({at:nu, soort:"IMPORT", productId:pid, van:null, naar:lid,
      qty:v.qty, reden:"Beginvoorraad", ref:"IMPORT"});
  }

  db.log.unshift({at:nu, niveau:"INFO", bron:"import",
    bericht:`Ingelezen: ${db.locaties.length} locaties, ${db.artikelen.length} artikelen, ${db.voorraad.length} voorraadregels`});
  return db;
}

/* --- pad B: magazijn opzetten zonder bestand ------------------------ */
function opzetAantal(){
  return imp.opzet.reduce((a,z)=>a + Math.max(0,z.gangen)*Math.max(0,z.vakken)*Math.max(0,z.niveaus), 0);
}
function bouwUitOpzet(){
  const db = leegDb();
  const nu = Date.now();
  let gang = 1;
  imp.opzet.forEach((z, zi)=>{
    db.zones.push({id:zi, code:z.code, naam:z.naam});
    for(let g=0; g<Math.max(0,z.gangen); g++, gang++){
      for(let v=1; v<=z.vakken; v++){
        for(let n=1; n<=z.niveaus; n++){
          const vakPos = gang % 2 ? v : 9999 - v;
          db.locaties.push({id:db.locaties.length,
            code:`${z.code}-${String(gang).padStart(2,"0")}-${String(v).padStart(2,"0")}-${n}`,
            zoneId:zi, typeId: z.soort === "BL" ? 1 : 0,
            aisle:gang, bay:v, level:n, seq: gang*1e6 + vakPos*100 + n*10,
            L:z.L, W:z.W, H:z.H, maxG:Math.round(z.maxG*1000), actief:1});
        }
      }
    }
  });
  const ex = db.zones.length;
  db.zones.push({id:ex, code:"EX", naam:"Expeditie"});
  [["ONTVANGST",2,8000,4000,2500,4e6],["QC-01",3,1200,800,1000,6e5],
   ["SCHADE",4,1200,800,1000,6e5],["EXP-01",5,4000,2000,2000,2e6]]
   .forEach(([code,ti,L,W,H,maxG])=>db.locaties.push({id:db.locaties.length,
     code, zoneId:ex, typeId:ti, aisle:0,bay:0,level:0, seq:0, L,W,H,maxG, actief:1}));

  /* Artikelen mogen ontbreken: bij een nulmeting ontstaan ze onderweg. */
  const R = imp.bestanden.artikelen ? controleer() : null;
  if(R && R.artNaam.size){
    const groepIndex = new Map();
    const groepVan = (naam)=>{
      const s = (naam||"Overig").trim() || "Overig";
      if(!groepIndex.has(s)){ groepIndex.set(s, db.groepen.length);
        db.groepen.push({id:db.groepen.length, naam:s, telint:180}); }
      return groepIndex.get(s);
    };
    for(const [,a] of R.artNaam){
      const id = db.artikelen.length;
      db.artikelen.push({id, sku:a.sku, oms:a.oms, groepId:groepVan(a.groep),
        minQty:a.min, maxQty:a.max || (a.min ? a.min*4 : null),
        stapelbaar:1, barcode:a.barcode || a.sku});
      if(a.L) db.metingen.push({productId:id, at:nu, bron:"SUPPLIER", L:a.L,W:a.W,H:a.H,G:a.G});
    }
  }
  if(!db.groepen.length) db.groepen.push({id:0, naam:"Nog in te delen", telint:180});
  koppelAfleiding(db);
  db.log.unshift({at:nu, niveau:"INFO", bron:"opzet",
    bericht:`Magazijn opgezet: ${db.locaties.length} locaties in ${db.zones.length} zones`});
  return db;
}

/* --- omschakelen ----------------------------------------------------- */
function zetOver(db, bedrijf){
  DB = db;
  bouwGebruikers(DB);
  maakAanvultaken(DB);
  if(bedrijf) S["merk.klant"].v = bedrijf;
  staat = {pagina:1, zoek:"", filterType:"", filterMaat:"", inslagSku:"", inslagQty:24};
  resetDag();
  imp.stap = "klaar";
  return DB;
}
function terugNaarDemo(){
  startDemo();
  S["merk.klant"].v = "Van Delden Techniek B.V.";
  staat = {pagina:1, zoek:"", filterType:"", filterMaat:"", inslagSku:"", inslagQty:24};
  resetDag();
  imp.stap = "keuze"; imp.bron = null; imp.rapport = null;
  imp.bestanden = {locaties:null, artikelen:null, voorraad:null};
}

/* --- nulmeting: een artikel ontstaat tijdens het tellen -------------- */
function maakArtikelUitScan(db, code){
  const id = db.artikelen.length;
  if(!db.groepen.length) db.groepen.push({id:0, naam:"Nog in te delen", telint:180});
  db.artikelen.push({id, sku:code, oms:"Nieuw bij de nulmeting - nog benoemen en opmeten",
    groepId:0, minQty:null, maxQty:null, stapelbaar:1, barcode:code});
  db.herbereken();
  db.log.unshift({at:Date.now(), niveau:"INFO", bron:"nulmeting",
    bericht:`Nieuw artikel aangemaakt tijdens tellen: ${code}`});
  return db.artikelen[id];
}

/* =====================================================================
   EIGEN GEGEVENS INLEZEN

   Dit scherm is het verschil tussen "kijk eens wat een mooie demo" en
   "kijk, dit is jouw magazijn". Drie situaties komen in de praktijk voor:

     A. De klant heeft bestanden. Excel of CSV, uit het ERP getrokken.
        Nooit met de kolomnamen die jij zou kiezen. Dus herkennen we ze
        zelf en laten we de klant bevestigen.

     B. De klant heeft locaties, maar geen bestand. Alles staat in de
        stelling, niemand heeft het ooit vastgelegd. Dan bouwen we de
        structuur hier op en drukken we de etiketten af.

     C. De klant heeft helemaal niets. Geen locaties, geen voorraadlijst.
        De mensen weten waar het ligt. Dan beginnen we met een nulmeting:
        stellingen labelen, en met de scanner het magazijn in.

   In alle drie de gevallen eindigen we met dezelfde datastructuur als de
   demo. Vanaf dat punt is er geen verschil meer.
   ===================================================================== */

const imp = {
  stap:"keuze", bron:null, bedrijf:"",
  bestanden:{locaties:null, artikelen:null, voorraad:null},
  kolom:{locaties:{}, artikelen:{}, voorraad:{}},
  eenheid:{loc_maat:"mm", art_maat:"mm", loc_gew:"kg", art_gew:"g"},
  standaard:{L:600,W:400,H:350,maxG:50},
  rapport:null, bezig:false, fout:null,
  opzet:[
    {code:"KG", naam:"Kleingoed",     soort:"PL", gangen:4, vakken:20, niveaus:5, L:300,  W:400, H:220,  maxG:12},
    {code:"MV", naam:"Middenvakken",  soort:"PL", gangen:3, vakken:18, niveaus:4, L:600,  W:400, H:350,  maxG:45},
    {code:"PS", naam:"Palletstelling",soort:"BL", gangen:3, vakken:16, niveaus:4, L:1200, W:800, H:1500, maxG:900}
  ]
};

/* --- getal uit een cel, met Nederlandse komma en rommel ------------- */
function getal(v){
  if(v===null || v===undefined) return null;
  if(typeof v==="number") return isFinite(v)?v:null;
  let s = String(v).trim();
  if(!s) return null;
  s = s.replace(/[^0-9,.\-]/g,"");
  if(!s || s==="-") return null;
  if(s.includes(",") && s.includes(".")){
    s = s.lastIndexOf(",") > s.lastIndexOf(".")
      ? s.replace(/\./g,"").replace(",",".")
      : s.replace(/,/g,"");
  } else if(s.includes(",")) s = s.replace(",",".");
  const n = parseFloat(s);
  return isFinite(n) ? n : null;
}

/* =====================================================================
   CSV
   Scheidingsteken raden we: een Nederlandse Excel-export gebruikt de
   puntkomma, een Engelse de komma. Fout raden betekent één kolom met
   alles erin, en dat is precies waar mensen op vastlopen.
   ===================================================================== */
function raadScheiding(regel){
  const kandidaten = [";", ",", "\t", "|"];
  let beste = ";", max = 0;
  for(const c of kandidaten){
    let n = 0, inAanhaling = false;
    for(let i=0;i<regel.length;i++){
      if(regel[i]==='"') inAanhaling = !inAanhaling;
      else if(regel[i]===c && !inAanhaling) n++;
    }
    if(n>max){ max=n; beste=c; }
  }
  return beste;
}

function leesCsv(tekst){
  if(tekst.charCodeAt(0)===0xFEFF) tekst = tekst.slice(1);
  const eersteRegel = tekst.split(/\r?\n/).find(r=>r.trim()) || "";
  const sep = raadScheiding(eersteRegel);
  const rijen = [];
  let rij = [], veld = "", inAanhaling = false;
  for(let i=0;i<tekst.length;i++){
    const c = tekst[i];
    if(inAanhaling){
      if(c === '"'){
        if(tekst[i+1] === '"'){ veld += '"'; i++; }
        else inAanhaling = false;
      } else veld += c;
    } else if(c === '"') inAanhaling = true;
    else if(c === sep){ rij.push(veld); veld = ""; }
    else if(c === "\n"){ rij.push(veld); rijen.push(rij); rij = []; veld = ""; }
    else if(c === "\r"){ /* overslaan */ }
    else veld += c;
  }
  if(veld || rij.length){ rij.push(veld); rijen.push(rij); }
  return rijen.filter(r=>r.some(c=>String(c).trim()!==""));
}

/* =====================================================================
   EXCEL (.xlsx)
   Een xlsx-bestand is een zip met XML erin. De browser kan sinds kort
   zelf uitpakken (DecompressionStream), dus dit kan zonder externe
   bibliotheek - wat belangrijk is, want dit bestand moet offline werken
   in een magazijn zonder wifi.
   ===================================================================== */
async function leesZip(buf){
  const dv = new DataView(buf), u8 = new Uint8Array(buf);
  let eocd = -1;
  for(let i=u8.length-22; i>=0 && i>u8.length-66000; i--){
    if(dv.getUint32(i,true) === 0x06054b50){ eocd = i; break; }
  }
  if(eocd < 0) throw new Error("Dit lijkt geen geldig xlsx-bestand. Sla het in Excel op als 'Excel-werkmap (.xlsx)' of als CSV.");
  const aantal = dv.getUint16(eocd+10, true);
  let p = dv.getUint32(eocd+16, true);
  const uit = {};
  const dec = new TextDecoder();
  for(let i=0;i<aantal;i++){
    if(dv.getUint32(p,true) !== 0x02014b50) break;
    const methode = dv.getUint16(p+10,true);
    const compLen = dv.getUint32(p+20,true);
    const nLen = dv.getUint16(p+28,true);
    const eLen = dv.getUint16(p+30,true);
    const cLen = dv.getUint16(p+32,true);
    const lok  = dv.getUint32(p+42,true);
    const naam = dec.decode(u8.subarray(p+46, p+46+nLen));
    const lnLen = dv.getUint16(lok+26,true), leLen = dv.getUint16(lok+28,true);
    const start = lok+30+lnLen+leLen;
    uit[naam] = {methode, data: u8.subarray(start, start+compLen)};
    p += 46+nLen+eLen+cLen;
  }
  return uit;
}
async function uitpakken(item){
  if(!item) return null;
  if(item.methode === 0) return new TextDecoder().decode(item.data);
  if(typeof DecompressionStream === "undefined")
    throw new Error("Deze browser kan geen xlsx uitpakken. Gebruik Chrome of Edge, of sla het bestand op als CSV.");
  const stroom = new Blob([item.data]).stream()
    .pipeThrough(new DecompressionStream("deflate-raw"));
  return await new Response(stroom).text();
}
const kolomIndex = (ref)=>{
  const m = /^([A-Z]+)/.exec(ref||"");
  if(!m) return 0;
  let n = 0;
  for(const c of m[1]) n = n*26 + (c.charCodeAt(0)-64);
  return n-1;
};

async function leesXlsx(buf){
  const zip = await leesZip(buf);
  const P = new DOMParser();
  const tekst = [];
  const ssXml = await uitpakken(zip["xl/sharedStrings.xml"]);
  if(ssXml){
    const d = P.parseFromString(ssXml, "application/xml");
    for(const si of d.getElementsByTagName("si")){
      let s = "";
      for(const t of si.getElementsByTagName("t")){
        if(t.parentNode && t.parentNode.nodeName === "rPh") continue;
        s += t.textContent;
      }
      tekst.push(s);
    }
  }
  const blad = Object.keys(zip)
    .filter(k=>/^xl\/worksheets\/sheet\d*\.xml$/.test(k))
    .sort((a,b)=>a.length-b.length || a.localeCompare(b))[0];
  if(!blad) throw new Error("Geen werkblad gevonden in dit bestand.");
  const d = P.parseFromString(await uitpakken(zip[blad]), "application/xml");
  const rijen = [];
  for(const r of d.getElementsByTagName("row")){
    const rij = [];
    for(const c of r.getElementsByTagName("c")){
      const i = kolomIndex(c.getAttribute("r"));
      const t = c.getAttribute("t");
      let w = "";
      if(t === "s"){
        const v = c.getElementsByTagName("v")[0];
        w = v ? (tekst[+v.textContent] ?? "") : "";
      } else if(t === "inlineStr"){
        const ts = c.getElementsByTagName("t");
        w = ts.length ? ts[0].textContent : "";
      } else {
        const v = c.getElementsByTagName("v")[0];
        w = v ? v.textContent : "";
      }
      rij[i] = w;
    }
    for(let i=0;i<rij.length;i++) if(rij[i]===undefined) rij[i]="";
    rijen.push(rij);
  }
  return rijen.filter(r=>r.some(c=>String(c).trim()!==""));
}

/* --- één bestand inlezen, ongeacht het soort ------------------------ */
async function leesBestand(file){
  const naam = file.name.toLowerCase();
  let rijen;
  if(naam.endsWith(".xlsx") || naam.endsWith(".xlsm")){
    rijen = await leesXlsx(await file.arrayBuffer());
  } else if(naam.endsWith(".xls")){
    throw new Error("Het oude .xls-formaat kan ik niet lezen. Open het in Excel en sla het op als .xlsx of .csv.");
  } else {
    rijen = leesCsv(await file.text());
  }
  if(rijen.length < 2) throw new Error("Dit bestand heeft geen gegevensregels onder de kopregel.");
  const breedte = Math.max(...rijen.map(r=>r.length));
  const kop = [];
  for(let i=0;i<breedte;i++) kop.push(String(rijen[0][i] ?? "").trim() || `kolom ${i+1}`);
  return {naam:file.name, kop, rijen: rijen.slice(1).map(r=>{
    const uit = [];
    for(let i=0;i<breedte;i++) uit.push(String(r[i] ?? "").trim());
    return uit;
  })};
}

/* =====================================================================
   KOLOMMEN HERKENNEN
   Niemand levert een bestand aan met de kolomnamen die jij wilt. Dus
   raden we, en laten we het resultaat zien zodat de klant het kan
   corrigeren. Raden zonder tonen is hoe imports stilletjes fout gaan.
   ===================================================================== */
const VELDEN = {
  locaties: [
    {k:"code",  naam:"Locatiecode", eis:true,
     syn:["locatie","locatiecode","location","locationcode","loccode","bin","binlocation","binlocatie","plaats","adres","locatienummer","code","magazijnlocatie","stellingplaats"]},
    {k:"zone",  naam:"Zone of gebied",
     syn:["zone","gebied","area","warehouse","magazijn","afdeling","sectie","zonecode"]},
    {k:"soort", naam:"Soort locatie",
     syn:["soort","type","locatietype","locationtype","kind","categorie","soortlocatie"]},
    {k:"L", naam:"Diepte / lengte (binnenmaat)",
     syn:["diepte","depth","lengte","length","l","d","dieptemm","lengtemm"]},
    {k:"W", naam:"Breedte",
     syn:["breedte","width","b","w","breedtemm"]},
    {k:"H", naam:"Hoogte",
     syn:["hoogte","height","h","hoogtemm","vrijehoogte"]},
    {k:"maxG", naam:"Maximaal gewicht",
     syn:["maxgewicht","maximaalgewicht","draagvermogen","maxweight","capaciteit","belasting","gewichtmax","maxkg","maxbelasting"]}
  ],
  artikelen: [
    {k:"sku", naam:"Artikelnummer", eis:true,
     syn:["artikelnummer","artikelnr","artikel","sku","itemcode","item","itemnumber","productcode","productnummer","code","nummer","art","artnr"]},
    {k:"oms", naam:"Omschrijving",
     syn:["omschrijving","omschr","description","naam","artikelomschrijving","benaming","itemdescription","tekst"]},
    {k:"groep", naam:"Artikelgroep",
     syn:["groep","artikelgroep","productgroep","categorie","category","group","itemgroup","hoofdgroep","assortiment"]},
    {k:"L", naam:"Lengte",
     syn:["lengte","length","l","diepte","depth","d","lengtemm"]},
    {k:"W", naam:"Breedte",
     syn:["breedte","width","b","w","breedtemm"]},
    {k:"H", naam:"Hoogte",
     syn:["hoogte","height","h","dikte","hoogtemm"]},
    {k:"G", naam:"Gewicht per stuk",
     syn:["gewicht","weight","g","massa","stukgewicht","gewichtperstuk","nettogewicht","brutogewicht","kg","gram"]},
    {k:"barcode", naam:"Barcode",
     syn:["barcode","ean","eancode","gtin","streepjescode","upc","scancode"]},
    {k:"min", naam:"Minimum op picklocatie",
     syn:["min","minimum","minvoorraad","bestelniveau","aanvuldrempel","minimumvoorraad","meldpunt","minqty"]},
    {k:"max", naam:"Maximum op picklocatie",
     syn:["max","maximum","maxvoorraad","maximumvoorraad","maxqty","bestelniveaumax"]}
  ],
  voorraad: [
    {k:"sku", naam:"Artikelnummer", eis:true,
     syn:["artikelnummer","artikelnr","artikel","sku","itemcode","item","productcode","code","nummer"]},
    {k:"locatie", naam:"Locatiecode", eis:true,
     syn:["locatie","locatiecode","location","bin","plaats","adres","loccode"]},
    {k:"qty", naam:"Aantal", eis:true,
     syn:["aantal","voorraad","qty","quantity","stuks","hoeveelheid","stock","onhand","aanwezig","saldo"]}
  ]
};

const plat = (s)=>String(s||"").toLowerCase()
  .replace(/[èéêë]/g,"e").replace(/[àáâä]/g,"a")
  .replace(/[òóôö]/g,"o").replace(/[ìíîï]/g,"i")
  .replace(/[^a-z0-9]/g,"");

function herkenKolommen(soort, kop){
  const velden = VELDEN[soort];
  const punten = [];
  kop.forEach((h,i)=>{
    const p = plat(h);
    if(!p) return;
    for(const v of velden){
      let s = 0;
      for(const syn of v.syn){
        if(p === syn){ s = Math.max(s, 100); }
        else if(p.startsWith(syn) && syn.length >= 3){ s = Math.max(s, 70); }
        else if(p.includes(syn) && syn.length >= 4){ s = Math.max(s, 55); }
      }
      if(s) punten.push({veld:v.k, kol:i, score:s});
    }
  });
  punten.sort((a,b)=>b.score-a.score);
  const uit = {}, gebruikt = new Set();
  for(const p of punten){
    if(uit[p.veld] !== undefined || gebruikt.has(p.kol)) continue;
    uit[p.veld] = p.kol; gebruikt.add(p.kol);
  }
  return uit;
}

/* --- raden of iemand in mm of cm werkt, en in gram of kilo ----------
   Dit moet per soort bestand anders. Een stellingvak van 40 is altijd
   centimeters (40 mm diep bestaat niet), maar een artikel van 40 is
   bijna altijd millimeters. Dezelfde regel voor allebei gaat gegarandeerd
   een keer mis, en dan staan er pallets in een bakkenstelling. */
function raadMaat(waarden, soort){
  const g = waarden.map(getal).filter(n=>n>0);
  if(!g.length) return "mm";
  g.sort((a,b)=>a-b);
  const mediaan = g[Math.floor(g.length/2)];
  const hoog = g[Math.floor(g.length*0.9)], max = g[g.length-1];
  if(soort === "locaties"){
    if(mediaan < 3)   return "m";
    if(mediaan < 200) return "cm";     /* een vak van 150 mm diep bestaat niet */
    return "mm";
  }
  if(hoog < 3)  return "m";
  if(max > 400) return "mm";           /* een artikel van 4 meter in cm: nee */
  if(max <= 100) return "cm";
  return "mm";
}
function raadGewicht(waarden, soort){
  const g = waarden.map(getal).filter(n=>n>0);
  if(!g.length) return soort === "locaties" ? "kg" : "g";
  g.sort((a,b)=>a-b);
  const mediaan = g[Math.floor(g.length/2)], max = g[g.length-1];
  if(soort === "locaties") return max > 20000 ? "g" : "kg";
  if(max > 2000) return "g";
  return mediaan < 300 ? "kg" : "g";
}

const naarMm = {mm:1, cm:10, m:1000};
const naarG   = {g:1, kg:1000};

/* =====================================================================
   CONTROLEREN
   Het rapport is belangrijker dan de import zelf. Een klant die ziet
   dat er 41 artikelen zonder maat zijn, snapt meteen waarom de eerste
   week meten is. Een import die stilletjes doorgaat, wreekt zich later.
   ===================================================================== */
function nieuwProbleem(lijst, sleutel, tekst, ernst="let"){
  let p = lijst.find(x=>x.sleutel===sleutel);
  if(!p) lijst.push(p = {sleutel, tekst, ernst, n:0, voorbeeld:[]});
  return p;
}
function noteer(lijst, sleutel, tekst, voorbeeld, ernst="let"){
  const p = nieuwProbleem(lijst, sleutel, tekst, ernst);
  p.n++;
  if(p.voorbeeld.length < 3) p.voorbeeld.push(voorbeeld);
}

function controleer(){
  const R = {locaties:{rijen:0, goed:0, problemen:[]},
             artikelen:{rijen:0, goed:0, problemen:[]},
             voorraad:{rijen:0, goed:0, problemen:[]},
             locNaam:new Map(), artNaam:new Map(), klaar:false};

  /* --- locaties ---------------------------------------------------- */
  const B = imp.bestanden.locaties, K = imp.kolom.locaties;
  const fLoc = naarMm[imp.eenheid.loc_maat], fLocG = naarG[imp.eenheid.loc_gew];
  if(B){
    R.locaties.rijen = B.rijen.length;
    for(const r of B.rijen){
      const code = (r[K.code] || "").trim();
      if(!code){ noteer(R.locaties.problemen,"geencode","Rij zonder locatiecode; wordt overgeslagen","(lege rij)","fout"); continue; }
      if(R.locNaam.has(code.toUpperCase())){
        noteer(R.locaties.problemen,"dubbel","Locatiecode komt meer dan één keer voor; alleen de eerste telt",code,"fout"); continue;
      }
      const L = getal(r[K.L]) * fLoc, W = getal(r[K.W]) * fLoc, H = getal(r[K.H]) * fLoc;
      const mg = getal(r[K.maxG]);
      const zonder = !(L>0 && W>0 && H>0);
      if(zonder) noteer(R.locaties.problemen,"geenmaat",
        "Locatie zonder afmetingen; krijgt de standaardmaat die je hieronder invult", code);
      if(!(mg>0)) noteer(R.locaties.problemen,"geengewicht",
        "Locatie zonder maximaal gewicht; krijgt het standaardgewicht", code);
      R.locNaam.set(code.toUpperCase(), {
        code, zone:(r[K.zone]||"").trim(), soort:(r[K.soort]||"").trim(),
        L: zonder ? imp.standaard.L : Math.round(L),
        W: zonder ? imp.standaard.W : Math.round(W),
        H: zonder ? imp.standaard.H : Math.round(H),
        maxG: mg>0 ? Math.round(mg*fLocG) : imp.standaard.maxG*1000,
        geschat: zonder
      });
      R.locaties.goed++;
    }
  }

  /* --- artikelen ---------------------------------------------------- */
  const A = imp.bestanden.artikelen, KA = imp.kolom.artikelen;
  const fArt = naarMm[imp.eenheid.art_maat], fArtG = naarG[imp.eenheid.art_gew];
  if(A){
    R.artikelen.rijen = A.rijen.length;
    for(const r of A.rijen){
      const sku = (r[KA.sku] || "").trim();
      if(!sku){ noteer(R.artikelen.problemen,"geensku","Rij zonder artikelnummer; wordt overgeslagen","(lege rij)","fout"); continue; }
      if(R.artNaam.has(sku.toUpperCase())){
        noteer(R.artikelen.problemen,"dubbel","Artikelnummer komt meer dan één keer voor; alleen de eerste telt",sku,"fout"); continue;
      }
      const L = getal(r[KA.L])*fArt, W = getal(r[KA.W])*fArt,
            H = getal(r[KA.H])*fArt, G = getal(r[KA.G])*fArtG;
      const gemeten = L>0 && W>0 && H>0 && G>0;
      if(!gemeten) noteer(R.artikelen.problemen,"nietgemeten",
        "Artikel zonder complete maat of gewicht; komt op de lijst 'nog opmeten'", sku);
      R.artNaam.set(sku.toUpperCase(), {
        sku, oms:(r[KA.oms]||"").trim() || sku,
        groep:(r[KA.groep]||"").trim() || "Overig",
        L:gemeten?Math.round(L):null, W:gemeten?Math.round(W):null,
        H:gemeten?Math.round(H):null, G:gemeten?Math.round(G):null,
        barcode:(r[KA.barcode]||"").trim() || null,
        min: getal(r[KA.min]) || null, max: getal(r[KA.max]) || null
      });
      R.artikelen.goed++;
    }
  }

  /* --- voorraad ----------------------------------------------------- */
  const V = imp.bestanden.voorraad, KV = imp.kolom.voorraad;
  R.voorraadRijen = [];
  if(V){
    R.voorraad.rijen = V.rijen.length;
    for(const r of V.rijen){
      const sku = (r[KV.sku]||"").trim().toUpperCase();
      const loc = (r[KV.locatie]||"").trim().toUpperCase();
      const q = getal(r[KV.qty]);
      if(!sku || !loc){ noteer(R.voorraad.problemen,"leeg","Rij zonder artikel of locatie","(lege rij)","fout"); continue; }
      if(!R.artNaam.has(sku)){ noteer(R.voorraad.problemen,"onbekendart",
        "Voorraad op een artikel dat niet in het artikelbestand staat", sku, "fout"); continue; }
      if(!R.locNaam.has(loc)){ noteer(R.voorraad.problemen,"onbekendloc",
        "Voorraad op een locatie die niet in het locatiebestand staat", loc, "fout"); continue; }
      if(!(q>0)){ noteer(R.voorraad.problemen,"nul","Regel met nul of geen aantal; overgeslagen", sku); continue; }
      R.voorraadRijen.push({sku, loc, qty:Math.round(q)});
      R.voorraad.goed++;
    }
  }

  R.klaar = R.locaties.goed > 0;
  imp.rapport = R;
  return R;
}

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

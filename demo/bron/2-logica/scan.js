/* =====================================================================
   SCANMODUS - het scherm voor op de vloer

   Ontwerpregels die uit de praktijk komen, niet uit een ontwerpboek:
     - een handscanner gedraagt zich als een toetsenbord: hij "typt" de
       code en drukt op enter. Er is dus geen aparte techniek nodig.
     - de cursor moet ALTIJD in het invoerveld staan. Raakt hij kwijt,
       dan lijkt de scanner stuk. Vandaar het terugzetten van de focus.
     - eerst de locatie scannen, dan pas het artikel. Anders pakt iemand
       van het verkeerde schap en klopt je voorraad niet meer.
     - piep bij goed, buzz bij fout. Met oordoppen in en een heftruck
       ernaast kijk je niet naar een tekstregel.
     - grote knoppen. Mensen werken met handschoenen aan.
   ===================================================================== */

const scan = {
  actief:false, taak:"PICKEN", stap:"LOCATIE", job:null, regel:null,
  locatie:null, artikel:null, aantal:0, bericht:null, berichtSoort:"ok", nulmeting:false,
  gescand:[], gebruiker:null
};

/* --- geluid: piep bij goed, buzz bij fout ---------------------------- */
let audioCtx = null;
function toon(frequentie, duur, soort="sine"){
  try{
    audioCtx = audioCtx || new (window.AudioContext||window.webkitAudioContext)();
    const o = audioCtx.createOscillator(), g = audioCtx.createGain();
    o.type = soort; o.frequency.value = frequentie;
    g.gain.setValueAtTime(0.14, audioCtx.currentTime);
    g.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime+duur);
    o.connect(g); g.connect(audioCtx.destination);
    o.start(); o.stop(audioCtx.currentTime+duur);
  }catch(e){ /* geluid is een extraatje, nooit een blokkade */ }
}
const piep  = ()=>toon(1180, 0.09);
const buzz  = ()=>{ toon(180, 0.22, "square"); if(navigator.vibrate) navigator.vibrate(150); };
const klaar = ()=>{ toon(880,0.09); setTimeout(()=>toon(1320,0.13), 95); };

function scanMelding(tekst, soort="ok"){
  scan.bericht = tekst; scan.berichtSoort = soort;
  if(soort==="fout") buzz(); else if(soort==="klaar") klaar(); else piep();
}

/* --- wat is er gescand? ---------------------------------------------- */
function herkenScan(code){
  code = (code||"").trim();
  if(!code) return {soort:"leeg"};
  const loc = DB.locaties.find(l=>l.code.toLowerCase()===code.toLowerCase());
  if(loc) return {soort:"locatie", loc};
  const art = DB.artikelen.find(a=>a.barcode===code
                              || a.sku.toLowerCase()===code.toLowerCase());
  if(art) return {soort:"artikel", art};
  const gb = DB.gebruikers.find(g=>g.badge===code);
  if(gb) return {soort:"gebruiker", gb};
  return {soort:"onbekend", code};
}

/* --- volgende pickregel ophalen -------------------------------------- */
function volgendeRegel(){
  const jobs = DB.pickjobs.filter(j=>j.status==="TODO")
    .sort((a,b)=>a.prio-b.prio || a.id-b.id);
  for(const j of jobs){
    const r = j.regels.find(x=>x.status==="TODO");
    if(r) return {job:j, regel:r};
  }
  return null;
}

function scanStart(taak){
  scan.actief = true; scan.taak = taak || "PICKEN";
  scan.nulmeting = getB("opstart.onbekend_aanmaken");
  scan.bericht = null; scan.gescand = [];
  scanVolgende();
  document.body.classList.add("scanmodus");
}
function scanStop(){
  scan.actief = false;
  document.body.classList.remove("scanmodus");
  location.hash = "#dashboard";
}

function scanVolgende(){
  scan.locatie = null; scan.artikel = null; scan.aantal = 0;
  if(scan.taak==="PICKEN"){
    const v = volgendeRegel();
    if(!v){ scan.job=null; scan.regel=null; scan.stap="KLAAR"; return; }
    scan.job = v.job; scan.regel = v.regel; scan.stap = "LOCATIE";
  } else if(scan.taak==="INSLAG"){
    scan.stap = "ARTIKEL";
  } else if(scan.taak==="TELLEN"){
    scan.stap = "LOCATIE";
  } else {
    scan.stap = "VRIJ";
  }
}

/* --- de kern: één invoerveld, gedrag hangt af van de stap ------------ */
function verwerkScan(code){
  let h = herkenScan(code);
  if(h.soort==="leeg") return;

  /* Een badge werkt altijd: wisselen van gebruiker zonder uitloggen. */
  if(h.soort==="gebruiker"){
    scan.gebruiker = h.gb; HUIDIGE = h.gb;
    scanMelding(`Ingelogd als ${h.gb.naam}`);
    return;
  }

  if(scan.taak==="VRIJ" || scan.stap==="VRIJ"){
    if(h.soort==="locatie"){ scan.locatie = h.loc; scanMelding(`Locatie ${h.loc.code}`); }
    else if(h.soort==="artikel"){ scan.artikel = h.art; scanMelding(`${h.art.sku}`); }
    else scanMelding(`Onbekende code: ${h.code}`, "fout");
    return;
  }

  /* ---------------- PICKEN ---------------- */
  if(scan.taak==="PICKEN"){
    if(!scan.regel){ scanMelding("Geen openstaande pickregels", "fout"); return; }
    const doelLoc = DB.locaties[scan.regel.locationId];
    const doelArt = DB.artikelen[scan.regel.productId];

    if(scan.stap==="LOCATIE"){
      if(h.soort==="onbekend"){
        scanMelding(`Onbekende code: ${h.code}. Label onleesbaar of locatie niet in het systeem.`, "fout");
        return;
      }
      if(h.soort!=="locatie"){ scanMelding("Scan eerst de locatie waar je staat", "fout"); return; }
      if(h.loc.id !== doelLoc.id){
        scanMelding(`Verkeerde locatie. Je staat bij ${h.loc.code}, je moet naar ${doelLoc.code}.`, "fout");
        return;
      }
      scan.locatie = h.loc; scan.stap = "ARTIKEL";
      scanMelding(`${h.loc.code} — scan nu het artikel`);
      return;
    }
    if(scan.stap==="ARTIKEL"){
      if(h.soort==="onbekend"){
        scanMelding(`Onbekende code: ${h.code}. Label onleesbaar of artikel niet in het systeem.`, "fout");
        return;
      }
      if(h.soort!=="artikel"){ scanMelding("Scan het artikel, niet de locatie", "fout"); return; }
      if(h.art.id !== doelArt.id){
        scanMelding(`Verkeerd artikel. Dit is ${h.art.sku}, gevraagd is ${doelArt.sku}.`, "fout");
        return;
      }
      scan.artikel = h.art;
      scan.aantal = scan.regel.qty - scan.regel.gepickt;
      scan.stap = "AANTAL";
      scanMelding(`${h.art.sku} — bevestig het aantal`);
      return;
    }
  }

  /* ---------------- INSLAG ---------------- */
  if(scan.taak==="INSLAG"){
    if(scan.stap==="ARTIKEL"){
      if(h.soort!=="artikel"){ scanMelding("Scan het artikel dat je wilt inslaan", "fout"); return; }
      const p = DB.artikelNu(h.art.id);
      if(!p.L){ scanMelding(`${h.art.sku} is nooit opgemeten — meet het eerst op`, "fout"); return; }
      scan.artikel = h.art; scan.aantal = 12; scan.stap = "INSLAG_AANTAL";
      scanMelding(`${h.art.sku} — hoeveel sla je in?`);
      return;
    }
    if(scan.stap==="INSLAG_LOCATIE"){
      if(h.soort!=="locatie"){ scanMelding("Scan de locatie waar je het neerzet", "fout"); return; }
      const v = voorstelInslag(DB, scan.artikel.id, scan.aantal, 40);
      const gekozen = v.find(x=>x.loc.id===h.loc.id);
      if(!gekozen){
        scanMelding(`Hier past het niet, of de locatie zit vol. Kies een voorgestelde plek.`, "fout");
        return;
      }
      const neem = Math.min(scan.aantal, gekozen.vrij);
      boek(DB, scan.artikel.id, neem, "PUTAWAY", null, h.loc.id, null, "Scan inslag");
      maakAanvultaken(DB);
      scanMelding(`${neem} x ${scan.artikel.sku} ingeslagen op ${h.loc.code}`, "klaar");
      scanVolgende();
      return;
    }
  }

  /* ---------------- TELLEN ---------------- */
  if(scan.taak==="TELLEN"){
    if(scan.stap==="LOCATIE"){
      if(h.soort!=="locatie"){ scanMelding("Scan de locatie die je gaat tellen", "fout"); return; }
      scan.locatie = h.loc; scan.stap = "TEL_ARTIKEL";
      scanMelding(`${h.loc.code} — scan het artikel`);
      return;
    }
    if(scan.stap==="TEL_ARTIKEL"){
      /* Nulmeting: bij een magazijn dat nooit iets vastlegde is bijna elke
         code onbekend. Weigeren betekent dat het tellen stilvalt. */
      if(h.soort==="onbekend" && getB("opstart.onbekend_aanmaken")){
        h = {soort:"artikel", art: maakArtikelUitScan(DB, h.code), nieuw:true};
      }
      if(h.soort!=="artikel"){ scanMelding("Scan het artikel", "fout"); return; }
      scan.artikel = h.art;
      if(h.nieuw){
        scan.aantal = 0; scan.stap = "TEL_AANTAL";
        scanMelding(`Nieuw artikel ${h.art.sku} aangemaakt — hoeveel liggen er?`, "waarschuw");
        return;
      }
      const s = DB.voorraad.find(x=>x.productId===h.art.id && x.locationId===scan.locatie.id);
      scan.aantal = s ? s.qty : 0;
      scan.stap = "TEL_AANTAL";
      scanMelding(`${h.art.sku} — tel en vul het echte aantal in`);
      return;
    }
  }

  scanMelding(`Onverwachte scan op deze stap`, "fout");
}

/* --- bevestigen van het aantal --------------------------------------- */
function scanBevestig(aantal){
  aantal = Math.max(0, parseInt(aantal,10) || 0);

  if(scan.taak==="PICKEN" && scan.stap==="AANTAL"){
    const st = bevestigPick(DB, scan.job, scan.regel.nr, aantal);
    scan.gescand.unshift({tijd:Date.now(),
      tekst:`${DB.locaties[scan.regel.locationId].code} · ${DB.artikelen[scan.regel.productId].sku} · ${aantal} st`,
      soort: st==="MANCO" ? "manco" : "ok"});
    if(st==="MANCO") scanMelding(`Manco vastgelegd. Reservering vrijgegeven en teltaak aangemaakt.`, "fout");
    else scanMelding(`Afgemeld: ${aantal} st`, "klaar");
    scanVolgende();
    return;
  }

  if(scan.taak==="INSLAG" && scan.stap==="INSLAG_AANTAL"){
    scan.aantal = Math.max(1, aantal);
    scan.stap = "INSLAG_LOCATIE";
    scanMelding(`Loop naar een van de voorgestelde plekken en scan die`);
    return;
  }

  if(scan.taak==="TELLEN" && scan.stap==="TEL_AANTAL"){
    const s = DB.voorraad.find(x=>x.productId===scan.artikel.id
                                && x.locationId===scan.locatie.id);
    const was = s ? s.qty : 0;
    const verschil = aantal - was;
    /* Bij een nulmeting is er geen "verschil": er was nog niets vastgelegd.
       Dat hoort ook zo in het journaal te staan, anders lijkt de eerste dag
       van een nieuwe klant vol telfouten te zitten. */
    const nul = was === 0 && scan.nulmeting;
    if(verschil !== 0){
      const reden = nul ? "NULMETING" : "TELVERSCHIL";
      const ref   = nul ? "Opstartinventarisatie" : "Cyclustelling";
      if(verschil > 0) boek(DB, scan.artikel.id, verschil, "COUNT", null, scan.locatie.id, reden, ref);
      else             boek(DB, scan.artikel.id, -verschil, "COUNT", scan.locatie.id, null, reden, ref);
      scan.gescand.unshift({tijd:Date.now(),
        tekst: nul ? `${scan.locatie.code} · ${scan.artikel.sku} · vastgelegd: ${aantal}`
                   : `${scan.locatie.code} · ${scan.artikel.sku} · was ${was}, geteld ${aantal}`,
        soort: nul ? "ok" : "manco"});
      if(nul) scanMelding(`${aantal} st vastgelegd op ${scan.locatie.code}`, "klaar");
      else scanMelding(`Verschil van ${verschil>0?"+":""}${verschil} geboekt met reden TELVERSCHIL`, "fout");
    } else {
      scan.gescand.unshift({tijd:Date.now(),
        tekst:`${scan.locatie.code} · ${scan.artikel.sku} · klopt (${aantal})`, soort:"ok"});
      scanMelding(`Telling klopt`, "klaar");
    }
    DB.locaties[scan.locatie.id].geteldOp = Date.now();
    scanVolgende();
    return;
  }
}

function scanOverslaan(){
  if(scan.taak==="PICKEN" && scan.regel){
    /* Overslaan is geen manco: de regel blijft staan, je gaat er later heen. */
    const job = scan.job;
    const idx = job.regels.indexOf(scan.regel);
    job.regels.push(job.regels.splice(idx,1)[0]);
    scanMelding("Regel achteraan gezet");
  }
  scanVolgende();
}

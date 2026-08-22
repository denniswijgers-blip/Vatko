/* =====================================================================
   KLIKKEN

   Eén afhandelaar voor de hele demo. Dat is met opzet: schermen worden
   steeds opnieuw getekend, dus knoppen die hun eigen luisteraar hebben
   raken die kwijt. Deze hangt aan het document en blijft dus staan.

   Alles wat klikbaar is draagt een data-attribuut (data-actie,
   data-pagina, data-inslaan, ...). Zoek je waar een knop heen gaat, zoek
   dan hier op de naam van dat attribuut.
   ===================================================================== */

/* --- alle klikken op één plek --------------------------------------- */
document.addEventListener("click", (e)=>{
  const t = e.target.closest("[data-actie],[data-pagina],[data-drift],[data-inslaan],"
    + "[data-meet],[data-taak],[data-sim],[data-order],[data-pick],[data-login],"
    + "[data-scan-taak],[data-scan-werk],[data-scan-uit],[data-scan-bevestig],[data-aantal-stap],[data-scan-skip],[data-imp-actie],[data-menu-smal],[data-palet-open],[data-palet-kies],[data-ga],[data-advies],[data-pickplek]");
  if(!t) return;

  if(t.hasAttribute("data-menu-smal")){ smalMenu = !smalMenu;
    document.body.classList.toggle("smal", smalMenu); return; }
  if(t.hasAttribute("data-palet-open")){ paletOpen(); return; }
  if(t.dataset.paletKies !== undefined){ paletGa(+t.dataset.paletKies); return; }
  if(t.dataset.ga){ location.hash = t.dataset.ga; return; }
  if(t.dataset.actie === "thema"){
    e.preventDefault();
    const nu = document.documentElement.getAttribute("data-theme");
    const donker = nu ? nu==="dark" : matchMedia("(prefers-color-scheme: dark)").matches;
    document.documentElement.setAttribute("data-theme", donker?"light":"dark");
    return;
  }
  if(t.dataset.actie === "reset"){
    if(!confirm("De hele demo-omgeving wordt opnieuw opgebouwd. Doorgaan?")) return;
    startDemo(); staat.pagina=1; teken();
    melding("Demo opnieuw opgebouwd. Alles staat weer op begin."); return;
  }
  if(t.dataset.actie === "wis"){
    staat.zoek=""; staat.filterType=""; staat.filterMaat=""; staat.pagina=1; teken(); return;
  }
  if(t.dataset.actie === "instellingen-opslaan"){
    for(const inp of document.querySelectorAll("[data-inst]")) S[inp.dataset.inst].v = inp.value;
    teken(); melding("Instellingen opgeslagen. Ze werken direct door in de berekeningen.");
    return;
  }
  if(t.dataset.impActie){
    e.preventDefault();
    const a = t.dataset.impActie;
    if(a==="kies"){ imp.bron = t.dataset.bron; imp.fout=null; teken(); return; }
    if(a==="controleer"){
      try{
        const R = controleer();
        teken();
        melding(R.klaar
          ? `Gecontroleerd: ${fmt(R.locaties.goed)} locaties, ${fmt(R.artikelen.goed)} artikelen, ${fmt(R.voorraad.goed)} voorraadregels bruikbaar.`
          : "Geen bruikbare locaties gevonden. Controleer de kolomkeuze hierboven.",
          R.klaar ? "ok" : "fout");
      }catch(err){ melding("Controleren mislukt: "+err.message, "fout"); }
      return;
    }
    if(a==="overnemen"){
      try{
        controleer();
        zetOver(bouwEigen(), imp.bedrijf);
        location.hash = "#dashboard"; teken();
        melding(`Overgenomen. Je draait nu op ${fmt(DB.locaties.length)} locaties en ${fmt(DB.artikelen.length)} artikelen.`);
      }catch(err){ melding("Overnemen mislukt: "+err.message, "fout"); }
      return;
    }
    if(a==="terug"){
      if(!confirm("Terug naar de demo-omgeving van Van Delden? De ingelezen gegevens verdwijnen.")) return;
      terugNaarDemo(); location.hash = "#demo"; teken();
      melding("Terug op de demo-omgeving."); return;
    }
    if(a==="opzet-erbij"){
      imp.opzet.push({code:"NW", naam:"Nieuwe zone", soort:"PL",
        gangen:2, vakken:16, niveaus:4, L:600, W:400, H:350, maxG:45});
      teken(); return;
    }
    if(a==="opzet-weg"){ imp.opzet.splice(+t.dataset.i,1); teken(); return; }
    if(a==="opzet-bouw"){
      try{
        zetOver(bouwUitOpzet(), imp.bedrijf);
        location.hash = "#etiketten"; teken();
        melding(`Magazijn opgezet: ${fmt(DB.locaties.length)} locaties. Print nu de etiketten.`);
      }catch(err){ melding("Opzetten mislukt: "+err.message, "fout"); }
      return;
    }
    return;
  }
  if(t.dataset.pagina){ staat.pagina = +t.dataset.pagina; teken(); return; }

  if(t.dataset.drift){
    DB.drift[+t.dataset.drift].status = t.dataset.status;
    teken(); melding("Melding afgehandeld."); return;
  }
  if(t.dataset.inslaan){
    const loc = DB.locaties[+t.dataset.inslaan];
    try{
      boek(DB, +t.dataset.product, +t.dataset.qty, "PUTAWAY", null, loc.id, null, "Handmatige inslag");
      maakAanvultaken(DB); teken();
      melding(`${t.dataset.qty} st ingeslagen op ${loc.code}.`);
    }catch(err){ melding("Inslag mislukt: "+err.message, "fout"); }
    return;
  }
  if(t.dataset.meet){
    const pid = +t.dataset.meet;
    const v = {};
    for(const veld of ["L","W","H","G"]){
      const inp = document.querySelector(`.meet[data-pid="${pid}"][data-veld="${veld}"]`);
      v[veld] = parseInt(inp.value, 10);
    }
    if(!v.L||!v.W||!v.H||!v.G){ melding("Vul alle vier de waarden in.", "fout"); return; }
    const alert = legMetingVast(DB, pid, v.L, v.W, v.H, v.G, "RECEIPT");
    teken();
    if(alert) melding(`Meting opgeslagen. LET OP: volume ${alert.dVol>0?"+":""}${alert.dVol}%, `
      + `gewicht ${alert.dGew>0?"+":""}${alert.dGew}% ten opzichte van de vorige meting. `
      + alert.gevolg, "waarschuw");
    else melding("Meting opgeslagen.");
    return;
  }
  if(t.hasAttribute("data-scan-uit")){ scanStop(); return; }
  if(t.dataset.scanTaak){ scanStart(t.dataset.scanTaak); teken(); return; }
  if(t.hasAttribute("data-scan-werk")){
    /* Zet echt werk klaar: order aanmaken, reserveren, vrijgeven.
       Geen namaak - het loopt door dezelfde functies als de dagsimulatie. */
    let n = 0;
    for(const o of DB.orders.filter(o=>o.status==="GERESERVEERD")) { if(geefVrij(DB,o)) n++; }
    while(n < 2){
      const o = maakOrder(DB, Date.now());
      if(!o) break;
      reserveer(DB, o);
      if(geefVrij(DB, o)) n++; else break;
    }
    scanStart("PICKEN"); teken();
    return;
  }
  if(t.hasAttribute("data-scan-skip")){ scanOverslaan(); teken(); return; }
  if(t.dataset.aantalStap){
    const inp = document.getElementById("scanAantal");
    if(inp) inp.value = Math.max(0, (+inp.value||0) + (+t.dataset.aantalStap));
    return;
  }
  if(t.hasAttribute("data-scan-bevestig")){
    const inp = document.getElementById("scanAantal");
    scanBevestig(t.hasAttribute("data-nul") ? 0 : (inp ? inp.value : 0));
    teken(); return;
  }
  if(t.dataset.login){
    logIn(DB.gebruikers[+t.dataset.login]);
    teken(); melding(`Je werkt nu als ${HUIDIGE.naam} (${ROLLEN[HUIDIGE.rol].naam}).`);
    return;
  }
  if(t.dataset.sim){
    const a = t.dataset.sim;
    if(a==="start") startDag();
    else if(a==="pauze") pauzeerDag();
    else if(a==="uur"){ pauzeerDag(); stapUur(); }
    else if(a==="reset"){ resetDag(); }
    teken(); return;
  }
  if(t.dataset.order){
    const o = DB.orders[+t.dataset.order];
    const stap = t.dataset.stap;
    try{
      if(stap==="reserveer"){
        const st = reserveer(DB, o);
        melding(st==="GERESERVEERD" ? "Voorraad gereserveerd op concrete locaties."
          : "Niet alles kon gereserveerd worden. De order wacht op voorraad.",
          st==="GERESERVEERD"?"ok":"waarschuw");
      }
      else if(stap==="vrijgeef"){ geefVrij(DB,o); melding("Vrijgegeven. De pickopdracht staat klaar op de vloer."); }
      else if(stap==="pick"){ location.hash="#picken"; return; }
      else if(stap==="pak"){ pakIn(DB,o); melding(`Ingepakt: ${o.colli} colli, ${(o.gewicht/1000).toFixed(1)} kg.`); }
      else if(stap==="verzend"){ verzend(DB,o); melding(`Verzonden met zendingnummer ${o.track}.`); }
      teken();
    }catch(err){ melding("Mislukt: "+err.message,"fout"); }
    return;
  }
  if(t.dataset.pick){
    const job = DB.pickjobs[+t.dataset.pick];
    try{
      const st = bevestigPick(DB, job, +t.dataset.regel, +t.dataset.aantal);
      teken();
      melding(st==="MANCO"
        ? "Manco vastgelegd: reservering vrijgegeven, correctie geboekt en onderzoekstaak aangemaakt."
        : "Regel afgemeld en voorraad geboekt.", st==="MANCO"?"waarschuw":"ok");
    }catch(err){ melding("Afmelden mislukt: "+err.message,"fout"); }
    return;
  }
  if(t.dataset.taak){
    const taak = DB.taken[+t.dataset.taak];
    try{
      if(taak.soort==="CYCLE_COUNT"){
        /* Tellen boekt niets: het legt alleen vast dat er gekeken is.
           Een echt telverschil ontstaat in de scanmodus. */
        DB.locaties[taak.naar].geteldOp = Date.now();
        taak.status = "DONE";
        DB.log.unshift({at:Date.now(), niveau:"INFO", bron:"tellen",
          bericht:`${DB.locaties[taak.naar].code} geteld, geen verschil`});
        teken(); melding(`${DB.locaties[taak.naar].code} geteld en afgetekend.`);
        return;
      }
      boek(DB, taak.productId, taak.qty, "MOVE", taak.van, taak.naar, null, `Taak ${taak.id}`);
      taak.status = "DONE"; teken();
      melding(taak.soort==="SAMENVOEG"
        ? `Samengevoegd op ${DB.locaties[taak.naar].code}. ${DB.locaties[taak.van].code} is nu vrij.`
        : "Taak afgemeld en voorraad geboekt.");
    }catch(err){ melding("Afmelden mislukt: "+err.message, "fout"); }
    return;
  }
  if(t.dataset.pickplek !== undefined){
    const z = (DB.zonderPick||[])[+t.dataset.pickplek];
    if(!z) return;
    DB.taken.push({id:DB.taken.length, soort:"PICKPLEK", naam:"Picklocatie inrichten",
      prio:18, status:"TODO", productId:z.pid, van:z.van, naar:z.naar, qty:z.qty,
      automatisch:false, aanleiding:"hardloper zonder vak",
      reden:`${DB.artikelen[z.pid].sku} gaat ${z.perDag.toFixed(1)} st per dag en lag alleen in bulk`,
      at:Date.now()});
    const p2 = DB.artikelen[z.pid];
    if(!p2.minQty){ p2.minQty = Math.max(1, Math.round(z.qty/2)); p2.maxQty = z.qty*2; }
    teken();
    melding(`Taak klaargezet: ${fmt(z.qty)} st naar ${DB.locaties[z.naar].code}.`);
    return;
  }
  if(t.dataset.advies !== undefined){
    const a = DB.adviezen[+t.dataset.advies];
    if(!a) return;
    const p = DB.artikelen[a.pid];
    if(t.dataset.keuze === "neem"){
      p.minQty = a.zou; p.maxQty = a.maxZou;
      DB.log.unshift({at:Date.now(), niveau:"INFO", bron:"advies",
        bericht:`${p.sku}: aanvuldrempel van ${a.nu} naar ${a.zou} gezet op basis van ${a.perDag.toFixed(1)} st per dag`});
      teken(); melding(`Drempel van ${esc(p.sku)} staat nu op ${a.zou}.`);
    } else {
      p.drempelAkkoord = true;
      teken(); melding(`${esc(p.sku)}: advies genegeerd, dit artikel wordt niet meer voorgesteld.`);
    }
    return;
  }
});

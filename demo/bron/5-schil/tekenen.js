/* =====================================================================
   TEKENEN

   Welk scherm komt er in beeld, en wat gebeurt er daarna: de navigatie
   bijwerken, de cijfers laten oplopen, een melding tonen.
   ===================================================================== */

function tekenNav(actief){
  const groepen = [];
  for(const s of SCHERMEN){
    if(s.sleutel!=="scan" && s.sleutel!=="inloggen" && !mag(s.sleutel)) continue;
    let g = groepen.find(x=>x.naam===s.groep);
    if(!g) groepen.push(g={naam:s.groep, items:[]});
    g.items.push(s);
  }
  const nTaken = DB.taken.filter(t=>t.status==="TODO").length;
  const nDrift = DB.drift.filter(d=>d.status==="OPEN").length;
  const nMeten = teMeten(DB).length;
  const nOrders = DB.orders.filter(o=>o.status!=="VERZONDEN").length;
  const nPick = DB.pickjobs.filter(j=>j.status==="TODO")
    .reduce((a,j)=>a+j.regels.filter(r=>r.status==="TODO").length,0);
  const tel = {taken:nTaken, meten:nMeten, orders:nOrders, picken:nPick};

  document.getElementById("nav").innerHTML = `
    <div class="merk">${MERKTEKEN}<span class="merknaam">${esc(get("merk.naam"))}</span></div>
    <div class="ondertitel">Warehouse Management</div>
    ${groepen.map(g=>`<div class="navgroep">${esc(g.naam)}</div>
      ${g.items.map(i=>`<a href="#${i.sleutel}" class="${actief===i.sleutel?"actief":""}"
          title="${esc(i.titel)} — ${esc(i.uitleg||"")}">
        <span class="lbl">${ICONEN[i.sleutel]||""}<span class="lbltekst">
          <span class="lbltitel">${esc(i.titel)}</span>
          <span class="lblbij">${esc(i.bij||"")}</span></span></span>
        ${tel[i.sleutel]?`<span class="badge ${(i.sleutel==="meten"&&nDrift)||i.sleutel==="picken"?"let":""}">${fmt(tel[i.sleutel])}</span>`:""}
      </a>`).join("")}`).join("")}
    <div class="visite">
      <div class="visite-merk">${esc(get("merk.naam"))}</div>
      <div>${esc(get("contact.naam"))}</div>
      <a href="mailto:${esc(get("contact.email"))}">${esc(get("contact.email"))}</a>
      ${get("contact.telefoon") ? `<div>${esc(get("contact.telefoon"))}</div>` : ""}
    </div>`;
}

function teken(){
  const h = (location.hash||"#dashboard").slice(1);
  const [naam, a, b] = h.split("/");
  /* Na elke handeling toetst het systeem zichzelf: meldingen die vanzelf
     zijn opgelost sluiten, werk dat nodig is klaarzetten, taken die
     overbodig zijn laten vervallen. Niemand hoeft iets af te vinken. */
  if(DB) hertoets(DB);

  /* Scanmodus neemt het hele scherm over: op een telefoon heb je niets
     aan een menubalk van 226 pixels. */
  if(naam==="scan"){
    if(!scan.actief) scanStart(scan.taak);
    document.body.classList.add("scanmodus");
    document.getElementById("inhoud").innerHTML = schermScan();
    zetScanFocus();
    return;
  }
  document.body.classList.remove("scanmodus");
  document.body.classList.toggle("smal", smalMenu);
  scan.actief = false;

  /* Rechten: wie er niet bij mag, komt op het dashboard uit. */
  if(RECHTEN[naam] && !mag(naam)){
    melding(`Als ${ROLLEN[HUIDIGE.rol].naam.toLowerCase()} heb je geen toegang tot dat scherm.`, "waarschuw");
    location.hash = mag("dashboard") ? "#dashboard" : "#picken";
    return;
  }
  let inhoud = "";
  switch(naam){
    case "dashboard":    inhoud = schermDashboard(); break;
    case "locaties":     inhoud = schermLocaties(); break;
    case "locatie":      inhoud = schermLocatie(+a); break;
    case "artikelen":    inhoud = schermArtikelen(); break;
    case "artikel":      inhoud = schermArtikel(a); break;
    case "inslag":
      if(a!==undefined){ staat.inslagSku = decodeURIComponent(a);
                         staat.inslagQty = b?+b:24; }
      inhoud = schermInslag(); break;
    case "dag":          inhoud = schermDag(); break;
    case "orders":       inhoud = schermOrders(); break;
    case "order":        inhoud = schermOrder(a); break;
    case "picken":       inhoud = schermPicken(); break;
    case "scan":         inhoud = schermScan(); break;
    case "inloggen":     inhoud = schermInloggen(); break;
    case "meten":        inhoud = schermMeten(); break;
    case "taken":        inhoud = schermTaken(); break;
    case "instellingen": inhoud = schermInstellingen(); break;
    case "optimalisatie":inhoud = schermOptimalisatie(); break;
    case "eigen":        inhoud = schermEigen(); break;
    case "etiketten":    inhoud = schermEtiketten(); break;
    default:             inhoud = schermDemo();
  }
  const actief = naam==="locatie"?"locaties" : naam==="artikel"?"artikelen"
               : naam==="order"?"orders" : naam==="etiketten"?"eigen" : naam||"demo";
  tekenNav(actief);
  tekenBovenbalk(actief);
  const m = document.getElementById("inhoud");
  m.innerHTML = inhoud;
  m.scrollTop = 0;
  window.scrollTo(0,0);
  /* Beweging alleen bij een NIEUW scherm. Tijdens de dagsimulatie tekent
     hetzelfde scherm zich elke tik opnieuw; dan zou alles blijven
     binnenvliegen en dat is na een minuut niet meer om aan te zien. */
  if(vorigScherm !== h){
    vorigScherm = h;
    if(!rustig()){
      m.classList.remove("binnen"); void m.offsetWidth; m.classList.add("binnen");
      clearTimeout(teken._t);
      teken._t = setTimeout(()=>m.classList.remove("binnen"), 900);
      telCijfersOp(m);
    }
  }
  const f = m.querySelector("input[autofocus]");
  if(f) f.focus();
}

let vorigScherm = null;
const rustig = ()=> window.matchMedia
  && matchMedia("(prefers-reduced-motion: reduce)").matches;

/* Grote getallen tellen op bij het openen van een scherm. Puur gevoel,
   maar het is het verschil tussen een tabel en iets dat leeft. */
function telCijfersOp(wortel){
  for(const el of wortel.querySelectorAll(".cijfer")){
    const orig = el.textContent;
    const m = /^\s*(\d[\d.]*)(.*)$/.exec(orig);
    if(!m) continue;
    const doel = parseInt(m[1].replace(/\./g,""), 10);
    if(!isFinite(doel) || doel < 8) continue;
    const staart = m[2] || "";
    const begin = performance.now(), duur = 620;
    const stap = (nu)=>{
      if(!el.isConnected) return;
      const t = Math.min(1, (nu-begin)/duur);
      const e = 1 - Math.pow(1-t, 3);
      el.textContent = Math.round(doel*e).toLocaleString("nl-NL") + staart;
      if(t < 1) requestAnimationFrame(stap); else el.textContent = orig;
    };
    el.textContent = "0" + staart;
    requestAnimationFrame(stap);
  }
}

function melding(tekst, soort="ok"){
  const b = document.getElementById("balk");
  b.className = "vlag " + soort;
  b.textContent = tekst;
  b.hidden = false;
  clearTimeout(melding._t);
  melding._t = setTimeout(()=>{b.hidden=true;}, 7000);
}

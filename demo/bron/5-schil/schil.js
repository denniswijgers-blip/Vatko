/* =====================================================================
   DE SCHIL: bovenbalk, snelzoeker, inklapbaar menu

   Dit is wat het verschil maakt tussen "een website met tabellen" en
   iets dat aanvoelt als gereedschap. Eén toetsaanslag (Ctrl+K) en je
   springt naar een artikel, een locatie of een order zonder ergens
   doorheen te klikken. Wie dat één keer gebruikt, wil niet meer terug.
   ===================================================================== */
let smalMenu = false;

const AVATAR = (naam)=> naam.split(" ").filter(Boolean)
  .map(w=>w[0]).slice(0,2).join("").toUpperCase();

function tekenBovenbalk(naam){
  const scherm = SCHERMEN.find(s=>s.sleutel===naam);
  const open = DB.drift.filter(d=>d.status==="OPEN").length;
  const laatst = controle.at
    ? new Date(controle.at).toLocaleTimeString("nl-NL",{hour:"2-digit",minute:"2-digit"})
    : "—";
  document.getElementById("balkboven").innerHTML = `
    <button class="ikoonknop" data-menu-smal title="Menu smal of breed" aria-label="Menu smal of breed">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
           stroke-linecap="round"><path d="M4 7h16M4 12h10M4 17h16"/></svg>
    </button>
    <nav class="kruimels" aria-label="Waar je bent">
      <span>${esc(scherm?scherm.groep:"Vakto")}</span>
      <span class="sep">/</span>
      <b>${esc(scherm?scherm.titel:get("merk.klant"))}</b>
    </nav>
    <button class="zoekknop" data-palet-open>
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
           stroke-linecap="round"><circle cx="11" cy="11" r="6.5"/><path d="M16 16l4.5 4.5"/></svg>
      <span>Zoek artikel, locatie of order</span>
      <kbd>${navigator.platform.indexOf("Mac")===0?"⌘":"Ctrl"} K</kbd>
    </button>
    <div class="balkrechts">
      <span class="klantchip" title="${esc(get("merk.klant"))}">${esc(get("merk.klant"))}</span>
      <button class="ikoonknop ${open?"let":""}" data-ga="#dashboard"
              title="${open?open+" openstaande afwijking(en)":"Geen openstaande afwijkingen"} · laatste zelfcontrole ${laatst}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
             stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 3.5a5.5 5.5 0 015.5 5.5v3.2l1.6 3.1H4.9l1.6-3.1V9A5.5 5.5 0 0112 3.5z"/>
          <path d="M10 18.5a2 2 0 004 0"/></svg>
        ${open?`<i class="stipje"></i>`:""}
      </button>
      <button class="ikoonknop" data-actie="thema" title="Licht of donker" aria-label="Licht of donker">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
             stroke-linecap="round" stroke-linejoin="round">
          <path d="M20 13.5A8 8 0 1110.5 4a6.5 6.5 0 009.5 9.5z"/></svg>
      </button>
      <a class="wiechip" href="#inloggen" title="${esc(HUIDIGE.naam)} — ${esc(ROLLEN[HUIDIGE.rol].naam)}">
        <span class="avatar">${esc(AVATAR(HUIDIGE.naam))}</span>
        <span class="wienaam">${esc(HUIDIGE.naam.split(" ")[0])}</span>
      </a>
    </div>`;
}

/* =====================================================================
   SNELZOEKER
   ===================================================================== */
const palet = {open:false, keuze:0, treffers:[]};

/* Rangschikking: precies gelijk, dan begint-met, dan bevat-ergens.
   Wie "04-1" typt zoekt gang 04, niet locatie 01-04-1. */
function rang(tekst, v){
  const t = String(tekst).toLowerCase();
  if(t === v) return 0;
  if(t.startsWith(v)) return 1;
  return t.includes(v) ? 2 : -1;
}
function zoekAlles(vraag){
  const v = vraag.trim().toLowerCase();
  const uit = [];
  const voegToe = (t)=>{ uit.push(t); };

  if(!v){
    for(const s of SCHERMEN.filter(s=>mag(s.sleutel)).slice(0,6))
      voegToe({soort:"Scherm", titel:s.titel, bij:s.groep, hash:"#"+s.sleutel, ico:"scherm"});
    return uit;
  }
  for(const s of SCHERMEN){
    if(!mag(s.sleutel)) continue;
    if(s.titel.toLowerCase().includes(v) || s.groep.toLowerCase().includes(v))
      voegToe({soort:"Scherm", titel:s.titel, bij:s.groep, hash:"#"+s.sleutel, ico:"scherm"});
  }
  for(const l of DB.locaties){
    const r = rang(l.code, v);
    if(r<0) continue;
    voegToe({soort:"Locatie", titel:l.code, bij:DB.zones[l.zoneId].naam+" · "+maatVan(l),
             hash:"#locatie/"+l.id, r});
    if(uit.length>400) break;
  }
  for(const a of DB.artikelen){
    const r = Math.min(...[rang(a.sku,v), rang(a.oms,v), a.barcode===v?0:-1]
                        .filter(x=>x>=0).concat(9));
    if(r>8) continue;
    voegToe({soort:"Artikel", titel:a.sku, bij:a.oms, hash:"#artikel/"+a.id, r:r+0.1});
    if(uit.length>800) break;
  }
  if(mag("orders")) for(const o of DB.orders){
    const r = Math.min(...[rang(o.nummer,v), rang(o.klant,v)].filter(x=>x>=0).concat(9));
    if(r>8) continue;
    voegToe({soort:"Order", titel:o.nummer, bij:o.klant+" · "+STATUSNAAM[o.status],
             hash:"#order/"+o.id, r:r+0.2});
  }
  uit.sort((a,b)=>(a.r??0)-(b.r??0));
  return uit.slice(0,9);
}

function tekenPalet(){
  const vak = document.getElementById("paletUit");
  if(!palet.treffers.length){
    vak.innerHTML = `<div class="palet-leeg">Niets gevonden. Probeer een artikelnummer,
      een locatiecode als <span class="mono">04-12-2</span>, of een ordernummer.</div>`;
    return;
  }
  vak.innerHTML = palet.treffers.map((t,i)=>`
    <button class="palet-rij ${i===palet.keuze?"aan":""}" data-palet-kies="${i}">
      <span class="palet-soort">${esc(t.soort)}</span>
      <span class="palet-titel mono">${esc(t.titel)}</span>
      <span class="palet-bij">${esc(t.bij)}</span>
    </button>`).join("");
}

function paletZoek(){
  const inv = document.getElementById("paletInvoer");
  palet.treffers = zoekAlles(inv ? inv.value : "");
  palet.keuze = 0;
  tekenPalet();
}
function paletOpen(){
  palet.open = true;
  const d = document.getElementById("palet");
  d.hidden = false;
  requestAnimationFrame(()=>d.classList.add("aan"));
  const inv = document.getElementById("paletInvoer");
  inv.value = ""; inv.focus();
  paletZoek();
}
function paletDicht(){
  palet.open = false;
  const d = document.getElementById("palet");
  d.classList.remove("aan");
  setTimeout(()=>{ if(!palet.open) d.hidden = true; }, 150);
}
function paletGa(i){
  const t = palet.treffers[i];
  if(!t) return;
  paletDicht();
  location.hash = t.hash;
}

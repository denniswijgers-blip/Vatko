/* =====================================================================
   TOETSEN, FORMULIEREN EN DE START

   Toetsenbord, formulieren, keuzelijsten, zoeken en de tekstballon bij
   grafieken. Dit bestand hoort ALTIJD als laatste geplakt te worden:
   de laatste twee regels starten de demo, en dan moet al het andere er
   al zijn.
   ===================================================================== */

/* --- tekstballon bij grafieken en balken ---------------------------- */
(function tekstballon(){
  const t = document.createElement("div");
  t.id = "tip"; t.hidden = true;
  document.body.appendChild(t);
  let aan = null;
  const plaats = (e)=>{
    const b = t.getBoundingClientRect();
    let x = e.clientX + 14, y = e.clientY - b.height - 12;
    if(x + b.width > innerWidth - 8) x = e.clientX - b.width - 14;
    if(y < 8) y = e.clientY + 18;
    t.style.left = x + "px"; t.style.top = y + "px";
  };
  document.addEventListener("mousemove",(e)=>{
    const el = e.target.closest ? e.target.closest("[data-tip]") : null;
    if(el){
      if(el !== aan){ aan = el; t.textContent = el.dataset.tip; t.hidden = false;
                      requestAnimationFrame(()=>t.classList.add("aan")); }
      plaats(e);
    } else if(aan){ aan = null; t.classList.remove("aan"); t.hidden = true; }
  }, {passive:true});
  document.addEventListener("mouseleave",()=>{ aan=null; t.classList.remove("aan"); t.hidden=true; });
})();

function zetScanFocus(){
  const i = document.getElementById("scanInvoer");
  if(i && document.activeElement !== i
       && document.activeElement?.id !== "scanAantal") i.focus();
}
/* De cursor moet ALTIJD in het scanveld staan. Raakt hij kwijt, dan lijkt
   de scanner stuk en gaat iemand er tegenaan tikken. */
setInterval(()=>{ if(scan.actief) zetScanFocus(); }, 600);

document.addEventListener("keydown",(e)=>{
  /* Ctrl+K of Cmd+K: overal vandaan zoeken. */
  if((e.ctrlKey||e.metaKey) && (e.key==="k"||e.key==="K")){
    e.preventDefault(); palet.open ? paletDicht() : paletOpen(); return;
  }
  if(palet.open){
    if(e.key==="Escape"){ e.preventDefault(); paletDicht(); return; }
    if(e.key==="ArrowDown"||e.key==="ArrowUp"){
      e.preventDefault();
      if(!palet.treffers.length) return;
      palet.keuze = (palet.keuze + (e.key==="ArrowDown"?1:-1) + palet.treffers.length)
                    % palet.treffers.length;
      tekenPalet(); return;
    }
    if(e.key==="Enter"){ e.preventDefault(); paletGa(palet.keuze); return; }
    return;
  }
  if(!scan.actief) return;
  if(e.key==="Enter"){
    if(e.target.id==="scanInvoer"){
      e.preventDefault();
      const code = e.target.value; e.target.value = "";
      verwerkScan(code); teken();
    } else if(e.target.id==="scanAantal"){
      e.preventDefault();
      scanBevestig(e.target.value); teken();
    }
  }
});

document.addEventListener("submit",(e)=>{
  if(e.target.dataset.form !== "inslag") return;
  e.preventDefault();
  const f = new FormData(e.target);
  staat.inslagSku = (f.get("sku")||"").trim();
  staat.inslagQty = Math.max(1, +f.get("qty")||1);
  location.hash = `#inslag/${encodeURIComponent(staat.inslagSku)}/${staat.inslagQty}`;
  teken();
});

document.addEventListener("change",(e)=>{
  if(e.target.dataset.impBestand){
    const soort = e.target.dataset.impBestand;
    const file = e.target.files && e.target.files[0];
    if(!file) return;
    imp.fout = null;
    melding(`${file.name} wordt gelezen…`);
    leesBestand(file).then(b=>{
      imp.bestanden[soort] = b;
      imp.kolom[soort] = herkenKolommen(soort, b.kop);
      /* Eenheden raden we uit de getallen zelf; de gebruiker ziet het en kan het omzetten. */
      const K = imp.kolom[soort];
      const kol = (i)=> i===undefined ? [] : b.rijen.slice(0,400).map(r=>r[i]);
      if(soort==="locaties"){
        imp.eenheid.loc_maat = raadMaat([...kol(K.L),...kol(K.W),...kol(K.H)], "locaties");
        imp.eenheid.loc_gew  = raadGewicht(kol(K.maxG), "locaties");
      }
      if(soort==="artikelen"){
        imp.eenheid.art_maat = raadMaat([...kol(K.L),...kol(K.W),...kol(K.H)], "artikelen");
        imp.eenheid.art_gew  = raadGewicht(kol(K.G), "artikelen");
      }
      imp.rapport = null;
      teken();
      const gevonden = VELDEN[soort].filter(v=>K[v.k]!==undefined).length;
      melding(`${b.naam}: ${fmt(b.rijen.length)} regels gelezen, ${gevonden} van de ${VELDEN[soort].length} kolommen herkend. Controleer ze hieronder.`);
    }).catch(err=>{
      imp.fout = err.message; imp.bestanden[soort] = null; teken();
      melding("Lezen mislukt: "+err.message, "fout");
    });
    return;
  }
  if(e.target.dataset.impKol){
    const v = e.target.value;
    if(v==="") delete imp.kolom[e.target.dataset.impKol][e.target.dataset.veld];
    else imp.kolom[e.target.dataset.impKol][e.target.dataset.veld] = +v;
    imp.rapport = null; teken(); return;
  }
  if(e.target.dataset.impEenheid){
    imp.eenheid[e.target.dataset.impEenheid] = e.target.value;
    imp.rapport = null; teken(); return;
  }
  if(e.target.dataset.impStd){
    imp.standaard[e.target.dataset.impStd] = Math.max(1, +e.target.value||1);
    return;
  }
  if(e.target.hasAttribute("data-imp-nul")){
    S["opstart.onbekend_aanmaken"].v = e.target.value;
    melding(e.target.value==="true"
      ? "Onbekende codes worden nu tijdens het tellen aangemaakt."
      : "Onbekende codes geven weer een foutmelding.");
    return;
  }
  if(e.target.dataset.opzet !== undefined && e.target.dataset.veld){
    const z = imp.opzet[+e.target.dataset.opzet], v = e.target.dataset.veld;
    z[v] = ["code","naam","soort"].includes(v) ? e.target.value : Math.max(0, +e.target.value||0);
    teken(); return;
  }
  if(e.target.hasAttribute("data-sim-snelheid")){
    sim.snelheid = +e.target.value; if(sim.draait) startDag(); return;
  }
  if(e.target.hasAttribute("data-sim-pickers")){ sim.pickers = +e.target.value; return; }
  if(e.target.hasAttribute("data-sim-rommel")){ sim.rommel = e.target.value==="echt"; teken(); return; }
  if(e.target.dataset.filter){
    staat[e.target.dataset.filter] = e.target.value; staat.pagina=1; teken();
  }
});
let zoekT;
document.addEventListener("input",(e)=>{
  if(e.target.id === "paletInvoer"){ paletZoek(); return; }
  if(e.target.hasAttribute("data-imp-bedrijf")){ imp.bedrijf = e.target.value; return; }
  if(e.target.hasAttribute("data-zoek")){
    clearTimeout(zoekT);
    const v = e.target.value;
    zoekT = setTimeout(()=>{ staat.zoek=v; staat.pagina=1; teken(); }, 250);
  }
});
document.addEventListener("mousedown",(e)=>{
  if(palet.open && e.target.id === "palet") paletDicht();
});
window.addEventListener("hashchange", ()=>{ staat.pagina=1; teken(); });

/* --- start ---------------------------------------------------------- */
startDemo();
teken();

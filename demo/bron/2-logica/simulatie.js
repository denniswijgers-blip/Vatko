/* =====================================================================
   DAGSIMULATIE
   Speelt een werkdag af van 07:00 tot 17:00. Orders komen binnen, worden
   gereserveerd, in golven vrijgegeven, gepickt, ingepakt en verzonden.
   Er gaat ook af en toe iets mis, want dat hoort bij een normale dag.

   Alles wat hier gebeurt loopt door dezelfde functies als handmatig
   werken. Er is geen aparte "demo-modus" die dingen voorwendt.
   ===================================================================== */

const DAGSTART = 7*60, DAGEIND = 17*60, TIK = 5;   /* minuten */

/* Hoe druk het is per uur. Piek 's ochtends, dip tijdens de lunch. */
const DRUKTE = {7:0.4, 8:1.0, 9:1.6, 10:1.7, 11:1.4, 12:0.5,
                13:1.2, 14:1.5, 15:1.3, 16:0.8};

const sim = {
  tijd: DAGSTART, draait:false, klaar:false, snelheid:200, timer:null,
  pickers:4, rommel:false, gebeurtenissen:[], perUur:{},
  teller:{binnen:0, verzonden:0, regels:0, manco:0, stuks:0, storing:0}
};

/* Hoe rommelig is de dag?
   "Nette dag" is hoe een demo er meestal uitziet: alles klopt, iedereen
   doet zijn werk, niets valt om. "Rommelige dag" lijkt op een echte
   maandag. Het verschil is groot, en dat is precies het punt. */
const ROMMEL = {
  net:    {manco:0.03, storing:0.00, spoed:0.00, traag:0.00, naam:"Nette dag"},
  echt:   {manco:0.09, storing:0.035, spoed:0.028, traag:0.18, naam:"Rommelige dag"}
};
const rommelNu = ()=> sim.rommel ? ROMMEL.echt : ROMMEL.net;

const klok = (m)=>`${String(Math.floor(m/60)).padStart(2,"0")}:${String(m%60).padStart(2,"0")}`;

function meld(soort, tekst){
  sim.gebeurtenissen.unshift({tijd:sim.tijd, soort, tekst});
  if(sim.gebeurtenissen.length>140) sim.gebeurtenissen.pop();
}
function uurvak(){
  const u = Math.floor(sim.tijd/60);
  return sim.perUur[u] || (sim.perUur[u] = {binnen:0, regels:0, verzonden:0, manco:0});
}

/* --- één tik van vijf minuten ---------------------------------------- */
function tik(){
  if(sim.tijd >= DAGEIND){ stopDag(true); return; }
  const uur = Math.floor(sim.tijd/60);
  const drukte = DRUKTE[uur] ?? 0.5;
  const vak = uurvak();

  /* 1. Orders komen binnen uit de webshop en van de servicedienst */
  if(rnd() < 0.55*drukte){
    const n = rnd()<0.25 ? 2 : 1;
    for(let i=0;i<n;i++){
      const o = maakOrder(DB, Date.now());
      if(o){ sim.teller.binnen++; vak.binnen++;
        meld("order", `${o.nummer} binnen — ${o.klant}, ${o.regels.length} regel(s), ${o.typenaam.toLowerCase()}`); }
    }
  }

  /* 2. Reserveren gebeurt direct bij binnenkomst */
  for(const o of DB.orders.filter(o=>o.status==="NIEUW")){
    const st = reserveer(DB, o);
    if(st==="WACHT_OP_VOORRAAD")
      meld("tekort", `${o.nummer} wacht op voorraad — niet alles kon gereserveerd worden`);
  }

  /* 3. Vrijgeven. Servicedienst gaat meteen door, de rest in golven op
        het hele uur. Zo lopen er niet vijf pickers door dezelfde gang. */
  const golf = sim.tijd % 60 === 0;
  for(const o of DB.orders.filter(o=>o.status==="GERESERVEERD")){
    if(o.type==="SERVICE" || golf){
      if(geefVrij(DB, o) && golf) { /* stil */ }
    }
  }
  if(golf){
    const n = DB.pickjobs.filter(j=>j.status==="TODO").length;
    if(n) meld("golf", `Golf vrijgegeven — ${n} pickopdracht(en) klaar op de vloer`);
  }

  /* 4. Picken. Pickers doen ongeveer twee minuten per regel. Op een
        rommelige dag gaat een deel van de tijd op aan van alles behalve
        picken: iemand komt iets vragen, een pallet staat in de weg. */
  const traag = rommelNu().traag;
  let budget = Math.round(sim.pickers * TIK / 2 * (1 - traag));
  if(traag && rnd() < 0.12){
    budget = Math.max(0, budget - 3);
    meld("oponthoud", pick([
      "Pallet staat in gang 04 — picker moet omlopen",
      "Nieuwe medewerker heeft uitleg nodig bij het scannen",
      "Vraag van de klantenservice: waar blijft ORD-2500xx?",
      "Heftruck bezet, bulkregel moet wachten"]));
  }
  const jobs = DB.pickjobs.filter(j=>j.status==="TODO")
    .sort((a,b)=>a.prio-b.prio || a.id-b.id);
  for(const job of jobs){
    for(const r of job.regels.filter(x=>x.status==="TODO")){
      if(budget<=0) break;
      budget--;
      /* Kans dat het schap minder bevat dan het systeem denkt */
      const misgreep = rnd() < rommelNu().manco;
      const aantal = misgreep ? Math.floor((r.qty-r.gepickt)*rnd()) : r.qty-r.gepickt;
      const st = bevestigPick(DB, job, r.nr, aantal);
      sim.teller.regels++; vak.regels++; sim.teller.stuks += aantal;
      if(st==="MANCO"){ sim.teller.manco++; vak.manco++;
        meld("manco", `Manco op ${DB.locaties[r.locationId].code} — ${DB.artikelen[r.productId].sku}, ${r.qty-r.gepickt} te weinig`); }
    }
    if(budget<=0) break;
  }

  /* 4b. Verstoringen die op een echte dag gewoon gebeuren */
  const r = rommelNu();
  if(r.storing && rnd() < r.storing){
    const soort = pick(["schade","blokkade","spoed"]);
    if(soort==="schade"){
      const s2 = pick(DB.voorraad.filter(x=>x.qty>4 && (x.res||0)===0));
      /* Op soort zoeken, niet op naam: bij een ingelezen magazijn heet de
         schadelocatie zelden "SCHADE". */
      const schadeLoc = DB.locaties.find(l=>l.typeId===4) || DB.locaties.find(l=>LOCTYPES[l.typeId].blok);
      if(s2 && schadeLoc){
        const n = rint(1, Math.min(3, s2.qty));
        boek(DB, s2.productId, n, "MOVE", s2.locationId, schadeLoc.id, "BREUK", "Schademelding");
        sim.teller.storing++;
        meld("schade", `${n}x ${DB.artikelen[s2.productId].sku} beschadigd op ${DB.locaties[s2.locationId].code} — naar de schadelocatie`);
      }
    } else if(soort==="blokkade"){
      const l = pick(DB.locaties.filter(x=>x.aisle>0 && x.actief));
      l.actief = 0;
      sim.teller.storing++;
      meld("blokkade", `Locatie ${l.code} tijdelijk geblokkeerd — stelling beschadigd`);
      setTimeout(()=>{ l.actief = 1; }, 50);
    }
  }
  if(r.spoed && rnd() < r.spoed){
    const o = maakOrder(DB, Date.now());
    if(o){ o.prio = 0; o.typenaam = "Spoedorder"; o.type = "SERVICE";
      sim.teller.binnen++; vak.binnen++; sim.teller.storing++;
      meld("spoed", `SPOED: ${o.nummer} voor ${o.klant} — klant staat aan de balie te wachten`); }
  }

  /* 5. Inpakken */
  let pakBudget = 3;
  for(const o of DB.orders.filter(o=>o.status==="GEPICKT")){
    if(pakBudget--<=0) break;
    pakIn(DB, o);
    meld("pak", `${o.nummer} ingepakt — ${o.colli} colli, ${(o.gewicht/1000).toFixed(1)} kg`);
  }

  /* 6. Verzenden op de vaste momenten: middagrit en eindedagrit */
  if(sim.tijd===12*60 || sim.tijd===16*60){
    const klaar = DB.orders.filter(o=>o.status==="INGEPAKT");
    for(const o of klaar){ verzend(DB, o); sim.teller.verzonden++; vak.verzonden++; }
    if(klaar.length) meld("rit", `${sim.tijd===720?"Middagrit":"Eindrit"} vertrokken — ${klaar.length} order(s) mee`);
  }

  /* 7. Aanvullen: het systeem kijkt zelf of picklocaties leeglopen */
  if(sim.tijd % 30 === 0){
    const n = maakAanvultaken(DB);
    if(n) meld("aanvul", `${n} picklocatie(s) onder de drempel — aanvultaken aangemaakt`);
  }

  /* 8. De levering van tien uur, inclusief een verpakking die afwijkt */
  if(sim.tijd===10*60){
    const kand = DB.artikelen.map(a=>DB.artikelNu(a.id))
      .filter(p=>p.L && p.bron==="SUPPLIER")[0];
    if(kand){
      const a = legMetingVast(DB, kand.id, Math.round(kand.L*1.21),
        Math.round(kand.W*1.15), Math.round(kand.H*1.09),
        Math.round(kand.G*1.17), "RECEIPT", "Gemeten bij ontvangst levering");
      meld("inbound", a
        ? `Levering binnen — ${kand.sku} wijkt af: volume ${a.dVol>0?"+":""}${a.dVol}%. ${a.gevolg}`
        : `Levering binnen — ${kand.sku} opgemeten, geen afwijking`);
    }
  }

  sim.tijd += TIK;
}

/* --- besturing -------------------------------------------------------- */
function startDag(){
  if(sim.klaar) resetDag();
  sim.draait = true;
  clearInterval(sim.timer);
  sim.timer = setInterval(()=>{ tik(); if(location.hash.startsWith("#dag")) teken(); },
                          sim.snelheid);
}
function pauzeerDag(){ sim.draait=false; clearInterval(sim.timer); }
function stopDag(klaar){
  pauzeerDag(); sim.klaar = !!klaar;
  if(klaar) meld("eind", `Dag afgesloten — ${sim.teller.verzonden} orders verzonden, ${sim.teller.regels} regels gepickt`);
  if(location.hash.startsWith("#dag")) teken();
}
function stapUur(){
  const doel = Math.min(DAGEIND, sim.tijd + 60);
  while(sim.tijd < doel) tik();
  teken();
}
function resetDag(){
  pauzeerDag();
  sim.tijd=DAGSTART; sim.klaar=false; sim.gebeurtenissen=[]; sim.perUur={};
  sim.teller={binnen:0,verzonden:0,regels:0,manco:0,stuks:0,storing:0};
  for(const l of DB.locaties) l.actief = 1;
  DB.orders=[]; DB.reserveringen=[]; DB.pickjobs=[];
  for(const s of DB.voorraad) s.res=0;
  DB.taken = DB.taken.filter(t=>t.soort!=="MISSING");
}

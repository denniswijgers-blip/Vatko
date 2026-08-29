/* =====================================================================
   VAKTO - rekenkern
   Dit is dezelfde logica als in de Python-versie, geschreven voor de
   browser. Geen namaak: de voorstellen worden hier echt uitgerekend.
   ===================================================================== */

/* Vaste toevalsgenerator: de demo ziet er elke keer hetzelfde uit. */
function mulberry32(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
let rnd = mulberry32(20260820);
const rint=(a,b)=>Math.floor(rnd()*(b-a+1))+a;
const pick=(a)=>a[Math.floor(rnd()*a.length)];

/* Een decimaal, en overal op dezelfde manier. Niet toFixed(1): die geeft
   tekst terug die je weer moet omzetten, en rondt bij een half getal net
   anders dan de Python-versie (die doet rond(x*10)/10). Twee versies die
   12,25% verschillend afronden zetten verschillende percentages in
   dezelfde melding, en dan lijkt er een kapot terwijl er niets is. */
const rond1 = (x) => Math.round(x*10)/10;

/* --- instellingen: alles wat per klant kan verschillen --------------- */
const S = {
  "merk.naam":{v:"Vakto",g:"Huisstijl",d:"Naam linksboven en in de paginatitel."},
  "merk.klant":{v:"Van Delden Techniek B.V.",g:"Huisstijl",d:"Naam van de klant of vestiging."},
  "contact.naam":{v:"Dennis Wijgers",g:"Huisstijl",d:"Naam die onderaan de navigatie staat. Belangrijk zodra dit bestand rondgestuurd wordt: dan weet iedereen wie het gemaakt heeft."},
  "contact.email":{v:"info@vaktowms.nl",g:"Huisstijl",d:"Je zakelijke e-mailadres. Vervang dit voordat je het bestand deelt."},
  "contact.telefoon":{v:"",g:"Huisstijl",d:"Telefoonnummer. Laat leeg als je dat niet wilt tonen."},
  "putaway.fill_factor":{v:"0.85",g:"Inslag",d:"Je krijgt een schap nooit 100% vol. 0.85 = reken met 85% van het theoretische aantal. Verlaag bij onregelmatige verpakkingen."},
  "putaway.prefer_smallest_fit":{v:"true",g:"Inslag",d:"Straf locaties af die veel te ruim zijn voor de partij. Voorkomt dat palletplaatsen vollopen met kleingoed."},
  "drift.alert_threshold_pct":{v:"15",g:"Artikelbeheer",d:"Bij hoeveel procent afwijking tussen twee metingen slaat het systeem alarm?"},
  "drift.remeasure_after_days":{v:"180",g:"Artikelbeheer",d:"Na hoeveel dagen wordt een artikel opnieuw aangeboden om te meten."},
  "opstart.onbekend_aanmaken":{v:"false",g:"Opstarten",d:"Alleen tijdens een nulmeting. Staat dit aan, dan maakt Vakto een onbekende gescande code ter plekke aan als nieuw artikel in plaats van een fout te geven. Zet het uit zodra je klaar bent met tellen, anders ontstaan er artikelen door een verkeerd label."},
  "opt.samenvoegen":{v:"true",g:"Optimalisatie",d:"Maak zelf verplaatstaken aan als hetzelfde artikel op meerdere locaties ligt en alles op één plek past. Elke locatie die vrijkomt is een locatie die je niet hoeft bij te bouwen."},
  "opt.dekking_dagen":{v:"3",g:"Optimalisatie",d:"Hoeveel dagen verbruik moet er minimaal op een picklocatie liggen. Hoger = minder vaak aanvullen maar meer voorraad op de vloer."},
  "opt.hardloper_per_dag":{v:"6",g:"Optimalisatie",d:"Vanaf hoeveel stuks per dag geldt een artikel als hardloper en houdt Vakto de picklocatie vooruit gevuld."},
  "opt.venster_dagen":{v:"30",g:"Optimalisatie",d:"Over hoeveel dagen wordt de pickvraag gemeten. Korter reageert sneller op seizoen, langer is rustiger."},
  "opt.max_open_teltaken":{v:"12",g:"Optimalisatie",d:"Maximaal aantal openstaande teltaken. Zonder plafond zet het systeem er duizend klaar en telt niemand er één."},
  "opt.drempel_afwijking_pct":{v:"60",g:"Optimalisatie",d:"Vanaf hoeveel procent verschil tussen de ingestelde aanvuldrempel en het werkelijke verbruik geeft Vakto een advies."},
  "uit.max_colli_gewicht_g":{v:"25000",g:"Uitgaand",d:"Maximaal gewicht per collo in gram. Hieruit volgt het aantal dozen bij het inpakken. 25 kg is wat een pakketvervoerder aanneemt; rijd je zelf, dan mag het hoger."},
  "ui.rows_per_page":{v:"60",g:"Weergave",d:"Maximaal aantal rijen per scherm. Nooit onbeperkt."}
};
const get=(k)=>S[k].v, getN=(k)=>parseFloat(S[k].v), getB=(k)=>S[k].v==="true";

/* --- wegingen van het inslagvoorstel --------------------------------- */
const WEGING = {
  zelfde_artikel:     400,
  picklocatie_aanvul: 600,
  hele_partij_past:   200,
  benutting:          500,
  te_ruim_straf:     -550,
  deelvulling_max:    150
};
const TE_RUIM_ONDER = 0.20;

/* --- maatklassen: berekend uit de afmetingen, nooit ingevuld --------- */
const MAATREGELS=[
  {code:"XS",naam:"Bak",          min:0,       max:8000},
  {code:"S", naam:"Klein vak",    min:8000,    max:50000},
  {code:"M", naam:"Middelvak",    min:50000,   max:200000},
  {code:"L", naam:"Groot vak",    min:200000,  max:900000},
  {code:"XL",naam:"Palletplaats", min:900000,  max:99000000}
];
const maatKlasse=(cm3)=>(MAATREGELS.find(r=>cm3>=r.min&&cm3<r.max)||{code:"XL"}).code;

/* --- soorten locatie: gedrag als vlaggen, niet als code -------------- */
const LOCTYPES=[
  {code:"PL", naam:"Picklocatie",   pick:1,bulk:0,mix:0,blok:0,doel:1},
  {code:"BL", naam:"Bulklocatie",   pick:0,bulk:1,mix:0,blok:0,doel:1},
  {code:"INC",naam:"Ontvangst",     pick:0,bulk:0,mix:1,blok:0,doel:0},
  {code:"QC", naam:"Keuring",       pick:0,bulk:0,mix:1,blok:1,doel:0},
  {code:"DM", naam:"Schade",        pick:0,bulk:0,mix:1,blok:1,doel:0},
  {code:"EXP",naam:"Verzendgereed", pick:0,bulk:0,mix:1,blok:1,doel:0}
];

/* =====================================================================
   PASSEN - hoeveel van dit artikel gaat er echt op deze locatie?
   ===================================================================== */
function orientaties(l,w,h,stapelbaar){
  return stapelbaar
    ? [[l,w,h],[l,h,w],[w,l,h],[w,h,l],[h,l,w],[h,w,l]]
    : [[l,w,h],[w,l,h]];
}

function pasBerekening(p, loc, vulfactor){
  if(!p.L||!p.W||!p.H||!p.G) return {qty:null,limiet:"ONBEKEND",reden:"Artikel is nog nooit opgemeten"};
  let beste=0, orient=null;
  for(const [ol,ow,oh] of orientaties(p.L,p.W,p.H,p.stapelbaar)){
    if(ol>loc.L||ow>loc.W||oh>loc.H) continue;
    const n = p.stapelbaar
      ? Math.floor(loc.L/ol)*Math.floor(loc.W/ow)*Math.floor(loc.H/oh)
      : Math.floor(loc.L/ol)*Math.floor(loc.W/ow);
    if(n>beste){beste=n;orient=[ol,ow,oh];}
  }
  if(beste===0) return {qty:0,limiet:"AFMETING",
    reden:`Artikel (${p.L}×${p.W}×${p.H} mm) past in geen enkele draaiing in deze locatie (${loc.L}×${loc.W}×${loc.H} mm)`};

  /* max(1,...) is geen detail: zonder dat maakt 1 x 0,85 afgerond een nul,
     en dan past een pomp nergens. */
  const opMaat = Math.max(1, Math.floor(beste*vulfactor));
  const opGewicht = Math.floor(loc.maxG/p.G);
  if(opGewicht < opMaat) return {qty:opGewicht,limiet:"GEWICHT",orient,
    reden:`Ruimte biedt plek aan ${opMaat} st, maar het maximale gewicht (${Math.round(loc.maxG/1000)} kg) is bij ${opGewicht} st bereikt`};
  return {qty:opMaat,limiet:"AFMETING",orient,
    reden:`${opMaat} st passen (vulfactor ${Math.round(vulfactor*100)}%); gewicht zou ${opGewicht} st toestaan`};
}

/* ---------------------------------------------------------------------
   Hoeveel stuks van dit artikel kunnen er NOG bij op deze locatie?

   Dezelfde drie budgetten als het inslagvoorstel (R-INS-02). Deze functie
   bestaat omdat het aanvullen van een picklocatie er net zo goed langs
   moet: een aanvultaak van 115 stuks naar een vak waar er zestig in gaan
   is geen taak, dat is een probleem dat je op de vloer aflevert.

   `bezetKaart` is optioneel. Roep je dit in een lus aan, geef hem dan
   mee - anders loop je per aanroep de hele voorraad langs.
   --------------------------------------------------------------------- */
function ruimteVoor(db, productId, locId, bezetKaart, vulfactor){
  const p = db.artikelNu(productId);
  const loc = db.locaties[locId];
  if(!p || !p.L || !loc) return 0;
  const vul = vulfactor ?? getN("putaway.fill_factor");
  const fit = pasBerekening(p, loc, vul);
  if(!fit.qty) return 0;

  let bezetVol = 0, bezetGew = 0, dit = 0;
  if(bezetKaart){
    const b = bezetKaart.get ? bezetKaart.get(locId) : bezetKaart[locId];
    if(b){ bezetVol = b.vol; bezetGew = b.gew;
           dit = (b.perArt && b.perArt.get) ? (b.perArt.get(productId)||0)
                                            : (b.perArt ? b.perArt[productId]||0 : 0); }
  } else {
    for(const s of db.voorraad){
      if(s.locationId!==locId || s.qty<=0) continue;
      const m = db.artikelNu(s.productId);
      if(!m || !m.L) continue;
      bezetVol += s.qty*m.L*m.W*m.H;
      bezetGew += s.qty*m.G;
      if(s.productId===productId) dit += s.qty;
    }
  }
  const locVol = loc.L*loc.W*loc.H;
  return Math.max(0, Math.floor(Math.min(
    fit.qty - dit,
    (locVol*vul - bezetVol)/(p.L*p.W*p.H),
    (loc.maxG - bezetGew)/p.G)));
}

/* =====================================================================
   INSLAGVOORSTEL
   Kern is `benutting`: welk deel van de vrije ruimte vult deze partij?
   40 schroefsets in een palletplaats geeft 0,3% - dat voorstel hoort
   onderaan. Zonder die regel loopt een magazijn langzaam vast.
   ===================================================================== */
function voorstelInslag(db, productId, aantal, limiet=8){
  const vul = getN("putaway.fill_factor");
  const strafAan = getB("putaway.prefer_smallest_fit");
  const p = db.artikelNu(productId);
  if(!p || !p.L) return [];
  const pVol = p.L*p.W*p.H, pGew = p.G;

  /* Wat er al ligt telt in VOLUME en GEWICHT, niet in stuks. Een pallet met
     300 boutjes erop mag niet 300 aftrekken van het aantal pompen dat erbij kan. */
  const bezet = {};
  for(const s of db.voorraad){
    if(s.qty<=0) continue;
    const m = db.artikelNu(s.productId);
    if(!m || !m.L) continue;
    const b = bezet[s.locationId] || (bezet[s.locationId]={vol:0,gew:0,skus:new Set()});
    b.vol += s.qty*m.L*m.W*m.H;
    b.gew += s.qty*m.G;
    b.skus.add(s.productId);
  }

  const uit=[];
  for(const loc of db.locaties){
    const t = LOCTYPES[loc.typeId];
    if(!t.doel || !loc.actief) continue;
    const fit = pasBerekening(p, loc, vul);
    if(!fit.qty) continue;

    const b = bezet[loc.id] || {vol:0,gew:0,skus:new Set()};
    const ditArtikel = b.skus.has(productId)
      ? db.voorraad.filter(s=>s.locationId===loc.id&&s.productId===productId)
          .reduce((a,s)=>a+s.qty,0) : 0;
    if(!t.mix && b.skus.size>0 && ditArtikel===0) continue;

    /* Drie budgetten, en het kleinste wint:
         1. wat er geometrisch bij kan - MINUS wat er van dit artikel al
            ligt. Zonder die aftrek stelt het systeem 16 stuks voor op een
            vak waar er dertig in gaan en er dertig liggen: het volume-
            budget is ruimer dan de echte stapeling, want dozen laten
            altijd lucht over.
         2. wat er qua volume nog bij kan, na alles wat er ligt
         3. wat er qua gewicht nog bij kan                                */
    const locVol = loc.L*loc.W*loc.H;
    const vrij = Math.floor(Math.min(
      fit.qty - ditArtikel,
      (locVol*vul - b.vol)/pVol,
      (loc.maxG - b.gew)/pGew));
    if(vrij<=0) continue;

    const alles = vrij>=aantal, geplaatst = Math.min(aantal,vrij);
    let score=0; const redenen=[];

    const benutting = (geplaatst*pVol)/(locVol*vul);
    score += Math.round(WEGING.benutting*Math.min(1,benutting));

    if(ditArtikel>0){
      score += Math.round(WEGING.zelfde_artikel*Math.min(1,vrij/aantal));
      redenen.push("artikel ligt hier al");
    }
    if(t.pick && p.minQty && ditArtikel<p.minQty){
      score += WEGING.picklocatie_aanvul;
      redenen.push("picklocatie onder aanvuldrempel");
    }
    if(alles){ score+=WEGING.hele_partij_past; redenen.push("hele partij past"); }
    else { score+=Math.round(WEGING.deelvulling_max*(vrij/aantal));
           redenen.push(`${vrij} van ${aantal} st past`); }

    if(strafAan && benutting<TE_RUIM_ONDER){
      score += Math.round(WEGING.te_ruim_straf*(1-benutting/TE_RUIM_ONDER));
      redenen.push(`benutting ${(benutting*100).toFixed(1)}%`);
    }
    uit.push({loc,vrij,alles,fit,score,redenen,benutting});
  }
  uit.sort((a,b)=>b.score-a.score || a.loc.seq-b.loc.seq);
  return uit.slice(0,limiet);
}

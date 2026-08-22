/* =====================================================================
   DEMO-OMGEVING - fictief bedrijf, realistische schaal
   Van Delden Techniek B.V., technische groothandel. Alles verzonnen,
   maar de spreiding in afmetingen klopt: van een M6-bout tot een pomp
   van zestig kilo. Juist die spreiding is wat Vakto laat zien.
   ===================================================================== */

const GROEPEN=[
  ["Bevestigingsmateriaal",180,"BEV",620,[100,70,35],[180,130,70],[150,1400],1],
  ["Lagers",                 90,"LAG",410,[85,85,35],[280,280,110],[120,5200],1],
  ["Afdichtingen",          180,"AFD",350,[90,90,20],[220,220,60],[40,700],1],
  ["Aandrijving",            90,"AAN",380,[180,140,70],[430,400,170],[700,13000],1],
  ["Pneumatiek",             90,"PNE",340,[140,80,70],[520,220,210],[250,6500],1],
  ["Hydrauliek",             60,"HYD",300,[110,70,60],[700,500,450],[200,42000],1],
  ["Elektro",                90,"ELE",330,[150,100,60],[620,460,410],[300,38000],1],
  ["Transmissie",           120,"TRA",260,[200,200,40],[520,520,160],[400,9000],1],
  ["Gereedschap",            60,"GER",250,[240,110,55],[620,310,210],[350,9500],1],
  ["Smeermiddelen",          30,"SME",140,[190,190,240],[410,410,610],[4800,61000],0],
  ["Pompen",                 30,"POM",120,[380,330,380],[820,620,720],[14000,86000],0]
];

const TEKST={
 BEV:["Zeskantbout DIN933 M{a}×{b}","Moer DIN934 M{a}","Carrosseriering M{a}","Inbusbout DIN912 M{a}×{b}","Draadeind DIN975 M{a}","Blindklinknagel {a}×{b}","Zelftapper {a}×{b} RVS","Sluitring DIN125 M{a}"],
 LAG:["Groefkogellager {a}{b}","Cilinderlager NU{a}","Zelfinstellend lager {a}","Naaldlager HK{a}{b}","Kogelgewrichtslager GE{a}","Flenslager UCF{a}"],
 AFD:["O-ring {a}×{b} NBR","Keerring {a}×{b}×7 FPM","Pakkingring koper {a}","V-ring VA{a}","Stofkeerring {a}×{b}","Vlakpakking {a} mm"],
 AAN:["Rollenketting 08B-1 {a} m","Tandwiel Z{a} 08B","Kettingschakel 10B-1","Poelie SPZ {a} mm","Koppelstuk GG{a}","Tandriemschijf HTD {a}"],
 PNE:["Cilinder ISO15552 {a}×{b}","5/2 magneetventiel G1/{a}","Snelkoppeling {a} mm","Luchtbehandeling FRL G{a}","Kunststofslang {a}×{b} PU","Geluiddemper G1/{a}"],
 HYD:["Hydrauliekslang 2SN DN{a}","Koppeling BSP {a}","Handpomp {a} cc","Cilinder {a}×{b} dubbelwerkend","Filterelement {a} micron","Manometer {a} bar"],
 ELE:["Installatiekabel YMvK {a}×{b}","Motorbeveiliging {a}-{b}A","Frequentieregelaar {a} kW","Contactor {a}A 24VDC","Kabelwartel M{a}","Klemmenblok {a} mm²"],
 TRA:["V-snaar SPA {a}","Tandriem HTD {a}-8M","Vlakriem {a} mm","Koppeling ROTEX {a}","Tussenas {a} mm","Spanrol {a} mm"],
 GER:["Momentsleutel {a}-{b} Nm","Steeksleutelset {a}-delig","Slagmoersleutel 1/{a}","Meetklok {a} mm","Schuifmaat {a} mm digitaal","Boorset HSS {a}-delig"],
 SME:["Lagervet EP2 {a} kg","Hydrauliekolie HLP{a} {b} L","Kettingspray {a} ml","Tandwielolie {a} {b} L","Reiniger industrieel {a} L"],
 POM:["Centrifugaalpomp {b} m³/h","Schroefspindelpomp {b} m³/h","Membraanpomp {a} mm RVS","Dompelpomp {a} kW","Zelfaanzuigende pomp {b} m³/h"]
};
const GETAL=[4,5,6,8,10,12,16,20,25,32,40,50,63], GETAL2=[10,16,20,25,30,40,50,60,80,100];

/* Een magazijn is nooit uniform: een handjevol artikelen is goed voor de
   helft van alle picks, en de staart beweegt bijna niet. Zonder die
   scheefheid heeft het meten van vraagsnelheid geen enkele betekenis -
   dan lijkt alles even hard te lopen en klopt er niets van je
   aanvulplanning. */
function wegingSampler(items, gewichtVan){
  const cum = []; let totaal = 0;
  for(const it of items){ totaal += gewichtVan(it); cum.push(totaal); }
  return ()=>{
    const x = rnd()*totaal;
    let lo = 0, hi = cum.length-1;
    while(lo < hi){ const m = (lo+hi)>>1; if(cum[m] < x) lo = m+1; else hi = m; }
    return items[lo];
  };
}

function bouwDemo(){
  rnd = mulberry32(20260820);            // altijd dezelfde demo
  const db = {
    zones:[], locaties:[], groepen:[], artikelen:[], metingen:[],
    voorraad:[], boekingen:[], drift:[], taken:[], log:[],
    orders:[], reserveringen:[], pickjobs:[]
  };
  const nu = Date.now();
  const dag = 86400000;

  /* --- zones ------------------------------------------------------- */
  [["KG","Kleingoed"],["MV","Middenvakken"],["GV","Grootvakken"],
   ["PS","Palletstelling"],["LG","Langgoed"],["EX","Expeditie"]]
   .forEach((z,i)=>db.zones.push({id:i,code:z[0],naam:z[1]}));

  /* --- locaties ----------------------------------------------------
     Let op: KG, MV en GV zijn ALLEMAAL type PL (picklocatie), met heel
     verschillende afmetingen. In de meeste WMS'en is dat één categorie
     en moet je zelf onthouden wat waar past.                          */
  const layout=[
    ["KG",0,1,6, 32,5,[300,400,220],  12000],
    ["MV",1,1,4, 26,4,[600,400,350],  45000],
    ["GV",2,1,3, 22,3,[1200,600,500], 120000],
    ["PS",3,0,6, 24,4,[1200,800,1500],900000],
    ["LG",4,0,2, 20,2,[2400,600,400], 200000]
  ];
  let gang=1, id=0;
  for(const [zc,zi,isPick,gangen,vakken,niveaus,[L,W,H],maxG] of layout){
    for(let g=0; g<gangen; g++,gang++){
      for(let v=1; v<=vakken; v++){
        for(let n=1; n<=niveaus; n++){
          const vakPos = gang%2 ? v : 9999-v;      // snake-route
          db.locaties.push({id:id++,
            code:`${String(gang).padStart(2,"0")}-${String(v).padStart(2,"0")}-${n}`,
            zoneId:zi, typeId:isPick?0:1, aisle:gang, bay:v, level:n,
            seq:gang*1e6+vakPos*100+n*10, L,W,H,maxG, actief:1});
        }
      }
    }
  }
  [["ONTVANGST",2,8000,4000,2500,4e6],["QC-01",3,1200,800,1000,6e5],
   ["QC-02",3,1200,800,1000,6e5],["SCHADE",4,1200,800,1000,6e5],
   ["EXP-01",5,4000,2000,2000,2e6],["EXP-02",5,4000,2000,2000,2e6]]
   .forEach(([code,ti,L,W,H,maxG])=>db.locaties.push(
     {id:id++,code,zoneId:5,typeId:ti,aisle:0,bay:0,level:0,seq:0,L,W,H,maxG,actief:1}));

  /* --- artikelen en metingen ---------------------------------------
     De metingen zijn met opzet rommelig, zoals in het echt: ~10% is
     nooit gemeten, ~25% heeft alleen een opgave van de leverancier.   */
  let pid=0;
  GROEPEN.forEach(([naam,telint,prefix,aantal,mn,mx,gew,stapel],gi)=>{
    db.groepen.push({id:gi,naam,telint});
    for(let n=0;n<aantal;n++){
      const sjabloon = pick(TEKST[prefix]);
      const oms = sjabloon.replace("{a}",pick(GETAL)).replace("{b}",pick(GETAL2));
      const snel = rnd()<0.55;
      const minQty = snel ? pick([10,20,25,40,60]) : null;
      /* vierde macht: de meeste artikelen krijgen een lage vraag, een
         enkeling een hoge. Dat is de verdeling die je in het echt ziet. */
      const vraag = Math.pow(rnd(), 5) + 0.0015;
      db.artikelen.push({id:pid, sku:`${prefix}-${1000+n}`, oms, groepId:gi, vraag,
        minQty, maxQty: minQty? minQty*pick([3,4,5]) : null,
        stapelbaar:stapel, barcode:`87${String(gi).padStart(2,"0")}${String(n).padStart(6,"0")}12`});

      const L=rint(mn[0],mx[0]), W=rint(mn[1],Math.min(mx[1],L)),
            H=rint(mn[2],mx[2]), G=rint(gew[0],gew[1]);
      const r=rnd();
      if(r>=0.10){
        let bron,dagen;
        if(r<0.35){bron="SUPPLIER";dagen=rint(200,900);}
        else if(r<0.60){bron="RECEIPT";dagen=rint(190,400);}
        else {bron="RECEIPT";dagen=rint(1,170);}
        db.metingen.push({productId:pid,at:nu-dagen*dag,bron,L,W,H,G});
      }
      pid++;
    }
  });

  /* actuele maat = nieuwste meting. Altijd afgeleid, nooit opgeslagen. */
  const laatste={};
  for(const m of db.metingen){
    if(!laatste[m.productId]||m.at>laatste[m.productId].at) laatste[m.productId]=m;
  }
  db._laatste=laatste;
  db.artikelNu=function(id){
    const a=this.artikelen[id]; if(!a) return null;
    const m=this._laatste[id];
    return {...a, L:m?m.L:null, W:m?m.W:null, H:m?m.H:null, G:m?m.G:null,
            gemetenOp:m?m.at:null, bron:m?m.bron:null};
  };
  db.herbereken=function(){
    const l={};
    for(const m of this.metingen){ if(!l[m.productId]||m.at>l[m.productId].at) l[m.productId]=m; }
    this._laatste=l;
  };

  /* --- voorraad: klein artikel op kleine locatie -------------------- */
  const past=(p,loc,f=0.85)=>{
    const n=Math.floor(loc.L/p.L)*Math.floor(loc.W/p.W)*Math.floor(loc.H/p.H);
    return n===0?0:Math.max(0,Math.min(Math.floor(n*f),Math.floor(loc.maxG/p.G)));
  };
  const gemeten = db.artikelen.map(a=>db.artikelNu(a.id)).filter(p=>p.L);
  const pickLocs = db.locaties.filter(l=>LOCTYPES[l.typeId].pick)
                     .sort((a,b)=>a.L*a.W*a.H-b.L*b.W*b.H);
  const bulkLocs = db.locaties.filter(l=>LOCTYPES[l.typeId].bulk);
  const opPick={};
  let j=0;
  for(const p of [...gemeten].sort((a,b)=>a.L*a.W*a.H-b.L*b.W*b.H)){
    while(j<pickLocs.length && past(p,pickLocs[j])===0) j++;
    if(j>=pickLocs.length) break;
    if(rnd()<0.28) continue;
    const loc=pickLocs[j++], cap=past(p,loc);
    if(cap<=0) continue;
    /* ongeveer een derde zakt onder de drempel -> geeft echte aanvultaken */
    const qty = (p.minQty && rnd()<0.30)
      ? Math.max(1,Math.floor(p.minQty*(0.25+rnd()*0.6)))
      : Math.max(1,Math.floor(cap*(0.35+rnd()*0.55)));
    db.voorraad.push({productId:p.id,locationId:loc.id,qty:Math.min(qty,cap)});
    opPick[p.id]=loc.id;
  }
  /* bulk op ongeveer de helft van de pallets: een magazijn zit nooit vol,
     en zonder vrije ruimte kan de demo geen grote inslag meer plaatsen */
  const gekozen = bulkLocs.filter(()=>rnd()<0.52);
  for(const loc of gekozen){
    const p = pick(gemeten), cap = past(p,loc);
    if(cap<=0) continue;
    db.voorraad.push({productId:p.id,locationId:loc.id,
      qty:Math.max(1,Math.floor(cap*(0.4+rnd()*0.55)))});
  }

  /* --- twee maanden boekingen op echte intensiteit --------------------
     Eerder stond hier een half jaar met twintig picks per dag. Dat leek
     veel, maar het is een tiende van wat een groothandel van deze omvang
     werkelijk doet - en dan is elke berekening op vraagsnelheid onzin.
     Nu: zestig dagen op de intensiteit die de dagsimulatie ook haalt. */
  const kiesArt = wegingSampler(gemeten, p=>db.artikelen[p.id].vraag);
  const soorten=[...Array(55).fill("PICK"),...Array(15).fill("RECEIPT"),
    ...Array(15).fill("PUTAWAY"),...Array(8).fill("MOVE"),
    ...Array(4).fill("ADJUST"),...Array(3).fill("COUNT")];
  const ontvangst = db.locaties.find(l=>l.code==="ONTVANGST").id;
  const HISTORIE_DAGEN = 60, PER_DAG = 430;
  for(let i=0;i<HISTORIE_DAGEN*PER_DAG;i++){
    const d=rint(1,HISTORIE_DAGEN);
    const datum=new Date(nu-d*dag);
    if(datum.getDay()===0||datum.getDay()===6){ if(rnd()<0.85) continue; }
    const soort=pick(soorten), p=kiesArt();
    let van=null,naar=null;
    if(soort==="PICK"||soort==="ADJUST"||soort==="COUNT") van=opPick[p.id]??pick(pickLocs).id;
    else if(soort==="RECEIPT") naar=ontvangst;
    else if(soort==="PUTAWAY"){van=ontvangst;naar=opPick[p.id]??pick(pickLocs).id;}
    else {van=pick(bulkLocs).id;naar=opPick[p.id]??pick(pickLocs).id;}
    const uur=pick([7,8,8,9,9,10,10,11,11,13,13,14,14,15,16]);
    db.boekingen.push({at:nu-d*dag+(uur-12)*3600000, soort, productId:p.id,
      van, naar, qty:rint(1,40),
      reden: soort==="ADJUST"?"TELVERSCHIL":null,
      ref: soort==="PICK"?`ORD-${rint(240000,249999)}`:null});
  }
  db.boekingen.sort((a,b)=>b.at-a.at);

  /* Wanneer is elke locatie voor het laatst geteld? In een echt magazijn
     is dat een rommelige verzameling data, en juist dat maakt zichtbaar
     welke locaties al veel te lang niet meer aan de beurt zijn geweest. */
  for(const loc of db.locaties){
    if(!LOCTYPES[loc.typeId].doel) continue;
    db.locaties[loc.id].geteldOp = rnd()<0.12 ? 0 : nu - rint(5, 430)*dag;
  }
  return db;
}

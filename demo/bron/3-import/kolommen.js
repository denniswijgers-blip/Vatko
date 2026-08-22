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

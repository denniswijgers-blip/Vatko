import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
/* De demo staat één map hoger. Zo werkt de test ook als je hem vanuit
   een andere map start. */
const DEMO = 'file://' + join(dirname(fileURLToPath(import.meta.url)), '..', 'vakto-demo.html');

const b = await chromium.launch();
const p = await b.newPage({viewport:{width:1500,height:1000}});
const fouten=[];
p.on('pageerror', e=>fouten.push("PAGEERROR: "+e.message));
p.on('console', m=>{ if(m.type()==='error') fouten.push("CONSOLE: "+m.text()); });
await p.goto(DEMO);
await p.waitForTimeout(600);

const stap = async (naam)=>{ console.log("--- "+naam); };

await stap("naar Eigen gegevens");
await p.evaluate(()=>location.hash="#eigen");
await p.waitForTimeout(300);
console.log("titel:", await p.locator('h1').first().textContent());

await p.locator('[data-imp-actie="kies"][data-bron="bestand"]').click();
await p.waitForTimeout(200);

await stap("locatiebestand (csv, cm, puntkomma)");
await p.locator('[data-imp-bestand="locaties"]').setInputFiles('test-bestanden/locaties.csv');
await p.waitForTimeout(600);
console.log("melding:", await p.locator('#balk').textContent());
console.log("herkend:", await p.evaluate(()=>JSON.stringify(imp.kolom.locaties)+" eenheid="+imp.eenheid.loc_maat+"/"+imp.eenheid.loc_gew));

await stap("artikelbestand (xlsx, mm/gram, engels)");
await p.locator('[data-imp-bestand="artikelen"]').setInputFiles('test-bestanden/artikelen.xlsx');
await p.waitForTimeout(1500);
console.log("melding:", await p.locator('#balk').textContent());
console.log("herkend:", await p.evaluate(()=>JSON.stringify(imp.kolom.artikelen)+" eenheid="+imp.eenheid.art_maat+"/"+imp.eenheid.art_gew));

await stap("voorraadbestand (csv, komma)");
await p.locator('[data-imp-bestand="voorraad"]').setInputFiles('test-bestanden/voorraad.csv');
await p.waitForTimeout(600);
console.log("herkend:", await p.evaluate(()=>JSON.stringify(imp.kolom.voorraad)));

await p.locator('[data-imp-bedrijf]').fill('Kuipers Techniek B.V.');
await p.locator('[data-imp-actie="controleer"]').first().click();
await p.waitForTimeout(600);
console.log("rapport:", await p.evaluate(()=>{
  const R=imp.rapport;
  return JSON.stringify({loc:[R.locaties.rijen,R.locaties.goed], art:[R.artikelen.rijen,R.artikelen.goed],
    vrd:[R.voorraad.rijen,R.voorraad.goed],
    prob:[...R.locaties.problemen,...R.artikelen.problemen,...R.voorraad.problemen].map(x=>x.sleutel+":"+x.n)});
}));
await p.screenshot({path:'shot-import.png', fullPage:false});

await stap("overnemen");
await p.locator('[data-imp-actie="overnemen"]').click();
await p.waitForTimeout(1200);
console.log("na overnemen:", await p.evaluate(()=>JSON.stringify({
  klant:get("merk.klant"), loc:DB.locaties.length, art:DB.artikelen.length,
  vrd:DB.voorraad.filter(s=>s.qty>0).length, boek:DB.boekingen.length,
  taken:DB.taken.length, zones:DB.zones.length, groepen:DB.groepen.map(g=>g.naam)
})));

await stap("alle schermen aflopen op hun gegevens");
for(const h of ["demo","dashboard","locaties","artikelen","inslag","meten","taken","orders","picken","instellingen","eigen","etiketten","dag"]){
  await p.evaluate(x=>location.hash="#"+x, h);
  await p.waitForTimeout(260);
  const t = await p.locator('#inhoud h1').first().textContent().catch(()=>"(geen h1)");
  console.log("  ", h.padEnd(13), "->", (t||"").trim().slice(0,42));
}

await stap("inslagvoorstel op hun eigen artikel");
const inslag = await p.evaluate(()=>{
  const p2 = DB.artikelen.map(a=>DB.artikelNu(a.id)).filter(x=>x.L);
  const klein = [...p2].sort((a,b)=>a.L*a.W*a.H-b.L*b.W*b.H)[0];
  const groot = [...p2].sort((a,b)=>b.L*b.W*b.H-a.L*a.W*a.H)[0];
  const f=(x,n)=>voorstelInslag(DB,x.id,n,3).map(v=>v.loc.code+" ("+maatVan(v.loc)+", benut "+(v.benutting*100).toFixed(0)+"%)");
  return {klein:klein.sku+" "+klein.L+"x"+klein.W+"x"+klein.H, kleinVoorstel:f(klein,40),
          groot:groot.sku+" "+groot.L+"x"+groot.W+"x"+groot.H, grootVoorstel:f(groot,2)};
});
console.log(JSON.stringify(inslag,null,1));

await p.evaluate(()=>location.hash="#etiketten");
await p.waitForTimeout(400);
await p.screenshot({path:'shot-etiketten.png'});

await stap("een dag draaien op hun magazijn");
await p.evaluate(()=>{ location.hash="#dag"; });
await p.waitForTimeout(300);
await p.evaluate(()=>{ sim.snelheid=1; sim.rommel=true; startDag(); });
await p.waitForTimeout(9000);
console.log("dag:", await p.evaluate(()=>JSON.stringify({tijd:klok(sim.tijd), ...sim.teller})));

console.log("integriteit:", await p.evaluate(()=>{
  const neg = DB.voorraad.filter(s=>s.qty<0).length;
  const over = DB.voorraad.filter(s=>(s.res||0)>s.qty).length;
  return JSON.stringify({negatief:neg, overgereserveerd:over, journaal:DB.boekingen.length});
}));

await stap("terug naar Van Delden");
await p.evaluate(()=>location.hash="#eigen"); await p.waitForTimeout(300);
p.on('dialog', d=>d.accept());
await p.locator('[data-imp-actie="terug"]').click();
await p.waitForTimeout(900);
console.log("terug:", await p.evaluate(()=>JSON.stringify({klant:get("merk.klant"), loc:DB.locaties.length, art:DB.artikelen.length, eigen:!!DB.eigen})));

console.log(fouten.length ? "FOUTEN:\n"+fouten.join("\n") : "geen JS-fouten");
await b.close();

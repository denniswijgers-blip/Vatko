import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
/* De demo staat één map hoger. Zo werkt de test ook als je hem vanuit
   een andere map start. */
const DEMO = 'file://' + join(dirname(fileURLToPath(import.meta.url)), '..', 'vakto-demo.html');

const b = await chromium.launch();
const p = await b.newPage({viewport:{width:1500,height:1100}});
const f=[]; p.on('pageerror',e=>f.push('PAGEERROR: '+e.message+' | '+String(e.stack).split('\n')[1]));
p.on('console', m=>{ if(m.type()==='error' && !m.text().includes('TUNNEL')) f.push("CONSOLE: "+m.text()); });
p.on('dialog', d=>d.accept());
await p.goto(DEMO);
await p.waitForTimeout(500);

/* ---------- PAD B: magazijn opzetten zonder enig bestand ---------- */
console.log("=== PAD B: opzetten ===");
await p.evaluate(()=>location.hash="#eigen"); await p.waitForTimeout(250);
await p.locator('[data-imp-actie="kies"][data-bron="opzet"]').click(); await p.waitForTimeout(250);
console.log("zones in het formulier:", await p.locator('[data-opzet][data-veld="code"]').count());
await p.locator('[data-opzet="0"][data-veld="gangen"]').fill('5');
await p.locator('[data-opzet="0"][data-veld="gangen"]').dispatchEvent('change');
await p.waitForTimeout(250);
await p.locator('[data-imp-actie="opzet-erbij"]').click(); await p.waitForTimeout(250);
console.log("na zone erbij:", await p.evaluate(()=>imp.opzet.length + " zones, " + opzetAantal() + " locaties"));
await p.locator('[data-imp-actie="opzet-weg"][data-i="3"]').click(); await p.waitForTimeout(200);
await p.screenshot({path:'shot-opzet.png'});
await p.locator('[data-imp-actie="opzet-bouw"]').click(); await p.waitForTimeout(900);
console.log("gebouwd:", await p.evaluate(()=>JSON.stringify({
  hash:location.hash, loc:DB.locaties.length, zones:DB.zones.map(z=>z.code),
  art:DB.artikelen.length, vrd:DB.voorraad.length,
  eerste:DB.locaties[0].code, seq:DB.locaties.slice(0,3).map(l=>l.seq),
  types:[...new Set(DB.locaties.map(l=>l.typeId))]
})));
await p.waitForTimeout(300);
console.log("etiketten getekend:", await p.locator('.etiket').count(), "streepjescodes:", await p.locator('.c39').count());
await p.screenshot({path:'shot-etiketten.png'});

/* ---------- PAD C: nulmeting met de scanner ---------- */
console.log("=== PAD C: nulmeting ===");
await p.evaluate(()=>location.hash="#eigen"); await p.waitForTimeout(250);
await p.locator('[data-imp-actie="kies"][data-bron="nul"]').click(); await p.waitForTimeout(250);
await p.locator('[data-imp-nul]').selectOption('true'); await p.waitForTimeout(200);
console.log("instelling:", await p.evaluate(()=>get("opstart.onbekend_aanmaken")));
await p.evaluate(()=>{ scan.taak="TELLEN"; location.hash="#scan"; }); await p.waitForTimeout(400);

const scanIn = async (code)=>{ await p.locator('#scanInvoer').fill(code);
  await p.locator('#scanInvoer').press('Enter'); await p.waitForTimeout(220); };
const loc1 = await p.evaluate(()=>DB.locaties.find(l=>LOCTYPES[l.typeId].pick).code);
await scanIn(loc1);
console.log("na locatie:", await p.evaluate(()=>scan.stap+" | "+scan.bericht));
await scanIn("8712345678901");            // volstrekt onbekend
console.log("na onbekend artikel:", await p.evaluate(()=>scan.stap+" | "+scan.bericht));
await p.locator('#scanAantal').fill('37');
await p.locator('[data-scan-bevestig]').first().click(); await p.waitForTimeout(400);
console.log("na tellen:", await p.evaluate(()=>JSON.stringify({
  artikelen:DB.artikelen.length, laatste:DB.artikelen[DB.artikelen.length-1],
  voorraad:DB.voorraad.length, boeking:DB.boekingen[0]
})));
await p.screenshot({path:'shot-nulmeting.png'});
/* nog twee tellen, en daarna kijken of de rest van het systeem meedraait */
await scanIn(loc1); await scanIn("8712345678902");
await p.locator('#scanAantal').fill('12');
await p.locator('[data-scan-bevestig]').first().click(); await p.waitForTimeout(300);
console.log("twee artikelen ontstaan:", await p.evaluate(()=>DB.artikelen.map(a=>a.sku+" ("+a.oms.slice(0,22)+")").join(" / ")));
await p.evaluate(()=>{ scan.actief=false; location.hash="#artikelen"; }); await p.waitForTimeout(350);
console.log("artikelenscherm rijen:", await p.locator('#inhoud tbody tr').count());
await p.evaluate(()=>location.hash="#meten"); await p.waitForTimeout(300);
console.log("meetlijst:", await p.evaluate(()=>teMeten(DB).length + " te meten"));

/* ---------- onherkenbare kopjes, handmatig koppelen ---------- */
console.log("=== handmatig koppelen ===");
await p.evaluate(()=>{ terugNaarDemo(); location.hash="#eigen"; }); await p.waitForTimeout(350);
await p.locator('[data-imp-actie="kies"][data-bron="bestand"]').click(); await p.waitForTimeout(200);
await p.locator('[data-imp-bestand="locaties"]').setInputFiles('test-bestanden/raar.csv');
await p.waitForTimeout(600);
console.log("automatisch herkend:", await p.evaluate(()=>JSON.stringify(imp.kolom.locaties)));
for(const [veld,kol] of [["code","0"],["zone","1"],["L","2"],["W","3"],["H","4"]]){
  await p.locator(`[data-imp-kol="locaties"][data-veld="${veld}"]`).selectOption(kol);
  await p.waitForTimeout(180);
}
console.log("na handmatig:", await p.evaluate(()=>JSON.stringify(imp.kolom.locaties)));
await p.locator('[data-imp-actie="controleer"]').first().click(); await p.waitForTimeout(500);
console.log("rapport:", await p.evaluate(()=>JSON.stringify({goed:imp.rapport.locaties.goed,
  prob:imp.rapport.locaties.problemen.map(x=>x.sleutel+":"+x.n)})));
await p.locator('[data-imp-actie="overnemen"]').click(); await p.waitForTimeout(700);
console.log("overgenomen:", await p.evaluate(()=>DB.locaties.length+" locaties, "+DB.artikelen.length+" artikelen"));
await p.evaluate(()=>location.hash="#dashboard"); await p.waitForTimeout(300);
await p.evaluate(()=>location.hash="#inslag"); await p.waitForTimeout(300);
await p.evaluate(()=>location.hash="#demo"); await p.waitForTimeout(300);
console.log("lege omgeving overleeft alle schermen");

/* ---------- mobiel ---------- */
const m = await b.newPage({viewport:{width:390,height:844}, deviceScaleFactor:2});
m.on('pageerror',e=>f.push('MOBIEL: '+e.message));
await m.goto(DEMO); await m.waitForTimeout(500);
await m.evaluate(()=>location.hash="#eigen"); await m.waitForTimeout(400);
await m.screenshot({path:'shot-eigen-mobiel.png', fullPage:false});

console.log(f.length ? "FOUTEN:\n"+f.join("\n") : "geen JS-fouten");
await b.close();

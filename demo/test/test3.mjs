import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
/* De demo staat één map hoger. Zo werkt de test ook als je hem vanuit
   een andere map start. */
const DEMO = 'file://' + join(dirname(fileURLToPath(import.meta.url)), '..', 'vakto-demo.html');

const b = await chromium.launch();
const p = await b.newPage({viewport:{width:1500,height:1000}});
const f=[]; p.on('pageerror',e=>f.push('JS: '+e.message));
p.on('console',m=>{ if(m.type()==='error' && !m.text().includes('TUNNEL')) f.push('console: '+m.text()); });
await p.goto(DEMO);
await p.waitForSelector('#inhoud h1');

console.log('--- alle schermen ---');
for(const [h,n] of [['#demo','Rondleiding'],['#dag','Een dag'],['#dashboard','Dashboard'],
  ['#orders','Orders'],['#taken','Taken'],['#locaties','Locaties'],['#artikelen','Artikelen'],
  ['#inslag','Inslag'],['#picken','Picken'],['#meten','Opmeten'],['#inloggen','Gebruiker'],
  ['#instellingen','Instellingen']]){
  await p.evaluate(x=>{location.hash=x},h); await p.waitForTimeout(90);
  const kop=await p.textContent('#inhoud h1').catch(()=>'-');
  console.log('  '+n.padEnd(15)+kop.slice(0,32));
}

console.log('\n--- rechten ---');
for(const [id,naam] of [[2,'Kevin (medewerker)'],[1,'Ruben (teamleider)'],[0,'Dennis (beheerder)']]){
  await p.evaluate(i=>{ logIn(DB.gebruikers[i]); location.hash='#dashboard'; teken(); }, id);
  await p.waitForTimeout(90);
  const zichtbaar = await p.locator('#nav a').evaluateAll(a=>a.map(x=>x.textContent.trim().split('\n')[0]));
  const hash = await p.evaluate(()=>location.hash);
  console.log('  '+naam.padEnd(22)+'menu: '+zichtbaar.filter(x=>x&&!x.includes('@')).join(', '));
  console.log(' '.repeat(24)+'#dashboard -> '+hash);
}

console.log('\n--- scanmodus: picken van A tot Z ---');
await p.evaluate(()=>{ logIn(DB.gebruikers[0]); resetDag();
  // werk klaarzetten via dezelfde functies als de simulatie
  for(let i=0;i<3;i++){ const o=maakOrder(DB,Date.now()); reserveer(DB,o); geefVrij(DB,o); }
  location.hash='#scan'; scanStart('PICKEN'); teken(); });
await p.waitForTimeout(200);

const stap = async (code,label)=>{
  await p.fill('#scanInvoer', code);
  await p.press('#scanInvoer','Enter');
  await p.waitForTimeout(120);
  const m = await p.textContent('.scanbericht').catch(()=>'(geen melding)');
  console.log('  '+label.padEnd(30)+m.slice(0,66));
};
const info = await p.evaluate(()=>({
  loc: DB.locaties[scan.regel.locationId].code,
  sku: DB.artikelen[scan.regel.productId].sku,
  bc:  DB.artikelen[scan.regel.productId].barcode,
  qty: scan.regel.qty,
  andereLoc: DB.locaties.find(l=>l.id!==scan.regel.locationId && l.code.startsWith('01')).code
}));
console.log('  opdracht: '+info.loc+' / '+info.sku+' / '+info.qty+' st');
await stap(info.andereLoc, 'verkeerde locatie');
await stap(info.bc,        'artikel voordat locatie');
await stap(info.loc,       'juiste locatie');
await stap('87999999999',  'onbekende barcode');
await stap(info.bc,        'juist artikel (barcode)');
await p.click('[data-scan-bevestig]:not([data-nul])');
await p.waitForTimeout(150);
console.log('  afmelden'.padEnd(32)+(await p.textContent('.scanbericht').catch(()=>'-')).slice(0,66));

const na = await p.evaluate(()=>({
  gepickt: DB.pickjobs.flatMap(j=>j.regels).filter(r=>r.status==='DONE').length,
  boekingen: DB.boekingen.filter(b=>b.soort==='PICK').length,
  stap: scan.stap, volgende: scan.regel?DB.locaties[scan.regel.locationId].code:'-'
}));
console.log('  -> regels DONE:',na.gepickt,'| PICK-boekingen:',na.boekingen,'| nu bij:',na.volgende);

console.log('\n--- manco via de scanner ---');
const m = await p.evaluate(()=>({loc:DB.locaties[scan.regel.locationId].code,
                                 bc:DB.artikelen[scan.regel.productId].barcode,
                                 qty:scan.regel.qty}));
console.log('  opdracht: '+m.loc+' / '+m.qty+' st');
await stap(m.loc,'locatie');
await stap(m.bc,'artikel');
await p.click('[data-scan-bevestig][data-nul]');
await p.waitForTimeout(150);
const mancoInfo = await p.evaluate(()=>({
  bericht: scan.bericht,
  telTaken: DB.taken.filter(t=>t.soort==='CYCLE_COUNT').length
}));
console.log('  '+(mancoInfo.bericht||'-').slice(0,80));
console.log('  teltaken aangemaakt:', mancoInfo.telTaken);

await p.setViewportSize({width:420,height:900});
await p.waitForTimeout(200);
await p.screenshot({path:'shot-scan.png'});
await b.close();
console.log('\n'+(f.length?'FOUTEN:\n'+f.join('\n'):'0 fouten'));

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

// alle schermen
console.log('scherm'.padEnd(16)+'ms'.padStart(5)+'  kop');
console.log('-'.repeat(52));
for(const [h,n] of [['#demo','Rondleiding'],['#dag','Een dag'],['#dashboard','Dashboard'],
  ['#orders','Orders'],['#taken','Taken'],['#locaties','Locaties'],['#artikelen','Artikelen'],
  ['#inslag','Inslag'],['#picken','Picken'],['#meten','Opmeten'],['#instellingen','Instellingen']]){
  const t=Date.now(); await p.evaluate(x=>{location.hash=x},h); await p.waitForTimeout(110);
  console.log(n.padEnd(16)+String(Date.now()-t).padStart(5)+'  '+(await p.textContent('#inhoud h1')).slice(0,30));
}

// hele dag doorspelen
console.log('\n--- volledige dag doorspelen ---');
await p.evaluate(()=>{location.hash='#dag'}); await p.waitForTimeout(150);
const t0=Date.now();
const r = await p.evaluate(()=>{
  resetDag();
  while(sim.tijd < DAGEIND) tik();
  const orders=DB.orders;
  const som=k=>orders.reduce((a,o)=>a+o.regels.reduce((x,r)=>x+(r[k]||0),0),0);
  const perStatus={};
  for(const o of orders) perStatus[o.status]=(perStatus[o.status]||0)+1;
  return {binnen:sim.teller.binnen, verzonden:sim.teller.verzonden,
    regels:sim.teller.regels, stuks:sim.teller.stuks, manco:sim.teller.manco,
    besteld:som('besteld'), gepickt:som('gepickt'), mancoStuks:som('manco'),
    perStatus, taken:DB.taken.filter(t=>t.status==='TODO').length,
    boekingen:DB.boekingen.filter(b=>b.ref&&b.ref.startsWith('ORD-')).length,
    negatief:DB.voorraad.filter(s=>s.qty<0).length,
    resFout:DB.voorraad.filter(s=>(s.res||0)>s.qty).length};
});
console.log('rekentijd hele dag:', Date.now()-t0,'ms');
console.log(`orders binnen ${r.binnen} | verzonden ${r.verzonden} | regels gepickt ${r.regels} | stuks ${r.stuks}`);
console.log(`manco's ${r.manco} (${r.mancoStuks} stuks) | open taken ${r.taken}`);
console.log('orderstatussen:', JSON.stringify(r.perStatus));
console.log('CONTROLE negatieve voorraad:', r.negatief, '| reservering > voorraad:', r.resFout);
await p.waitForTimeout(200);
await p.screenshot({path:'shot-dag.png'});
await p.evaluate(()=>{location.hash='#picken'}); await p.waitForTimeout(200);
await p.screenshot({path:'shot-picken.png'});
await b.close();
console.log('\n'+(f.length?'FOUTEN:\n'+f.join('\n'):'0 fouten'));

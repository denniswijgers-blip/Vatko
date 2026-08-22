import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
/* De demo staat één map hoger. Zo werkt de test ook als je hem vanuit
   een andere map start. */
const DEMO = 'file://' + join(dirname(fileURLToPath(import.meta.url)), '..', 'vakto-demo.html');

const b = await chromium.launch();
const p = await b.newPage();
const fouten = [];
p.on('pageerror', e => fouten.push('JS-fout: ' + e.message));
p.on('console', m => { if (m.type() === 'error') fouten.push('console: ' + m.text()); });

const t0 = Date.now();
await p.goto(DEMO);
await p.waitForSelector('#inhoud h1');
console.log('laadtijd:', Date.now() - t0, 'ms');
console.log('titel   :', await p.title());

const schermen = [
  ['#demo','Rondleiding'], ['#dashboard','Dashboard'], ['#locaties','Locaties'],
  ['#locatie/5','Locatie klein'], ['#locatie/2000','Locatie pallet'],
  ['#artikelen','Artikelen'], ['#artikel/12','Artikel'],
  ['#inslag','Inslag'], ['#meten','Opmeten'], ['#taken','Taken'],
  ['#instellingen','Instellingen'],
];
console.log('\n' + 'scherm'.padEnd(18) + 'ms'.padStart(6) + '   kop');
console.log('-'.repeat(62));
for (const [hash, naam] of schermen) {
  const t = Date.now();
  await p.evaluate(h => { location.hash = h; }, hash);
  await p.waitForTimeout(120);
  const kop = await p.textContent('#inhoud h1');
  const rijen = await p.locator('#inhoud tbody tr').count();
  console.log(naam.padEnd(18) + String(Date.now()-t).padStart(6) + '   ' +
              kop.slice(0,26).padEnd(27) + rijen + ' rijen');
}

// demo-doorklik: precies wat Dennis bij een klant doet
console.log('\ndemo-doorklik:');
await p.evaluate(() => { location.hash = '#demo'; });
await p.waitForTimeout(150);
const links = await p.locator('a[href^="#inslag/"]').evaluateAll(a => a.map(x => x.getAttribute('href')));
for (const l of links) {
  await p.evaluate(h => { location.hash = h; }, l);
  await p.waitForTimeout(200);
  const eerste = await p.locator('#inhoud tr.beste td:nth-child(2) a').textContent().catch(()=>null);
  const maat = await p.locator('#inhoud tr.beste .maat').textContent().catch(()=>null);
  const ben = await p.locator('#inhoud tr.beste td:nth-child(7) .hint').textContent().catch(()=>null);
  console.log('  ' + l.padEnd(26) + ' -> ' + (eerste||'geen') + ' (' + (maat||'-') + ', benutting ' + (ben||'-') + ')');
}
await b.close();
console.log('\n' + (fouten.length ? 'FOUTEN:\n' + fouten.join('\n') : '0 fouten'));

import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
const DEMO = 'file://' + join(dirname(fileURLToPath(import.meta.url)), '..', 'vakto-demo.html');
const b = await chromium.launch();
const p = await b.newPage({viewport:{width:1400,height:900}, deviceScaleFactor:1.5});
const fouten=[]; p.on('pageerror',e=>fouten.push(e.message));
await p.goto(DEMO); await p.waitForSelector('#inhoud h1'); await p.waitForTimeout(400);
await p.screenshot({path:'rook-dashboard.png'});
// menu, iconen, palet en een paar schermen
const nav = await p.$$eval('#nav a, #nav [data-pagina]', els=>els.length);
const ico = await p.$$eval('#nav svg.ico', els=>els.length);
await p.keyboard.press('Meta+k'); await p.waitForTimeout(300);
const paletOpen = await p.$eval('#palet', el=>!el.hidden);
await p.keyboard.press('Escape'); await p.waitForTimeout(200);
for(const h of ['#inslag','#optimalisatie','#locaties','#orders']){
  await p.goto(DEMO + h); await p.waitForTimeout(350);
}
await p.screenshot({path:'rook-orders.png'});
console.log(JSON.stringify({navItems:nav, iconen:ico, paletOpent:paletOpen, fouten}));
await b.close();

import { chromium } from 'playwright';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';
/* De demo staat één map hoger. Zo werkt de test ook als je hem vanuit
   een andere map start. */
const DEMO = 'file://' + join(dirname(fileURLToPath(import.meta.url)), '..', 'vakto-demo.html');

const b = await chromium.launch();
const f=[];
async function pak(thema, achter){
  const p = await b.newPage({viewport:{width:1440,height:1000}, deviceScaleFactor:2,
    colorScheme: achter});
  p.on('pageerror',e=>f.push('PAGEERROR: '+e.message));
  await p.goto(DEMO);
  await p.waitForTimeout(700);
  if(thema) await p.evaluate(t=>document.documentElement.setAttribute("data-theme",t), thema);
  const naam = thema || "auto";
  for(const [hash,bestand] of [["#inslag/AAN-1229/24","inslag"],["#dashboard","dashboard"],
                               ["#locaties","locaties"],["#dag","dag"]]){
    await p.evaluate(h=>location.hash=h, hash);
    await p.waitForTimeout(1200);
    await p.screenshot({path:`nw-${bestand}-${naam}.png`});
  }
  await p.close();
}
await pak("light","light");
await pak("dark","dark");

/* contrast van de nieuwe tokens */
const p = await b.newPage();
await p.goto(DEMO); await p.waitForTimeout(500);
const lum = (hex)=>{const c=hex.replace('#','');
  const v=[0,2,4].map(i=>parseInt(c.slice(i,i+2),16)/255)
   .map(x=>x<=0.03928?x/12.92:Math.pow((x+0.055)/1.055,2.4));
  return 0.2126*v[0]+0.7152*v[1]+0.0722*v[2];};
const ratio=(a,bb)=>{const l1=lum(a),l2=lum(bb);return (Math.max(l1,l2)+.05)/(Math.min(l1,l2)+.05);};
for(const thema of ["light","dark"]){
  const t = await p.evaluate(th=>{
    document.documentElement.setAttribute("data-theme",th);
    const cs=getComputedStyle(document.documentElement);
    const g=n=>cs.getPropertyValue(n).trim();
    return {ink:g('--ink'),ink2:g('--ink-2'),ink3:g('--ink-3'),surface:g('--surface'),
      ground:g('--ground'),surface2:g('--surface-2'),accent:g('--accent'),
      accentink:g('--accent-ink'),accentsoft:g('--accent-soft'),nav:g('--nav-2'),
      navink:g('--nav-ink'),navink2:g('--nav-ink-2'),ok:g('--ok'),oks:g('--ok-soft'),
      warn:g('--warn'),warns:g('--warn-soft'),bad:g('--bad'),bads:g('--bad-soft')};
  }, thema);
  const tests=[["ink/surface",t.ink,t.surface,4.5],["ink2/surface",t.ink2,t.surface,4.5],
    ["ink3/surface",t.ink3,t.surface,3],["ink/ground",t.ink,t.ground,4.5],
    ["ink2/surface2",t.ink2,t.surface2,4.5],
    ["accentink/accent",t.accentink,t.accent,4.5],["accent/accentsoft",t.accent,t.accentsoft,4.5],
    ["navink/nav",t.navink,t.nav,4.5],["navink2/nav",t.navink2,t.nav,3],
    ["ok/oksoft",t.ok,t.oks,4.5],["warn/warnsoft",t.warn,t.warns,4.5],
    ["bad/badsoft",t.bad,t.bads,4.5],["accent/surface",t.accent,t.surface,4.5]];
  const stuk = tests.filter(([n,x,y,m])=>ratio(x,y)<m)
    .map(([n,x,y,m])=>`  !! ${n} ${ratio(x,y).toFixed(2)} < ${m}`);
  console.log(`[${thema}] ${stuk.length? "\n"+stuk.join("\n") : "alle contrasten halen de norm"}`);
}
console.log(f.length? "FOUTEN:\n"+f.join("\n") : "geen JS-fouten");
await b.close();

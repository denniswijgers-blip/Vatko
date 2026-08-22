/* =====================================================================
   GRAFIEKEN

   Met de hand getekende SVG, geen bibliotheek: dit bestand moet offline
   in een magazijn openen. Regels die overal gelden:

     - dunne strepen, rustig raster, de gegevens zijn het enige wat mag
       schreeuwen
     - één maatstreep per as, nooit twee y-assen naast elkaar
     - kleur zegt WIE, niet HOEVEEL: twee series krijgen twee vaste
       kleuren die ook voor kleurenblinden uit elkaar te houden zijn
       (gecontroleerd op deutaan, protaan en tritaan)
     - groen, oranje en rood blijven gereserveerd voor goed, let op en
       fout; die komen nooit als "serie 3" terug
     - cijfers staan in de tabel eronder, dus niemand mist iets als hij
       de grafiek niet kan lezen
   ===================================================================== */

/* Nette ronde stappen op de y-as: 0 / 25 / 50, niet 0 / 23 / 46. */
function asStappen(max){
  const ruw = Math.max(max,1)/4;
  const macht = Math.pow(10, Math.floor(Math.log10(ruw)));
  const stap = [1,2,2.5,5,10].map(m=>m*macht).find(s=>s>=ruw) || macht*10;
  const top = Math.max(stap, Math.ceil(max/stap)*stap);
  const ticks = [];
  for(let v=0; v<=top+1e-9; v+=stap) ticks.push(Math.round(v*100)/100);
  return {top, ticks};
}
const kort = (n)=> n>=10000 ? (n/1000).toFixed(0)+"k" : fmt(n);

/* Staaf met ronde bovenkant en vierkante voet: hij groeit uit de nullijn. */
function staafPad(x,y,w,h,r=4){
  if(h<=0.6) return "";
  r = Math.min(r, w/2, h);
  return `M${x} ${y+h}L${x} ${y+r}Q${x} ${y} ${x+r} ${y}L${x+w-r} ${y}`
       + `Q${x+w} ${y} ${x+w} ${y+r}L${x+w} ${y+h}Z`;
}

/* --- vlakgrafiek: één reeks over de tijd ---------------------------- */
function grafiekVlak({punten, hoogte=200, eenheid="", stippen=false, titel=""}){
  if(!punten || punten.length<2) return `<p class="leeg">Te weinig gegevens voor een grafiek.</p>`;
  const B=720, M={l:46,r:16,t:14,b:30};
  const w=B-M.l-M.r, h=hoogte-M.t-M.b;
  const {top,ticks} = asStappen(Math.max(...punten.map(p=>p.y)));
  const X = i => M.l + i*w/(punten.length-1);
  const Y = v => M.t + h - (v/top)*h;

  const d = punten.map((p,i)=>`${i?"L":"M"}${X(i).toFixed(1)} ${Y(p.y).toFixed(1)}`).join("");
  const vlak = `${d}L${X(punten.length-1).toFixed(1)} ${M.t+h}L${M.l} ${M.t+h}Z`;
  const laatste = punten[punten.length-1];

  /* om de hoeveel punten een datumlabel, zodat ze elkaar niet raken */
  const om = Math.max(1, Math.ceil(punten.length/7));

  return `
  <div class="grafiekvak">
    <svg viewBox="0 0 ${B} ${hoogte}" role="img" class="gr"
         aria-label="${esc(titel||"grafiek")}">
      ${ticks.map(v=>`
        <line class="gr-raster" x1="${M.l}" x2="${B-M.r}" y1="${Y(v)}" y2="${Y(v)}"/>
        <text class="gr-as" x="${M.l-8}" y="${Y(v)+3.5}" text-anchor="end">${kort(v)}</text>`).join("")}
      <path class="gr-vlak" d="${vlak}"/>
      <path class="gr-lijn" d="${d}"/>
      ${stippen?punten.map((p,i)=>`<circle class="gr-stip" cx="${X(i).toFixed(1)}"
        cy="${Y(p.y).toFixed(1)}" r="4.5"/>`).join(""):""}
      <circle class="gr-eind" cx="${X(punten.length-1).toFixed(1)}"
              cy="${Y(laatste.y).toFixed(1)}" r="5"/>
      ${punten.map((p,i)=> i%om===0 || i===punten.length-1 ? `
        <text class="gr-as" x="${X(i).toFixed(1)}" y="${M.t+h+18}"
              text-anchor="${i===0?"start":i===punten.length-1?"end":"middle"}">${esc(p.label)}</text>`:"").join("")}
      ${punten.map((p,i)=>`<rect class="gr-raak" x="${(X(i)-w/(punten.length-1)/2).toFixed(1)}"
        y="${M.t}" width="${(w/(punten.length-1)).toFixed(1)}" height="${h}"
        data-tip="${esc(p.label)} — ${fmt(p.y)} ${esc(eenheid)}"></rect>`).join("")}
    </svg>
  </div>`;
}

/* --- gegroepeerde staven: twee reeksen naast elkaar per uur --------- */
function grafiekGroep({groepen, series, hoogte=214, eenheid=""}){
  if(!groepen || !groepen.length) return `<p class="leeg">Nog geen gegevens. Start de dag.</p>`;
  const B=720, M={l:46,r:16,t:14,b:30};
  const w=B-M.l-M.r, h=hoogte-M.t-M.b;
  const alle = groepen.flatMap(g=>g.waarden);
  const {top,ticks} = asStappen(Math.max(1,...alle));
  const Y = v => M.t + h - (v/top)*h;
  const vak = w/groepen.length;
  const n = series.length;
  const sb = Math.min(22, (vak-10)/n - 2);          /* nooit dikker dan 22 */
  const groep = sb*n + 2*(n-1);

  return `
  <div class="grafiekvak">
    <div class="gr-legenda">
      ${series.map((s,i)=>`<span class="gr-sleutel">
        <i class="gr-vlek s${i+1}"></i>${esc(s.naam)}</span>`).join("")}
    </div>
    <svg viewBox="0 0 ${B} ${hoogte}" role="img" class="gr"
         aria-label="Per uur: ${series.map(s=>s.naam).join(" en ")}">
      ${ticks.map(v=>`
        <line class="gr-raster" x1="${M.l}" x2="${B-M.r}" y1="${Y(v)}" y2="${Y(v)}"/>
        <text class="gr-as" x="${M.l-8}" y="${Y(v)+3.5}" text-anchor="end">${kort(v)}</text>`).join("")}
      ${groepen.map((g,gi)=>{
        const x0 = M.l + gi*vak + (vak-groep)/2;
        return g.waarden.map((v,si)=>{
          const x = x0 + si*(sb+2), y = Y(v), hh = M.t+h-y;
          return `<path class="gr-staaf s${si+1}" d="${staafPad(x,y,sb,hh)}"
            data-tip="${esc(g.label)} — ${esc(series[si].naam)}: ${fmt(v)} ${esc(eenheid)}"/>`;
        }).join("");
      }).join("")}
      ${groepen.map((g,gi)=>`<text class="gr-as" x="${(M.l+gi*vak+vak/2).toFixed(1)}"
        y="${M.t+h+18}" text-anchor="middle">${esc(g.label)}</text>`).join("")}
    </svg>
  </div>`;
}

/* --- liggende balken: bezetting per maatklasse ---------------------- */
function grafiekBalken({rijen, eenheid=""}){
  if(!rijen || !rijen.length) return `<p class="leeg">Geen gegevens.</p>`;
  const max = Math.max(1, ...rijen.map(r=>r.totaal));
  return `
  <div class="balkgrafiek">
    ${rijen.map(r=>{
      const pct = Math.round(r.waarde/r.totaal*100);
      return `<div class="bg-rij" data-tip="${esc(r.label)} — ${fmt(r.waarde)} van ${fmt(r.totaal)} bezet (${pct}%)">
        <span class="bg-naam">${r.pil||""}<span class="bg-tekst">${esc(r.label)}</span></span>
        <span class="bg-spoor" style="width:${(r.totaal/max*100).toFixed(1)}%">
          <i style="width:${pct}%"></i></span>
        <span class="bg-waarde">${fmt(r.waarde)}<span class="bg-van"> / ${fmt(r.totaal)}</span></span>
        <span class="bg-pct">${pct}%</span>
      </div>`;
    }).join("")}
  </div>`;
}

/* --- liggende staven voor een enkele grootheid ----------------------
   Eén reeks, dus geen legenda: de kop zegt al wat er staat. Waarde aan
   de punt van de staaf, want dat is de enige plek waar hij niet in de
   weg staat. */
function grafiekLiggend({rijen, eenheid=""}){
  if(!rijen || !rijen.length) return `<p class="leeg">Geen gegevens.</p>`;
  const max = Math.max(...rijen.map(r=>r.waarde), 1);
  return `
  <div class="balkgrafiek">
    ${rijen.map(r=>`
      <div class="bg-rij enkel" data-tip="${esc(r.label)} — ${esc(r.tip||(r.toon||r.waarde)+" "+eenheid)}">
        <span class="bg-naam">${r.pil||""}<span class="bg-tekst">${esc(r.label)}</span></span>
        <span class="bg-spoor vol"><i style="width:${(r.waarde/max*100).toFixed(1)}%"></i></span>
        <span class="bg-waarde">${esc(r.toon ?? fmt(r.waarde))}</span>
        <span class="bg-pct">${r.extra||""}</span>
      </div>`).join("")}
  </div>`;
}

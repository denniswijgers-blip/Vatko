/* =====================================================================
   KLEINE HULPMIDDELEN

   Ontsnappen, pillen, maatlabels en pagineren. Wordt door elk scherm
   gebruikt, dus dit bestand wordt als eerste geladen.
   ===================================================================== */

const el = (h)=>{const d=document.createElement("div");d.innerHTML=h.trim();return d;};
const esc = (s)=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const maatVan = (loc)=>maatKlasse(loc.L*loc.W*loc.H/1000);
const pil=(k,t)=>`<span class="pil ${k}">${esc(t)}</span>`;
const maatPil=(m)=>`<span class="maat ${m}">${m}</span>`;
let staat = {pagina:1, zoek:"", filterType:"", filterMaat:"", inslagSku:"", inslagQty:24};

/* --- paginering: nooit een scherm zonder limiet --------------------- */
function pagineer(rijen){
  const per = getN("ui.rows_per_page");
  const laatste = Math.max(1, Math.ceil(rijen.length/per));
  const p = Math.min(staat.pagina, laatste);
  return {rijen: rijen.slice((p-1)*per, p*per), p, laatste, totaal:rijen.length,
          van:rijen.length?(p-1)*per+1:0, tot:Math.min(p*per, rijen.length)};
}
function pagBalk(pg){
  if(!pg.totaal) return "";
  const knop=(n,t,uit)=>uit?"":`<button class="stil klein" data-pagina="${n}">${t}</button>`;
  return `<div class="pagbalk">
    <span class="hint">${fmt(pg.van)}&ndash;${fmt(pg.tot)} van ${fmt(pg.totaal)}</span>
    ${pg.laatste>1?`<span class="pagknoppen">
      ${knop(pg.p-1,"Vorige",pg.p<=1)}
      <span class="hint">pagina ${pg.p} van ${pg.laatste}</span>
      ${knop(pg.p+1,"Volgende",pg.p>=pg.laatste)}</span>`:""}</div>`;
}

/* =====================================================================
   SCHERM: OPTIMALISATIE

   Wat het systeem zelf gevonden heeft en waar het een oordeel van een
   mens voor nodig heeft.
   ===================================================================== */

/* ===================== OPTIMALISATIE ================================ */
function schermOptimalisatie(){
  const open = DB.taken.filter(t=>t.status==="TODO");
  const samen = open.filter(t=>t.soort==="SAMENVOEG");
  const tel   = open.filter(t=>t.soort==="CYCLE_COUNT" && t.aanleiding==="telinterval");
  const telManco = open.filter(t=>t.soort==="CYCLE_COUNT" && t.aanleiding!=="telinterval");
  const aanvul= open.filter(t=>t.soort==="REPLENISH");
  const perAanleiding = {ordervraag:[], hardloper:[], drempel:[]};
  for(const t of aanvul) (perAanleiding[t.aanleiding||"drempel"] ||= []).push(t);
  const vrij = new Set(samen.map(t=>t.van)).size;

  const snel = pickSnelheden(DB);
  const dekking = getN("opt.dekking_dagen");
  const hard = [...snel.entries()]
    .filter(([,v])=>v >= getN("opt.hardloper_per_dag"))
    .sort((a,b)=>b[1]-a[1]).slice(0,8)
    .map(([pid,perDag])=>{
      const opPick = DB.voorraad.filter(s=>s.productId===pid && s.qty>0
        && LOCTYPES[DB.locaties[s.locationId].typeId].pick).reduce((a,s)=>a+s.qty,0);
      const heeftPick = DB.voorraad.some(s2=>s2.productId===pid && s2.qty>0
        && LOCTYPES[DB.locaties[s2.locationId].typeId].pick);
      const d = perDag>0 ? opPick/perDag : 99;
      return {pid, sku:DB.artikelen[pid].sku, oms:DB.artikelen[pid].oms,
              perDag, opPick, dagen:d, heeftPick};
    });

  const adv = DB.adviezen || [];

  return `
  <h1>Optimalisatie</h1>
  <p class="lead">Vier dingen waar een magazijn geld op verliest zonder het te merken.
  Vakto rekent ze door na elke boeking en zet het werk klaar. <b>Niemand vult hier iets in</b>
  &mdash; en zodra de aanleiding weg is, vervalt de taak vanzelf.</p>

  <div class="tegels vier">
    <a class="kaart tegel" href="#taken"><span class="label">Locaties vrij te spelen</span>
      <span class="cijfer">${fmt(vrij)}</span>
      <span class="hint">door voorraad samen te voegen</span></a>
    <a class="kaart tegel" href="#taken"><span class="label">Aanvullen voor orders</span>
      <span class="cijfer ${perAanleiding.ordervraag.length?"slecht":""}">${fmt(perAanleiding.ordervraag.length)}</span>
      <span class="hint">er wacht werk op</span></a>
    <a class="kaart tegel" href="#taken"><span class="label">Hardlopers bijvullen</span>
      <span class="cijfer">${fmt(perAanleiding.hardloper.length)}</span>
      <span class="hint">onder ${dekking} dagen dekking</span></a>
    <a class="kaart tegel" href="#taken"><span class="label">Te tellen locaties</span>
      <span class="cijfer">${fmt(tel.length)}</span>
      <span class="hint">over hun telinterval${telManco.length?` &middot; +${fmt(telManco.length)} na manco`:""}</span></a>
  </div>

  <div class="kaart">
    <h2>Voorraad samenvoegen</h2>
    <p class="hint">Hetzelfde artikel op meerdere plekken kost je locaties &mdash; en locaties
      zijn het duurste wat een magazijn heeft. Vakto zoekt de gevallen waar <b>alles</b> op één
      plek past, houdt de picklocatie altijd in stand, en blijft af van voorraad die al voor een
      order gereserveerd is.</p>
    ${samen.length?`<div class="tabelwrap"><table>
      <thead><tr><th>Artikel</th><th>Van</th><th>Naar</th><th class="num">Aantal</th>
        <th>Wat het oplevert</th><th></th></tr></thead>
      <tbody>${samen.slice(0,12).map(t=>`<tr>
        <td><a href="#artikel/${t.productId}" class="mono sterk">${esc(DB.artikelen[t.productId].sku)}</a>
          <div class="hint">${esc(DB.artikelen[t.productId].oms)}</div></td>
        <td class="mono">${esc(DB.locaties[t.van].code)}</td>
        <td class="mono">${esc(DB.locaties[t.naar].code)}</td>
        <td class="num sterk">${fmt(t.qty)}</td>
        <td class="hint">${esc(DB.locaties[t.van].code)} komt vrij
          ${maatPil(maatVan(DB.locaties[t.van]))}</td>
        <td><button class="klein" data-taak="${t.id}">Afmelden</button></td>
      </tr>`).join("")}</tbody></table></div>
      ${samen.length>12?`<p class="hint">Nog ${fmt(samen.length-12)} meer in de takenlijst.</p>`:""}`
    :`<p class="leeg">Niets samen te voegen. Elk artikel ligt op één plek, of het past niet op één plek.</p>`}
  </div>

  <div class="tweeluik">
    <div class="kaart">
      <h2>Hardlopers en hun dekking</h2>
      <p class="hint">Hoeveel stuks gaan er per dag uit, gemeten over de laatste
        ${getN("opt.venster_dagen")} dagen uit het journaal. Niet uit een veld dat iemand ooit
        heeft ingevuld.</p>
      ${grafiekLiggend({rijen: hard.map(h=>({
        label:h.sku, waarde:h.perDag, toon:h.perDag.toFixed(1),
        tip:`${h.sku} — ${h.perDag.toFixed(1)} st per dag, ${fmt(h.opPick)} op de picklocatie`,
        extra: h.heeftPick ? `${h.dagen>=99?"&infin;":h.dagen.toFixed(1)} dg` : "geen vak",
        pil: !h.heeftPick ? pil("r","los") : h.dagen < dekking ? pil("o","laag") : pil("g","ok")
      })), eenheid:"st per dag"})}
      <p class="hint">De laatste kolom is de <b>dekking</b>: hoeveel dagen je met de huidige
        picklocatie vooruit kunt. Zakt die onder ${dekking}, dan zet Vakto zelf een aanvultaak
        klaar &mdash; vóór de picker misgrijpt, niet erna.</p>
    </div>

    <div class="kaart">
      <h2>Waarom er wordt aangevuld</h2>
      <p class="hint">Drie aanleidingen, één takenlijst. De zwaarste aanleiding wint: staat er
        een order op te wachten, dan schuift die taak vooraan.</p>
      <div class="tabelwrap"><table>
        <thead><tr><th>Aanleiding</th><th>Wat het betekent</th>
          <th class="num">Prio</th><th class="num">Open</th></tr></thead>
        <tbody>
          <tr><td>${pil("r","ordervraag")}</td>
            <td class="hint">Er staan orders open die meer vragen dan er op de picklocatie ligt.</td>
            <td class="num">10</td><td class="num sterk">${fmt(perAanleiding.ordervraag.length)}</td></tr>
          <tr><td>${pil("o","hardloper")}</td>
            <td class="hint">Verbruik zegt dat het vak binnen ${dekking} dagen leeg is.</td>
            <td class="num">20</td><td class="num sterk">${fmt(perAanleiding.hardloper.length)}</td></tr>
          <tr><td>${pil("n","drempel")}</td>
            <td class="hint">Klassiek: onder de ingestelde minimumvoorraad.</td>
            <td class="num">25</td><td class="num sterk">${fmt(perAanleiding.drempel.length)}</td></tr>
        </tbody></table></div>
      <div class="uitleg"><b>Waarom dit uitmaakt.</b> De meeste systemen kennen alleen de derde
        regel. Die reageert pas als het al te laat is, en hij weet niets van wat er vandaag
        besteld is. De eerste twee zorgen dat de picker het vak vol vindt zonder dat iemand
        's ochtends een lijstje heeft doorgelopen.</div>
    </div>
  </div>

  ${(DB.zonderPick||[]).length?`
  <div class="kaart">
    <h2>Hardlopers zonder picklocatie ${pil("r",DB.zonderPick.length)}</h2>
    <p class="hint">Deze artikelen gaan hard, maar liggen alleen in bulk. Elke order laat een
      picker naar de palletstelling lopen, en dat kost per regel meer dan wat het artikel
      opbrengt. Vakto heeft een geschikt vak uitgerekend &mdash; <b>welk vak je vrijmaakt is
      een keuze</b>, dus dit gaat niet vanzelf.</p>
    <div class="tabelwrap"><table>
      <thead><tr><th>Artikel</th><th class="num">Per dag</th><th>Nu in bulk</th>
        <th>Voorgesteld vak</th><th class="num">Startvoorraad</th><th></th></tr></thead>
      <tbody>${DB.zonderPick.map((z,i)=>`<tr>
        <td><a href="#artikel/${z.pid}" class="mono sterk">${esc(DB.artikelen[z.pid].sku)}</a>
          <div class="hint">${esc(DB.artikelen[z.pid].oms)}</div></td>
        <td class="num sterk">${z.perDag.toFixed(1)}</td>
        <td class="mono">${esc(DB.locaties[z.van].code)}</td>
        <td><span class="mono sterk">${esc(DB.locaties[z.naar].code)}</span>
          ${maatPil(maatVan(DB.locaties[z.naar]))}</td>
        <td class="num">${fmt(z.qty)}</td>
        <td><button class="klein" data-pickplek="${i}">Vak inrichten</button></td>
      </tr>`).join("")}</tbody></table></div>
  </div>`:""}

  <div class="kaart">
    <h2>Aanvuldrempels die niet meer kloppen ${adv.length?pil("o",adv.length):""}</h2>
    <p class="hint">Een drempel die drie jaar geleden is ingetypt, is precies zo betrouwbaar als
      een artikelmaat die drie jaar geleden is ingetypt. Vakto vergelijkt hem met het werkelijke
      verbruik. <b>Dit is een advies, geen taak</b> &mdash; hoeveel je op de vloer wilt hebben
      is een besluit, en besluiten horen bij mensen.</p>
    ${adv.length?`<div class="tabelwrap"><table>
      <thead><tr><th>Artikel</th><th class="num">Per dag</th><th class="num">Drempel nu</th>
        <th class="num">Zou moeten</th><th>Richting</th><th></th></tr></thead>
      <tbody>${adv.slice(0,10).map((a,i)=>`<tr>
        <td><a href="#artikel/${a.pid}" class="mono sterk">${esc(a.sku)}</a>
          <div class="hint">${esc(a.oms)}</div></td>
        <td class="num">${a.perDag.toFixed(1)}</td>
        <td class="num">${fmt(a.nu)}</td>
        <td class="num sterk">${fmt(a.zou)}</td>
        <td>${a.richting==="omhoog"?pil("r","te laag \u2014 misgrijpen"):pil("o","te hoog \u2014 onnodig voorraad")}</td>
        <td><button class="klein" data-advies="${i}" data-keuze="neem">Overnemen</button>
            <button class="klein stil" data-advies="${i}" data-keuze="negeer">Laten</button></td>
      </tr>`).join("")}</tbody></table></div>
      ${adv.length>10?`<p class="hint">Nog ${fmt(adv.length-10)} andere adviezen.</p>`:""}`
    :`<p class="leeg">Alle aanvuldrempels liggen binnen
      ${getN("opt.drempel_afwijking_pct")}% van het werkelijke verbruik.</p>`}
  </div>

  <div class="kaart">
    <h2>Telplan</h2>
    <p class="hint">Elke artikelgroep heeft een eigen telinterval &mdash; bevestigingsmateriaal
      vaker dan pompen. Vakto zet de locaties klaar die het verst over tijd zijn, met een plafond
      van ${getN("opt.max_open_teltaken")} open teltaken. Zonder plafond staan er duizend klaar en
      telt niemand er één.</p>
    ${tel.length?`<div class="tabelwrap"><table>
      <thead><tr><th>Locatie</th><th>Artikel</th><th class="num">Systeem zegt</th>
        <th>Reden</th><th></th></tr></thead>
      <tbody>${tel.slice(0,12).map(t=>`<tr>
        <td><a href="#locatie/${t.naar}" class="mono sterk">${esc(DB.locaties[t.naar].code)}</a></td>
        <td class="mono">${esc(DB.artikelen[t.productId].sku)}</td>
        <td class="num">${fmt(t.qty)}</td>
        <td class="hint">${esc(t.reden)}</td>
        <td><a class="knop klein stil" href="#scan" data-scan-taak="TELLEN">Tellen</a></td>
      </tr>`).join("")}</tbody></table></div>`
    :`<p class="leeg">Geen locatie is over zijn telinterval.</p>`}
  </div>

  <div class="kaart">
    <h2>Alle knoppen staan in de instellingen</h2>
    <p class="hint">Dekking in dagen, wanneer iets een hardloper is, over welke periode het
      verbruik wordt gemeten, hoeveel teltaken er tegelijk open mogen staan. Bij elke klant
      staan die anders, en er hoeft geen regel code voor aangepast te worden.</p>
    <div class="knoprij"><a class="knop stil" href="#instellingen">Naar de instellingen &rarr;</a>
      <a class="knop stil" href="#taken">Alle taken &rarr;</a></div>
  </div>`;
}

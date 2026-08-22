/* ===================== LOCATIES ===================================== */
function schermLocaties(){
  let rijen = DB.locaties.filter(l=>{
    const t=LOCTYPES[l.typeId];
    if(staat.filterType && t.code!==staat.filterType) return false;
    if(staat.filterMaat && maatVan(l)!==staat.filterMaat) return false;
    return true;
  }).sort((a,b)=>a.seq-b.seq||a.code.localeCompare(b.code));
  const pg = pagineer(rijen);

  return `
  <h1>Locaties</h1>
  <p class="lead">Let op gang 01 tot 06 en gang 11 tot 13: allemaal
  <b>type PL (picklocatie)</b>, maar met totaal andere afmetingen. Hier is dat geen
  probleem, want de maatklasse wordt <i>berekend</i> uit de afmetingen. Niemand hoeft
  hem in te vullen, dus hij kan ook niet verouderen.</p>

  <div class="uitleg"><b>Wat je hier kunt aanpassen.</b> De grenzen tussen XS en XL
  staan in één tabel. Verander een grens en elke locatie herclassificeert zichzelf
  &mdash; er hoeft geen enkel record bijgewerkt te worden.</div>

  <div class="filters">
    <label>Soort locatie
      <select data-filter="filterType">
        <option value="">alle soorten</option>
        ${LOCTYPES.map(t=>`<option value="${t.code}" ${staat.filterType===t.code?"selected":""}>${t.code} &mdash; ${esc(t.naam)}</option>`).join("")}
      </select></label>
    <label>Maatklasse
      <select data-filter="filterMaat">
        <option value="">alle maten</option>
        ${MAATREGELS.map(m=>`<option value="${m.code}" ${staat.filterMaat===m.code?"selected":""}>${m.code} &mdash; ${esc(m.naam)}</option>`).join("")}
      </select></label>
    <button class="stil" data-actie="wis">Wissen</button>
    <span class="rechts hint">${fmt(pg.totaal)} locaties</span>
  </div>

  <div class="kaart">
    <div class="tabelwrap"><table>
      <thead><tr><th>Locatie</th><th>Zone</th><th>Soort</th><th>Maat</th>
        <th>Afmeting (mm)</th><th class="num">Max. gew.</th><th class="num">Inhoud</th>
        <th class="num">Ligt er</th></tr></thead>
      <tbody>${pg.rijen.map(l=>{
        const t=LOCTYPES[l.typeId], v=voorraadOp(DB,l.id);
        return `<tr>
        <td><a href="#locatie/${l.id}" class="mono sterk">${esc(l.code)}</a></td>
        <td class="hint">${esc(DB.zones[l.zoneId].naam)}</td>
        <td>${pil(t.pick?"g":t.bulk?"n":"o", t.code)}</td>
        <td>${maatPil(maatVan(l))}</td>
        <td class="mono hint">${l.L} &times; ${l.W} &times; ${l.H}</td>
        <td class="num">${Math.round(l.maxG/1000)} kg</td>
        <td class="num hint">${(l.L*l.W*l.H/1e6).toFixed(1)} l</td>
        <td class="num">${v.length?`<b>${fmt(v.reduce((a,s)=>a+s.qty,0))}</b>
          <div class="hint">${v.length} art.</div>`:""}</td></tr>`}).join("")}
      </tbody></table></div>
      ${pagBalk(pg)}
      ${pg.totaal?"":`<p class="leeg">Geen locaties met dit filter.</p>`}
  </div>`;
}

function schermLocatie(id){
  const loc = DB.locaties[id];
  if(!loc) return `<h1>Locatie niet gevonden</h1>`;
  const t = LOCTYPES[loc.typeId], vul = getN("putaway.fill_factor");
  const locVol = loc.L*loc.W*loc.H;

  let passen=[], nietPassen=0;
  for(const a of DB.artikelen){
    const p = DB.artikelNu(a.id);
    if(!p.L) continue;
    if(p.L*p.W*p.H > locVol){ nietPassen++; continue; }
    const fit = pasBerekening(p, loc, vul);
    if(fit.qty) passen.push({p,fit}); else nietPassen++;
  }
  passen.sort((a,b)=>b.fit.qty-a.fit.qty);
  const totaalPassen = passen.length;
  passen = passen.slice(0,40);
  const vrd = voorraadOp(DB, loc.id);

  return `
  <div class="kruimel"><a href="#locaties">Locaties</a> / ${esc(loc.code)}</div>
  <h1>Locatie ${esc(loc.code)}</h1>
  <p class="lead">${esc(t.naam)} in ${esc(DB.zones[loc.zoneId].naam)} &mdash;
    maatklasse ${maatPil(maatVan(loc))}</p>

  <div class="tegels vier">
    <div class="kaart tegel"><span class="label">Afmeting</span>
      <span class="cijfer mono klein">${loc.L}&times;${loc.W}&times;${loc.H}</span>
      <span class="hint">millimeter</span></div>
    <div class="kaart tegel"><span class="label">Inhoud</span>
      <span class="cijfer">${(locVol/1e6).toFixed(1)} l</span></div>
    <div class="kaart tegel"><span class="label">Max. gewicht</span>
      <span class="cijfer">${Math.round(loc.maxG/1000)} kg</span></div>
    <div class="kaart tegel"><span class="label">Looproute</span>
      <span class="cijfer">${fmt(loc.seq)}</span>
      <span class="hint">gang ${loc.aisle} &middot; vak ${loc.bay} &middot; niveau ${loc.level}</span></div>
  </div>

  <div class="tweeluik">
    <div class="kaart">
      <h2>Wat ligt hier nu</h2>
      ${vrd.length?`<div class="tabelwrap"><table>
        <thead><tr><th>Artikel</th><th class="num">Aantal</th></tr></thead>
        <tbody>${vrd.map(s=>{const p=DB.artikelen[s.productId];return `<tr>
          <td><a href="#artikel/${p.id}" class="mono">${esc(p.sku)}</a>
              <div class="hint">${esc(p.oms)}</div></td>
          <td class="num sterk">${fmt(s.qty)}</td></tr>`}).join("")}</tbody></table></div>`
        :`<p class="leeg">Deze locatie is leeg.</p>`}

      <h2 class="verderop">Gedrag van dit soort locatie</h2>
      <p class="hint">Deze vlaggen staan in een tabel, niet in de programmacode.
        Nieuw soort locatie nodig? Rij toevoegen.</p>
      <div class="tabelwrap"><table><tbody>
        <tr><td>Picklocatie</td><td class="num">${t.pick?"ja":"nee"}</td></tr>
        <tr><td>Bulklocatie</td><td class="num">${t.bulk?"ja":"nee"}</td></tr>
        <tr><td>Meerdere artikelen toegestaan</td><td class="num">${t.mix?"ja":"nee"}</td></tr>
        <tr><td>Telt mee als beschikbaar</td><td class="num">${t.blok?"nee":"ja"}</td></tr>
      </tbody></table></div>
    </div>

    <div class="kaart">
      <h2>Wat past hier &mdash; en hoeveel</h2>
      <p class="hint">Berekend uit de afmetingen van artikel en locatie, in alle
        draaiingen. De kolom <i>beperking</i> is het nuttigste getal: staat er
        ${pil("o","GEWICHT")}, dan is je schap te zwak, niet te klein.</p>
      <p class="hint"><b>${fmt(totaalPassen)}</b> artikelen passen hier,
        ${fmt(nietPassen)} niet. Hieronder de ${passen.length} waar er de meeste van in gaan.</p>
      <div class="tabelwrap"><table>
        <thead><tr><th>Artikel</th><th class="num">Past</th><th>Beperking</th></tr></thead>
        <tbody>${passen.map(r=>`<tr>
          <td><a href="#artikel/${r.p.id}" class="mono">${esc(r.p.sku)}</a>
              <div class="hint">${esc(r.p.oms)}</div></td>
          <td class="num sterk">${fmt(r.fit.qty)}</td>
          <td>${pil(r.fit.limiet==="GEWICHT"?"o":"n", r.fit.limiet)}
              <div class="hint">${esc(r.fit.reden)}</div></td></tr>`).join("")}
      </tbody></table></div>
    </div>
  </div>`;
}

/* ===================== ARTIKELEN ==================================== */
function schermArtikelen(){
  const z = staat.zoek.toLowerCase();
  let rijen = DB.artikelen.map(a=>DB.artikelNu(a.id)).filter(p=>
    !z || p.sku.toLowerCase().includes(z) || p.oms.toLowerCase().includes(z));
  const pg = pagineer(rijen);

  return `
  <h1>Artikelen</h1>
  <p class="lead">De kolom <b>gemeten</b> is het belangrijkste veld op dit scherm.
  Afmetingen die niemand ooit heeft gecontroleerd zijn de stille oorzaak van inslag
  die niet past en van vakken die te vol of te leeg staan.</p>

  <div class="filters">
    <label class="breed">Zoek op nummer of omschrijving
      <input data-zoek value="${esc(staat.zoek)}" placeholder="bijv. LAG-1024 of kogellager"></label>
    <button class="stil" data-actie="wis">Wissen</button>
    <span class="rechts hint">${fmt(pg.totaal)} artikelen</span>
  </div>

  <div class="kaart">
    <div class="tabelwrap"><table>
      <thead><tr><th>Artikel</th><th>Groep</th><th>Afmeting (mm)</th>
        <th class="num">Gewicht</th><th>Gemeten</th><th class="num">Beschikbaar</th></tr></thead>
      <tbody>${pg.rijen.map(p=>{
        const d = dagenOud(p.gemetenOp);
        const status = p.gemetenOp===null ? pil("r","nooit")
          : p.bron==="SUPPLIER" ? pil("o","opgave leverancier")
          : d>180 ? pil("o",d+" dagen") : pil("g",d+" dagen");
        return `<tr>
        <td><a href="#artikel/${p.id}" class="mono sterk">${esc(p.sku)}</a>
            <div class="hint">${esc(p.oms)}</div></td>
        <td class="hint">${esc(DB.groepen[p.groepId].naam)}</td>
        <td class="mono">${p.L?`${p.L} &times; ${p.W} &times; ${p.H}`:`<span class="hint">onbekend</span>`}</td>
        <td class="num">${p.G?(p.G/1000).toFixed(2)+" kg":""}</td>
        <td>${status}</td>
        <td class="num sterk">${fmt(beschikbaar(DB,p.id))}</td></tr>`}).join("")}
      </tbody></table></div>
      ${pagBalk(pg)}
      ${pg.totaal?"":`<p class="leeg">Geen artikelen gevonden.</p>`}
  </div>`;
}

function schermArtikel(id){
  const p = DB.artikelNu(+id);
  if(!p) return `<h1>Artikel niet gevonden</h1>`;
  const metingen = DB.metingen.filter(m=>m.productId===p.id).sort((a,b)=>b.at-a.at);
  const drift = DB.drift.filter(d=>d.productId===p.id);
  const vrd = voorraadVan(DB, p.id);
  const vul = getN("putaway.fill_factor");

  const perMaat = {};
  if(p.L){
    for(const loc of DB.locaties){
      if(!LOCTYPES[loc.typeId].doel) continue;
      const m = maatVan(loc);
      perMaat[m] = perMaat[m] || {maat:m, locaties:0, passen:0, max:0};
      perMaat[m].locaties++;
      const f = pasBerekening(p, loc, vul);
      if(f.qty){ perMaat[m].passen++; perMaat[m].max = Math.max(perMaat[m].max, f.qty); }
    }
  }

  return `
  <div class="kruimel"><a href="#artikelen">Artikelen</a> / ${esc(p.sku)}</div>
  <h1>${esc(p.sku)}</h1>
  <p class="lead">${esc(p.oms)} &mdash; ${esc(DB.groepen[p.groepId].naam)}</p>

  ${drift.filter(d=>d.status==="OPEN").map(d=>`
  <div class="melding waarschuw groot">
    <b>Afmeting week af bij de laatste meting.</b>
    Volume ${d.dVol>0?"+":""}${d.dVol}%, gewicht ${d.dGew>0?"+":""}${d.dGew}%.
    ${esc(d.gevolg)}
  </div>`).join("")}

  <div class="tegels vier">
    <div class="kaart tegel"><span class="label">Afmeting</span>
      <span class="cijfer mono klein">${p.L?`${p.L}&times;${p.W}&times;${p.H}`:"&mdash;"}</span>
      <span class="hint">${p.L?"millimeter":"nooit gemeten"}</span></div>
    <div class="kaart tegel"><span class="label">Gewicht</span>
      <span class="cijfer">${p.G?(p.G/1000).toFixed(2)+" kg":"&mdash;"}</span></div>
    <div class="kaart tegel"><span class="label">Beschikbaar</span>
      <span class="cijfer">${fmt(beschikbaar(DB,p.id))}</span>
      <span class="hint">op ${vrd.length} locatie(s)</span></div>
    <div class="kaart tegel"><span class="label">Aanvuldrempel</span>
      <span class="cijfer">${p.minQty??"&mdash;"}</span>
      <span class="hint">${p.maxQty?"tot "+p.maxQty:"geen vaste picklocatie"}</span></div>
  </div>

  <div class="tweeluik">
    <div class="kaart">
      <h2>Meetgeschiedenis</h2>
      <p class="hint">Elke meting is een regel met een tijdstip en een bron. De actuele
        maat is de nieuwste meting &mdash; nooit een veld dat stil veroudert.</p>
      ${metingen.length>1?grafiekVlak({
        punten: [...metingen].reverse().map(m=>({
          y: Math.round(m.L*m.W*m.H/1000), label: dat(m.at)})),
        eenheid:"cm\u00B3", stippen:true, hoogte:170,
        titel:"Gemeten volume per meting"}):""}
      <div class="tabelwrap"><table>
        <thead><tr><th>Datum</th><th>Bron</th><th>Afmeting</th><th class="num">Gewicht</th></tr></thead>
        <tbody>${metingen.length?metingen.map((m,i)=>`<tr>
          <td class="mono">${dat(m.at)}${i===0?" "+pil("a","actueel"):""}</td>
          <td>${m.bron==="SUPPLIER"?pil("o","opgave leverancier"):pil("g","gemeten bij ontvangst")}
            ${m.notitie?`<div class="hint">${esc(m.notitie)}</div>`:""}</td>
          <td class="mono">${m.L}&times;${m.W}&times;${m.H}</td>
          <td class="num">${(m.G/1000).toFixed(2)} kg</td></tr>`).join("")
          :`<tr><td colspan="4" class="leeg">Dit artikel is nog nooit opgemeten.</td></tr>`}
      </tbody></table></div>
      <div class="knoprij"><a class="knop stil" href="#meten">Opmeten &rarr;</a>
        ${p.L?`<a class="knop" href="#inslag/${p.sku}/24">Zoek een inslaglocatie</a>`:""}</div>
    </div>

    <div class="kaart">
      <h2>Waar past dit artikel</h2>
      ${p.L?`<p class="hint">Per maatklasse: in hoeveel locaties past het, en hoeveel
        gaan er maximaal in.</p>
      <div class="tabelwrap"><table>
        <thead><tr><th>Maat</th><th class="num">Locaties</th><th class="num">Passen</th><th class="num">Max. per locatie</th></tr></thead>
        <tbody>${MAATREGELS.filter(r=>perMaat[r.code]).map(r=>{const d=perMaat[r.code];
          return `<tr><td>${maatPil(r.code)}<span class="hint"> ${esc(r.naam)}</span></td>
            <td class="num hint">${fmt(d.locaties)}</td>
            <td class="num">${d.passen?fmt(d.passen):pil("r","0")}</td>
            <td class="num sterk">${d.max?fmt(d.max):"&mdash;"}</td></tr>`}).join("")}
      </tbody></table></div>`:`<p class="leeg">Meet dit artikel eerst op, dan kan het
        systeem berekenen waar het past.</p>`}

      <h2 class="verderop">Huidige voorraad</h2>
      ${vrd.length?`<div class="tabelwrap"><table>
        <thead><tr><th>Locatie</th><th>Maat</th><th class="num">Aantal</th></tr></thead>
        <tbody>${vrd.map(s=>{const l=DB.locaties[s.locationId];return `<tr>
          <td><a href="#locatie/${l.id}" class="mono">${esc(l.code)}</a></td>
          <td>${maatPil(maatVan(l))}</td>
          <td class="num sterk">${fmt(s.qty)}</td></tr>`}).join("")}</tbody></table></div>`
        :`<p class="leeg">Geen voorraad.</p>`}
    </div>
  </div>`;
}

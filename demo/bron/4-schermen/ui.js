/* =====================================================================
   VAKTO - weergave
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

/* ===================== RONDLEIDING ================================== */
function schermDemo(){
  const drift = DB.drift.filter(d=>d.status==="OPEN")
    .sort((a,b)=>Math.abs(b.dVol)-Math.abs(a.dVol))[0];
  const gem = DB.artikelen.map(a=>DB.artikelNu(a.id)).filter(p=>p.L);
  const heeft = new Set(DB.voorraad.filter(s=>s.qty>0).map(s=>s.productId));
  const v=p=>p.L*p.W*p.H;
  const klein = gem.filter(p=>!heeft.has(p.id)).sort((a,b)=>v(a)-v(b))[0] || gem[0];
  const groot = [...gem].sort((a,b)=>v(b)-v(a))[0];
  const taak = DB.taken.find(t=>t.soort==="REPLENISH"&&t.status==="TODO");
  const dp = drift ? DB.artikelen[drift.productId] : null;

  return `
  <h1>Rondleiding</h1>
  <p class="lead">Drie situaties die je bij een klant in twee minuten voordoet.
  Ze zijn niet nagebootst &mdash; Vakto rekent ze echt uit op de gegevens hieronder.
  Vertel eerst het verhaal, klik dan pas.</p>

  <div class="tegels vier">
    <div class="kaart tegel"><span class="label">Artikelen</span><span class="cijfer">${fmt(DB.artikelen.length)}</span></div>
    <div class="kaart tegel"><span class="label">Locaties</span><span class="cijfer">${fmt(DB.locaties.length)}</span></div>
    <div class="kaart tegel"><span class="label">Voorraadregels</span><span class="cijfer">${fmt(DB.voorraad.filter(s=>s.qty>0).length)}</span></div>
    <div class="kaart tegel"><span class="label">Boekingen</span><span class="cijfer">${fmt(DB.boekingen.length)}</span><span class="hint">zestig dagen historie</span></div>
  </div>

  <div class="kaart">
    <h2><span class="stap">1</span> De leverancier wijzigt de doos en zegt niets</h2>
    ${drift?`
    <p class="verhaal">"Jullie krijgen een zending binnen. De leverancier is stilletjes
    overgestapt op een grotere verpakking. In de meeste systemen merk je dat pas als
    de inslag niet past &mdash; en dan staat er iemand met een pallet in zijn handen."</p>
    <div class="tabelwrap"><table>
      <thead><tr><th>Artikel</th><th class="num">Volume</th><th class="num">Gewicht</th><th>Gevolg</th></tr></thead>
      <tbody><tr>
        <td><a href="#artikel/${dp.id}" class="mono sterk">${esc(dp.sku)}</a>
            <div class="hint">${esc(dp.oms)}</div></td>
        <td class="num">${pil("o",(drift.dVol>0?"+":"")+drift.dVol+"%")}</td>
        <td class="num">${pil("o",(drift.dGew>0?"+":"")+drift.dGew+"%")}</td>
        <td>${esc(drift.gevolg)}</td>
      </tr></tbody></table></div>
    <div class="uitleg"><b>Wat je laat zien.</b> Bij ontvangst is het artikel opgemeten.
      Vakto vergeleek die meting met de vorige, zag de afwijking, en zocht daarna zelf
      uit op welke locaties de huidige voorraad niet meer past. Niemand hoefde iets
      te signaleren.</div>
    <div class="knoprij"><a class="knop" href="#artikel/${dp.id}">Toon het artikel</a>
      <a class="knop stil" href="#dashboard">Toon het op het dashboard</a></div>
    `:`<p class="leeg">Geen openstaande melding. Zet de demo terug.</p>`}
  </div>

  <div class="kaart">
    <h2><span class="stap">2</span> Kleingoed hoort niet in een palletplaats</h2>
    <p class="verhaal">"Bij ons zijn alle picklocaties hetzelfde soort. Maar een vak van
    30 centimeter en een vak van een meter twintig zijn niet hetzelfde. Wie bepaalt
    waar dit heen gaat?"</p>
    ${klein&&groot?`
    <div class="tweeluik">
      <div><div class="tabelwrap"><table>
        <thead><tr><th>Klein artikel</th><th>Afmeting</th></tr></thead>
        <tbody><tr><td><a href="#artikel/${klein.id}" class="mono sterk">${esc(klein.sku)}</a>
          <div class="hint">${esc(klein.oms)}</div></td>
          <td class="mono">${klein.L}&times;${klein.W}&times;${klein.H} mm
          <div class="hint">${(klein.G/1000).toFixed(2)} kg</div></td></tr></tbody></table></div>
        <div class="knoprij"><a class="knop" href="#inslag/${klein.sku}/40">Zoek een plek voor 40 stuks</a></div></div>
      <div><div class="tabelwrap"><table>
        <thead><tr><th>Groot artikel</th><th>Afmeting</th></tr></thead>
        <tbody><tr><td><a href="#artikel/${groot.id}" class="mono sterk">${esc(groot.sku)}</a>
          <div class="hint">${esc(groot.oms)}</div></td>
          <td class="mono">${groot.L}&times;${groot.W}&times;${groot.H} mm
          <div class="hint">${(groot.G/1000).toFixed(1)} kg</div></td></tr></tbody></table></div>
        <div class="knoprij"><a class="knop stil" href="#inslag/${groot.sku}/2">Zoek een plek voor 2 stuks</a></div></div>
    </div>`:`<p class="leeg">Er zijn nog geen opgemeten artikelen. Meet er een paar op
    (<a href="#meten">Opmeten</a>), dan kun je dit voordoen met hun eigen artikelen.</p>`}
    <div class="uitleg"><b>Wat je laat zien.</b> Twee keer hetzelfde scherm, twee totaal
      verschillende voorstellen. Vakto filtert niet op een maatcategorie die iemand ooit
      heeft ingetypt, maar rekent per locatie uit hoeveel er in past: alle draaiingen,
      het maximale gewicht, en wat er al ligt. Daarna scoort het op <i>benutting</i>.
      Veertig schroefsets in een palletplaats komt uit op nog geen procent, en zo'n
      voorstel zakt vanzelf naar onderen.</div>
  </div>

  <div class="kaart">
    <h2><span class="stap">3</span> Het systeem ziet zelf dat een picklocatie leegloopt</h2>
    ${taak?`
    <p class="verhaal">"Wie houdt bij dat de picklocatie bijna leeg is? Bij ons meestal
    de picker die er als eerste misgrijpt."</p>
    <div class="tabelwrap"><table>
      <thead><tr><th>Artikel</th><th>Van</th><th>Naar</th><th class="num">Aantal</th><th>Reden</th></tr></thead>
      <tbody><tr>
        <td><a href="#artikel/${taak.productId}" class="mono sterk">${esc(DB.artikelen[taak.productId].sku)}</a>
            <div class="hint">${esc(DB.artikelen[taak.productId].oms)}</div></td>
        <td class="mono">${esc(DB.locaties[taak.van].code)}</td>
        <td class="mono">${esc(DB.locaties[taak.naar].code)}</td>
        <td class="num sterk">${taak.qty}</td>
        <td class="hint">${esc(taak.reden)}</td>
      </tr></tbody></table></div>
    <div class="uitleg"><b>Wat je laat zien.</b> Niemand heeft deze taak aangemaakt. De
      voorraad zakte onder de drempel, Vakto zocht bulkvoorraad van hetzelfde artikel
      en zette de opdracht klaar. Aanvullen, verplaatsen en tellen zitten in dezelfde
      lijst, met een prioriteit erbij.</div>
    <div class="knoprij"><a class="knop" href="#taken">Toon de takenlijst
      (${DB.taken.filter(t=>t.status==="TODO").length} open)</a></div>
    `:`<p class="leeg">Geen aanvultaken open. Zet de demo terug.</p>`}
  </div>

  <div class="kaart waarschuw">
    <h2>Demo terugzetten</h2>
    <p class="hint">Bouwt de omgeving opnieuw op met verse gegevens. Doe dit voor elk
      klantgesprek: je wilt niet beginnen met de boekingen van het vorige.</p>
    <div class="knoprij"><button data-actie="reset">Demo opnieuw opbouwen</button></div>
  </div>`;
}

/* ===================== DASHBOARD ==================================== */
function schermDashboard(){
  const drift = DB.drift.filter(d=>d.status==="OPEN");
  const taken = DB.taken.filter(t=>t.status==="TODO").sort((a,b)=>a.prio-b.prio);
  const meten = teMeten(DB);

  const dicht = {};
  for(const l of DB.locaties){
    const t = LOCTYPES[l.typeId];
    if(!t.pick && !t.bulk) continue;
    const m = maatVan(l);
    dicht[m] = dicht[m] || {totaal:0, gevuld:0};
    dicht[m].totaal++;
    if(voorraadOp(DB,l.id).length) dicht[m].gevuld++;
  }

  /* --- mutaties per dag over de laatste vier weken ------------------ */
  const dag = 86400000, nu = Date.now();
  const vanaf = nu - 29*dag;
  const perDag = new Array(30).fill(0);
  for(const b of DB.boekingen){
    if(b.at < vanaf) continue;
    const i = Math.floor((b.at - vanaf)/dag);
    if(i>=0 && i<30) perDag[i]++;
  }
  const punten = perDag.map((y,i)=>({
    y, label:new Date(vanaf+i*dag).toLocaleDateString("nl-NL",{day:"2-digit",month:"2-digit"})}));

  const vakken = DB.locaties.filter(l=>LOCTYPES[l.typeId].pick||LOCTYPES[l.typeId].bulk);
  const bezet  = vakken.filter(l=>voorraadOp(DB,l.id).length).length;
  const bezetPct = Math.round(bezet/Math.max(1,vakken.length)*100);

  const vanzelf = DB.drift.filter(d=>d.status==="OPGELOST").length;
  const autoTaken = DB.taken.filter(t=>t.automatisch).length;
  const vervallen = DB.taken.filter(t=>t.status==="VERVALLEN").length;

  return `
  <h1>Dashboard</h1>
  <p class="lead">Dit scherm toont wat er <b>stilstaat</b>, niet wat er af is. "Aantal
  orders vandaag" is een rapport; daar kun je nu niets mee. Alles hieronder vraagt om
  een handeling.</p>

  <div class="controle">
    <span class="controle-punt"></span>
    <span class="controle-tekst"><b>Het systeem heeft zichzelf net gecontroleerd.</b>
      Dat gebeurt na elke boeking, meting en telling &mdash; niet op een knop.
      ${controle.at?`Laatste keer om ${new Date(controle.at).toLocaleTimeString("nl-NL",{hour:"2-digit",minute:"2-digit",second:"2-digit"})}.`:""}</span>
    <span class="controle-cijfers">
      <span class="controle-cijfer"><b>${fmt(vanzelf)}</b><span>vanzelf gesloten</span></span>
      <span class="controle-cijfer"><b>${fmt(autoTaken)}</b><span>zelf klaargezet</span></span>
      <span class="controle-cijfer"><b>${fmt(vervallen)}</b><span>vervallen</span></span>
    </span>
  </div>

  <div class="tegels vier">
    <a class="kaart tegel" href="#taken"><span class="label">Openstaande taken</span>
      <span class="cijfer">${fmt(taken.length)}</span>
      <span class="hint">${(()=>{const a=taken.filter(t=>t.soort==="REPLENISH").length;
        return a===taken.length?"allemaal aanvullen":fmt(a)+" aanvullen, rest tellen";})()}</span></a>
    <a class="kaart tegel" href="#meten"><span class="label">Afwijkende maten</span>
      <span class="cijfer ${drift.length?"slecht":""}">${fmt(drift.length)}</span>
      <span class="hint">gemeld bij ontvangst</span></a>
    <a class="kaart tegel" href="#meten"><span class="label">Nog opmeten</span>
      <span class="cijfer">${fmt(meten.length)}</span>
      <span class="hint">van ${fmt(DB.artikelen.length)} artikelen</span></a>
    <a class="kaart tegel" href="#locaties"><span class="label">Vakken in gebruik</span>
      <span class="cijfer">${bezetPct}%</span>
      <span class="hint">${fmt(bezet)} van ${fmt(vakken.length)}</span></a>
  </div>

  <div class="kaart">
    <h2>Voorraadmutaties per dag</h2>
    <p class="hint">Elke ontvangst, pick, verplaatsing en telling van de laatste vier weken.
      Zakt deze lijn zonder dat het rustiger is in het magazijn, dan wordt er buiten het
      systeem om gewerkt &mdash; en dat is precies het moment waarop je voorraad gaat afwijken.</p>
    ${grafiekVlak({punten, eenheid:"boekingen", titel:"Voorraadmutaties per dag"})}
  </div>

  <div class="tweeluik">
    <div class="kaart">
      <h2>Afwijkende artikelmaten ${drift.length?pil("o",drift.length):""}</h2>
      <p class="hint">Bij de laatste meting week het artikel af van de vorige. Het systeem
        zocht zelf uit wat dat betekent voor de voorraad die er nu ligt, en zette het werk
        klaar. Je hoeft hier niets af te vinken: zodra het probleem weg is, verdwijnt de
        melding vanzelf.</p>
      ${drift.length?drift.map(d=>{const p=DB.artikelen[d.productId];return `
        <div class="melding waarschuw">
          <div class="meldkop">
            <a href="#artikel/${p.id}" class="mono sterk">${esc(p.sku)}</a>
            <span>${pil("o","volume "+(d.dVol>0?"+":"")+d.dVol+"%")}
                  ${pil("o","gewicht "+(d.dGew>0?"+":"")+d.dGew+"%")}</span>
          </div>
          <div class="hint">${esc(p.oms)}</div>
          <div class="meldtekst">${esc(d.gevolg)}</div>
          ${(()=>{const tk = DB.taken.find(t=>t.soort==="OVERLOOP" && t.status==="TODO"
                                              && t.productId===d.productId);
            return tk ? `<div class="meldtekst"><b>Al klaargezet:</b> verplaats ${fmt(tk.qty)} st van
              <span class="mono">${esc(DB.locaties[tk.van].code)}</span> naar
              <span class="mono">${esc(DB.locaties[tk.naar].code)}</span>.
              <a href="#taken">Staat in de takenlijst &rarr;</a></div>`
            : `<div class="meldtekst hint">Er is geen betere plek gevonden voor de overloop;
              dit vraagt om een menselijke keuze.</div>`;})()}
          <div class="knoprij">
            <button class="klein stil" data-drift="${d.id}" data-status="DISMISSED">Niet meer melden voor dit artikel</button>
            <span class="hint">Deze melding sluit zichzelf zodra de voorraad weer past.</span>
          </div>
        </div>`}).join(""):`<p class="leeg">Geen openstaande afwijkingen.
          ${vanzelf?`${fmt(vanzelf)} eerdere melding(en) zijn vanzelf gesloten toen de voorraad weer paste.`:""}</p>`}
    </div>

    <div class="kaart">
      <h2>Openstaande taken ${taken.length?pil("n",taken.length):""}</h2>
      <p class="hint">Aanvullen, verplaatsen en tellen zitten in dezelfde tabel.
        Lager prioriteitsnummer betekent urgenter.</p>
      ${taken.length?`<div class="tabelwrap"><table>
        <thead><tr><th>Prio</th><th>Taak</th><th>Artikel</th><th>Van &rarr; naar</th><th class="num">Aantal</th></tr></thead>
        <tbody>${taken.slice(0,8).map(t=>`<tr>
          <td>${pil("n",t.prio)}</td><td>${esc(t.naam)}</td>
          <td class="mono">${esc(DB.artikelen[t.productId].sku)}</td>
          <td class="mono">${esc(DB.locaties[t.van].code)} &rarr; ${esc(DB.locaties[t.naar].code)}</td>
          <td class="num">${t.qty}</td></tr>`).join("")}</tbody></table></div>
        <div class="knoprij"><a href="#taken">Alle taken &rarr;</a></div>`
        :`<p class="leeg">Geen openstaande taken.</p>`}
    </div>

    <div class="kaart">
      <h2>Bezetting per maatklasse</h2>
      <p class="hint">De maatklasse wordt berekend uit de afmetingen van de locatie.
        Zo zie je of je grote vakken tekortkomt terwijl de kleine leegstaan.</p>
      ${grafiekBalken({rijen: MAATREGELS.filter(r=>dicht[r.code]).map(r=>({
        label: r.naam, pil: maatPil(r.code),
        waarde: dicht[r.code].gevuld, totaal: dicht[r.code].totaal }))})}
      <p class="hint">De breedte van elk spoor is het aantal locaties in die klasse; de
        vulling is hoeveel ervan in gebruik zijn. Zo zie je in één blik of je aan de
        verkeerde kant vol zit.</p>
    </div>

    <div class="kaart">
      <h2>Te meten artikelen ${meten.length?pil("n",fmt(meten.length)):""}</h2>
      <p class="hint">Bij ontvangst heb je het artikel in je handen. Dat is het enige
        moment waarop meten niets kost.</p>
      ${meten.length?`<div class="tabelwrap"><table>
        <thead><tr><th>Artikel</th><th>Reden</th></tr></thead>
        <tbody>${meten.slice(0,8).map(m=>`<tr>
          <td><a href="#artikel/${m.id}" class="mono">${esc(m.sku)}</a>
              <div class="hint">${esc(m.oms)}</div></td>
          <td>${pil(m.gemetenOp===null?"r":"o", m.reden)}</td></tr>`).join("")}</tbody></table></div>
        <div class="knoprij"><a href="#meten">Naar de meetlijst &rarr;</a></div>`
        :`<p class="leeg">Alles is actueel opgemeten.</p>`}
    </div>
  </div>

  <div class="kaart">
    <h2>Laatste boekingen</h2>
    <div class="tabelwrap"><table>
      <thead><tr><th>Tijd</th><th>Soort</th><th>Artikel</th><th>Van</th><th>Naar</th><th class="num">Aantal</th></tr></thead>
      <tbody>${DB.boekingen.slice(0,10).map(b=>`<tr>
        <td class="mono hint">${tijd(b.at)}</td><td>${pil("n",b.soort)}</td>
        <td class="mono">${esc(DB.artikelen[b.productId].sku)}</td>
        <td class="mono">${b.van!==null?esc(DB.locaties[b.van].code):"&mdash;"}</td>
        <td class="mono">${b.naar!==null?esc(DB.locaties[b.naar].code):"&mdash;"}</td>
        <td class="num">${b.qty}</td></tr>`).join("")}</tbody></table></div>
  </div>`;
}

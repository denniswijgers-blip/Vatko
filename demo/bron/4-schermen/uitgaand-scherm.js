/* =====================================================================
   SCHERMEN: ORDERS EN PICKEN

   Alles wat de deur uit gaat. Let op de naam: de rekenregels staan in
   2-logica/uitgaand.js, dit is alleen het scherm. Twee bestanden met
   dezelfde naam in verschillende mappen werkt wel, maar niet als je om
   elf uur 's avonds naar een foutmelding zit te kijken.
   ===================================================================== */

/* ===================== ORDERS ======================================= */
function schermOrders(){
  const rijen = [...DB.orders].sort((a,b)=>b.id-a.id);
  const pg = pagineer(rijen);
  return `
  <h1>Orders</h1>
  <p class="lead">Orders komen normaal uit een ERP of webshop; hier maakt de
  dagsimulatie ze aan. Vakto beheert het magazijn, niet de verkoop &mdash; die scheiding
  houd je het beste zuiver.</p>
  ${!rijen.length?`<div class="kaart"><p class="leeg">Nog geen orders.
    Start een dag om ze binnen te laten komen.</p>
    <div class="knoprij"><a class="knop" href="#dag">Naar de dagsimulatie</a></div></div>`:`
  <div class="kaart">
    <div class="tabelwrap"><table>
      <thead><tr><th>Order</th><th>Klant</th><th>Soort</th><th class="num">Regels</th>
        <th class="num">Voortgang</th><th>Vervoerder</th><th>Status</th></tr></thead>
      <tbody>${pg.rijen.map(o=>{
        const besteld=o.regels.reduce((a,r)=>a+r.besteld,0);
        const gepickt=o.regels.reduce((a,r)=>a+r.gepickt,0);
        const manco=o.regels.reduce((a,r)=>a+(r.manco||0),0);
        return `<tr>
        <td><a href="#order/${o.id}" class="mono sterk">${esc(o.nummer)}</a>
            <div class="hint">${klok(Math.floor((o.at%86400000)/60000)%1440)||""}</div></td>
        <td>${esc(o.klant)}<div class="hint">${esc(o.plaats)}, ${esc(o.land)}</div></td>
        <td class="hint">${esc(o.typenaam)}</td>
        <td class="num">${o.regels.length}</td>
        <td class="num"><span class="balk mini"><i style="width:${besteld?gepickt/besteld*100:0}%"></i></span>
          <div class="hint">${gepickt}/${besteld}${manco?` &middot; ${manco} manco`:""}</div></td>
        <td class="hint">${esc(o.vervoerder)}</td>
        <td>${pil(STATUSKLEUR[o.status], STATUSNAAM[o.status])}</td></tr>`}).join("")}
      </tbody></table></div>
    ${pagBalk(pg)}
  </div>`}`;
}

function schermOrder(id){
  const o = DB.orders[+id];
  if(!o) return `<h1>Order niet gevonden</h1>`;
  const job = DB.pickjobs.find(j=>j.orderId===o.id);
  const knoppen = {
    NIEUW:["reserveer","Reserveren"], GERESERVEERD:["vrijgeef","Vrijgeven voor de vloer"],
    WACHT_OP_VOORRAAD:["reserveer","Opnieuw proberen te reserveren"],
    VRIJGEGEVEN:["pick","Naar de piklijst"], PICKEN:["pick","Naar de piklijst"],
    GEPICKT:["pak","Inpakken"], INGEPAKT:["verzend","Verzenden"]
  }[o.status];

  return `
  <div class="kruimel"><a href="#orders">Orders</a> / ${esc(o.nummer)}</div>
  <h1>${esc(o.nummer)}</h1>
  <p class="lead">${esc(o.klant)} &middot; ${esc(o.plaats)}, ${esc(o.land)} &middot;
    ${esc(o.typenaam)} &middot; vervoerder ${esc(o.vervoerder)}</p>

  <div class="tegels vier">
    <div class="kaart tegel"><span class="label">Status</span>
      <span class="cijfer klein">${pil(STATUSKLEUR[o.status], STATUSNAAM[o.status])}</span></div>
    <div class="kaart tegel"><span class="label">Regels</span>
      <span class="cijfer">${o.regels.length}</span></div>
    <div class="kaart tegel"><span class="label">Colli</span>
      <span class="cijfer">${o.colli??"&mdash;"}</span>
      <span class="hint">${o.gewicht?(o.gewicht/1000).toFixed(1)+" kg":"nog niet ingepakt"}</span></div>
    <div class="kaart tegel"><span class="label">Zending</span>
      <span class="cijfer klein mono">${o.track??"&mdash;"}</span></div>
  </div>

  ${knoppen?`<div class="knoprij" style="margin-bottom:16px">
    <button data-order="${o.id}" data-stap="${knoppen[0]}">${knoppen[1]}</button></div>`:""}

  <div class="kaart">
    <h2>Orderregels</h2>
    <div class="tabelwrap"><table>
      <thead><tr><th>Artikel</th><th class="num">Besteld</th><th class="num">Gereserveerd</th>
        <th class="num">Gepickt</th><th class="num">Manco</th><th>Gereserveerd op</th></tr></thead>
      <tbody>${o.regels.map(r=>{
        const res = DB.reserveringen.filter(x=>x.orderId===o.id && x.regel===r.idx);
        return `<tr>
        <td><a href="#artikel/${r.productId}" class="mono sterk">${esc(DB.artikelen[r.productId].sku)}</a>
            <div class="hint">${esc(DB.artikelen[r.productId].oms)}</div></td>
        <td class="num sterk">${r.besteld}</td>
        <td class="num">${r.gereserveerd}</td>
        <td class="num">${r.gepickt}</td>
        <td class="num">${r.manco?pil("r",r.manco):""}</td>
        <td>${res.length?res.map(x=>`<span class="mono">${esc(DB.locaties[x.locationId].code)}</span>
            <span class="hint">(${x.qty})</span>`).join("<br>"):`<span class="hint">nog niet</span>`}</td>
      </tr>`}).join("")}</tbody></table></div>
    <div class="uitleg"><b>Waarom reserveren losstaat van picken.</b> Reserveren
      verplaatst niets: het legt vast wélke voorraad op wélke locatie voor deze order
      bestemd is. Zonder die stap verkoop je twee keer dezelfde doos en staat er straks
      iemand met lege handen bij het schap.</div>
  </div>

  ${job?`<div class="kaart">
    <h2>Pickopdracht ${job.status==="DONE"?pil("g","afgerond"):pil("o","open")}</h2>
    <p class="hint">Gesorteerd op looproute, niet op ordervolgorde. Dat scheelt stappen.</p>
    <div class="tabelwrap"><table>
      <thead><tr><th>#</th><th>Locatie</th><th>Artikel</th><th class="num">Te picken</th>
        <th class="num">Gepickt</th><th>Status</th></tr></thead>
      <tbody>${job.regels.map(r=>`<tr>
        <td class="hint">${r.nr}</td>
        <td><a href="#locatie/${r.locationId}" class="mono sterk">${esc(DB.locaties[r.locationId].code)}</a></td>
        <td class="mono">${esc(DB.artikelen[r.productId].sku)}</td>
        <td class="num sterk">${r.qty}</td><td class="num">${r.gepickt}</td>
        <td>${r.status==="DONE"?pil("g","gepickt"):r.status==="MANCO"?pil("r","manco"):pil("n","open")}</td>
      </tr>`).join("")}</tbody></table></div>
  </div>`:""}`;
}

/* ===================== PICKEN ======================================= */
function schermPicken(){
  const jobs = DB.pickjobs.filter(j=>j.status==="TODO")
    .sort((a,b)=>a.prio-b.prio || a.id-b.id);
  const job = jobs[0];
  if(!job) return `
    <h1>Picken</h1>
    <p class="lead">Geen openstaande pickopdrachten.</p>
    <div class="kaart"><p class="leeg">Start een dag, of geef een order handmatig vrij.</p>
      <div class="knoprij"><a class="knop" href="#dag">Naar de dagsimulatie</a>
        <a class="knop stil" href="#orders">Naar de orders</a></div></div>`;

  const o = DB.orders[job.orderId];
  const open = job.regels.filter(r=>r.status==="TODO");
  const nu = open[0];

  return `
  <h1>Picken</h1>
  <p class="lead">Zo ziet het eruit op de vloer: één regel tegelijk, in looproute.
  Grote knoppen, weinig tekst. De invoervelden werken meteen met een handscanner
  &mdash; die gedraagt zich als een toetsenbord.</p>

  <div class="tweeluik">
    <div class="kaart pickkaart">
      <div class="pickkop">
        <span class="hint">${esc(o.nummer)} &middot; ${esc(o.klant)}</span>
        <span class="pil a">regel ${job.regels.length-open.length+1} van ${job.regels.length}</span>
      </div>
      ${nu?`
      <div class="picklocatie mono">${esc(DB.locaties[nu.locationId].code)}</div>
      <div class="pickartikel">
        <span class="mono sterk">${esc(DB.artikelen[nu.productId].sku)}</span>
        <div class="hint">${esc(DB.artikelen[nu.productId].oms)}</div>
      </div>
      <div class="pickaantal"><span class="label">Te picken</span>
        <span class="pickcijfer">${nu.qty - nu.gepickt}</span></div>
      <div class="knoprij">
        <button data-pick="${job.id}" data-regel="${nu.nr}" data-aantal="${nu.qty-nu.gepickt}">
          Gepickt &mdash; ${nu.qty-nu.gepickt} stuks</button>
        <button class="stil" data-pick="${job.id}" data-regel="${nu.nr}" data-aantal="0">
          Niets gevonden (manco)</button>
      </div>
      <p class="hint" style="margin-top:12px">Bij een manco loopt het systeem niet
        stilletijd door: de reservering wordt vrijgegeven zodat een ander de voorraad kan
        gebruiken, er komt een correctieboeking met reden, en er wordt een onderzoekstaak
        aangemaakt.</p>
      `:`<p class="leeg">Alle regels afgehandeld.</p>`}
    </div>

    <div class="kaart">
      <h2>De hele opdracht</h2>
      <div class="tabelwrap"><table>
        <thead><tr><th>#</th><th>Locatie</th><th>Artikel</th><th class="num">Aantal</th><th>Status</th></tr></thead>
        <tbody>${job.regels.map(r=>`<tr class="${nu&&r.nr===nu.nr?"beste":""}">
          <td class="hint">${r.nr}</td>
          <td class="mono sterk">${esc(DB.locaties[r.locationId].code)}</td>
          <td class="mono">${esc(DB.artikelen[r.productId].sku)}</td>
          <td class="num sterk">${r.qty}</td>
          <td>${r.status==="DONE"?pil("g","gepickt"):r.status==="MANCO"?pil("r","manco"):pil("n","open")}</td>
        </tr>`).join("")}</tbody></table></div>
      ${jobs.length>1?`<p class="hint" style="margin-top:12px">Daarna staan er nog
        ${jobs.length-1} opdracht(en) klaar.</p>`:""}
    </div>
  </div>`;
}

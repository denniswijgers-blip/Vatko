/* ===================== SCANSCHERM =================================== */
function schermScan(){
  const taken = [["PICKEN","Picken"],["INSLAG","Inslaan"],
                 ["TELLEN","Tellen"],["VRIJ","Opzoeken"]];

  let kern = "";
  const s = scan;

  if(s.taak==="PICKEN"){
    if(s.stap==="KLAAR" || !s.regel){
      const wachtend = DB.orders.filter(o=>["NIEUW","GERESERVEERD","WACHT_OP_VOORRAAD"].includes(o.status)).length;
      kern = `<div class="scanklaar">
        <div class="scangroot">Niets te picken</div>
        <p class="scanhint">Er staan geen vrijgegeven pickregels.
          ${wachtend?`Er wachten wel ${wachtend} order(s) op vrijgave.`:""}</p>
        <div class="scanknoppen">
          <button class="groot" data-scan-werk>Zet werk klaar</button>
          <button class="groot stil" data-scan-taak="VRIJ">Iets opzoeken</button>
        </div>
      </div>`;
    } else {
      const loc = DB.locaties[s.regel.locationId];
      const art = DB.artikelNu(s.regel.productId);
      const open = s.job.regels.filter(r=>r.status==="TODO").length;
      const totaal = s.job.regels.length;
      const nog = s.regel.qty - s.regel.gepickt;

      kern = `
      <div class="scanvoortgang">
        <span>${DB.orders[s.job.orderId].nummer}</span>
        <span>${totaal-open+1} van ${totaal}</span>
      </div>
      <div class="scanstappen">
        ${["LOCATIE","ARTIKEL","AANTAL"].map((st,i)=>`
          <span class="scanstap ${s.stap===st?"nu":(["LOCATIE","ARTIKEL","AANTAL"].indexOf(s.stap)>i?"gedaan":"")}">
            ${i+1}. ${st.toLowerCase()}</span>`).join("")}
      </div>

      <div class="scanveld ${s.stap==="LOCATIE"?"vraag":"gedaan"}">
        <span class="scanlabel">Ga naar</span>
        <span class="scanwaarde mono">${esc(loc.code)}</span>
        ${s.stap==="LOCATIE"?`<span class="scanhint">scan de locatie</span>`
          :`<span class="scanvink">✓</span>`}
      </div>

      ${["ARTIKEL","AANTAL"].includes(s.stap)?`
      <div class="scanveld ${s.stap==="ARTIKEL"?"vraag":"gedaan"}">
        <span class="scanlabel">Pak</span>
        <span class="scanwaarde mono">${esc(art.sku)}</span>
        <span class="scanhint">${esc(art.oms)}</span>
        ${s.stap==="ARTIKEL"?`<span class="scanhint">scan het artikel</span>`
          :`<span class="scanvink">✓</span>`}
      </div>`:""}

      ${s.stap==="AANTAL"?`
      <div class="scanveld vraag aantal">
        <span class="scanlabel">Aantal</span>
        <div class="aantalrij">
          <button class="ronde" data-aantal-stap="-1">&minus;</button>
          <input id="scanAantal" type="number" inputmode="numeric" value="${nog}" min="0">
          <button class="ronde" data-aantal-stap="1">+</button>
        </div>
        <button class="groot" data-scan-bevestig>Afmelden</button>
        <button class="groot stil" data-scan-bevestig data-nul>Niets gevonden</button>
      </div>`:""}
      `;
    }
  }

  if(s.taak==="INSLAG"){
    if(s.stap==="ARTIKEL") kern = `
      <div class="scanveld vraag">
        <span class="scanlabel">Inslaan</span>
        <span class="scanwaarde">Scan het artikel</span>
        <span class="scanhint">of typ het artikelnummer</span>
      </div>`;
    else if(s.stap==="INSLAG_AANTAL") kern = `
      <div class="scanveld gedaan">
        <span class="scanlabel">Artikel</span>
        <span class="scanwaarde mono">${esc(s.artikel.sku)}</span>
        <span class="scanhint">${esc(s.artikel.oms)}</span></div>
      <div class="scanveld vraag aantal">
        <span class="scanlabel">Hoeveel</span>
        <div class="aantalrij">
          <button class="ronde" data-aantal-stap="-1">&minus;</button>
          <input id="scanAantal" type="number" inputmode="numeric" value="${s.aantal}" min="1">
          <button class="ronde" data-aantal-stap="1">+</button>
        </div>
        <button class="groot" data-scan-bevestig>Zoek een plek</button>
      </div>`;
    else if(s.stap==="INSLAG_LOCATIE"){
      const v = voorstelInslag(DB, s.artikel.id, s.aantal, 4);
      kern = `
      <div class="scanveld gedaan">
        <span class="scanlabel">Inslaan</span>
        <span class="scanwaarde mono">${s.aantal} × ${esc(s.artikel.sku)}</span></div>
      <div class="scanveld vraag">
        <span class="scanlabel">Breng naar</span>
        ${v.length?v.map((x,i)=>`
          <div class="voorstelrij ${i===0?"beste":""}">
            <span class="mono groot2">${esc(x.loc.code)}</span>
            <span class="scanhint">${maatVan(x.loc)} · past ${x.vrij} · benutting ${(x.benutting*100).toFixed(0)}%</span>
          </div>`).join(""):`<span class="scanwaarde">Geen plek gevonden</span>`}
        <span class="scanhint">scan de locatie waar je het neerzet</span>
      </div>`;
    }
  }

  if(s.taak==="TELLEN"){
    if(s.stap==="LOCATIE") kern = `
      <div class="scanveld vraag"><span class="scanlabel">Tellen</span>
        <span class="scanwaarde">Scan de locatie</span></div>`;
    else if(s.stap==="TEL_ARTIKEL") kern = `
      <div class="scanveld gedaan"><span class="scanlabel">Locatie</span>
        <span class="scanwaarde mono">${esc(s.locatie.code)}</span></div>
      <div class="scanveld vraag"><span class="scanlabel">Artikel</span>
        <span class="scanwaarde">Scan het artikel</span></div>`;
    else if(s.stap==="TEL_AANTAL") kern = `
      <div class="scanveld gedaan"><span class="scanlabel">Locatie</span>
        <span class="scanwaarde mono">${esc(s.locatie.code)}</span></div>
      <div class="scanveld gedaan"><span class="scanlabel">Artikel</span>
        <span class="scanwaarde mono">${esc(s.artikel.sku)}</span></div>
      <div class="scanveld vraag aantal">
        <span class="scanlabel">Hoeveel tel je?</span>
        <span class="scanhint">Het systeem denkt ${s.aantal}. Tel zelf en vul in wat er ligt.</span>
        <div class="aantalrij">
          <button class="ronde" data-aantal-stap="-1">&minus;</button>
          <input id="scanAantal" type="number" inputmode="numeric" value="${s.aantal}" min="0">
          <button class="ronde" data-aantal-stap="1">+</button>
        </div>
        <button class="groot" data-scan-bevestig>Telling vastleggen</button>
      </div>`;
  }

  if(s.taak==="VRIJ"){
    const p = s.artikel ? DB.artikelNu(s.artikel.id) : null;
    kern = `
      <div class="scanveld vraag"><span class="scanlabel">Opzoeken</span>
        <span class="scanwaarde">Scan een locatie of artikel</span>
        <span class="scanhint">handig als iemand vraagt: waar ligt dit?</span></div>
      ${s.locatie?`<div class="scanveld gedaan">
        <span class="scanlabel">Locatie ${esc(s.locatie.code)}</span>
        ${voorraadOp(DB,s.locatie.id).map(x=>`<div class="voorstelrij">
          <span class="mono">${esc(DB.artikelen[x.productId].sku)}</span>
          <span class="scanhint">${x.qty} stuks</span></div>`).join("")
          || `<span class="scanhint">leeg</span>`}
      </div>`:""}
      ${p?`<div class="scanveld gedaan">
        <span class="scanlabel">${esc(p.sku)}</span>
        <span class="scanhint">${esc(p.oms)}</span>
        ${voorraadVan(DB,p.id).map(x=>`<div class="voorstelrij">
          <span class="mono groot2">${esc(DB.locaties[x.locationId].code)}</span>
          <span class="scanhint">${x.qty} stuks</span></div>`).join("")
          || `<span class="scanhint">geen voorraad</span>`}
      </div>`:""}`;
  }

  return `
  <div class="scanschil">
    <div class="scanbalk">
      <button class="scanuit" data-scan-uit>&larr;</button>
      <div class="scantaken">
        ${taken.map(([k,n])=>`<button class="scantaak ${scan.taak===k?"aan":""}"
          data-scan-taak="${k}">${n}</button>`).join("")}
      </div>
      <div class="scanwie">${esc(HUIDIGE.naam.split(" ")[0])}</div>
    </div>

    ${scan.bericht?`<div class="scanbericht ${scan.berichtSoort}">${esc(scan.bericht)}</div>`:""}

    <div class="scaninhoud">${kern}</div>

    <div class="scaninvoer">
      <input id="scanInvoer" autocomplete="off" autocapitalize="off" spellcheck="false"
             placeholder="scan of typ een code…">
      ${scan.taak==="PICKEN"&&scan.regel?`<button class="stil" data-scan-skip>Overslaan</button>`:""}
    </div>

    ${scan.gescand.length?`<div class="scanlog">
      ${scan.gescand.slice(0,5).map(g=>`<div class="scanlogregel ${g.soort}">
        <span class="mono">${new Date(g.tijd).toLocaleTimeString("nl-NL",{hour:"2-digit",minute:"2-digit"})}</span>
        <span>${esc(g.tekst)}</span></div>`).join("")}
    </div>`:""}
  </div>`;
}

/* ===================== INLOGGEN ===================================== */
function schermInloggen(){
  return `
  <h1>Wie ben je?</h1>
  <p class="lead">In het echt scan je hier je badge. Zonder inlog weet je bij een
  telverschil niet wie het geboekt heeft &mdash; en dan kun je achteraf niet navragen
  wat er gebeurde. Voor de demo kies je gewoon een naam.</p>
  <div class="kaart">
    <div class="tabelwrap"><table>
      <thead><tr><th>Naam</th><th>Rol</th><th>Badge</th><th></th></tr></thead>
      <tbody>${DB.gebruikers.map(g=>`<tr>
        <td class="sterk">${esc(g.naam)}</td>
        <td>${pil(g.rol==="ADMIN"?"a":g.rol==="SUPERVISOR"?"g":"n", ROLLEN[g.rol].naam)}</td>
        <td class="mono hint">${esc(g.badge)}</td>
        <td><button class="klein ${g.id===HUIDIGE.id?"":"stil"}" data-login="${g.id}">
          ${g.id===HUIDIGE.id?"Actief":"Word deze"}</button></td>
      </tr>`).join("")}</tbody></table></div>
    <div class="uitleg"><b>Wat de rol bepaalt.</b> Een magazijnmedewerker ziet alleen
      het werk: picken, inslaan, opmeten, opzoeken. Een teamleider ziet daarnaast de
      orders en het dashboard. Alleen een beheerder komt bij de instellingen. Dat is
      geen wantrouwen &mdash; het is minder schermen om je door te worstelen.</div>
  </div>`;
}

/* =====================================================================
   SCHERMEN: TAKEN, DE WERKDAG EN DE SCANMODUS

   Wat er op de vloer gebeurt. Drie schermen die bij elkaar horen omdat
   ze alle drie over hetzelfde gaan: iemand met een kar en een scanner.
   ===================================================================== */

/* ===================== TAKEN ======================================== */
function schermTaken(){
  const rang = t => t.status==="TODO" ? 0 : t.status==="DONE" ? 1 : 2;
  const rijen = [...DB.taken].sort((a,b)=> rang(a)-rang(b) || a.prio-b.prio || a.id-b.id);
  const pg = pagineer(rijen);
  return `
  <h1>Taken</h1>
  <p class="lead">Aanvullen, verplaatsen, tellen en inslaan zitten in <b>één</b> tabel
  met een type en een prioriteit. Daardoor krijg je die processen er bijna gratis bij
  en heeft een medewerker één lijst waarop hij zijn volgende opdracht ziet.</p>

  <div class="uitleg"><b>Niemand maakt deze taken aan.</b> Ze volgen uit de toestand van
  het magazijn: een picklocatie zakt onder de drempel, een artikel blijkt groter dan het
  was, een telling wijkt af. En ze verdwijnen ook weer vanzelf &mdash; vult iemand een
  locatie handmatig bij, dan vervalt de aanvultaak met de reden erbij. Een lijst die
  alleen groeit, gaat niemand bijhouden.</div>

  <div class="kaart">
    <div class="tabelwrap"><table>
      <thead><tr><th>Prio</th><th>Taak</th><th>Artikel</th><th>Van</th><th>Naar</th>
        <th class="num">Aantal</th><th>Reden</th><th>Status</th><th></th></tr></thead>
      <tbody>${pg.rijen.map(t=>`<tr class="${t.status==="VERVALLEN"?"vervallen":""}">
        <td>${pil("n",t.prio)}</td>
        <td class="${t.status==="VERVALLEN"?"doorheen":""}">${esc(t.naam)}</td>
        <td><a href="#artikel/${t.productId}" class="mono">${esc(DB.artikelen[t.productId].sku)}</a></td>
        <td class="mono">${esc(DB.locaties[t.van].code)}</td>
        <td class="mono">${esc(DB.locaties[t.naar].code)}</td>
        <td class="num sterk">${fmt(t.qty)}</td>
        <td class="hint">${esc(t.reden)}${t.automatisch?` ${pil("a","door het systeem")}`:""}</td>
        <td>${t.status==="DONE"?pil("g","afgemeld")
             :t.status==="VERVALLEN"?pil("n","vervallen"):pil("o","open")}
          ${t.vervallenReden?`<div class="hint">${esc(t.vervallenReden)}</div>`:""}</td>
        <td>${t.status==="TODO"?`<button class="klein" data-taak="${t.id}">Afmelden</button>`:""}</td>
      </tr>`).join("")}</tbody></table></div>
    ${pagBalk(pg)}
    ${pg.totaal?"":`<p class="leeg">Geen taken.</p>`}
  </div>`;
}

/* ===================== DAG ========================================== */
function schermDag(){
  const t = sim.teller;
  const perStatus = {};
  for(const st of ORDERSTATUS) perStatus[st] = DB.orders.filter(o=>o.status===st);
  const openRegels = DB.pickjobs.filter(j=>j.status==="TODO")
    .reduce((a,j)=>a+j.regels.filter(r=>r.status==="TODO").length,0);

  const uren = Object.keys(sim.perUur).map(Number).sort((a,b)=>a-b);
  const maxRegels = Math.max(1, ...uren.map(u=>sim.perUur[u].regels));

  const soortKleur = {order:"a", manco:"r", tekort:"r", rit:"g", pak:"g",
                      golf:"a", aanvul:"o", inbound:"o", eind:"g"};

  return `
  <h1>Een dag in het magazijn</h1>
  <p class="lead">Speelt een werkdag af van 07:00 tot 17:00: orders komen binnen, worden
  gereserveerd, in golven vrijgegeven, gepickt, ingepakt en verzonden.
  <b>Alles loopt door dezelfde functies als handmatig werken</b> &mdash; er is geen
  aparte demo-modus die iets voorwendt.</p>

  <div class="uitleg"><b>Zet hem op "rommelig".</b> Een nette dag is hoe een demo er
  meestal uitziet: alles klopt en niets valt om. Op rommelig lijkt het op een echte
  maandag &mdash; drie keer zoveel manco's, spoedorders van klanten die aan de balie
  staan, breuk, een geblokkeerde stelling, en pickers die een deel van hun tijd kwijt
  zijn aan van alles behalve picken. Dat verschil is groot, en het is eerlijker.</div>

  <div class="kaart dagbalk">
    <div class="klok">
      <span class="klokcijfer mono">${klok(Math.min(sim.tijd, DAGEIND))}</span>
      <span class="hint">${sim.klaar ? "dag afgesloten"
        : sim.draait ? "loopt" : sim.tijd===DAGSTART ? "nog niet begonnen" : "gepauzeerd"}</span>
    </div>
    <div class="knoprij">
      ${sim.draait
        ? `<button data-sim="pauze">Pauzeer</button>`
        : `<button data-sim="start">${sim.tijd===DAGSTART?"Start de dag":"Verder"}</button>`}
      <button class="stil" data-sim="uur" ${sim.klaar?"disabled":""}>Sla een uur over</button>
      <button class="stil" data-sim="reset">Opnieuw</button>
      <label class="inlijn">Tempo
        <select data-sim-snelheid>
          ${[[400,"rustig"],[200,"normaal"],[120,"snel"],[40,"heel snel"]]
            .map(([v,n])=>`<option value="${v}" ${sim.snelheid===v?"selected":""}>${n}</option>`).join("")}
        </select></label>
      <label class="inlijn">Dag
        <select data-sim-rommel>
          <option value="net" ${!sim.rommel?"selected":""}>netjes</option>
          <option value="echt" ${sim.rommel?"selected":""}>rommelig</option>
        </select></label>
      <label class="inlijn">Pickers
        <select data-sim-pickers>
          ${[2,3,4,5,6,8].map(n=>`<option value="${n}" ${sim.pickers===n?"selected":""}>${n}</option>`).join("")}
        </select></label>
    </div>
  </div>

  <div class="tegels vijf">
    <div class="kaart tegel"><span class="label">Orders binnen</span>
      <span class="cijfer">${fmt(t.binnen)}</span></div>
    <div class="kaart tegel"><span class="label">Verzonden</span>
      <span class="cijfer">${fmt(t.verzonden)}</span>
      <span class="hint">${openRegels?fmt(openRegels)+" regels open":"niets open"}</span></div>
    <div class="kaart tegel"><span class="label">Regels gepickt</span>
      <span class="cijfer">${fmt(t.regels)}</span>
      <span class="hint">${fmt(t.stuks)} stuks</span></div>
    <div class="kaart tegel"><span class="label">Manco's</span>
      <span class="cijfer ${t.manco?"slecht":""}">${fmt(t.manco)}</span>
      <span class="hint">${t.regels?((t.manco/t.regels)*100).toFixed(1)+"% van de regels":"&nbsp;"}</span></div>
    <div class="kaart tegel"><span class="label">Verstoringen</span>
      <span class="cijfer ${t.storing?"slecht":""}">${fmt(t.storing)}</span>
      <span class="hint">${sim.rommel?"schade, spoed, oponthoud":"nette dag: geen"}</span></div>
  </div>

  <div class="tweeluik">
    <div class="kaart">
      <h2>Werk per uur</h2>
      <p class="hint">Hieraan zie je je piekuren, en dus wanneer je bezetting nodig hebt.
        Een dagtotaal vertelt je dat niet. Verzendingen komen in golven om 12:00 en 16:00 &mdash;
        daarom staan die staven daar hoog en elders op nul.</p>
      ${grafiekGroep({
        groepen: uren.map(u=>({label:String(u).padStart(2,"0"),
          waarden:[sim.perUur[u].regels, sim.perUur[u].verzonden]})),
        series: [{naam:"Gepickte regels"},{naam:"Verzonden orders"}],
        eenheid:"" })}
    </div>

    <div class="kaart">
      <h2>Wat er nu gebeurt</h2>
      <p class="hint">De laatste gebeurtenissen, nieuwste bovenaan.</p>
      <div class="logboek">
        ${sim.gebeurtenissen.length?sim.gebeurtenissen.slice(0,14).map(g=>`
          <div class="logregel">
            <span class="mono hint">${klok(g.tijd)}</span>
            ${pil(soortKleur[g.soort]||"n", g.soort)}
            <span>${esc(g.tekst)}</span>
          </div>`).join(""):`<p class="leeg">Nog niets gebeurd.</p>`}
      </div>
    </div>
  </div>

  <div class="kaart">
    <h2>Orderbord</h2>
    <p class="hint">Elke order doorloopt deze stappen. Een order kan alleen langs
      toegestane overgangen &mdash; geen vrij tekstveld waar iemand "klaar?" in typt.</p>
    <div class="bord">
      ${ORDERSTATUS.map(st=>`
        <div class="kolom">
          <div class="kolomkop">
            <span>${esc(STATUSNAAM[st])}</span>
            <span class="pil ${STATUSKLEUR[st]}">${perStatus[st].length}</span>
          </div>
          ${perStatus[st].slice(0,6).map(o=>`
            <a class="orderkaart" href="#order/${o.id}">
              <span class="mono sterk">${esc(o.nummer)}</span>
              <span class="hint">${esc(o.klant)}</span>
              <span class="hint">${o.regels.length} regel(s) &middot; ${esc(o.vervoerder)}</span>
            </a>`).join("")}
          ${perStatus[st].length>6?`<div class="hint meer">+ ${perStatus[st].length-6} meer</div>`:""}
        </div>`).join("")}
    </div>
  </div>`;
}

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

/* =====================================================================
   SCHERM: EIGEN GEGEVENS
   ===================================================================== */

const SOORTNAAM = {locaties:"Locatiebestand", artikelen:"Artikelbestand", voorraad:"Voorraadbestand"};

function bestandsblok(soort, verplicht){
  const B = imp.bestanden[soort];
  const K = imp.kolom[soort];
  return `
  <div class="impvak ${B?"geladen":""}">
    <div class="impkop">
      <div>
        <b>${SOORTNAAM[soort]}</b>
        ${verplicht?pil("a","nodig"):pil("n","mag ontbreken")}
        <div class="hint">${soort==="locaties"
          ? "Elke stellingplaats één regel. Minimaal de code; afmetingen als je ze hebt."
          : soort==="artikelen"
          ? "Elk artikel één regel. Zonder maten kan het ook &mdash; die komen dan op de meetlijst."
          : "Wat er nu waar ligt. Heb je dit niet, sla het over en begin met een nulmeting."}</div>
      </div>
      <label class="impknop">
        <span>${B?"Ander bestand":"Kies bestand"}</span>
        <input type="file" accept=".csv,.txt,.xlsx,.xlsm" data-imp-bestand="${soort}" hidden>
      </label>
    </div>
    ${B?`
      <div class="impgelezen">
        <span class="mono">${esc(B.naam)}</span>
        <span class="hint">${fmt(B.rijen.length)} regels, ${B.kop.length} kolommen</span>
      </div>
      <div class="tabelwrap"><table>
        <thead><tr><th>Vakto verwacht</th><th>Jouw kolom</th><th>Eerste waarden</th></tr></thead>
        <tbody>${VELDEN[soort].map(v=>{
          const gekozen = K[v.k];
          const vb = gekozen===undefined ? [] :
            B.rijen.slice(0,3).map(r=>r[gekozen]).filter(x=>x!=="");
          return `<tr>
            <td>${esc(v.naam)} ${v.eis?`<span class="fout">*</span>`:""}
              ${gekozen===undefined && v.eis?`<div class="fout hint">niet gevonden &mdash; kies zelf</div>`:""}</td>
            <td><select data-imp-kol="${soort}" data-veld="${v.k}">
              <option value="">&mdash; niet aanwezig &mdash;</option>
              ${B.kop.map((h,i)=>`<option value="${i}" ${gekozen===i?"selected":""}>${esc(h)}</option>`).join("")}
            </select></td>
            <td class="mono hint">${vb.length?esc(vb.join(" · ")):"&mdash;"}</td>
          </tr>`;}).join("")}</tbody></table></div>
    `:""}
  </div>`;
}

function eenheidsrij(){
  const kies=(sleutel,opties)=>`<select data-imp-eenheid="${sleutel}">
    ${opties.map(([w,t])=>`<option value="${w}" ${imp.eenheid[sleutel]===w?"selected":""}>${t}</option>`).join("")}</select>`;
  return `
  <div class="filters">
    ${imp.bestanden.locaties?`<label class="inlijn">Locatiematen in ${kies("loc_maat",[["mm","millimeter"],["cm","centimeter"],["m","meter"]])}</label>
    <label class="inlijn">Draagvermogen in ${kies("loc_gew",[["kg","kilo"],["g","gram"]])}</label>`:""}
    ${imp.bestanden.artikelen?`<label class="inlijn">Artikelmaten in ${kies("art_maat",[["mm","millimeter"],["cm","centimeter"],["m","meter"]])}</label>
    <label class="inlijn">Artikelgewicht in ${kies("art_gew",[["g","gram"],["kg","kilo"]])}</label>`:""}
  </div>
  <div class="hint">Vakto raadt dit uit de getallen zelf. Klopt het niet, zet het hier om.
  Kijk vooral naar de regel hieronder: dáár zie je meteen of het klopt.</div>
  ${omrekenVoorbeeld("locaties")}${omrekenVoorbeeld("artikelen")}`;
}

/* Eén concreet voorbeeld zegt meer dan een keuzelijst: als hier "30 x 40 x 22 mm"
   staat voor een stellingvak, ziet iedereen meteen dat de eenheid fout staat. */
function omrekenVoorbeeld(soort){
  const B = imp.bestanden[soort], K = imp.kolom[soort];
  if(!B) return "";
  const fM = naarMm[soort==="locaties"?imp.eenheid.loc_maat:imp.eenheid.art_maat];
  const fG = naarG[soort==="locaties"?imp.eenheid.loc_gew:imp.eenheid.art_gew];
  const gk = soort==="locaties" ? "maxG" : "G";
  const rij = B.rijen.find(r=>getal(r[K.L])>0 && getal(r[K.W])>0 && getal(r[K.H])>0);
  if(!rij) return "";
  const L = Math.round(getal(rij[K.L])*fM), W = Math.round(getal(rij[K.W])*fM),
        H = Math.round(getal(rij[K.H])*fM), G = Math.round((getal(rij[gk])||0)*fG);
  const naam = (rij[soort==="locaties"?K.code:K.sku]||"?");
  const raar = soort==="locaties" ? (L<150 || L>6000) : (L>2000);
  return `<div class="melding ${raar?"waarschuw":""}" style="margin-top:10px">
    <span class="mono">${esc(naam)}</span> wordt
    <b>${fmt(L)} &times; ${fmt(W)} &times; ${fmt(H)} mm</b>${G?`, ${G>=1000?(G/1000).toFixed(G>=10000?0:1)+" kg":G+" gram"}`:""}.
    ${raar?`<span class="hint">Dat lijkt niet te kloppen voor ${soort==="locaties"?"een stellingvak":"een artikel"}. Zet de eenheid om.</span>`:""}</div>`;
}

function rapportblok(R){
  const deel=(sleutel,titel)=>{
    const d = R[sleutel];
    if(!d.rijen) return "";
    return `<tr>
      <td class="sterk">${titel}</td>
      <td class="num">${fmt(d.rijen)}</td>
      <td class="num ${d.goed<d.rijen?"fout":""}">${fmt(d.goed)}</td>
      <td>${d.problemen.length
        ? d.problemen.map(p=>`<div class="impprobleem ${p.ernst}">
            ${pil(p.ernst==="fout"?"r":"o", fmt(p.n)+"×")} ${esc(p.tekst)}
            <span class="hint mono">${esc(p.voorbeeld.join(", "))}${p.n>3?" …":""}</span></div>`).join("")
        : `<span class="hint">Niets bijzonders.</span>`}</td></tr>`;
  };
  const nietGemeten = R.artikelen.problemen.find(p=>p.sleutel==="nietgemeten");
  const geenMaat = R.locaties.problemen.find(p=>p.sleutel==="geenmaat");
  return `
  <div class="kaart">
    <h2>Wat er in de bestanden staat</h2>
    <div class="tabelwrap"><table>
      <thead><tr><th>Bestand</th><th class="num">Regels</th><th class="num">Bruikbaar</th><th>Wat opvalt</th></tr></thead>
      <tbody>${deel("locaties","Locaties")}${deel("artikelen","Artikelen")}${deel("voorraad","Voorraad")}</tbody></table></div>

    ${geenMaat?`
    <div class="uitleg"><b>${fmt(geenMaat.n)} locaties zonder afmeting.</b> Dat is normaal:
    bijna geen enkel systeem legt dit vast &mdash; en precies daarom kan zo'n systeem ook niet
    uitrekenen wat waar past. Geef hieronder één standaardmaat op, en meet daarna per zone
    één stellingvak op. Eén middag werk, en het klopt voor duizend locaties tegelijk.
      <div class="filters" style="margin-top:12px">
        <label class="inlijn">Diepte <input type="number" data-imp-std="L" value="${imp.standaard.L}"> mm</label>
        <label class="inlijn">Breedte <input type="number" data-imp-std="W" value="${imp.standaard.W}"> mm</label>
        <label class="inlijn">Hoogte <input type="number" data-imp-std="H" value="${imp.standaard.H}"> mm</label>
        <label class="inlijn">Max <input type="number" data-imp-std="maxG" value="${imp.standaard.maxG}"> kg</label>
        <button class="klein stil" data-imp-actie="controleer">Opnieuw controleren</button>
      </div>
    </div>`:""}

    ${nietGemeten?`
    <div class="uitleg"><b>${fmt(nietGemeten.n)} artikelen zonder complete maat.</b> Die komen
    op de lijst <a href="#meten">Opmeten</a>. Ze doen gewoon mee, alleen kan Vakto er nog geen
    plek voor uitrekenen. Meet ze bij de eerstvolgende ontvangst: dan heb je ze toch in je
    handen en kost het niets.</div>`:""}

    <div class="knoprij">
      <button data-imp-actie="overnemen" ${R.klaar?"":"disabled"}>Neem deze gegevens over</button>
      <button class="stil" data-imp-actie="controleer">Opnieuw controleren</button>
    </div>
    ${R.klaar?`<p class="hint">Hierna draait de hele demo op deze gegevens: dashboard,
    inslag, picken, scannen. Je kunt altijd terug naar Van Delden.</p>`
    :`<p class="fout">Er zijn geen bruikbare locaties. Zonder locaties kan er niets.</p>`}
  </div>`;
}

/* --- pad B: magazijn opzetten ---------------------------------------- */
function opzetblok(){
  const n = opzetAantal();
  return `
  <div class="kaart">
    <h2>Zet het magazijn op</h2>
    <p class="lead">Voor een magazijn waar niets is vastgelegd. Je beschrijft de stellingen
    zoals ze er staan &mdash; hoeveel gangen, hoeveel vakken per gang, hoeveel niveaus &mdash;
    en Vakto maakt de locaties aan, inclusief looproute en etiketten. Meet per zone één vak op;
    de rest is hetzelfde.</p>
    <div class="tabelwrap"><table>
      <thead><tr>
        <th>Code</th><th>Naam</th><th>Soort</th>
        <th class="num">Gangen</th><th class="num">Vakken</th><th class="num">Niveaus</th>
        <th class="num">Diepte</th><th class="num">Breedte</th><th class="num">Hoogte</th>
        <th class="num">Max kg</th><th class="num">Locaties</th><th></th>
      </tr></thead>
      <tbody>${imp.opzet.map((z,i)=>`<tr>
        <td><input class="mono" data-opzet="${i}" data-veld="code" value="${esc(z.code)}" style="min-width:56px"></td>
        <td><input data-opzet="${i}" data-veld="naam" value="${esc(z.naam)}" style="min-width:130px"></td>
        <td><select data-opzet="${i}" data-veld="soort">
          <option value="PL" ${z.soort==="PL"?"selected":""}>Picklocatie</option>
          <option value="BL" ${z.soort==="BL"?"selected":""}>Bulk / pallet</option></select></td>
        <td><input type="number" data-opzet="${i}" data-veld="gangen" value="${z.gangen}"></td>
        <td><input type="number" data-opzet="${i}" data-veld="vakken" value="${z.vakken}"></td>
        <td><input type="number" data-opzet="${i}" data-veld="niveaus" value="${z.niveaus}"></td>
        <td><input type="number" data-opzet="${i}" data-veld="L" value="${z.L}"></td>
        <td><input type="number" data-opzet="${i}" data-veld="W" value="${z.W}"></td>
        <td><input type="number" data-opzet="${i}" data-veld="H" value="${z.H}"></td>
        <td><input type="number" data-opzet="${i}" data-veld="maxG" value="${z.maxG}"></td>
        <td class="num sterk">${fmt(Math.max(0,z.gangen)*Math.max(0,z.vakken)*Math.max(0,z.niveaus))}</td>
        <td><button class="klein stil" data-imp-actie="opzet-weg" data-i="${i}">Weg</button></td>
      </tr>`).join("")}</tbody>
    </table></div>
    <div class="knoprij">
      <button class="stil klein" data-imp-actie="opzet-erbij">Zone erbij</button>
      <span class="hint">Samen <b>${fmt(n)}</b> locaties, plus ontvangst, keuring, schade en expeditie.</span>
    </div>
    ${n>20000?`<p class="fout">Meer dan twintigduizend locaties wordt traag in de browser.
      Voor zo'n magazijn hoort de serverversie, niet dit demobestand.</p>`:""}

    <div class="impvak" style="margin-top:16px">
      ${bestandsblok("artikelen", false)}
    </div>

    <div class="knoprij">
      <button data-imp-actie="opzet-bouw" ${n>0&&n<=20000?"":"disabled"}>Bouw dit magazijn</button>
    </div>
  </div>`;
}

/* --- etiketten: Code 39, want dat leest elke scanner zonder instellen - */
const C39 = {"0":"nnnwwnwnn","1":"wnnwnnnnw","2":"nnwwnnnnw","3":"wnwwnnnnn","4":"nnnwwnnnw",
"5":"wnnwwnnnn","6":"nnwwwnnnn","7":"nnnwnnwnw","8":"wnnwnnwnn","9":"nnwwnnwnn",
"A":"wnnnnwnnw","B":"nnwnnwnnw","C":"wnwnnwnnn","D":"nnnnwwnnw","E":"wnnnwwnnn",
"F":"nnwnwwnnn","G":"nnnnnwwnw","H":"wnnnnwwnn","I":"nnwnnwwnn","J":"nnnnwwwnn",
"K":"wnnnnnnww","L":"nnwnnnnww","M":"wnwnnnnwn","N":"nnnnwnnww","O":"wnnnwnnwn",
"P":"nnwnwnnwn","Q":"nnnnnnwww","R":"wnnnnnwwn","S":"nnwnnnwwn","T":"nnnnwnwwn",
"U":"wwnnnnnnw","V":"nwwnnnnnw","W":"wwwnnnnnn","X":"nwnnwnnnw","Y":"wwnnwnnnn",
"Z":"nwwnwnnnn","-":"nwnnnnwnw",".":"wwnnnnwnn"," ":"nwwnnnwnn","*":"nwnnwnwnn"};

/* Als SVG, niet als reeks divjes: een streepjescode moet zijn breedte-
   verhoudingen exact houden. Wordt hij ergens uitgerekt of samengedrukt,
   dan piept de scanner en denkt de klant dat het systeem niet werkt.
   Smal:breed is 1:3, met een rustzone van tien eenheden aan weerskanten. */
function code39(tekst){
  const s = "*" + String(tekst).toUpperCase().replace(/[^0-9A-Z\-. ]/g,"-") + "*";
  const RUST = 10, H = 30;
  let x = RUST, rects = "";
  for(const c of s){
    const p = C39[c] || C39["-"];
    for(let i=0;i<9;i++){
      const b = p[i]==="w" ? 3 : 1;
      if(i % 2 === 0) rects += `<rect x="${x}" y="0" width="${b}" height="${H}"/>`;
      x += b;
    }
    x += 1;                                  /* scheiding tussen tekens */
  }
  const breed = x + RUST - 1;
  return `<svg class="c39" viewBox="0 0 ${breed} ${H}" preserveAspectRatio="none"
    width="100%" height="34" role="img" aria-label="streepjescode ${esc(tekst)}">
    <rect x="0" y="0" width="${breed}" height="${H}" fill="#fff"/>
    <g fill="#000">${rects}</g></svg>`;
}

function schermEtiketten(){
  const locs = DB.locaties.filter(l=>LOCTYPES[l.typeId].doel);
  const pg = pagineer(locs);
  return `
  <h1>Locatie-etiketten</h1>
  <p class="lead">Print deze pagina (Ctrl&#8239;+&#8239;P, of Cmd&#8239;+&#8239;P op een Mac) op
  etiketvellen of gewoon op papier. De streepjescode is Code&nbsp;39: die leest elke handscanner
  zonder dat je iets hoeft in te stellen. Plak ze op de stelling, links van het vak, altijd op
  dezelfde hoogte &mdash; anders zoekt iedereen zich suf.</p>
  <div class="knoprij nietprinten">
    <a class="knop stil" href="#eigen">Terug</a>
    <span class="hint">${fmt(pg.van)}&ndash;${fmt(pg.tot)} van ${fmt(pg.totaal)} locaties.
      Print per pagina; ${getN("ui.rows_per_page")} etiketten per keer.</span>
  </div>
  <div class="etiketvel">
    ${pg.rijen.map(l=>`<div class="etiket">
      <div class="etiketcode mono">${esc(l.code)}</div>
      ${code39(l.code)}
      <div class="etiketmaat">${maatVan(l)} · ${l.L}×${l.W}×${l.H} mm · max ${Math.round(l.maxG/1000)} kg</div>
    </div>`).join("")}
  </div>
  <div class="nietprinten">${pagBalk(pg)}</div>`;
}

/* --- het scherm zelf --------------------------------------------------- */
function schermEigen(){
  const eigen = !!DB.eigen;
  const R = imp.rapport;

  const kop = `
  <h1>Eigen gegevens</h1>
  <p class="lead">Hiermee wordt de demo hún magazijn. Dat is het verschil tussen een klant
  die beleefd knikt en een klant die zijn eigen artikelnummer op het scherm ziet staan.</p>

  ${eigen?`
  <div class="melding groot waarschuw">
    <div class="meldkop"><b>Je draait nu op ingelezen gegevens</b>
      <span class="hint">${fmt(DB.locaties.length)} locaties · ${fmt(DB.artikelen.length)} artikelen · ${fmt(DB.voorraad.filter(s=>s.qty>0).length)} voorraadregels</span></div>
    <div class="meldtekst">Alles werkt hier hetzelfde als in de demo. Zet het terug voordat je
      naar een volgende klant gaat &mdash; je wilt niet met het magazijn van de vorige binnenkomen.</div>
    <div class="knoprij">
      <button class="stil" data-imp-actie="terug">Terug naar Van Delden</button>
      <a class="knop stil" href="#etiketten">Locatie-etiketten</a>
    </div>
  </div>`:""}

  <div class="impkeuze">
    ${[["bestand","Ze hebben bestanden","Een locatielijst en een artikellijst, uit het ERP of uit Excel. Hoe rommelig ook."],
       ["opzet","Ze hebben geen locaties","Alles staat ergens, de mensen weten waar. Dan zetten we de structuur hier op en printen we etiketten."],
       ["nul","Ze hebben geen voorraadbestand","Locaties wel, lijst niet. Dan tel je het magazijn één keer met de scanner in."]]
      .map(([k,t,u])=>`<button class="impkaart ${imp.bron===k?"aan":""}" data-imp-actie="kies" data-bron="${k}">
        <b>${t}</b><span class="hint">${u}</span></button>`).join("")}
  </div>`;

  if(imp.bron === "bestand"){
    return kop + `
    <div class="kaart">
      <h2>Bestanden inlezen</h2>
      <p class="lead">CSV of Excel (.xlsx). Vakto zoekt zelf uit welke kolom wat is en laat je
      dat controleren &mdash; raden zonder tonen is precies hoe imports stilletjes fout gaan.</p>
      ${imp.fout?`<div class="melding fout groot">${esc(imp.fout)}</div>`:""}
      ${bestandsblok("locaties", true)}
      ${bestandsblok("artikelen", false)}
      ${bestandsblok("voorraad", false)}
      ${imp.bestanden.locaties||imp.bestanden.artikelen?eenheidsrij():""}
      <div class="knoprij">
        <button data-imp-actie="controleer" ${imp.bestanden.locaties?"":"disabled"}>Controleer de gegevens</button>
        <label class="inlijn">Bedrijfsnaam
          <input data-imp-bedrijf value="${esc(imp.bedrijf)}" placeholder="naam van de klant" style="min-width:230px"></label>
      </div>
    </div>
    ${R?rapportblok(R):""}

    <div class="kaart">
      <h2>Wat je vraagt voordat je langsgaat</h2>
      <p class="hint">Stuur dit lijstje vooraf. Dan sta je er niet met lege handen.</p>
      <div class="tabelwrap"><table>
        <thead><tr><th>Bestand</th><th>Wat er minimaal in moet</th><th>Waar het meestal vandaan komt</th></tr></thead>
        <tbody>
          <tr><td class="sterk">Locaties</td><td>Locatiecode. Afmetingen en draagvermogen als ze die hebben.</td>
              <td class="hint">Vaak bestaat dit niet. Dan is het pad hiernaast de route.</td></tr>
          <tr><td class="sterk">Artikelen</td><td>Artikelnummer, omschrijving. Maten en gewicht als ze die hebben.</td>
              <td class="hint">Exact/AFAS/SnelStart, of een oude Excel van de inkoop.</td></tr>
          <tr><td class="sterk">Voorraad</td><td>Artikelnummer, locatie, aantal.</td>
              <td class="hint">Vaak alleen een totaal per artikel zonder locatie. Ook goed: dan tel je in.</td></tr>
        </tbody></table></div>
    </div>`;
  }

  if(imp.bron === "opzet") return kop + opzetblok() + `
    <div class="kaart">
      <h2>Wat je op de vloer doet</h2>
      <ol class="stappen">
        <li><b>Loop het magazijn af en teken de gangen.</b> Nummer ze zoals je loopt, niet zoals
          ze toevallig staan. De looproute komt hier vandaan.</li>
        <li><b>Meet per zone één vak op.</b> Diepte, breedte, vrije hoogte. Vijf minuten werk voor
          duizend locaties, en het is de reden dat Vakto kan uitrekenen wat waar past.</li>
        <li><b>Vul het hierboven in en print de etiketten.</b> Plak ze op dezelfde plek op elk vak.</li>
        <li><b>Tel het magazijn in met de scanner.</b> Locatie scannen, artikel scannen, aantal
          intypen. Onbekend artikel? Dat maakt Vakto ter plekke aan.</li>
      </ol>
      <div class="uitleg"><b>Hoelang dit duurt.</b> Een magazijn van tweeduizend locaties label je
      met twee mensen in een dag. Inteltellen kost ongeveer een minuut per locatie waar iets ligt;
      reken op twee tot drie dagen met twee man. Doe het op een vrijdagmiddag en het weekend erna,
      dan verschuift er niets terwijl je telt. Dat is de eerlijke planning &mdash; beloof geen
      ochtend, want dan sta je er zaterdag nog.</div>
    </div>`;

  if(imp.bron === "nul") return kop + `
    <div class="kaart">
      <h2>Nulmeting: het magazijn één keer intellen</h2>
      <p class="lead">Er is geen voorraadbestand. Dat is geen probleem, het is een startpunt.
      Je hebt locaties nodig (uit een bestand of hierboven opgezet) en verder alleen een scanner.</p>
      <ol class="stappen">
        <li>Zet <b>Onbekende code aanmaken</b> aan. Scan je iets dat het systeem niet kent, dan
          maakt Vakto het artikel ter plekke aan in plaats van te piepen.</li>
        <li>Ga naar <b>Scanmodus &rarr; Tellen</b>. Locatie scannen, artikel scannen, aantal intypen.</li>
        <li>Werk gang voor gang. Wat je overslaat blijft nul, en dat zie je terug.</li>
        <li>Na afloop: de nieuwe artikelen staan op <a href="#artikelen">Artikelen</a> met de
          omschrijving "nog benoemen". Die werk je in één zitting bij.</li>
      </ol>
      <div class="filters">
        <label class="inlijn">Onbekende code aanmaken tijdens tellen
          <select data-imp-nul>
            <option value="false" ${!getB("opstart.onbekend_aanmaken")?"selected":""}>uit</option>
            <option value="true" ${getB("opstart.onbekend_aanmaken")?"selected":""}>aan</option>
          </select></label>
      </div>
      <div class="knoprij">
        <a class="knop" href="#scan" data-scan-taak="TELLEN">Begin met tellen</a>
        <a class="knop stil" href="#etiketten">Locatie-etiketten</a>
      </div>
      <div class="uitleg"><b>Waarom dit werkt en een Excel-lijst niet.</b> Bij een telling in Excel
      typt iemand achteraf over wat op een papiertje stond. Hier ontstaat de regel op het moment
      dat iemand ernaar kijkt, mét locatie en mét tijdstip in het journaal. Vanaf de eerste dag
      klopt de herkomst van elk getal. Dat is precies wat een magazijn dat nooit iets vastlegde
      nog nooit heeft gehad.</div>
    </div>

    <div class="kaart">
      <h2>Wat je een klant zonder locaties eerlijk vertelt</h2>
      <p class="verhaal">"Jullie weten waar alles ligt. Dat werkt, tot de ene die het weet ziek is,
      of tot je er twee mensen bij zet. Dan blijkt dat kennis in iemands hoofd niet te delen is."</p>
      <div class="tabelwrap"><table>
        <thead><tr><th>Wat ze nu hebben</th><th>Wat het kost</th><th>Wat er verandert</th></tr></thead>
        <tbody>
          <tr><td>Geen locaties</td><td class="hint">Een dag labelen, met z'n tweeën</td>
              <td>Nieuwe medewerker is in een uur productief in plaats van in een maand</td></tr>
          <tr><td>Geen voorraadlijst</td><td class="hint">Twee tot drie dagen intellen</td>
              <td>Je weet wat je hebt. Nabestellen op gevoel stopt</td></tr>
          <tr><td>Geen maten</td><td class="hint">Meten bij ontvangst, kost niets extra</td>
              <td>Het systeem gaat zelf zeggen waar iets heen moet</td></tr>
        </tbody></table></div>
      <div class="uitleg"><b>De valkuil.</b> Bedrijven willen dit vaak "erbij" doen in een gewone
      werkweek. Dat mislukt: je telt terwijl er gepickt wordt en dan klopt niets. Plan het in een
      rustige periode of een weekend, en zeg dat vooraf. Een implementatie die eerlijk begint met
      "dit kost jullie drie dagen" wordt een succes; eentje die begint met "dat regelen we even"
      wordt een ruzie.</div>
    </div>`;

  return kop + `
  <div class="kaart">
    <h2>Waarom dit scherm er is</h2>
    <p>Een demo met verzonnen artikelen laat zien dát het werkt. Een demo met hún artikelen laat
    zien dat het bij hén werkt. Het verschil in een verkoopgesprek is groter dan welke functie
    dan ook.</p>
    <div class="uitleg"><b>Hoe je dit gebruikt.</b> Vraag het locatie- en artikelbestand op vóór
    het gesprek. Lees het thuis in, kijk of het klopt, en open op het gesprek meteen hún magazijn.
    Zit er rommel in de gegevens &mdash; en die zit er altijd &mdash; dan is dát je eerste
    gespreksonderwerp, en niet een functielijst.</div>
  </div>`;
}

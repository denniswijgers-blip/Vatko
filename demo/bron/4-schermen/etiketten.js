/* =====================================================================
   SCHERM: ETIKETTEN

   Barcodes tekenen en afdrukken. Code 39, want dat leest elke scanner
   zonder dat je er iets voor hoeft in te stellen.
   ===================================================================== */

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

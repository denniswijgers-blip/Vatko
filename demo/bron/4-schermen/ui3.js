/* =====================================================================
   PASTEKENING
   Twee aanzichten zoals op een werktekening: van boven en van voren.
   Dit is het scherm waar iemand "oh, zó" zegt. Een tabel vertelt dat er
   23 in passen; deze tekening laat zien waarom er geen 24 in gaan.
   ===================================================================== */
function pasFiguur(p, loc, fit, geplaatst){
  if(!fit || !fit.orient) return "";
  const [ol,ow,oh] = fit.orient;
  const nl = Math.max(1, Math.floor(loc.L/ol));
  const nw = Math.max(1, Math.floor(loc.W/ow));
  const nh = p.stapelbaar ? Math.max(1, Math.floor(loc.H/oh)) : 1;
  const perLaag = nl*nw;
  const lagen = Math.min(nh, Math.max(1, Math.ceil(geplaatst/perLaag)));
  const inOnderlaag = Math.min(perLaag, geplaatst);

  const x0 = 42, x1 = 372, y0 = 34;
  const s = Math.min(268/loc.L, 112/loc.W, 112/loc.H);
  const bW = loc.L*s, bH1 = loc.W*s, bH2 = loc.H*s;
  const tekenRaster = nl<=44 && nw<=44 && nh<=44;

  const maatH = (x,y,br,tekst)=>`
    <path class="pf-maat" d="M${x} ${y+7}v-7M${x+br} ${y+7}v-7M${x} ${y+3.5}h${br}"/>
    <text class="pf-tekst" x="${x+br/2}" y="${y+18}" text-anchor="middle">${tekst}</text>`;
  const maatV = (x,y,ho,tekst)=>`
    <path class="pf-maat" d="M${x-7} ${y}h7M${x-7} ${y+ho}h7M${x-3.5} ${y}v${ho}"/>
    <text class="pf-tekst" x="${x-9}" y="${y+ho/2+3}" text-anchor="end">${tekst}</text>`;

  /* --- bovenaanzicht: één laag, de vakjes die deze partij bezet --- */
  let boven = "";
  if(tekenRaster){
    const cw = bW/nl, ch = bH1/nw;
    for(let r=0;r<nw;r++) for(let c=0;c<nl;c++){
      const vol = r*nl+c < inOnderlaag;
      boven += `<rect class="${vol?"pf-vol":"pf-cel"}" x="${(x0+c*cw).toFixed(1)}"
        y="${(y0+r*ch).toFixed(1)}" width="${(cw-1).toFixed(1)}" height="${(ch-1).toFixed(1)}" rx="1"/>`;
    }
  }
  /* --- vooraanzicht: de lagen op elkaar --------------------------- */
  let voor = "";
  if(tekenRaster){
    const lh = bH2/nh, cw = bW/nl;
    for(let n=0;n<nh;n++){
      const vol = n < lagen;
      const y = y0 + bH2 - (n+1)*lh;
      for(let c=0;c<nl;c++){
        voor += `<rect class="${vol?"pf-vol":"pf-cel"}" x="${(x1+c*cw).toFixed(1)}"
          y="${(y+1).toFixed(1)}" width="${(cw-1).toFixed(1)}" height="${(lh-2).toFixed(1)}" rx="1"/>`;
      }
    }
  }

  const hoogte = Math.round(y0 + Math.max(bH1,bH2) + 30);
  return `
  <div class="pasfiguur">
    <svg viewBox="0 0 660 ${hoogte}" role="img"
         aria-label="Tekening: ${esc(p.sku)} in locatie ${esc(loc.code)}">
      <text class="pf-titel" x="${x0}" y="${y0-13}">Bovenaanzicht &mdash; één laag</text>
      <rect class="pf-vak" x="${x0}" y="${y0}" width="${bW.toFixed(1)}" height="${bH1.toFixed(1)}" rx="2"/>
      ${boven}
      ${maatH(x0, y0+bH1+4, bW, loc.L+" mm")}
      ${maatV(x0, y0, bH1, loc.W+" mm")}

      <text class="pf-titel" x="${x1}" y="${y0-13}">Vooraanzicht &mdash; ${nh===1?"één laag":nh+" lagen"}</text>
      <rect class="pf-vak" x="${x1}" y="${y0}" width="${bW.toFixed(1)}" height="${bH2.toFixed(1)}" rx="2"/>
      ${voor}
      ${maatH(x1, y0+bH2+4, bW, loc.L+" mm")}
      ${maatV(x1, y0, bH2, loc.H+" mm")}
    </svg>
    <div class="pf-uitleg">
      <span>Draaiing <b>${ol}&times;${ow}&times;${oh}</b> mm</span>
      <span>Per laag <b>${nl}&times;${nw} = ${fmt(perLaag)}</b> st</span>
      <span>Lagen <b>${lagen} van ${nh}</b></span>
      <span>Deze partij <b>${fmt(geplaatst)}</b> st${tekenRaster?"":" &middot; te veel vakjes om te tekenen"}</span>
    </div>
  </div>`;
}

/* ===================== INSLAG ======================================= */
function schermInslag(){
  const sku = staat.inslagSku, aantal = staat.inslagQty;
  let p=null, voorstellen=null, fout=null;
  if(sku){
    p = DB.artikelen.find(a=>a.sku.toLowerCase()===sku.toLowerCase()
                          || a.barcode===sku);
    if(!p) fout = `Artikel "${esc(sku)}" niet gevonden. Zoek op artikelnummer of scan de barcode.`;
    else {
      p = DB.artikelNu(p.id);
      if(!p.L) fout = `${esc(p.sku)} is nog nooit opgemeten, dus het systeem kan niet berekenen waar het past. Meet het eerst op.`;
      else voorstellen = voorstelInslag(DB, p.id, aantal);
    }
  }

  return `
  <h1>Inslag</h1>
  <p class="lead">Hier komen de twee kernideeën samen. Het systeem zoekt geen locaties
  op maatcategorie, maar <b>rekent per locatie uit of het past</b> &mdash; met de
  nieuwste gemeten afmetingen van het artikel.</p>

  <div class="tweeluik">
    <div class="kaart">
      <h2>Waar moet dit heen?</h2>
      <form data-form="inslag">
        <label>Artikelnummer of barcode
          <input name="sku" class="mono" value="${esc(sku)}" autofocus
                 placeholder="bijv. BEV-1012 &mdash; of scan de barcode"></label>
        <label>Aantal
          <input name="qty" type="number" min="1" value="${aantal}"></label>
        <div class="knoprij"><button type="submit">Zoek locaties</button></div>
      </form>
      ${p&&p.L?`<div class="gevonden">
        <span class="mono sterk">${esc(p.sku)}</span>
        <div class="hint">${esc(p.oms)}</div>
        <div class="hint mono">${p.L}&times;${p.W}&times;${p.H} mm &middot;
          ${(p.G/1000).toFixed(2)} kg &middot; gemeten ${dat(p.gemetenOp)}
          (${p.bron==="SUPPLIER"?"opgave leverancier":"zelf gemeten"})</div>
      </div>`:""}
    </div>

    <div class="kaart">
      <h2>Hoe het voorstel tot stand komt</h2>
      <p class="hint">Voor elke kandidaat rekent Vakto uit hoeveel er in past: alle
        draaiingen van de doos, het maximale gewicht van het schap, en wat er al ligt
        &mdash; dat laatste in volume, niet in stuks. Een pallet met 300 boutjes mag
        immers geen 300 aftrekken van het aantal pompen dat erbij kan.</p>
      <div class="tabelwrap"><table>
        <thead><tr><th>Weegt mee</th><th class="num">Punten</th></tr></thead>
        <tbody>
          <tr><td>Benutting van de vrije ruimte</td><td class="num">${WEGING.benutting}</td></tr>
          <tr><td>Picklocatie onder aanvuldrempel</td><td class="num">${WEGING.picklocatie_aanvul}</td></tr>
          <tr><td>Artikel ligt hier al</td><td class="num">${WEGING.zelfde_artikel}</td></tr>
          <tr><td>Hele partij past in één keer</td><td class="num">${WEGING.hele_partij_past}</td></tr>
          <tr><td>Locatie veel te ruim</td><td class="num fout">${WEGING.te_ruim_straf}</td></tr>
        </tbody></table></div>
      <p class="hint">Elk magazijn heeft hier zijn eigen mening over. Bij een klant
        stel je deze getallen bij; er hoeft geen regel code aangepast te worden.</p>
    </div>
  </div>

  ${fout?`<div class="melding fout groot">${fout}</div>`:""}

  ${voorstellen&&voorstellen.length?`<div class="kaart">
    <h2>Waarom hier, en hoeveel</h2>
    <p class="hint">De beste plek is <a href="#locatie/${voorstellen[0].loc.id}"
      class="mono sterk">${esc(voorstellen[0].loc.code)}</a>. Zo ligt het erin:</p>
    ${pasFiguur(p, voorstellen[0].loc, voorstellen[0].fit,
                voorstellen[0].alles ? aantal : voorstellen[0].vrij)}
  </div>`:""}

  ${voorstellen?`<div class="kaart">
    <h2>Voorstellen</h2>
    ${voorstellen.length?`
    <p class="hint">Gesorteerd op geschiktheid. Let op de kolom <b>benutting</b>: dat
      is wat voorkomt dat je palletplaatsen volgooit met kleingoed.</p>
    <div class="tabelwrap"><table>
      <thead><tr><th></th><th>Locatie</th><th>Soort</th><th>Maat</th><th>Afmeting</th>
        <th class="num">Past</th><th class="num">Benutting</th><th>Waarom</th><th></th></tr></thead>
      <tbody>${voorstellen.map((v,i)=>`<tr class="${i===0?"beste":""}">
        <td>${i===0?pil("g","beste"):`<span class="hint">${i+1}</span>`}</td>
        <td><a href="#locatie/${v.loc.id}" class="mono sterk">${esc(v.loc.code)}</a>
            <div class="hint">${esc(DB.zones[v.loc.zoneId].naam)}</div></td>
        <td>${pil("n",LOCTYPES[v.loc.typeId].code)}</td>
        <td>${maatPil(maatVan(v.loc))}</td>
        <td class="mono hint">${v.loc.L}&times;${v.loc.W}&times;${v.loc.H}</td>
        <td class="num">${v.alles?`<b>${fmt(aantal)}</b><div class="hint">alles</div>`
                                 :`<b>${fmt(v.vrij)}</b><div class="hint">van ${fmt(aantal)}</div>`}</td>
        <td class="num"><span class="balk mini"><i style="width:${Math.min(100,v.benutting*100)}%"></i></span>
            <div class="hint">${(v.benutting*100).toFixed(1)}%</div></td>
        <td class="hint">${esc(v.redenen.join(", "))}<br>${esc(v.fit.reden)}</td>
        <td><button class="klein ${i===0?"":"stil"}" data-inslaan="${v.loc.id}"
              data-product="${p.id}" data-qty="${v.alles?aantal:v.vrij}">Inslaan</button></td>
      </tr>`).join("")}</tbody></table></div>`
    :`<div class="melding fout">Geen enkele locatie is geschikt. Mogelijke oorzaken:
      het artikel past nergens, of alle passende locaties zitten vol.</div>`}
  </div>`:""}`;
}

/* ===================== OPMETEN ====================================== */
function schermMeten(){
  const alles = teMeten(DB);
  const rijen = alles.slice(0,30);
  return `
  <h1>Opmeten</h1>
  <p class="lead">Artikelen waarvan de afmetingen ontbreken of verouderd zijn. Meet ze
  bij ontvangst: dan heb je ze toch in je handen. Wijkt een meting meer dan
  ${get("drift.alert_threshold_pct")}% af van de vorige, dan slaat Vakto zelf alarm
  <b>en</b> zoekt uit welke locaties daardoor een probleem krijgen.</p>

  <div class="kaart">
    <h2>Te meten ${pil("n",fmt(alles.length))}</h2>
    <p class="hint">Hieronder de ${rijen.length} langst openstaande. Vul de gemeten
      waarden in en druk op vastleggen.</p>
    <div class="tabelwrap"><table>
      <thead><tr><th>Artikel</th><th>Reden</th><th>Lengte</th><th>Breedte</th>
        <th>Hoogte</th><th>Gewicht (g)</th><th></th></tr></thead>
      <tbody>${rijen.map(p=>`<tr>
        <td><a href="#artikel/${p.id}" class="mono sterk">${esc(p.sku)}</a>
            <div class="hint">${esc(p.oms)}</div></td>
        <td>${pil(p.gemetenOp===null?"r":"o", p.reden)}</td>
        <td><input class="meet" data-veld="L" data-pid="${p.id}" type="number" value="${p.L??""}" placeholder="mm"></td>
        <td><input class="meet" data-veld="W" data-pid="${p.id}" type="number" value="${p.W??""}" placeholder="mm"></td>
        <td><input class="meet" data-veld="H" data-pid="${p.id}" type="number" value="${p.H??""}" placeholder="mm"></td>
        <td><input class="meet" data-veld="G" data-pid="${p.id}" type="number" value="${p.G??""}" placeholder="gram"></td>
        <td><button class="klein" data-meet="${p.id}">Vastleggen</button></td></tr>`).join("")}
    </tbody></table></div>
  </div>`;
}

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

/* ===================== INSTELLINGEN ================================= */
function schermInstellingen(){
  const groepen = {};
  for(const [k,v] of Object.entries(S)){ (groepen[v.g] = groepen[v.g]||[]).push([k,v]); }
  return `
  <h1>Instellingen</h1>
  <p class="lead">Alles wat per klant kan verschillen staat hier, en niet in de code.
  Dát is wat "een algemeen systeem dat je per klant inricht" in de praktijk betekent.</p>

  <div class="uitleg"><b>Probeer dit eens.</b> Zet <span class="mono">putaway.fill_factor</span>
  op 0.60 en doe daarna dezelfde inslag opnieuw. Alle voorstellen veranderen, zonder
  dat er ook maar één regel code is aangepast. Dat is het antwoord op "ja, maar bij
  ons stapelen we anders".</div>

  ${Object.entries(groepen).map(([g,rijen])=>`
  <div class="kaart">
    <h2>${esc(g)}</h2>
    <div class="tabelwrap"><table>
      <thead><tr><th>Sleutel</th><th>Waarde</th><th>Wat het doet</th></tr></thead>
      <tbody>${rijen.map(([k,v])=>`<tr>
        <td class="mono">${esc(k)}</td>
        <td><input data-inst="${esc(k)}" value="${esc(v.v)}"></td>
        <td class="hint">${esc(v.d)}</td></tr>`).join("")}</tbody></table></div>
  </div>`).join("")}

  <div class="knoprij"><button data-actie="instellingen-opslaan">Opslaan</button></div>`;
}

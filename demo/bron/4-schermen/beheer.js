/* =====================================================================
   SCHERMEN: INSTELLINGEN EN INLOGGEN

   De twee schermen die niet over het magazijn gaan maar over het
   systeem zelf.
   ===================================================================== */

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

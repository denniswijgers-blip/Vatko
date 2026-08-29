/* =====================================================================
   GEBRUIKERS EN RECHTEN

   Rollen bepalen wat iemand ziet. Een picker heeft niets te zoeken in
   de instellingen, en zonder inlog weet je bij een telverschil niet wie
   het geboekt heeft. Dat laatste is geen controledrang: als er iets
   misgaat wil je kunnen navragen wat er gebeurde, niet iemand straffen.
   ===================================================================== */

const ROLLEN = {
  OPERATOR:   {naam:"Magazijnmedewerker", kort:"MW",  rang:1},
  SUPERVISOR: {naam:"Teamleider",         kort:"TL",  rang:2},
  ADMIN:      {naam:"Beheerder",          kort:"BEH", rang:3}
};

/* Welke rang heb je minimaal nodig voor welk scherm? */
const RECHTEN = {
  demo:1, dag:2, dashboard:2, orders:2, taken:1, locaties:1, artikelen:1,
  inslag:1, picken:1, meten:1, instellingen:3, order:2, locatie:1, artikel:1,
  eigen:3, etiketten:2, optimalisatie:2
};
const mag = (sleutel)=> ROLLEN[HUIDIGE.rol].rang >= (RECHTEN[sleutel] ?? 1);

let HUIDIGE = null;

function bouwGebruikers(db){
  db.gebruikers = [
    {id:0, naam:"Dennis Wijgers",  badge:"BADGE-1001", rol:"ADMIN"},
    {id:1, naam:"Ruben de Groot",  badge:"BADGE-1002", rol:"SUPERVISOR"},
    {id:2, naam:"Kevin Timmermans",badge:"BADGE-1003", rol:"OPERATOR"},
    {id:3, naam:"Marta Nowak",     badge:"BADGE-1004", rol:"OPERATOR"},
    {id:4, naam:"Youssef El Amrani",badge:"BADGE-1005",rol:"OPERATOR"}
  ];
  HUIDIGE = db.gebruikers[0];
  return db.gebruikers;
}

function logIn(gb){
  HUIDIGE = gb;
  DB.log.unshift({at:Date.now(), niveau:"INFO", bron:"inloggen",
                  bericht:`${gb.naam} ingelogd (${ROLLEN[gb.rol].naam})`});
}

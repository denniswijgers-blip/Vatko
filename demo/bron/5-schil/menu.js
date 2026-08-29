/* =====================================================================
   MENU EN PICTOGRAMMEN

   Alleen gegevens, geen gedrag. Wil je een scherm toevoegen of een
   pictogram bijwerken, dan hoef je hier te zijn en nergens anders.

   De volgorde van SCHERMEN is de volgorde van de werkdag - binnen,
   op de vloer, buiten - en niet de volgorde waarin ze gebouwd zijn.
   ===================================================================== */

/* ===================== NAVIGATIE EN AFHANDELING ===================== */

/* Het merkteken: een doos in een vak. Dat is letterlijk waar het hele
   systeem over gaat, en het is herkenbaar op 16 pixels. */
const MERKTEKEN = `<svg viewBox="0 0 24 24" aria-hidden="true">
  <rect x="1.6" y="1.6" width="20.8" height="20.8" rx="4"
        fill="none" stroke="currentColor" stroke-width="1.5" opacity=".55"/>
  <rect x="6.4" y="12.2" width="11.2" height="5.4" rx="1.4" fill="currentColor"/>
  <path d="M6.4 8.4h11.2" stroke="currentColor" stroke-width="1.2"
        stroke-linecap="round" opacity=".4"/></svg>`;
const SCHERMEN = [
  {sleutel:"dashboard",    titel:"Dashboard",     groep:"Overzicht",
   bij:"wat vraagt aandacht", uitleg:"Wat er stilstaat en dus opgelost moet worden."},
  {sleutel:"taken",        titel:"Taken",         groep:"Overzicht",
   bij:"werk dat klaarstaat", uitleg:"Eén lijst met alles wat er gedaan moet worden: aanvullen, verplaatsen, tellen."},
  {sleutel:"optimalisatie",titel:"Optimalisatie", groep:"Overzicht",
   bij:"wat beter kan", uitleg:"Waar het magazijn ruimte of tijd verliest, en wat het systeem daaraan doet."},
  {sleutel:"inslag",       titel:"Inslag",        groep:"Inkomend",
   bij:"waar leg ik dit neer", uitleg:"Er komt iets binnen: het systeem rekent uit op welke locatie het past."},
  {sleutel:"meten",        titel:"Opmeten",       groep:"Inkomend",
   bij:"maten bijhouden", uitleg:"Lengte, breedte, hoogte en gewicht van artikelen. Zonder maten kan het systeem niets uitrekenen."},
  {sleutel:"orders",       titel:"Orders",        groep:"Uitgaand",
   bij:"wat er uit moet", uitleg:"Klantorders van binnenkomst tot verzending."},
  {sleutel:"picken",       titel:"Picken",        groep:"Uitgaand",
   bij:"verzamelen voor een order", uitleg:"De looproute langs de locaties om een order bij elkaar te halen."},
  {sleutel:"scan",         titel:"Scanmodus",     groep:"Op de vloer",
   bij:"scherm voor de scanner", uitleg:"Het volledige scherm voor op de werkvloer: scannen, tellen, afmelden."},
  {sleutel:"locaties",     titel:"Locaties",      groep:"Magazijn",
   bij:"de vakken en stellingen", uitleg:"Elke plek in het magazijn, met echte afmetingen en draagvermogen."},
  {sleutel:"artikelen",    titel:"Artikelen",     groep:"Magazijn",
   bij:"de producten zelf", uitleg:"Alle artikelen met hun maten, voorraad en meetgeschiedenis."},
  {sleutel:"eigen",        titel:"Eigen gegevens",groep:"Beheer",
   bij:"bestanden inlezen", uitleg:"Zet de demo om naar de locaties en artikelen van een echte klant."},
  {sleutel:"inloggen",     titel:"Gebruiker",     groep:"Beheer",
   bij:"wie er is ingelogd", uitleg:"Wisselen van medewerker. De rol bepaalt welke schermen je ziet."},
  {sleutel:"instellingen", titel:"Instellingen",  groep:"Beheer",
   bij:"regels per klant", uitleg:"Alles wat per magazijn verschilt, zonder dat er code aangepast hoeft te worden."},
  {sleutel:"demo",         titel:"Rondleiding",   groep:"Demo",
   bij:"drie situaties", uitleg:"De drie voorbeelden die je bij een klant in twee minuten voordoet."},
  {sleutel:"dag",          titel:"Een dag",       groep:"Demo",
   bij:"werkdag afspelen", uitleg:"Speelt een hele werkdag af van 07:00 tot 17:00, met alles wat er misgaat."}
];

/* Pictogrammen: één lijnstijl, 1,6 px, geen vulling. Ze zijn met opzet
   letterlijk. Iemand die nog nooit met een WMS heeft gewerkt moet aan
   het plaatje kunnen zien waar een scherm over gaat - een streepjescode
   is een streepjescode, een stelling is een stelling. Alles is getekend
   om leesbaar te blijven op zeventien pixels: weinig lijnen, duidelijke
   omtrek, geen fijne details die tot een vlek vervagen. */
const I = (d)=>`<svg class="ico" viewBox="0 0 24 24" fill="none"
  stroke="currentColor" stroke-width="1.6" stroke-linecap="round"
  stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const ICONEN = {
  /* meter: hoe staat het ervoor */
  dashboard:   I(`<path d="M3.8 17.5a8.2 8.2 0 1116.4 0"/><path d="M12 17.5l4.4-5.2"/>
                  <circle cx="12" cy="17.5" r="1.4" fill="currentColor" stroke="none"/>`),
  /* klembord met afvinkjes */
  taken:       I(`<rect x="4.5" y="4" width="15" height="17" rx="2.2"/>
                  <rect x="9" y="2" width="6" height="3.4" rx="1.2"/>
                  <path d="M8 12l1.7 1.7L13 10.4"/><path d="M8 17l1.7 1.7L13 15.4"/>`),
  /* stijgende lijn: wat beter kan */
  optimalisatie:I(`<path d="M4 4v16h16"/><path d="M7.5 16.2l3.6-4.4 2.9 2.6 4.5-5.4"/>
                  <path d="M15.4 9h3.1v3.1"/>`),
  /* pijl die een bak in gaat */
  inslag:      I(`<path d="M12 2.8v8.4"/><path d="M8.4 7.8L12 11.4l3.6-3.6"/>
                  <path d="M3.6 12.6v6.2a2.2 2.2 0 002.2 2.2h12.4a2.2 2.2 0 002.2-2.2v-6.2"/>
                  <path d="M3.6 12.6h16.8"/>`),
  /* doos met een maatlijn eronder */
  meten:       I(`<rect x="4" y="4.6" width="16" height="9.8" rx="1.6"/>
                  <path d="M4 19.4h16"/><path d="M6.2 17.6L4 19.4l2.2 1.8"/>
                  <path d="M17.8 17.6L20 19.4l-2.2 1.8"/>`),
  /* orderbon */
  orders:      I(`<path d="M6 2.8h7.6L18.6 8v13.2H6z"/><path d="M13.4 2.8V8h5.2"/>
                  <path d="M9 12.6h6"/><path d="M9 16.6h6"/>`),
  /* uit de stelling halen */
  picken:      I(`<rect x="3" y="4.6" width="10.6" height="14.8" rx="1.6"/>
                  <path d="M3 12h10.6"/><path d="M16.4 12h4.6"/>
                  <path d="M18.6 9.6L21 12l-2.4 2.4"/>`),
  /* streepjescode */
  scan:        I(`<path d="M4 6.4v11.2" stroke-width="1.5"/><path d="M7.4 6.4v11.2" stroke-width="2.6"/>
                  <path d="M10.6 6.4v11.2" stroke-width="1.2"/><path d="M13.4 6.4v11.2" stroke-width="2.4"/>
                  <path d="M16.6 6.4v11.2" stroke-width="1.2"/><path d="M19.8 6.4v11.2" stroke-width="2.2"/>`),
  /* stelling met een doos erin */
  locaties:    I(`<rect x="3" y="4" width="18" height="16" rx="1.6"/>
                  <path d="M3 9.4h18M3 14.8h18"/>
                  <rect x="5.4" y="10.8" width="5" height="3" rx=".7" fill="currentColor" stroke="none" opacity=".65"/>`),
  /* kartonnen doos */
  artikelen:   I(`<path d="M3.6 7.6L12 3.2l8.4 4.4v8.8L12 20.8l-8.4-4.4z"/>
                  <path d="M3.6 7.6L12 12l8.4-4.4"/><path d="M12 12v8.8"/>`),
  /* gegevens die de database in gaan */
  eigen:       I(`<ellipse cx="12" cy="5.6" rx="7.2" ry="2.8"/>
                  <path d="M4.8 5.6v12.8c0 1.55 3.22 2.8 7.2 2.8s7.2-1.25 7.2-2.8V5.6"/>
                  <path d="M12 9.6v6.2"/><path d="M9.6 13.4L12 15.8l2.4-2.4"/>`),
  /* badge met pasfoto */
  inloggen:    I(`<rect x="3.2" y="5" width="17.6" height="14" rx="2.4"/>
                  <circle cx="9.2" cy="10.6" r="2.2"/>
                  <path d="M6 16.4a3.5 3.5 0 016.4 0"/>
                  <path d="M14.8 9.8h3.4M14.8 13.4h2.6"/>`),
  /* schuifregelaars */
  instellingen:I(`<path d="M4 7.6h8.4M17.2 7.6h2.8"/><path d="M4 16.4h2.8M11.6 16.4h8.4"/>
                  <circle cx="14.8" cy="7.6" r="2.4"/><circle cx="9.2" cy="16.4" r="2.4"/>`),
  /* afspelen */
  demo:        I(`<circle cx="12" cy="12" r="8.6"/><path d="M10.2 8.6l5.6 3.4-5.6 3.4z"/>`),
  /* klok */
  dag:         I(`<circle cx="12" cy="12" r="8.6"/><path d="M12 6.8v5.4l3.4 2.1"/>`)
};

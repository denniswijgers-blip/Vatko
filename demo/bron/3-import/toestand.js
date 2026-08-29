/* =====================================================================
   DE STAND VAN DE IMPORT

   Waar de wizard is, welke bestanden er liggen, welke kolommen op
   welk veld zijn gelegd en in welke eenheid de klant werkt. Eén object,
   zodat het scherm en de controle naar hetzelfde kijken.
   ===================================================================== */

/* =====================================================================
   EIGEN GEGEVENS INLEZEN

   Dit scherm is het verschil tussen "kijk eens wat een mooie demo" en
   "kijk, dit is jouw magazijn". Drie situaties komen in de praktijk voor:

     A. De klant heeft bestanden. Excel of CSV, uit het ERP getrokken.
        Nooit met de kolomnamen die jij zou kiezen. Dus herkennen we ze
        zelf en laten we de klant bevestigen.

     B. De klant heeft locaties, maar geen bestand. Alles staat in de
        stelling, niemand heeft het ooit vastgelegd. Dan bouwen we de
        structuur hier op en drukken we de etiketten af.

     C. De klant heeft helemaal niets. Geen locaties, geen voorraadlijst.
        De mensen weten waar het ligt. Dan beginnen we met een nulmeting:
        stellingen labelen, en met de scanner het magazijn in.

   In alle drie de gevallen eindigen we met dezelfde datastructuur als de
   demo. Vanaf dat punt is er geen verschil meer.
   ===================================================================== */

const imp = {
  stap:"keuze", bron:null, bedrijf:"",
  bestanden:{locaties:null, artikelen:null, voorraad:null},
  kolom:{locaties:{}, artikelen:{}, voorraad:{}},
  eenheid:{loc_maat:"mm", art_maat:"mm", loc_gew:"kg", art_gew:"g"},
  standaard:{L:600,W:400,H:350,maxG:50},
  rapport:null, bezig:false, fout:null,
  opzet:[
    {code:"KG", naam:"Kleingoed",     soort:"PL", gangen:4, vakken:20, niveaus:5, L:300,  W:400, H:220,  maxG:12},
    {code:"MV", naam:"Middenvakken",  soort:"PL", gangen:3, vakken:18, niveaus:4, L:600,  W:400, H:350,  maxG:45},
    {code:"PS", naam:"Palletstelling",soort:"BL", gangen:3, vakken:16, niveaus:4, L:1200, W:800, H:1500, maxG:900}
  ]
};

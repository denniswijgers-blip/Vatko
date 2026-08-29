/* =====================================================================
   CONTROLEREN
   Het rapport is belangrijker dan de import zelf. Een klant die ziet
   dat er 41 artikelen zonder maat zijn, snapt meteen waarom de eerste
   week meten is. Een import die stilletjes doorgaat, wreekt zich later.
   ===================================================================== */
function nieuwProbleem(lijst, sleutel, tekst, ernst="let"){
  let p = lijst.find(x=>x.sleutel===sleutel);
  if(!p) lijst.push(p = {sleutel, tekst, ernst, n:0, voorbeeld:[]});
  return p;
}
function noteer(lijst, sleutel, tekst, voorbeeld, ernst="let"){
  const p = nieuwProbleem(lijst, sleutel, tekst, ernst);
  p.n++;
  if(p.voorbeeld.length < 3) p.voorbeeld.push(voorbeeld);
}

function controleer(){
  const R = {locaties:{rijen:0, goed:0, problemen:[]},
             artikelen:{rijen:0, goed:0, problemen:[]},
             voorraad:{rijen:0, goed:0, problemen:[]},
             locNaam:new Map(), artNaam:new Map(), klaar:false};

  /* --- locaties ---------------------------------------------------- */
  const B = imp.bestanden.locaties, K = imp.kolom.locaties;
  const fLoc = naarMm[imp.eenheid.loc_maat], fLocG = naarG[imp.eenheid.loc_gew];
  if(B){
    R.locaties.rijen = B.rijen.length;
    for(const r of B.rijen){
      const code = (r[K.code] || "").trim();
      if(!code){ noteer(R.locaties.problemen,"geencode","Rij zonder locatiecode; wordt overgeslagen","(lege rij)","fout"); continue; }
      if(R.locNaam.has(code.toUpperCase())){
        noteer(R.locaties.problemen,"dubbel","Locatiecode komt meer dan één keer voor; alleen de eerste telt",code,"fout"); continue;
      }
      const L = getal(r[K.L]) * fLoc, W = getal(r[K.W]) * fLoc, H = getal(r[K.H]) * fLoc;
      const mg = getal(r[K.maxG]);
      const zonder = !(L>0 && W>0 && H>0);
      if(zonder) noteer(R.locaties.problemen,"geenmaat",
        "Locatie zonder afmetingen; krijgt de standaardmaat die je hieronder invult", code);
      if(!(mg>0)) noteer(R.locaties.problemen,"geengewicht",
        "Locatie zonder maximaal gewicht; krijgt het standaardgewicht", code);
      R.locNaam.set(code.toUpperCase(), {
        code, zone:(r[K.zone]||"").trim(), soort:(r[K.soort]||"").trim(),
        L: zonder ? imp.standaard.L : Math.round(L),
        W: zonder ? imp.standaard.W : Math.round(W),
        H: zonder ? imp.standaard.H : Math.round(H),
        maxG: mg>0 ? Math.round(mg*fLocG) : imp.standaard.maxG*1000,
        geschat: zonder
      });
      R.locaties.goed++;
    }
  }

  /* --- artikelen ---------------------------------------------------- */
  const A = imp.bestanden.artikelen, KA = imp.kolom.artikelen;
  const fArt = naarMm[imp.eenheid.art_maat], fArtG = naarG[imp.eenheid.art_gew];
  if(A){
    R.artikelen.rijen = A.rijen.length;
    for(const r of A.rijen){
      const sku = (r[KA.sku] || "").trim();
      if(!sku){ noteer(R.artikelen.problemen,"geensku","Rij zonder artikelnummer; wordt overgeslagen","(lege rij)","fout"); continue; }
      if(R.artNaam.has(sku.toUpperCase())){
        noteer(R.artikelen.problemen,"dubbel","Artikelnummer komt meer dan één keer voor; alleen de eerste telt",sku,"fout"); continue;
      }
      const L = getal(r[KA.L])*fArt, W = getal(r[KA.W])*fArt,
            H = getal(r[KA.H])*fArt, G = getal(r[KA.G])*fArtG;
      const gemeten = L>0 && W>0 && H>0 && G>0;
      if(!gemeten) noteer(R.artikelen.problemen,"nietgemeten",
        "Artikel zonder complete maat of gewicht; komt op de lijst 'nog opmeten'", sku);
      R.artNaam.set(sku.toUpperCase(), {
        sku, oms:(r[KA.oms]||"").trim() || sku,
        groep:(r[KA.groep]||"").trim() || "Overig",
        L:gemeten?Math.round(L):null, W:gemeten?Math.round(W):null,
        H:gemeten?Math.round(H):null, G:gemeten?Math.round(G):null,
        barcode:(r[KA.barcode]||"").trim() || null,
        min: getal(r[KA.min]) || null, max: getal(r[KA.max]) || null
      });
      R.artikelen.goed++;
    }
  }

  /* --- voorraad ----------------------------------------------------- */
  const V = imp.bestanden.voorraad, KV = imp.kolom.voorraad;
  R.voorraadRijen = [];
  if(V){
    R.voorraad.rijen = V.rijen.length;
    for(const r of V.rijen){
      const sku = (r[KV.sku]||"").trim().toUpperCase();
      const loc = (r[KV.locatie]||"").trim().toUpperCase();
      const q = getal(r[KV.qty]);
      if(!sku || !loc){ noteer(R.voorraad.problemen,"leeg","Rij zonder artikel of locatie","(lege rij)","fout"); continue; }
      if(!R.artNaam.has(sku)){ noteer(R.voorraad.problemen,"onbekendart",
        "Voorraad op een artikel dat niet in het artikelbestand staat", sku, "fout"); continue; }
      if(!R.locNaam.has(loc)){ noteer(R.voorraad.problemen,"onbekendloc",
        "Voorraad op een locatie die niet in het locatiebestand staat", loc, "fout"); continue; }
      if(!(q>0)){ noteer(R.voorraad.problemen,"nul","Regel met nul of geen aantal; overgeslagen", sku); continue; }
      R.voorraadRijen.push({sku, loc, qty:Math.round(q)});
      R.voorraad.goed++;
    }
  }

  R.klaar = R.locaties.goed > 0;
  imp.rapport = R;
  return R;
}

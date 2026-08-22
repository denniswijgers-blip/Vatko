/* =====================================================================
   EEN GETAL UIT EEN CEL

   Een klantbestand is geen rekenblad. Er staat "12,5 kg", "1.200" of
   "n.v.t." in een kolom waar een getal hoort. Dit is de enige plek waar
   dat wordt rechtgetrokken (R-IMP-04).
   ===================================================================== */

/* --- getal uit een cel, met Nederlandse komma en rommel ------------- */
function getal(v){
  if(v===null || v===undefined) return null;
  if(typeof v==="number") return isFinite(v)?v:null;
  let s = String(v).trim();
  if(!s) return null;
  s = s.replace(/[^0-9,.\-]/g,"");
  if(!s || s==="-") return null;
  if(s.includes(",") && s.includes(".")){
    s = s.lastIndexOf(",") > s.lastIndexOf(".")
      ? s.replace(/\./g,"").replace(",",".")
      : s.replace(/,/g,"");
  } else if(s.includes(",")) s = s.replace(",",".");
  const n = parseFloat(s);
  return isFinite(n) ? n : null;
}

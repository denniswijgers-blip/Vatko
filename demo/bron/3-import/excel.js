/* =====================================================================
   EXCEL (.xlsx)
   Een xlsx-bestand is een zip met XML erin. De browser kan sinds kort
   zelf uitpakken (DecompressionStream), dus dit kan zonder externe
   bibliotheek - wat belangrijk is, want dit bestand moet offline werken
   in een magazijn zonder wifi.
   ===================================================================== */
async function leesZip(buf){
  const dv = new DataView(buf), u8 = new Uint8Array(buf);
  let eocd = -1;
  for(let i=u8.length-22; i>=0 && i>u8.length-66000; i--){
    if(dv.getUint32(i,true) === 0x06054b50){ eocd = i; break; }
  }
  if(eocd < 0) throw new Error("Dit lijkt geen geldig xlsx-bestand. Sla het in Excel op als 'Excel-werkmap (.xlsx)' of als CSV.");
  const aantal = dv.getUint16(eocd+10, true);
  let p = dv.getUint32(eocd+16, true);
  const uit = {};
  const dec = new TextDecoder();
  for(let i=0;i<aantal;i++){
    if(dv.getUint32(p,true) !== 0x02014b50) break;
    const methode = dv.getUint16(p+10,true);
    const compLen = dv.getUint32(p+20,true);
    const nLen = dv.getUint16(p+28,true);
    const eLen = dv.getUint16(p+30,true);
    const cLen = dv.getUint16(p+32,true);
    const lok  = dv.getUint32(p+42,true);
    const naam = dec.decode(u8.subarray(p+46, p+46+nLen));
    const lnLen = dv.getUint16(lok+26,true), leLen = dv.getUint16(lok+28,true);
    const start = lok+30+lnLen+leLen;
    uit[naam] = {methode, data: u8.subarray(start, start+compLen)};
    p += 46+nLen+eLen+cLen;
  }
  return uit;
}
async function uitpakken(item){
  if(!item) return null;
  if(item.methode === 0) return new TextDecoder().decode(item.data);
  if(typeof DecompressionStream === "undefined")
    throw new Error("Deze browser kan geen xlsx uitpakken. Gebruik Chrome of Edge, of sla het bestand op als CSV.");
  const stroom = new Blob([item.data]).stream()
    .pipeThrough(new DecompressionStream("deflate-raw"));
  return await new Response(stroom).text();
}
const kolomIndex = (ref)=>{
  const m = /^([A-Z]+)/.exec(ref||"");
  if(!m) return 0;
  let n = 0;
  for(const c of m[1]) n = n*26 + (c.charCodeAt(0)-64);
  return n-1;
};

async function leesXlsx(buf){
  const zip = await leesZip(buf);
  const P = new DOMParser();
  const tekst = [];
  const ssXml = await uitpakken(zip["xl/sharedStrings.xml"]);
  if(ssXml){
    const d = P.parseFromString(ssXml, "application/xml");
    for(const si of d.getElementsByTagName("si")){
      let s = "";
      for(const t of si.getElementsByTagName("t")){
        if(t.parentNode && t.parentNode.nodeName === "rPh") continue;
        s += t.textContent;
      }
      tekst.push(s);
    }
  }
  const blad = Object.keys(zip)
    .filter(k=>/^xl\/worksheets\/sheet\d*\.xml$/.test(k))
    .sort((a,b)=>a.length-b.length || a.localeCompare(b))[0];
  if(!blad) throw new Error("Geen werkblad gevonden in dit bestand.");
  const d = P.parseFromString(await uitpakken(zip[blad]), "application/xml");
  const rijen = [];
  for(const r of d.getElementsByTagName("row")){
    const rij = [];
    for(const c of r.getElementsByTagName("c")){
      const i = kolomIndex(c.getAttribute("r"));
      const t = c.getAttribute("t");
      let w = "";
      if(t === "s"){
        const v = c.getElementsByTagName("v")[0];
        w = v ? (tekst[+v.textContent] ?? "") : "";
      } else if(t === "inlineStr"){
        const ts = c.getElementsByTagName("t");
        w = ts.length ? ts[0].textContent : "";
      } else {
        const v = c.getElementsByTagName("v")[0];
        w = v ? v.textContent : "";
      }
      rij[i] = w;
    }
    for(let i=0;i<rij.length;i++) if(rij[i]===undefined) rij[i]="";
    rijen.push(rij);
  }
  return rijen.filter(r=>r.some(c=>String(c).trim()!==""));
}

/* --- één bestand inlezen, ongeacht het soort ------------------------ */
async function leesBestand(file){
  const naam = file.name.toLowerCase();
  let rijen;
  if(naam.endsWith(".xlsx") || naam.endsWith(".xlsm")){
    rijen = await leesXlsx(await file.arrayBuffer());
  } else if(naam.endsWith(".xls")){
    throw new Error("Het oude .xls-formaat kan ik niet lezen. Open het in Excel en sla het op als .xlsx of .csv.");
  } else {
    rijen = leesCsv(await file.text());
  }
  if(rijen.length < 2) throw new Error("Dit bestand heeft geen gegevensregels onder de kopregel.");
  const breedte = Math.max(...rijen.map(r=>r.length));
  const kop = [];
  for(let i=0;i<breedte;i++) kop.push(String(rijen[0][i] ?? "").trim() || `kolom ${i+1}`);
  return {naam:file.name, kop, rijen: rijen.slice(1).map(r=>{
    const uit = [];
    for(let i=0;i<breedte;i++) uit.push(String(r[i] ?? "").trim());
    return uit;
  })};
}

/* =====================================================================
   CSV
   Scheidingsteken raden we: een Nederlandse Excel-export gebruikt de
   puntkomma, een Engelse de komma. Fout raden betekent één kolom met
   alles erin, en dat is precies waar mensen op vastlopen.
   ===================================================================== */
function raadScheiding(regel){
  const kandidaten = [";", ",", "\t", "|"];
  let beste = ";", max = 0;
  for(const c of kandidaten){
    let n = 0, inAanhaling = false;
    for(let i=0;i<regel.length;i++){
      if(regel[i]==='"') inAanhaling = !inAanhaling;
      else if(regel[i]===c && !inAanhaling) n++;
    }
    if(n>max){ max=n; beste=c; }
  }
  return beste;
}

function leesCsv(tekst){
  if(tekst.charCodeAt(0)===0xFEFF) tekst = tekst.slice(1);
  const eersteRegel = tekst.split(/\r?\n/).find(r=>r.trim()) || "";
  const sep = raadScheiding(eersteRegel);
  const rijen = [];
  let rij = [], veld = "", inAanhaling = false;
  for(let i=0;i<tekst.length;i++){
    const c = tekst[i];
    if(inAanhaling){
      if(c === '"'){
        if(tekst[i+1] === '"'){ veld += '"'; i++; }
        else inAanhaling = false;
      } else veld += c;
    } else if(c === '"') inAanhaling = true;
    else if(c === sep){ rij.push(veld); veld = ""; }
    else if(c === "\n"){ rij.push(veld); rijen.push(rij); rij = []; veld = ""; }
    else if(c === "\r"){ /* overslaan */ }
    else veld += c;
  }
  if(veld || rij.length){ rij.push(veld); rijen.push(rij); }
  return rijen.filter(r=>r.some(c=>String(c).trim()!==""));
}

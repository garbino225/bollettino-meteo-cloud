/* Generic renderer for the multi-model comparison table.
   Consumes window.TABLE_DATA (built by build_comparison_table.py from real
   Open-Meteo data) — no synthetic generation here, only display logic. */

function classify(param, v){
  if(v===null || v===undefined || Number.isNaN(v)) return null;
  switch(param){
    case "temp": case "tmax": return v<28?0 : v<=31?1 : v<=33?2 : v<=36?3 : 4;
    case "tmin": return v<20?0 : v<=24?1 : v<=27?2 : v<=30?3 : 4;
    case "pressione": return v>=1013?0 : v>=1008?1 : v>=1003?2 : v>=998?3 : 4;
    case "umidita": return v<60?0 : v<=70?1 : v<=80?2 : v<=90?3 : 4;
    case "vento": return v<11?0 : v<=21?1 : v<=32?2 : v<=48?3 : 4;
    case "copertura": return v<20?0 : v<=50?1 : v<=80?2 : v<=95?3 : 4;
    case "pioggia": return v<=10?0 : v<=40?1 : v<=70?2 : v<=90?3 : 4;
    case "pioggia_mm": return v<0.5?0 : v<=2?1 : v<=6?2 : v<=15?3 : 4;
    case "pioggia_mm_daily": return v<=1?0 : v<=10?1 : v<=30?2 : v<=60?3 : 4;
    case "ondoso": return v<0.3?0 : v<=0.6?1 : v<=1.0?2 : v<=1.5?3 : 4;
    case "basenubi": return v<0.3?4 : v<=0.6?3 : v<=1.5?2 : v<=3.0?1 : 0;
  }
  return null;
}

function fmt(v, decimals){
  if(v===null || v===undefined || Number.isNaN(v)) return "—";
  return decimals>0 ? v.toFixed(decimals) : Math.round(v).toString();
}
function mean(arr){ const a = arr.filter(v=>v!==null && v!==undefined && !Number.isNaN(v)); return a.length ? a.reduce((s,v)=>s+v,0)/a.length : null; }

const D = window.TABLE_DATA;
const nCols = D.timeCols.length;
document.documentElement.style.setProperty('--ncols', nCols);

function dsc(i){
  if(D.mode!=="hourly") return "";
  return (D.timeCols[i].hod===0 && i>0) ? " day-start" : "";
}

// --- masthead / meta ---
document.getElementById("mh-eyebrow").textContent = D.meta.eyebrow;
document.getElementById("mh-title").innerHTML = D.meta.titleHtml;
document.getElementById("mh-sub").innerHTML = D.meta.subHtml;
document.getElementById("mh-version").textContent = D.meta.version;
document.getElementById("mh-meta-strip").innerHTML = D.meta.metaStripHtml;

// --- almanac ---
const almanacHead = D.dayLabels.map(d=>`<div class="cell colhead"><span class="day">${d}</span></div>`).join("");
document.getElementById("almanacGrid").style.gridTemplateColumns = `150px repeat(${D.dayLabels.length},1fr)`;
document.getElementById("almanacGrid").innerHTML = `
  <div class="cell rowlabel" style="font-weight:700;">Giorno</div>
  ${almanacHead}
  <div class="cell rowlabel">Alba</div>
  ${D.almanac.alba.map(t=>`<div class="cell time-cell">${t||"—"}</div>`).join("")}
  <div class="cell rowlabel">Tramonto</div>
  ${D.almanac.tramonto.map(t=>`<div class="cell time-cell">${t||"—"}</div>`).join("")}
  <div class="cell rowlabel" style="border-bottom:none;">Fase lunare</div>
  ${D.almanac.luna.map(l=>`<div class="cell moon-cell" style="border-bottom:none;">
      <span class="moonpct">${l.pct}%</span>
      <span class="spread-track"><span class="spread-fill" style="width:${l.pct}%"></span></span>
      <span class="moonlabel">${l.label}</span>
    </div>`).join("")}
`;

// --- models key (toolbar) ---
const allModels = D.modelsMeta.concat(D.waveModelsMeta||[]);
document.getElementById("modelsKey").innerHTML = allModels.map(m=>`<span class="mk" title="${m.full}"><b>${m.code}</b></span>`).join("");

const sections = document.getElementById("sections");

function buildTrendSVG(p){
  const codes = p.modelCodes;
  const allVals = [];
  for(const c of codes){ for(const v of p.values[c]){ if(v!==null && v!==undefined) allVals.push(v); } }
  if(!allVals.length) return "";
  let lo = Math.min(...allVals), hi = Math.max(...allVals);
  const pad = (hi-lo)*0.18 || 1;
  lo -= pad; hi += pad;
  const n = nCols;
  const x = i => (n>1) ? (i/(n-1))*700 : 350;
  const y = v => 90 - ((v-lo)/(hi-lo))*76;

  const modelLines = codes.map(c=>{
    const pts = [];
    p.values[c].forEach((v,i)=>{ if(v!==null && v!==undefined) pts.push(`${x(i).toFixed(1)},${y(v).toFixed(1)}`); });
    if(pts.length<2) return "";
    return `<polyline points="${pts.join(" ")}" fill="none" stroke="var(--ink-faint)" stroke-width="1" opacity="0.28" stroke-linejoin="round" stroke-linecap="round" />`;
  }).join("");

  const meanPts = [];
  for(let i=0;i<n;i++){
    const v = mean(codes.map(c=>p.values[c][i]));
    if(v!==null) meanPts.push(`${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  }
  const meanLine = meanPts.join(" ");
  const areaPts = meanPts.length ? `${meanPts[0].split(",")[0]},96 ${meanLine} ${meanPts[meanPts.length-1].split(",")[0]},96` : "";

  return `<svg viewBox="0 0 700 100" preserveAspectRatio="none">
      ${areaPts ? `<polygon points="${areaPts}" fill="var(--accent)" opacity="0.08" />` : ""}
      ${modelLines}
      <polyline points="${meanLine}" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
    </svg>`;
}

D.params.forEach(p=>{
  const codes = p.modelCodes;
  const trendSvg = buildTrendSVG(p);

  const dayColsCells = D.timeCols.map((tc,i)=>{
    const vals = codes.map(c=>p.values[c][i]);
    const present = vals.filter(v=>v!==null && v!==undefined);
    const avg = present.length ? present.reduce((a,b)=>a+b,0)/present.length : null;
    const sev = classify(p.classifyAs||p.key, avg);
    const dir = (p.hasDirection && p.dirValues && p.dirValues[i]!=null) ? `<span class="dir">${p.dirValues[i]}</span>` : "";
    let gustHtml = "";
    if(p.hasGust && p.gustValues){
      const gv = codes.map(c=>p.gustValues[c] ? p.gustValues[c][i] : null);
      const gp = gv.filter(v=>v!==null && v!==undefined);
      const gavg = gp.length ? gp.reduce((a,b)=>a+b,0)/gp.length : null;
      const gsev = classify(p.classifyAs||p.key, gavg);
      gustHtml = gavg!==null ? `<span class="gust-pill sev-${gsev}" title="Raffica">R${fmt(gavg,p.decimals)}</span>` : "";
    }
    return `<div class="cell consensus-cell${dsc(i)}" style="grid-column:${2+i};grid-row:1;">
        <span class="cval ${sev!==null?'sev-'+sev:''}">${fmt(avg,p.decimals)}${dir}</span>
        ${gustHtml}
      </div>`;
  }).join("");

  let prevGroup = null;
  const modelRows = codes.map(code=>{
    const meta = allModels.find(m=>m.code===code) || {code, group:null};
    const cells = D.timeCols.map((tc,i)=>{
      const v = p.values[code][i];
      if(v===null || v===undefined) return `<div class="cell na${dsc(i)}">—</div>`;
      const sev = classify(p.classifyAs||p.key, v);
      return `<div class="cell sev-${sev}${dsc(i)}">${fmt(v,p.decimals)}</div>`;
    }).join("");
    const divider = (meta.group && meta.group !== prevGroup && codes.length>4)
      ? `<div style="display:contents"><div class="cell group-label" style="grid-column:1/-1;">Modelli ${meta.group === "globale" ? "globali" : "locali (area limitata)"}</div></div>`
      : "";
    prevGroup = meta.group;
    return `${divider}<div class="model-row" style="display:contents">
        <div class="cell rowlabel">${code}</div>
        ${cells}
      </div>`;
  }).join("");

  const headCells = D.timeCols.map((tc,i)=>{
    if(D.mode==="hourly"){
      return `<div class="cell colhead${dsc(i)}">${tc.hod===0 ? `<span class="daytag">${D.dayLabels[tc.dayIndex]}</span>` : ""}<span class="day">${String(tc.hod).padStart(2,'0')}</span></div>`;
    }
    return `<div class="cell colhead"><span class="day">${tc.d}</span><span class="date">${tc.date}</span></div>`;
  }).join("");

  const excluded = p.excludedModels && p.excludedModels.length
    ? `<span class="warn" title="${p.excludedModels.map(e=>e.code+': '+e.reason).join(' · ')}">${p.excludedModels.length} modell${p.excludedModels.length===1?'o':'i'} escluso${p.excludedModels.length===1?'':'i'}</span>` : "";

  const section = document.createElement("details");
  section.className = "param";
  section.open = !!p.openDefault;
  section.innerHTML = `
    <summary><span class="arrow">&#9656;</span> ${p.label} <span class="unit">${p.unit}</span>${excluded}<span class="desc">${p.threshTxt}</span></summary>
    <div class="table-wrap">
      <div class="pgrid ${D.mode==='hourly'?'hourly':''}">
        <div class="cell rowlabel" style="font-weight:700;">${D.mode==='hourly'?'Ora':'Giorno'}</div>
        ${headCells}
        <div class="consensus-row ${D.mode==='hourly'?'hourly':''}">
          <div class="cell rowlabel" style="grid-column:1;grid-row:1;">Media modelli</div>
          <div class="consensus-svg" style="grid-column:2/-1;grid-row:1;">${trendSvg}</div>
          ${dayColsCells}
        </div>
        ${modelRows}
      </div>
    </div>`;
  sections.appendChild(section);
});

document.getElementById("notesHtml").innerHTML = D.notesHtml;

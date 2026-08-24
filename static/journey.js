const colors=['#a846c5','#ffb000','#18a8d8','#239a58','#3767e8','#ef6b62','#7e57c2','#20a39e'];
const $=s=>document.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
const pct=(n,d)=>d?`${(n*100/d).toFixed(1)}%`:'0%';
async function requestJson(url){const r=await fetch(url),text=await r.text();let body;try{body=text?JSON.parse(text):null}catch{body=null}if(!r.ok)throw new Error(body?.detail||text||`Falha HTTP ${r.status}`);if(body===null)throw new Error('O servidor retornou uma resposta inválida.');return body}

async function loadFilters(){
  const [batches,products]=await Promise.all([requestJson('/api/v1/batches'),requestJson('/api/v1/products')]);
  $('#batch-filter').insertAdjacentHTML('beforeend',batches.map(b=>`<option value="${esc(b.id)}">${esc(b.name)} · ${b.processed_files}</option>`).join(''));
  $('#product-filter').insertAdjacentHTML('beforeend',products.map(p=>`<option value="${esc(p.product)}">${esc(p.product)} · ${p.interactions}</option>`).join(''));
}

function renderFunnel(data){
  const svg=$('#funnel'), W=620,H=320,gap=3, top=570,bottom=220,stageH=(H-gap*(data.length-1))/data.length;
  svg.setAttribute('viewBox',`0 0 ${W} ${H}`); svg.innerHTML='';
  data.forEach((stage,i)=>{
    const y=i*(stageH+gap), w1=top-(top-bottom)*(i/data.length), w2=top-(top-bottom)*((i+1)/data.length), x1=(W-w1)/2,x2=(W-w2)/2;
    const path=document.createElementNS('http://www.w3.org/2000/svg','path');
    path.setAttribute('d',`M${x1},${y} H${x1+w1} L${x2+w2},${y+stageH} H${x2} Z`);path.setAttribute('fill',colors[i]);path.setAttribute('class','funnel-piece');
    path.addEventListener('click',()=>document.querySelector(`[data-stage="${stage.key}"]`)?.scrollIntoView({behavior:'smooth'}));svg.appendChild(path);
    const label=document.createElementNS('http://www.w3.org/2000/svg','text');label.setAttribute('x',W/2);label.setAttribute('y',y+stageH/2-3);label.setAttribute('class','funnel-label');label.textContent=stage.label;svg.appendChild(label);
    const count=document.createElementNS('http://www.w3.org/2000/svg','text');count.setAttribute('x',W/2);count.setAttribute('y',y+stageH/2+17);count.setAttribute('class','funnel-count');count.textContent=`${stage.count} atendimentos`;svg.appendChild(count);
  });
  $('#funnel-legend').innerHTML=data.map((s,i)=>`<div class="funnel-legend-item"><span class="legend-dot" style="background:${colors[i]}"></span><div><strong>${esc(s.label)}</strong><small>${pct(s.count,data[0]?.count)} da base alcança este nível</small></div><b>${s.count}</b></div>`).join('');
}

function renderRank(items){
  $('#presented-list').innerHTML=items.length?items.map((x,i)=>`<div class="rank-item"><span class="rank-number">${i+1}</span><span class="rank-label">${esc(x.label)}</span><span class="rank-meta"><strong>${x.count}</strong><span>${x.share}%</span></span></div>`).join(''):'<p>Nenhuma causa categorizada.</p>';
}

function renderProducts(items,total){
  let angle=0;const stops=[];items.forEach((x,i)=>{const next=angle+(x.count/(total||1))*360;stops.push(`${colors[i%colors.length]} ${angle}deg ${next}deg`);angle=next});
  $('#product-donut').style.background=items.length?`conic-gradient(${stops.join(',')})`:'#edf1f6';$('#donut-total').textContent=total;
  $('#product-legend').innerHTML=items.map((x,i)=>`<div class="donut-legend-item"><span class="legend-dot" style="background:${colors[i%colors.length]}"></span><span>${esc(x.label)}</span><strong>${x.count}</strong></div>`).join('');
}

function renderBars(items){
  const max=Math.max(1,...items.map(x=>x.count));$('#responsibility-bars').innerHTML=items.map(x=>`<div class="bar-row"><label>${esc(x.label)}</label><div class="bar-track"><div class="bar-fill" style="width:${x.count*100/max}%"></div></div><span class="bar-value">${x.count} · ${x.share}%</span></div>`).join('');
}

function renderPaths(items){
  $('#path-count').textContent=`${items.length} trilhas exibidas`;$('#path-rows').innerHTML=items.map(x=>`<tr onclick="location.href='/reports/${encodeURIComponent(x.id)}'"><td><strong>${esc(x.product)}</strong><br><small>${esc(x.filename)}</small></td><td class="voice-cell">“${esc(x.voice)}”<br><small>${esc((x.causal_evidence||[]).slice(0,2).join(' · '))}</small></td><td>${esc(x.motivating)}</td><td>${esc(x.journey_stage)}<br><small>${esc(x.friction)}</small></td><td>${esc(x.root)}<br><span class="root-confidence">${esc(x.root_confidence)} · ${Math.round((x.causal_confidence||0)*100)}%</span></td></tr>`).join('');
}

async function loadDashboard(){
  const params=new URLSearchParams();if($('#batch-filter').value)params.set('batch_id',$('#batch-filter').value);if($('#product-filter').value)params.set('product',$('#product-filter').value);
  const data=await requestJson(`/api/v1/journey?${params}`);
  $('#metric-total').textContent=data.total;$('#metric-experience').textContent=data.metrics.avg_experience;$('#metric-friction').textContent=data.metrics.friction;$('#metric-friction-share').textContent=`${pct(data.metrics.friction,data.total)} da base`;$('#metric-root').textContent=data.metrics.root_specific;
  renderFunnel(data.funnel);renderRank(data.stages.presented);renderProducts(data.products,data.total);renderBars(data.stages.responsibility);renderPaths(data.paths);
  $('#journey-empty').hidden=data.total!==0;
}

$('#batch-filter').addEventListener('change',loadDashboard);$('#product-filter').addEventListener('change',loadDashboard);
loadFilters().then(loadDashboard).catch(err=>{console.error(err);$('#journey-empty').hidden=false;$('#journey-empty').textContent='Não foi possível carregar o painel.'});

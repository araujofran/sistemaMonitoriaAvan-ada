const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
let DATA = null, CURRENT_PARAMS = new URLSearchParams();

async function requestData(params = new URLSearchParams()) {
  const response = await fetch(`/api/v1/explainability?${params}`);
  const type = response.headers.get('content-type') || '';
  const result = type.includes('application/json') ? await response.json() : {};
  if (!response.ok) throw new Error(result.detail || 'Não foi possível carregar a explicabilidade.');
  return result;
}

function renderKpis() {
  const summary = DATA.summary, official = summary.official, simulated = summary.simulated;
  $('#kpis').innerHTML = `
    <article class="kpi"><small>Atendimentos</small><strong>${summary.total}</strong><span>Política oficial: ${DATA.methodology.active_policy === 'hybrid' ? 'Híbrida' : 'Rígida'} · ${esc(DATA.methodology.active_version)}</span></article>
    <article class="kpi warning"><small>Zerados oficialmente</small><strong>${official.zeros}</strong><span>${official.zero_share}% da base</span></article>
    <article class="kpi"><small>Média oficial</small><strong>${official.average}</strong><span>Mediana ${official.median}</span></article>
    <article class="kpi success"><small>Zerados na simulação</small><strong>${simulated.zeros}</strong><span>${simulated.zero_share}% da base</span></article>
    <article class="kpi success"><small>Liberados pelo híbrido</small><strong>${summary.released_by_hybrid}</strong><span>NLP processado: ${summary.nlp_processed}</span></article>`;
  $('#impact-copy').innerHTML = `Na política atual, <b>${official.zeros}</b> atendimento(s) estão zerados. Na simulação híbrida, <b>${summary.released_by_hybrid}</b> deixam de zerar porque a ausência de uma expressão Regex não é tratada isoladamente como prova de falha crítica.`;
}

function renderDistribution() {
  const bands = ['0','1–49','50–69','70–84','85–99','100'];
  const maximum = Math.max(1, ...bands.flatMap(band => [DATA.distributions.official[band] || 0, DATA.distributions.simulated[band] || 0]));
  $('#distribution').innerHTML = bands.map(band => {
    const official = DATA.distributions.official[band] || 0, simulated = DATA.distributions.simulated[band] || 0;
    return `<div class="band"><span>${band}</span><div class="bars"><div class="track"><div class="fill" style="width:${official * 100 / maximum}%"></div></div><div class="track"><div class="fill sim" style="width:${simulated * 100 / maximum}%"></div></div></div><b>${official} / ${simulated}</b></div>`;
  }).join('');
}

function renderCriteria() {
  $('#criteria').innerHTML = DATA.criteria.map(item => `<tr class="criterion-row" data-code="${esc(item.code)}" title="Clique para listar os atendimentos">
    <td><b>${esc(item.label)}</b><br><code>${esc(item.code)}</code></td><td><b>${item.count}</b><br><small>${item.share}% da base</small></td>
    <td>${esc(item.current)}</td><td><span class="pill ${esc(item.kind)}">${item.kind === 'absence' ? 'Ausência de padrão' : item.kind === 'explicit' ? 'Evidência explícita' : 'Revisão'}</span></td>
    <td>Zera atendimento</td><td><b>${esc(item.hybrid)}</b></td></tr>`).join('');
  const select = $('#criterion'), current = select.value;
  select.innerHTML = '<option value="">Todas</option>' + DATA.criteria.map(item => `<option value="${esc(item.code)}">${esc(item.label)} · ${item.count}</option>`).join('');
  select.value = current;
  document.querySelectorAll('.criterion-row').forEach(row => row.onclick = () => {
    $('#criterion').value = row.dataset.code;
    const params = new URLSearchParams(); params.set('criterion', row.dataset.code); load(params);
    document.querySelector('#interactions').scrollIntoView({behavior:'smooth'});
  });
}

function statusLabel(item) {
  if (item.hybrid_zero) return '<span class="pill explicit">Mantém zero</span>';
  if (item.official_zero) return '<span class="pill absence">Liberado na simulação</span>';
  return '<span class="pill">Sem zeramento</span>';
}

function renderInteractions() {
  $('#result-count').textContent = `${DATA.result_count} resultado(s) · exibindo até ${DATA.interactions.length}`;
  $('#interactions').innerHTML = DATA.interactions.map((item, index) => `<article class="interaction" data-index="${index}"><div><b>${esc(item.filename)}</b><br><small>${esc(item.operator)} · ${esc(item.product)} · ${esc(item.analysis_date || 'Data não informada')}</small></div><div class="metric"><span>NOTA OFICIAL</span><b class="${item.official_zero ? 'zero' : ''}">${item.official_score}</b></div><div class="metric"><span>SIMULADA</span><b class="${!item.hybrid_zero && item.official_zero ? 'released' : ''}">${item.simulated_score}</b></div><div>${statusLabel(item)}</div><div><b>${item.triggers.length}</b><br><small>inaderência(s)</small></div></article>`).join('') || '<div class="empty">Nenhum atendimento corresponde aos filtros.</div>';
  if (DATA.result_count) $('#interactions').insertAdjacentHTML('beforeend', `<div class="pager"><button id="page-prev" ${DATA.pagination.has_previous?'':'disabled'}>← Anterior</button><span>${DATA.pagination.offset + 1}–${Math.min(DATA.pagination.offset + DATA.pagination.limit, DATA.result_count)} de ${DATA.result_count}</span><button id="page-next" ${DATA.pagination.has_next?'':'disabled'}>Próxima →</button></div>`);
  document.querySelectorAll('.interaction').forEach(element => element.onclick = () => openDetail(DATA.interactions[+element.dataset.index]));
  if ($('#page-prev')) $('#page-prev').onclick=()=>changePage(-DATA.pagination.limit);
  if ($('#page-next')) $('#page-next').onclick=()=>changePage(DATA.pagination.limit);
}

function changePage(delta){const params=new URLSearchParams(CURRENT_PARAMS);params.set('offset',Math.max(0,DATA.pagination.offset+delta));load(params);document.querySelector('#interactions').scrollIntoView({behavior:'smooth'})}

function triggerHtml(trigger) {
  return `<div class="trigger ${esc(trigger.kind)}"><b>${esc(trigger.name)}</b> <code>${esc(trigger.code)}</code><p><b>Fundamento:</b> ${esc(trigger.basis)}<br><b>Justificativa:</b> ${esc(trigger.justification)}<br><b>Regra atual:</b> ${esc(trigger.current_effect)}<br><b>Simulação:</b> ${esc(trigger.hybrid_effect)}</p>${trigger.evidence.length ? `<p><b>Evidências:</b> ${trigger.evidence.map(esc).join(' · ')}</p>` : '<p><b>Evidência textual:</b> nenhuma; conclusão gerada pela ausência do padrão esperado.</p>'}</div>`;
}

function openDetail(item) {
  $('#detail-title').textContent = item.filename;
  const nlp = item.nlp;
  $('#detail-body').innerHTML = `<div class="detail-grid">
    <section class="detail-block"><h3>Nota oficial</h3><p><b class="${item.official_zero ? 'zero' : ''}">${item.official_score}/100</b><br>${item.official_zero ? 'Zerada por ao menos uma regra de inaderência.' : 'Sem zeramento por inaderência.'}</p></section>
    <section class="detail-block"><h3>Simulação híbrida</h3><p><b class="${!item.hybrid_zero && item.official_zero ? 'released' : ''}">${item.simulated_score}/100</b><br>${item.hybrid_zero ? 'Mantém zeramento por evidência explícita grave.' : 'Ausências permanecem como alerta, sem zeramento automático.'}</p></section>
    <section class="detail-block"><h3>Regex e metadados</h3><p><b>Motor oficial:</b> Regex + regras<br><b>Protocolo nos metadados:</b> ${item.protocol_in_metadata ? 'Sim' : 'Não'}<br><b>Decide a nota:</b> Sim</p></section>
    <section class="detail-block"><h3>NLP contextual</h3><p><b>Papel:</b> ${esc(nlp.role)}<br><b>Tópico:</b> ${esc(nlp.topic)}<br><b>Sentimento:</b> ${esc(nlp.sentiment)}<br><b>Confiança:</b> ${Math.round(nlp.confidence * 100)}%<br><b>Modelo:</b> ${esc(nlp.version)}<br><b>Decide a nota:</b> Não</p></section>
    <section class="detail-block full"><h3>Regras acionadas</h3>${item.triggers.map(triggerHtml).join('') || '<p>Nenhuma inaderência acionada.</p>'}</section>
    <section class="detail-block full"><h3>Governança da simulação</h3><p>Este resultado é somente consultivo. A nota oficial persistida não foi modificada. A política híbrida precisa de homologação antes de qualquer reprocessamento.</p></section>
  </div>`;
  $('#detail').showModal();
}

function render() {
  renderKpis(); renderDistribution(); renderCriteria(); renderInteractions();
  $('#loading').hidden = true; $('#content').hidden = false;
}

async function load(params = new URLSearchParams()) {
  CURRENT_PARAMS = new URLSearchParams(params);
  $('#loading').hidden = false;
  try { DATA = await requestData(params); render(); }
  catch (error) { $('#loading').textContent = `Erro: ${error.message}`; }
}

$('#filters').onsubmit = event => {
  event.preventDefault();
  const params = new URLSearchParams();
  if ($('#status').value) params.set('status', $('#status').value);
  if ($('#criterion').value) params.set('criterion', $('#criterion').value);
  if ($('#search').value.trim()) params.set('search', $('#search').value.trim());
  load(params);
};
$('#clear').onclick = () => { $('#filters').reset(); load(); };
$('#close').onclick = () => $('#detail').close();
$('#detail').onclick = event => { if (event.target === $('#detail')) $('#detail').close(); };
load();

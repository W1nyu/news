'use strict';
const SECTIONS=['금융','증권','산업/재계','부동산','글로벌 경제','경제일반','중기/벤처','생활경제'];
const state={report:null,index:[],history:[],category:'전체',query:'',limit:18,request:0,today:'',latestDate:null,collectable:[],missingDate:'',running:false,awaiting:false};
const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function message(text,fraction){$('status').hidden=!text;$('status-text').textContent=text;$('progress').hidden=fraction==null;$('progress-bar').style.width=`${Math.round((fraction||0)*100)}%`;}
function dateText(value){const d=new Date(value);return Number.isNaN(d.getTime())?'':new Intl.DateTimeFormat('ko-KR',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Asia/Seoul'}).format(d);}
async function json(url){const response=await fetch(url,{cache:'no-store'});if(!response.ok)throw new Error('load');return response.json();}
function reportArticles(){return (state.report?.topics||[]).flatMap(t=>t.articles.map(a=>({...a,topic:t.name,date:state.report.date})));}
function card(a,extra=''){return `<article class="card"><span class="category">${esc(a.topic)}</span><h2><a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a></h2>${(a.summary||[]).map(s=>`<p>${esc(s)}</p>`).join('')}<div class="meta">${esc(a.source)} · ${esc(dateText(a.published_at))} 발행</div>${extra}</article>`;}
function renderBanner(){const show=Boolean(state.today)&&(state.latestDate||'')<state.today&&!state.running;$('missing-today').hidden=!show;if(show)$('missing-today-text').textContent=`오늘(${state.today.slice(5)}) 보고서가 아직 없습니다.${state.latestDate?` 최근 보고서는 ${state.latestDate.slice(5)}입니다.`:''}`;}
function renderDates(){const dates=new Map(state.history.map(h=>[h.date,true]));state.collectable.forEach(d=>{if(!dates.has(d))dates.set(d,false);});const selected=$('date').value;$('date').innerHTML='<option value="">최신 보고서</option>'+[...dates].sort((a,b)=>b[0].localeCompare(a[0])).map(([d,has])=>`<option value="${esc(d)}"${has?'':' data-missing="1"'}>${esc(d)}${has?'':' (미수집)'}</option>`).join('');$('date').value=dates.has(selected)?selected:'';}
function render(){
  $('categories').innerHTML=['전체',...SECTIONS].map(s=>`<button type="button" data-category="${esc(s)}" aria-pressed="${state.category===s}">${esc(s)}</button>`).join('');
  if(state.missingDate){$('articles').innerHTML=`<div class="missing"><p>${esc(state.missingDate)} 보고서가 없습니다.</p><button type="button" data-collect="${esc(state.missingDate)}">이 날짜 보고서 만들기</button></div>`;$('more').hidden=true;$('updated').textContent='';setCollectButtons(state.running);renderBanner();return;}
  let articles=state.query?state.index:reportArticles();
  if(state.category!=='전체')articles=articles.filter(a=>a.topic===state.category);
  if(state.query)articles=articles.filter(a=>[a.title,a.source,a.topic,a.date,...(a.summary||[])].join(' ').toLocaleLowerCase().includes(state.query));
  $('articles').innerHTML=articles.length?articles.slice(0,state.limit).map(a=>card(a,state.query?`<button class="open-report" data-date="${esc(a.date)}">${esc(a.date)} 보고서 보기</button>`:'')).join(''):'<p class="empty">조건에 맞는 뉴스가 없습니다.</p>';
  $('more').hidden=articles.length<=state.limit;
  $('updated').textContent=state.report?`${state.report.date} · ${dateText(state.report.generated_at)} 갱신`:'';
  renderBanner();
}
async function loadReport(date=''){
  const id=++state.request;state.missingDate='';
  try{const data=await json(`data/${date||'latest'}.json`);if(id!==state.request)return;if(data.schema_version!==4)throw new Error('old');state.report=data;message('');}
  catch{if(id!==state.request)return;state.report=null;message('보고서를 불러오지 못했습니다. 지금 수집을 눌러 새 보고서를 만들어 주세요.');}
  render();
}
async function loadArchive(){
  try{const [history,index]=await Promise.all([json('data/history.json'),json('data/search.json')]);state.history=history;state.index=index.filter(a=>a.source_id==='naver'&&SECTIONS.includes(a.topic));renderDates();render();}
  catch{message('보관함 검색을 불러오지 못했습니다. 새로고침해 주세요.');}
}
function setCollectButtons(disabled){document.querySelectorAll('[data-collect]').forEach(b=>{b.disabled=disabled;});}
$('date').onchange=()=>{state.query='';$('search').value='';state.limit=18;const option=$('date').selectedOptions[0];if(option&&option.dataset.missing){state.missingDate=$('date').value;render();return;}loadReport($('date').value);};
$('search').oninput=()=>{state.query=$('search').value.trim().toLocaleLowerCase();state.limit=18;if(state.query&&state.missingDate){state.missingDate='';$('date').value='';}render();};
$('categories').onclick=e=>{if(e.target.dataset.category){state.category=e.target.dataset.category;state.limit=18;render();}};
$('articles').onclick=e=>{const date=e.target.dataset.date;if(!date)return;$('date').value=date;state.query='';$('search').value='';state.category='전체';state.limit=18;loadReport(date);};
$('more').onclick=()=>{state.limit+=18;render();};
async function poll(){
  try{const status=await json('/api/status');
    Object.assign(state,{today:status.today||'',latestDate:status.latest_date??null,collectable:status.collectable_dates||[],running:Boolean(status.running)});
    setCollectButtons(state.running);
    if(state.running){state.awaiting=true;const p=status.progress;message(p&&p.total?`수집 중 · ${p.done}/${p.total}${p.section?' '+p.section:''}`:'뉴스를 수집하고 있습니다.',p&&p.total?p.done/p.total:0);renderBanner();setTimeout(poll,2000);return;}
    if(state.awaiting){state.awaiting=false;
      if(status.ok){const date=status.date||'';state.missingDate='';$('date').value=date;state.limit=18;await loadArchive();$('date').value=date;await loadReport(date);message('새 보고서가 준비됐습니다.');}
      else message(status.message);}
    renderDates();renderBanner();
  }catch{setCollectButtons(false);message('수집 상태 확인에 실패했습니다. 잠시 후 새로고침해 주세요.');}
}
async function startCollect(date){
  message(date?`${date} 보고서 수집 요청 중…`:'수집 요청 중…');setCollectButtons(true);state.awaiting=true;
  try{const r=await fetch('/api/collect',{method:'POST',headers:{'Content-Type':'application/json','X-Briefing-Request':'collect'},body:JSON.stringify(date?{date}:{})});
    if(r.status===400){const data=await r.json().catch(()=>({}));throw Object.assign(new Error(data.error||'요청이 거부되었습니다.'),{shown:true});}
    if(!r.ok&&r.status!==409)throw new Error('collect');
    await poll();}
  catch(error){state.awaiting=false;setCollectButtons(false);message(error.shown?error.message:'수집 서버에 연결하지 못했습니다. 바탕화면의 「아침 경제 수집」 바로가기를 실행해 주세요.');}
}
document.addEventListener('click',e=>{const button=e.target.closest('[data-collect]');if(button&&!button.disabled)startCollect(button.dataset.collect||'');});
loadReport();loadArchive();poll();

function keywordRow(rule={keyword:'',weight:1}){
  const row=document.createElement('div');row.className='keyword-row';
  row.innerHTML=`<input class="keyword-name" aria-label="키워드" maxlength="60" required placeholder="예: 반도체" value="${esc(rule.keyword)}"><input class="keyword-weight" aria-label="가중치" type="number" min="-100" max="100" step="1" required value="${esc(rule.weight)}"><button type="button" class="keyword-delete" aria-label="키워드 삭제">삭제</button>`;
  row.querySelector('button').onclick=()=>row.remove();
  $('keyword-rows').append(row);return row;
}
$('settings').onclick=async()=>{
  $('keyword-dialog').showModal();$('keyword-rows').replaceChildren();$('keyword-save').disabled=true;$('keyword-add').disabled=true;$('keyword-status').textContent='설정을 불러오는 중…';
  try{const data=await json('/api/keywords');data.rules.forEach(keywordRow);$('keyword-status').textContent='';$('keyword-save').disabled=false;$('keyword-add').disabled=false;}
  catch{$('keyword-status').textContent='설정을 불러오지 못했습니다. 서버를 확인하고 다시 열어 주세요.';}
};
$('keyword-close').onclick=()=>$('keyword-dialog').close();
$('keyword-add').onclick=()=>{if($('keyword-rows').children.length>=100){$('keyword-status').textContent='최대 100개까지 등록할 수 있습니다.';return;}keywordRow().querySelector('input').focus();};
$('keyword-form').onsubmit=async e=>{
  e.preventDefault();const rules=[...document.querySelectorAll('.keyword-row')].map(row=>({keyword:row.querySelector('.keyword-name').value.trim(),weight:Number(row.querySelector('.keyword-weight').value)}));
  $('keyword-save').disabled=true;
  try{const response=await fetch('/api/keywords',{method:'POST',headers:{'Content-Type':'application/json','X-Briefing-Request':'collect'},body:JSON.stringify({rules})});const data=await response.json();if(!response.ok)throw new Error(data.error||'저장 실패');$('keyword-status').textContent='저장했습니다. 다음 수집부터 적용됩니다.';}
  catch(error){$('keyword-status').textContent=error.message||'저장하지 못했습니다.';}
  finally{$('keyword-save').disabled=false;}
};

'use strict';
const SECTIONS=['금융','증권','산업/재계','부동산','글로벌 경제','경제일반','중기/벤처','생활경제'];
const state={report:null,index:[],category:'전체',query:'',limit:18,request:0};
const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function message(text){$('status').hidden=!text;$('status').textContent=text;}
function dateText(value){const d=new Date(value);return Number.isNaN(d.getTime())?'':new Intl.DateTimeFormat('ko-KR',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Asia/Seoul'}).format(d);}
async function json(url){const response=await fetch(url,{cache:'no-store'});if(!response.ok)throw new Error('load');return response.json();}
function render(){
  $('categories').innerHTML=['전체',...SECTIONS].map(s=>`<button type="button" data-category="${esc(s)}" aria-pressed="${state.category===s}">${esc(s)}</button>`).join('');
  let articles=state.query?state.index:(state.report?.topics||[]).flatMap(t=>t.articles.map(a=>({...a,topic:t.name,date:state.report.date})));
  if(state.category!=='전체')articles=articles.filter(a=>a.topic===state.category);
  if(state.query)articles=articles.filter(a=>[a.title,a.source,a.topic,a.date,...(a.summary||[])].join(' ').toLocaleLowerCase().includes(state.query));
  $('articles').innerHTML=articles.length?articles.slice(0,state.limit).map(a=>`<article class="card"><span class="category">${esc(a.topic)}</span><h2><a href="${esc(a.url)}" target="_blank" rel="noopener noreferrer">${esc(a.title)}</a></h2>${(a.summary||[]).map(s=>`<p>${esc(s)}</p>`).join('')}<div class="meta">${esc(a.source)} · ${esc(dateText(a.published_at))} 발행</div>${state.query?`<button class="open-report" data-date="${esc(a.date)}">${esc(a.date)} 보고서 보기</button>`:''}</article>`).join(''):'<p class="empty">조건에 맞는 뉴스가 없습니다.</p>';
  $('more').hidden=articles.length<=state.limit;
  $('pdf').hidden=!state.report?.pdf_url;
  if(state.report?.pdf_url)$('pdf').href=state.report.pdf_url+'?t='+encodeURIComponent(state.report.generated_at);
  $('updated').textContent=state.report?`${state.report.date} · ${dateText(state.report.generated_at)} 갱신`:'';
}
async function loadReport(date=''){
  const id=++state.request;
  try{const data=await json(`data/${date||'latest'}.json`);if(id!==state.request)return;if(data.schema_version!==4)throw new Error('old');state.report=data;message('');}
  catch{if(id!==state.request)return;state.report=null;message('보고서를 불러오지 못했습니다. 지금 수집을 눌러 새 보고서를 만들어 주세요.');}
  render();
}
async function loadArchive(){
  try{const [history,index]=await Promise.all([json('data/history.json'),json('data/search.json')]);state.index=index.filter(a=>a.source_id==='naver'&&SECTIONS.includes(a.topic));const selected=$('date').value;$('date').innerHTML='<option value="">최신 보고서</option>'+history.map(h=>`<option value="${esc(h.date)}">${esc(h.date)}</option>`).join('');$('date').value=selected;render();}
  catch{message('보관함 검색을 불러오지 못했습니다. 새로고침해 주세요.');}
}
$('date').onchange=()=>{state.query='';$('search').value='';state.limit=18;loadReport($('date').value);};
$('search').oninput=()=>{state.query=$('search').value.trim().toLocaleLowerCase();state.limit=18;render();};
$('categories').onclick=e=>{if(e.target.dataset.category){state.category=e.target.dataset.category;state.limit=18;render();}};
$('articles').onclick=e=>{const date=e.target.dataset.date;if(!date)return;$('date').value=date;state.query='';$('search').value='';state.category='전체';state.limit=18;loadReport(date);};
$('more').onclick=()=>{state.limit+=18;render();};
async function poll(){
  try{const status=await json('/api/status');$('collect').disabled=status.running;
    if(status.running){message('뉴스를 수집하고 보고서를 작성하고 있습니다.');setTimeout(poll,2000);return;}
    if(status.ok){$('date').value='';state.limit=18;await loadReport();await loadArchive();message('새 보고서가 준비됐습니다.');}
    else message(status.message);
  }catch{$('collect').disabled=false;message('수집 상태 확인에 실패했습니다. 잠시 후 새로고침해 주세요.');}
}
$('collect').onclick=async()=>{message('수집 요청 중…');$('collect').disabled=true;try{const r=await fetch('/api/collect',{method:'POST',headers:{'X-Briefing-Request':'collect'}});if(!r.ok&&r.status!==409)throw new Error('collect');await poll();}catch{$('collect').disabled=false;message('수집 서버에 연결하지 못했습니다. 실행 안내의 수동 수집 명령을 사용해 주세요.');}};
loadReport();loadArchive();

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

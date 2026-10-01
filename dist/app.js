'use strict';
const SECTIONS=['금융','증권','산업/재계','부동산','글로벌 경제','경제일반','중기/벤처','생활경제'];
const PAGE=80;
const state={report:null,index:[],history:[],category:'전체',query:'',limit:PAGE,request:0,today:'',latestDate:null,collectable:[],missingDate:'',running:false,awaiting:false,pollFailures:0,range:'all',from:'',to:'',publisher:'',keywords:[],selected:'',visible:[],keep:new Set()};
const $=id=>document.getElementById(id);
const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const SAVED='저장함';
const TABS=['전체',...SECTIONS,SAVED];
const store={load(key,fallback){try{const v=localStorage.getItem(key);return v?JSON.parse(v):fallback;}catch{return fallback;}},save(key,value){try{localStorage.setItem(key,JSON.stringify(value));}catch{}}};
const readList=store.load('briefing.read.v1',[]);state.read=new Set(Array.isArray(readList)?readList:[]);
state.bookmarks=new Map(Object.entries(store.load('briefing.bookmarks.v1',{})||{}).filter(([,v])=>v&&typeof v==='object'&&typeof v.url==='string'));
state.unreadOnly=store.load('briefing.unread-only.v1',false)===true;
function saveRead(){const list=[...state.read].slice(-2000);state.read=new Set(list);store.save('briefing.read.v1',list);}
function markRead(url){if(!url||state.read.has(url))return;state.read.add(url);saveRead();}
function toggleRead(url){if(!url)return;if(state.read.has(url))state.read.delete(url);else state.read.add(url);saveRead();}
function toggleBookmark(a){if(state.bookmarks.has(a.url))state.bookmarks.delete(a.url);else state.bookmarks.set(a.url,{url:a.url,title:a.title,source:a.source,topic:a.topic,date:a.date,published_at:a.published_at,summary:a.summary||[],related:(Array.isArray(a.related)?a.related:[]),keywords:state.keywords,keyword_matches:a.keyword_matches||[],saved_at:new Date().toISOString()});store.save('briefing.bookmarks.v1',Object.fromEntries(state.bookmarks));}
function findArticle(url){return [...reportArticles(),...state.index].find(a=>a.url===url)||state.bookmarks.get(url)||null;}
const escRe=s=>s.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
function highlight(title,matches){const keys=[...new Set((Array.isArray(matches)?matches:[]).filter(k=>typeof k==='string'&&k))].sort((a,b)=>b.length-a.length);if(!keys.length)return esc(title);const re=new RegExp(`(${keys.map(escRe).join('|')})`,'gi');return String(title??'').split(re).map((part,i)=>i%2?`<mark>${esc(part)}</mark>`:esc(part)).join('');}
function showHeadlines(){return !state.query&&state.category!==SAVED&&!state.missingDate&&Boolean(state.report);}
function headlineArticles(){return reportArticles().sort((x,y)=>(y.keyword_score||0)-(x.keyword_score||0)||String(y.published_at||'').localeCompare(String(x.published_at||''))).slice(0,6);}
function headlineButton(a){return `<button type="button" data-select="${esc(a.url)}" data-headline="1"><span class="badge">${esc(a.topic)}</span><em>${highlight(a.title,a.keyword_matches)}</em></button>`;}
function renderHeadlines(){const show=showHeadlines();$('headlines').hidden=!show;$('headlines').innerHTML=show?headlineArticles().map(headlineButton).join(''):'';}
function message(text,fraction){$('status').hidden=!text;$('status-text').textContent=text;$('progress').hidden=fraction==null;$('progress-bar').style.width=`${Math.round((fraction||0)*100)}%`;}
function dateText(value){const d=new Date(value);return Number.isNaN(d.getTime())?'':new Intl.DateTimeFormat('ko-KR',{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false,timeZone:'Asia/Seoul'}).format(d);}
async function json(url){const response=await fetch(url,{cache:'no-store'});if(!response.ok)throw new Error('load');return response.json();}
function reportArticles(){return (state.report?.topics||[]).flatMap(t=>t.articles.map(a=>({...a,topic:t.name,date:a.date||state.report.date})));}
const WEEK='week';
function weekReport(){
  const from=shiftDate(state.today||kstDate(Date.now()),-6);const seen=new Set();const rows=[];
  [...state.index].sort((a,b)=>String(b.date).localeCompare(String(a.date))).forEach(a=>{if(a.date>=from&&!seen.has(a.url)){seen.add(a.url);rows.push(a);}});
  const rank=(a,b)=>(b.keyword_score||0)-(a.keyword_score||0)||String(b.published_at||'').localeCompare(String(a.published_at||''));
  return {schema_version:4,date:WEEK,from,generated_at:'',topics:SECTIONS.map(name=>({name,articles:rows.filter(a=>a.topic===name).sort(rank)}))};
}
const kstDate=value=>{const d=new Date(value);return Number.isNaN(d.getTime())?'':new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul'}).format(d);};
function shiftDate(iso,days){const d=new Date(`${iso}T00:00:00Z`);d.setUTCDate(d.getUTCDate()+days);return d.toISOString().slice(0,10);}
function rangeBounds(){if(!state.query||state.range==='all')return null;if(state.range==='custom'){let from=state.from,to=state.to;if(!from&&!to)return null;if(from&&to&&from>to)[from,to]=[to,from];return {from,to};}const days=Number(state.range);return {from:shiftDate(state.today||kstDate(Date.now()),-(days-1)),to:''};}
function inRange(a,bounds){if(!bounds)return true;const d=kstDate(a.published_at);return Boolean(d)&&(!bounds.from||d>=bounds.from)&&(!bounds.to||d<=bounds.to);}
function baseArticles(){if(state.category===SAVED)return [...state.bookmarks.values()].sort((a,b)=>String(b.date||'').localeCompare(String(a.date||''))||String(b.published_at||'').localeCompare(String(a.published_at||'')));return state.query?state.index:reportArticles();}
function renderPublishers(list){const counts=new Map();list.forEach(a=>{if(a.source)counts.set(a.source,(counts.get(a.source)||0)+1);});const options=[...counts].sort((x,y)=>y[1]-x[1]||x[0].localeCompare(y[0]));if(!counts.has(state.publisher))state.publisher='';$('publisher').innerHTML='<option value="">전체 언론사</option>'+options.map(([s,n])=>`<option value="${esc(s)}">${esc(s)} (${n})</option>`).join('');$('publisher').value=state.publisher;}
function searchText(a){return [a.title,a.source,a.topic,a.date,...(Array.isArray(a.summary)?a.summary:[]),...(Array.isArray(a.related)?a.related.map(r=>r&&r.title):[])].join(' ').toLocaleLowerCase();}
function keywordsFor(a){return state.category===SAVED&&Array.isArray(a.keywords)?a.keywords:state.keywords;}
async function loadKeywords(){try{const data=await json('/api/keywords');state.keywords=(data.rules||[]).map(r=>r&&r.keyword).filter(k=>typeof k==='string'&&k);}catch{state.keywords=[];}render();}
function applyFilters(list){if(state.publisher)list=list.filter(a=>a.source===state.publisher);const bounds=rangeBounds();if(bounds)list=list.filter(a=>inRange(a,bounds));if(state.query)list=list.filter(a=>searchText(a).includes(state.query));return list;}
function filteredArticles(){let list=baseArticles();if(state.category!=='전체'&&state.category!==SAVED)list=list.filter(a=>a.topic===state.category);return applyFilters(list);}
function visibleArticles(){const list=filteredArticles();return state.unreadOnly&&state.category!==SAVED?list.filter(a=>!state.read.has(a.url)||state.keep.has(a.url)):list;}
function unreadCounts(){const counts=new Map(TABS.map(s=>[s,0]));if(state.missingDate)return counts;applyFilters(state.query?state.index:reportArticles()).forEach(a=>{if(state.read.has(a.url))return;counts.set('전체',counts.get('전체')+1);if(SECTIONS.includes(a.topic))counts.set(a.topic,counts.get(a.topic)+1);});return counts;}
function relatedItems(a){return (Array.isArray(a.related)?a.related:[]).filter(r=>r&&typeof r.url==='string');}
function detail(a,showDate){
  const saved=state.bookmarks.has(a.url);const read=state.read.has(a.url);const keys=keywordsFor(a);const related=relatedItems(a);const url=esc(a.url);
  return `<article class="detail-body" data-url="${url}"><div class="detail-top"><span class="badge">${esc(a.topic)}</span>${showDate?`<span class="detail-date">${esc(a.date)}</span>`:''}</div>`
    +`<h2><a href="${url}" target="_blank" rel="noopener noreferrer" data-open="${url}">${highlight(a.title,a.keyword_matches)}</a></h2>`
    +`<p class="meta">${esc(a.source)} · ${esc(dateText(a.published_at))} 발행</p>`
    +`<div class="detail-actions"><a class="btn-solid" href="${url}" target="_blank" rel="noopener noreferrer" data-open="${url}">원문 열기</a><button type="button" class="btn-outline" data-bookmark="${url}" aria-pressed="${saved}">${saved?'★ 저장됨':'☆ 저장'}</button><button type="button" class="btn-outline" data-copy="${url}">링크 복사</button><button type="button" class="btn-outline" data-toggle-read="${url}">${read?'안 읽음으로':'읽음으로'}</button>${showDate?`<button type="button" class="btn-outline" data-date="${esc(a.date)}">${esc(a.date)} 보고서 보기</button>`:''}</div>`
    +`<div class="summary">${(Array.isArray(a.summary)?a.summary:[]).map(s=>`<p>${highlight(s,keys)}</p>`).join('')}</div>`
    +(related.length?`<h3 class="related-heading">관련 보도 ${related.length}건</h3><ul class="related">${related.map(r=>`<li class="${state.read.has(r.url)?'read':''}"><span>${esc(r.source)}</span><a href="${esc(r.url)}" target="_blank" rel="noopener noreferrer" data-related="${esc(r.url)}">${esc(r.title)}</a><time>${esc(dateText(r.published_at))}</time></li>`).join('')}</ul>`:'')
    +'</article>';
}
function row(a,showDate){
  const selected=state.selected===a.url;const read=state.read.has(a.url);const related=relatedItems(a).length;
  const meta=[esc(a.source),esc(dateText(a.published_at)),showDate?esc(a.date):'',related?`관련 ${related}`:'',state.bookmarks.has(a.url)?'<span class="star" aria-label="저장됨">★</span>':''].filter(Boolean).join(' · ');
  return `<li class="row${read?' read':''}${selected?' selected':''}" data-url="${esc(a.url)}"><button type="button" class="row-main" data-select="${esc(a.url)}" aria-expanded="${selected}"><span class="row-title">${read?'':'<span class="dot"></span><span class="sr-only">안 읽음</span>'}${highlight(a.title,a.keyword_matches)}</span><span class="row-meta">${meta}</span></button>${selected?`<div class="row-detail">${detail(a,showDate)}</div>`:''}</li>`;
}
const HINT='<p class="hint"><kbd>j</kbd> <kbd>k</kbd> 또는 <kbd>↑</kbd> <kbd>↓</kbd>로 고르고 <kbd>Enter</kbd>로 원문을 엽니다 · <button type="button" data-shortcuts>단축키 전체 보기</button></p>';
function overview(list){
  if(!showHeadlines())return list.length?`<div class="overview"><p class="overview-count">${esc(state.query?'검색 결과':state.category)} ${list.length}건</p>${HINT}</div>`:'';
  const total=new Map(),unread=new Map();applyFilters(reportArticles()).forEach(a=>{total.set(a.topic,(total.get(a.topic)||0)+1);if(!state.read.has(a.url))unread.set(a.topic,(unread.get(a.topic)||0)+1);});
  const title=state.report.date===WEEK?'최근 7일 헤드라인':`${esc(state.report.date)} 헤드라인`;
  return `<div class="overview"><h2>${title}</h2><ol class="overview-heads">${headlineArticles().map(a=>`<li>${headlineButton(a)}</li>`).join('')}</ol><h3>섹션별 안 읽은 기사</h3><ul class="overview-sections">${SECTIONS.map(s=>`<li><button type="button" data-category="${esc(s)}"><span>${esc(s)}</span><span>${unread.get(s)||0} / ${total.get(s)||0}</span></button></li>`).join('')}</ul>${HINT}</div>`;
}
function renderTabs(){const counts=unreadCounts();$('categories').innerHTML=TABS.map((s,i)=>{const n=s===SAVED?state.bookmarks.size:counts.get(s);return `<button type="button" data-category="${esc(s)}" aria-pressed="${state.category===s}" aria-keyshortcuts="${i}">${esc(s)}${n?`<span class="count">${n}</span>`:''}</button>`;}).join('');}
function renderList(list,showDate){
  if(!list.length){state.visible=[];const hidden=state.unreadOnly&&state.category!==SAVED&&filteredArticles().length;$('articles').innerHTML=`<div class="empty"><p>${state.category===SAVED&&!state.bookmarks.size?'저장한 뉴스가 없습니다. 기사 상세에서 ☆ 저장을 누르세요.':hidden?'안 읽은 뉴스가 없습니다.':'조건에 맞는 뉴스가 없습니다.'}</p>${hidden?'<button type="button" class="btn-outline" data-unread-only>읽은 기사도 보기</button>':''}</div>`;return;}
  const shown=list.slice(0,state.limit);const grouped=state.category==='전체'&&!state.query;
  const groups=grouped?SECTIONS.map(s=>[s,shown.filter(a=>a.topic===s)]).filter(g=>g[1].length):[[state.query?'검색 결과':state.category,shown]];
  state.visible=groups.flatMap(g=>g[1].map(a=>a.url));
  $('articles').innerHTML=groups.map(([name,items])=>{const all=grouped?list.filter(a=>a.topic===name):list;const unread=all.filter(a=>!state.read.has(a.url)).length;return `<section class="group"><div class="group-head"><h2>${esc(name)}</h2><span>안 읽음 ${unread}/${all.length}</span>${unread?`<button type="button" class="read-all" data-read-all="${esc(name)}">모두 읽음</button>`:''}</div><ul class="rows">${items.map(a=>row(a,showDate)).join('')}</ul></section>`;}).join('');
}
function renderBanner(){const show=Boolean(state.today)&&(state.latestDate||'')<state.today&&!state.running;$('missing-today').hidden=!show;if(show)$('missing-today-text').textContent=`오늘(${state.today.slice(5)}) 보고서가 아직 없습니다.${state.latestDate?` 최근 보고서는 ${state.latestDate.slice(5)}입니다.`:''}`;}
function renderTrend(){
  const today=state.today||kstDate(Date.now());if(!state.history.length){$('trend').hidden=true;return;}
  const totals=new Map(state.history.map(h=>[h.date,h.selected]));const days=Array.from({length:14},(_,i)=>shiftDate(today,i-13));
  const perSection=new Map();state.index.forEach(a=>{const key=a.date+'|'+a.topic;perSection.set(key,(perSection.get(key)||0)+1);});
  const max=Math.max(1,...days.map(d=>totals.get(d)||0));
  $('trend').innerHTML=days.map(d=>{const n=totals.get(d);if(n==null)return `<span class="none" title="${esc(d)} · 보고서 없음"></span>`;const parts=SECTIONS.map(s=>`${s} ${perSection.get(d+'|'+s)||0}`).join(', ');return `<span style="height:${Math.max(8,Math.round(n/max*100))}%" title="${esc(d)} · ${n}건 (${esc(parts)})"></span>`;}).join('');
  $('trend').setAttribute('aria-label',`최근 14일 기사 수: ${days.map(d=>`${d.slice(5)} ${totals.get(d)??'없음'}`).join(', ')}`);$('trend').hidden=false;
}
function renderDates(){const dates=new Map(state.history.map(h=>[h.date,true]));state.collectable.forEach(d=>{if(!dates.has(d))dates.set(d,false);});const selected=$('date').value;$('date').innerHTML='<option value="">최신 보고서</option><option value="week">최근 7일 모아보기</option>'+[...dates].sort((a,b)=>b[0].localeCompare(a[0])).map(([d,has])=>`<option value="${esc(d)}"${has?'':' data-missing="1"'}>${esc(d)}${has?'':' (미수집)'}</option>`).join('');$('date').value=dates.has(selected)||selected===WEEK?selected:'';}
function render(){
  const missing=state.missingDate&&state.category!==SAVED;
  if(!missing)renderPublishers(baseArticles());
  renderTabs();renderHeadlines();$('unread-only').setAttribute('aria-pressed',String(state.unreadOnly));
  if(missing){state.visible=[];$('articles').innerHTML=`<div class="missing"><p>${esc(state.missingDate)} 보고서가 없습니다.</p><button type="button" data-collect="${esc(state.missingDate)}">이 날짜 보고서 만들기</button></div>`;$('detail').innerHTML='';$('more').hidden=true;$('updated').textContent='';setCollectButtons(state.running);renderBanner();return;}
  const list=visibleArticles();
  if(state.selected&&!list.some(a=>a.url===state.selected))state.selected='';
  $('range').disabled=!state.query;$('range-custom').hidden=!(state.query&&state.range==='custom');
  const week=state.report?.date===WEEK;const showDate=Boolean(state.query)||state.category===SAVED||week;
  renderList(list,showDate);
  $('more').hidden=list.length<=state.limit;
  const current=list.find(a=>a.url===state.selected);
  $('detail').innerHTML=current?detail(current,showDate):overview(list);
  $('updated').textContent=!state.report?'':week?`${state.report.from} ~ ${state.today||''} · ${reportArticles().length}건`:`${state.report.date} · ${dateText(state.report.generated_at)} 갱신`;
  renderBanner();
}
function resetView(){state.limit=PAGE;state.keep=new Set(state.selected?[state.selected]:[]);}
function select(url){
  state.selected=url||'';
  if(url){markRead(url);state.keep.add(url);const i=visibleArticles().findIndex(a=>a.url===url);if(i>=state.limit)state.limit=Math.ceil((i+1)/PAGE)*PAGE;}
  render();if(!url)return;
  $('detail').scrollTop=0;const el=$('articles').querySelector('.row.selected');if(el)el.scrollIntoView({block:'nearest'});
}
function selectHeadline(url){state.category='전체';state.query='';$('search').value='';state.publisher='';state.keep.clear();select(url);}
function move(delta){
  if(!state.visible.length)return;const i=state.visible.indexOf(state.selected);let next=i<0?(delta>0?0:state.visible.length-1):i+delta;
  if(next>=state.visible.length&&!$('more').hidden){state.limit+=PAGE;render();}
  next=Math.max(0,Math.min(next,state.visible.length-1));if(state.visible[next]!==state.selected)select(state.visible[next]);
}
function setCategory(name){if(!TABS.includes(name))return;state.category=name;resetView();render();}
function setUnreadOnly(on){state.unreadOnly=on;store.save('briefing.unread-only.v1',on);resetView();render();}
function readAll(name){const list=visibleArticles();(SECTIONS.includes(name)?list.filter(a=>a.topic===name):list).forEach(a=>{state.read.add(a.url);state.keep.delete(a.url);});saveRead();render();}
function openReport(date){$('date').value=date;state.query='';$('search').value='';state.category='전체';state.selected='';resetView();loadReport(date);}
function copyText(a){return `${a.title}${a.source?` (${a.source})`:''}\n${a.url}`;}
async function copyArticle(a){
  const text=copyText(a);let ok=false;
  try{await navigator.clipboard.writeText(text);ok=true;}
  catch{try{const area=document.createElement('textarea');area.value=text;area.setAttribute('readonly','');area.style.position='fixed';area.style.opacity='0';document.body.append(area);area.select();ok=document.execCommand('copy');area.remove();}catch{}}
  toast(ok?'제목과 링크를 복사했습니다.':'복사하지 못했습니다.');
}
function toast(text){const el=$('toast');el.textContent=text;el.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>{el.hidden=true;},2000);}
function onAction(e){
  const t=e.target;if(!t||!t.closest)return;let el;
  if((el=t.closest('[data-select]'))){const url=el.dataset.select;if(el.dataset.headline)selectHeadline(url);else select(state.selected===url?'':url);return;}
  if((el=t.closest('[data-category]'))){setCategory(el.dataset.category);return;}
  if((el=t.closest('[data-bookmark]'))){const a=findArticle(el.dataset.bookmark);if(a)toggleBookmark(a);render();return;}
  if((el=t.closest('[data-copy]'))){const a=findArticle(el.dataset.copy);if(a)copyArticle(a);return;}
  if((el=t.closest('[data-toggle-read]'))){const url=el.dataset.toggleRead;toggleRead(url);state.keep.add(url);render();return;}
  if((el=t.closest('[data-read-all]'))){readAll(el.dataset.readAll);return;}
  if((el=t.closest('[data-unread-only]'))){setUnreadOnly(false);return;}
  if((el=t.closest('[data-shortcuts]'))){$('shortcut-dialog').showModal();return;}
  if((el=t.closest('[data-open]'))){if(!state.read.has(el.dataset.open)){markRead(el.dataset.open);setTimeout(render);}return;}
  if((el=t.closest('[data-related]'))){markRead(el.dataset.related);el.closest('li').classList.add('read');return;}
  if((el=t.closest('[data-date]')))openReport(el.dataset.date);
}
function onAux(e){if(e.button!==1)return;const rel=e.target.closest('[data-related]');if(rel){markRead(rel.dataset.related);rel.closest('li').classList.add('read');return;}const open=e.target.closest('[data-open]');if(open&&!state.read.has(open.dataset.open)){markRead(open.dataset.open);setTimeout(render);}}
async function loadReport(date=''){
  const id=++state.request;state.missingDate='';
  try{const data=await json(`data/${date||'latest'}.json`);if(id!==state.request)return;if(data.schema_version!==4)throw new Error('old');state.report=data;message('');}
  catch{if(id!==state.request)return;state.report=null;message('보고서를 불러오지 못했습니다. 지금 수집을 눌러 새 보고서를 만들어 주세요.');}
  render();
}
async function loadArchive(){
  try{const [history,index]=await Promise.all([json('data/history.json'),json('data/search.json')]);state.history=history;state.index=index.filter(a=>a.source_id==='naver'&&SECTIONS.includes(a.topic));renderDates();renderTrend();if(state.report?.date===WEEK)state.report=weekReport();render();}
  catch{message('보관함 검색을 불러오지 못했습니다. 새로고침해 주세요.');}
}
function setCollectButtons(disabled){document.querySelectorAll('[data-collect]').forEach(b=>{b.disabled=disabled;});}
$('date').onchange=()=>{state.query='';$('search').value='';state.selected='';resetView();const option=$('date').selectedOptions[0];if(option&&option.dataset.missing){state.request++;state.report=null;state.missingDate=$('date').value;message('');render();return;}if($('date').value===WEEK){state.request++;state.missingDate='';state.report=weekReport();message('');render();return;}loadReport($('date').value);};
$('search').oninput=()=>{state.query=$('search').value.trim().toLocaleLowerCase();resetView();if(state.query&&state.missingDate){state.missingDate='';$('date').value='';}render();};
['articles','detail','headlines','categories'].forEach(id=>{$(id).onclick=onAction;});
$('articles').addEventListener('auxclick',onAux);$('detail').addEventListener('auxclick',onAux);
$('more').onclick=()=>{state.limit+=PAGE;render();};
$('range').onchange=()=>{state.range=$('range').value;resetView();render();};
$('from').onchange=()=>{state.from=$('from').value;resetView();render();};
$('to').onchange=()=>{state.to=$('to').value;resetView();render();};
$('publisher').onchange=()=>{state.publisher=$('publisher').value;resetView();render();};
$('unread-only').onclick=()=>setUnreadOnly(!state.unreadOnly);
async function poll(){
  try{const status=await json('/api/status');
    state.pollFailures=0;
    Object.assign(state,{today:status.today||'',latestDate:status.latest_date??null,collectable:status.collectable_dates||[],running:Boolean(status.running)});
    if(Number.isInteger(status.archive_days)&&status.archive_days>0)$('search').placeholder=`최근 ${status.archive_days}일 뉴스 검색`;
    setCollectButtons(state.running);
    if(state.running){state.awaiting=true;const p=status.progress;message(p&&p.total?`수집 중 · ${p.done}/${p.total}${p.section?' '+p.section:''}`:'뉴스를 수집하고 있습니다.',p&&p.total?p.done/p.total:0);renderBanner();setTimeout(poll,2000);return;}
    if(state.awaiting){state.awaiting=false;
      if(status.ok){const date=status.date||'';state.missingDate='';$('date').value=date;state.selected='';resetView();await loadArchive();$('date').value=date;await loadReport(date);message('새 보고서가 준비됐습니다.');}
      else message(status.message);}
    renderDates();renderTrend();renderBanner();
  }catch{if(state.awaiting&&++state.pollFailures<10){message('수집 상태를 다시 확인하는 중…');setTimeout(poll,2000);return;}state.awaiting=false;state.pollFailures=0;setCollectButtons(false);message('수집 상태 확인에 실패했습니다. 잠시 후 새로고침해 주세요.');}
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
loadReport();loadArchive();loadKeywords();poll();

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
  try{const response=await fetch('/api/keywords',{method:'POST',headers:{'Content-Type':'application/json','X-Briefing-Request':'collect'},body:JSON.stringify({rules})});const data=await response.json();if(!response.ok)throw new Error(data.error||'저장 실패');state.keywords=(data.rules||[]).map(r=>r.keyword);render();$('keyword-status').textContent='저장했습니다. 다음 수집부터 적용됩니다.';}
  catch(error){$('keyword-status').textContent=error.message||'저장하지 못했습니다.';}
  finally{$('keyword-save').disabled=false;}
};

// 보기 설정: 테마(기본 라이트)와 글자 크기. <head>의 인라인 스크립트가 같은 값을 먼저 적용한다.
const THEMES=['light','dark','system'];const FONTS=['s','m','l'];
function applyDisplay(){
  const theme=store.load('briefing.theme.v2','light');const font=store.load('briefing.font.v1','m');
  const t=THEMES.includes(theme)?theme:'light';const f=FONTS.includes(font)?font:'m';const root=document.documentElement;
  if(t==='system')delete root.dataset.theme;else root.dataset.theme=t;
  if(f==='m')delete root.dataset.font;else root.dataset.font=f;
  document.querySelectorAll('[data-theme-choice]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.themeChoice===t)));
  document.querySelectorAll('[data-font-choice]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.fontChoice===f)));
}
$('display').onclick=e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.themeChoice)store.save('briefing.theme.v2',b.dataset.themeChoice);if(b.dataset.fontChoice)store.save('briefing.font.v1',b.dataset.fontChoice);applyDisplay();};
applyDisplay();
try{localStorage.removeItem('briefing.theme.v1');}catch{}
$('shortcut-close').onclick=()=>$('shortcut-dialog').close();

// 단축키: 입력 중이거나 dialog가 열려 있으면 무시. 영문 키는 e.code로 읽어 한글 입력 상태에서도 동작한다.
function shortcutKey(e){return /^Key[A-Z]$/.test(e.code||'')&&!e.shiftKey?e.code.slice(3).toLowerCase():e.key;}
function onKey(e){
  if(e.defaultPrevented||e.ctrlKey||e.metaKey||e.altKey||e.isComposing)return;
  const t=e.target||{};const tag=t.tagName||'';
  if(/^(INPUT|SELECT|TEXTAREA)$/.test(tag)||t.isContentEditable){if(e.key==='Escape'&&t.id==='search')t.blur();return;}
  if(document.querySelector('dialog[open]'))return;
  const key=shortcutKey(e);if(key==='Enter'&&/^(BUTTON|A)$/.test(tag))return;
  const a=state.selected?findArticle(state.selected):null;
  if(key==='j'||key==='ArrowDown')move(1);
  else if(key==='k'||key==='ArrowUp')move(-1);
  else if((key==='Enter'||key==='o')&&a){markRead(a.url);window.open(a.url,'_blank','noopener');render();}
  else if(key==='s'&&a){toggleBookmark(a);render();}
  else if(key==='c'&&a)copyArticle(a);
  else if(key==='m'&&a){toggleRead(a.url);state.keep.add(a.url);render();}
  else if(key==='u')setUnreadOnly(!state.unreadOnly);
  else if(key==='/')$('search').focus();
  else if(key==='Escape'&&state.selected)select('');
  else if(key==='?')$('shortcut-dialog').showModal();
  else if(/^[0-9]$/.test(key))setCategory(TABS[Number(key)]);
  else return;
  e.preventDefault();
}
document.addEventListener('keydown',onKey);

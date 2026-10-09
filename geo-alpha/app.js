"use strict";
const $=id=>document.getElementById(id);
const esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dt=x=>x?new Date(x).toLocaleString('zh-CN',{timeZone:'America/New_York',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})+' ET':'—';
const statusNames={ok:'成功',cached:'缓存',watch:'观察',unavailable:'不可用',usable_observation:'可用观测',stale:'已陈旧',insufficient_clear_pixels:'云 / 有效像元不足',invalid_future_timestamp:'时间无效',source_unavailable:'来源失败'};
const badge=s=>'<span class="state '+(['ok','cached','usable_observation'].includes(s)?'':s==='unavailable'||s==='source_unavailable'?'bad':'warn')+'">'+esc(statusNames[s]||s)+'</span>';
function safeURL(u){try{const x=new URL(u);return ['https:','http:'].includes(x.protocol)?x.href:'#';}catch{return '#';}}
let data=null,base=null,backtest=null;
const RAW_BASE='https://raw.githubusercontent.com/qw-cloud/qw-aos-c204.github.io/main/geo-alpha/';
async function readJSON(path){const base=location.hostname.endsWith('github.io')?RAW_BASE:'';const r=await fetch(base+path+'?t='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error(path+': HTTP '+r.status);return r.json();}
async function refresh(){
  $('refresh').disabled=true;
  try{
    const latest=await readJSON('data/latest.json');
    data=latest;
    if(!base)base=await readJSON('data/basemap.json').catch(()=>({features:[]}));
    backtest=await readJSON('data/backtest.json').catch(()=>null);
    render();
  }catch(e){$('health').textContent='快照获取失败';$('health').className='pill bad';$('notice').textContent='最新快照获取失败。已有内容可能陈旧；请稍后刷新。';console.error(e);}
  finally{$('refresh').disabled=false;}
}
function selectedRegions(){const symbol=$('asset-filter').value;return data.regions.filter(r=>symbol==='all'||data.assets.find(a=>a.symbol===symbol)?.regions.includes(r.id));}
function render(){
  const age=(Date.now()-Date.parse(data.generated_at))/60000;
  const unavailable=Object.values(data.sources).filter(s=>s.status==='unavailable').length;
  $('health').textContent=age>60?'快照陈旧':unavailable?'部分来源不可用':'采集运行正常';
  $('health').className='pill '+(age>60?'bad':unavailable?'warn':'');
  $('updated').textContent='快照 '+dt(data.generated_at)+' · 浏览器每 60 秒检查';
  $('notice').textContent=age>60?'快照已超过 60 分钟，预警应视为过期。':'观察模式：地理异常不等于买卖信号。ETF 行情可能延迟；尚未验证卫星信息的成本后交易优势。';
  if($('asset-filter').options.length===1)data.assets.forEach(a=>{const o=document.createElement('option');o.value=a.symbol;o.textContent=a.symbol+' · '+a.name;$('asset-filter').append(o);});
  $('asset-grid').innerHTML=data.assets.map(a=>{const q=data.quotes[a.symbol];return '<div class="asset-card"><div class="asset-symbol">'+esc(a.symbol)+'<span class="future-tag">'+esc(a.future)+'</span></div><div class="asset-name">'+esc(a.name)+'</div><div class="price">'+(q?'$'+Number(q.price).toFixed(2):'—')+'</div><div class="tiny">'+(q?'行情 '+dt(q.observed_at):'行情不可用')+'</div><div class="tiny">'+esc(a.mechanism)+'</div></div>';}).join('');
  $('research-message').textContent=data.research.message;
  $('backtest-panel').innerHTML='<div class="stat-row"><span>历史交易优势</span><strong>尚未验证</strong></div><div class="stat-row"><span>经验证的方向信号</span><strong>0</strong></div><div class="stat-row"><span>真实回测收益 / 胜率</span><strong>— / —</strong></div><p>已建立时点回放框架。观察预警不擅自转换成多空交易，因此不会生成虚构绩效。</p>';
  $('source-table').innerHTML=Object.entries(data.sources).map(([name,s])=>'<tr><td>'+esc(name)+'</td><td>'+badge(s.status)+'</td><td>'+dt(s.checked_at)+'</td><td>'+(s.error?esc(s.error):s.observation_quality?badge(s.observation_quality):s.truncated?'事件结果达到上限，可能截断':'<a target="_blank" rel="noopener" href="'+esc(safeURL(s.endpoint))+'">来源 ↗</a>')+'</td></tr>').join('');
  renderFiltered();
}
function renderFiltered(){
  const regions=selectedRegions(),ids=new Set(regions.map(r=>r.id));
  document.querySelectorAll('.asset-card').forEach((el,i)=>el.classList.toggle('selected',data.assets[i].symbol===$('asset-filter').value));
  $('satellite-grid').innerHTML=regions.map(r=>{const s=data.satellites[r.id];return '<article class="satellite-card"><div class="sat-head">'+esc(r.name)+'</div><div class="sat-visual"><canvas id="ndvi-'+esc(r.id)+'" width="32" height="32"></canvas><small>Sentinel-2 · NDVI 样本</small></div><div class="sat-details">'+(s?'<div class="sat-values"><span>'+(s.median_ndvi===null?'—':Number(s.median_ndvi).toFixed(3))+' <small>NDVI</small></span><span>'+Math.round(s.clear_fraction*100)+'% <small>有效</small></span></div>'+badge(s.quality)+'<p>观测 '+dt(s.observed_at)+'<br>首次可用 '+dt(s.available_at)+'</p><a target="_blank" rel="noopener" href="'+esc(safeURL(s.url))+'">像元来源 ↗</a>':'暂无有效影像')+'</div></article>';}).join('');
  regions.forEach(r=>drawNDVI(r.id,data.satellites[r.id]?.grid));
  const alerts=data.alerts.filter(a=>ids.has(a.region_id));
  const active=alerts.filter(a=>Date.parse(a.expires_at)>Date.now());
  $('alert-count').textContent=active.length+' 条未到期观察';
  $('alerts').innerHTML=alerts.length?alerts.map(a=>'<div class="alert"><div>'+badge(Date.parse(a.expires_at)>Date.now()?'watch':'stale')+'</div><div><div class="alert-title">'+esc(a.title)+'</div><p>'+esc(regions.find(r=>r.id===a.region_id)?.name)+' · '+esc(a.symbols.join(' / '))+'</p><p>'+esc(a.reason)+'</p></div><div><p>'+esc(a.source)+'<br>'+dt(a.observed_at)+'</p><a target="_blank" rel="noopener" href="'+esc(safeURL(a.url))+'">核验来源 ↗</a></div></div>').join(''):'<div class="empty">当前筛选区域内没有满足时效条件的官方事件观察。没有预警不代表没有风险；请结合数据源状态判断。</div>';
  drawMap(regions);
}
function drawNDVI(id,grid){const c=$('ndvi-'+id),ctx=c.getContext('2d');ctx.fillStyle='#34403b';ctx.fillRect(0,0,32,32);if(!grid)return;grid.forEach((row,y)=>row.forEach((v,x)=>{if(v===null)return;const t=Math.max(0,Math.min(1,(v+0.1)/0.9));ctx.fillStyle='rgb('+Math.round(155-96*t)+','+Math.round(95+93*t)+','+Math.round(60+25*t)+')';ctx.fillRect(x,y,1,1);}));}
function drawMap(regions){
  const project=([lon,lat])=>[(lon+130)/70*800,(55-lat)/35*430];
  const path=ring=>ring.map((p,i)=>(i?'L':'M')+project(p).map(x=>x.toFixed(1)).join(',')).join('')+'Z';
  let html='';
  for(let lon=-130;lon<=-60;lon+=10){const [x]=project([lon,20]);html+='<path d="M'+x+',0V430" stroke="#203830"/><text x="'+(x+4)+'" y="420" fill="#536d61" font-size="10">'+lon+'°</text>';}
  for(let lat=20;lat<=55;lat+=5){const [,y]=project([-130,lat]);html+='<path d="M0,'+y+'H800" stroke="#203830"/>';}
  for(const f of base?.features||[]){const polys=f.geometry.type==='MultiPolygon'?f.geometry.coordinates:[f.geometry.coordinates];for(const p of polys)html+='<path d="'+p.map(path).join('')+'" fill="#18322a" stroke="#50644b" stroke-width=".7" fill-rule="evenodd"/>';}
  for(const r of regions){const [x1,y1]=project([r.exposure_bbox[0],r.exposure_bbox[3]]),[x2,y2]=project([r.exposure_bbox[2],r.exposure_bbox[1]]);html+='<rect x="'+x1+'" y="'+y1+'" width="'+(x2-x1)+'" height="'+(y2-y1)+'" fill="#b4f09822" stroke="#a4db88"/><text x="'+(x1+5)+'" y="'+(y1+13)+'" fill="#d0efc4" font-size="11">'+esc(r.id.toUpperCase())+'</text>';const [x,y]=project([(r.bbox[0]+r.bbox[2])/2,(r.bbox[1]+r.bbox[3])/2]);html+='<circle cx="'+x+'" cy="'+y+'" r="3" fill="#c9f7af"/>';}
  for(const e of [...data.events,...data.storms]){if(!e.bbox)continue;const [lon,lat]=[(e.bbox[0]+e.bbox[2])/2,(e.bbox[1]+e.bbox[3])/2];if(lon<-130||lon>-60||lat<20||lat>55)continue;const [x,y]=project([lon,lat]);html+='<circle cx="'+x+'" cy="'+y+'" r="4" fill="#eac280" opacity=".85"><title>'+esc(e.title)+' · '+dt(e.observed_at)+'</title></circle>';}
  $('map-content').innerHTML=html;
}
$('refresh').addEventListener('click',refresh);$('asset-filter').addEventListener('change',()=>data&&renderFiltered());refresh();setInterval(refresh,60000);
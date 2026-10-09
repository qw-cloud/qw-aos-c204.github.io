"use strict";
const $=id=>document.getElementById(id);
const esc=x=>String(x??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dt=x=>x?new Date(x).toLocaleString('zh-CN',{timeZone:'America/New_York',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false})+' ET':'—';
const statusNames={ok:'成功',cached:'缓存',watch:'观察',unavailable:'不可用',usable_observation:'可用观测',stale:'已陈旧',insufficient_clear_pixels:'云 / 有效像元不足',invalid_future_timestamp:'时间无效',source_unavailable:'来源失败'};
const badge=s=>'<span class="state '+(['ok','cached','usable_observation'].includes(s)?'':s==='unavailable'||s==='source_unavailable'?'bad':'warn')+'">'+esc(statusNames[s]||s)+'</span>';
function safeURL(u){try{const x=new URL(u);return ['https:','http:'].includes(x.protocol)?x.href:'#';}catch{return '#';}}
let data=null,base=null,backtest=null,research=null,marketSeries=null,satelliteHistory=null;
const REPO_NAME=location.pathname.startsWith('/qw-aos-c204.github.io/')?'qw-aos-c204.github.io':'qw-cloud.github.io';
const RAW_BASE='https://raw.githubusercontent.com/qw-cloud/'+REPO_NAME+'/main/projects/geo-alpha/';
async function readJSON(path){const base=location.hostname.endsWith('github.io')?RAW_BASE:'';const r=await fetch(base+path+'?t='+Date.now(),{cache:'no-store'});if(!r.ok)throw Error(path+': HTTP '+r.status);return r.json();}
async function refresh(){
  $('refresh').disabled=true;
  try{
    const latest=await readJSON('data/latest.json');
    data=latest;
    if(!base)base=await readJSON('data/basemap.json').catch(()=>({features:[]}));
    backtest=await readJSON('data/backtest.json').catch(()=>null);
    [research,marketSeries,satelliteHistory]=await Promise.all([
      readJSON('data/research_results.json').catch(()=>null),
      readJSON('data/market_series.json').catch(()=>null),
      readJSON('data/satellite_history.json').catch(()=>null)]);
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
  $('asset-grid').innerHTML=data.assets.map(a=>{const q=data.quotes[a.symbol];return '<button class="asset-card" data-symbol="'+esc(a.symbol)+'"><div class="asset-symbol">'+esc(a.symbol)+'<span class="future-tag">'+esc(a.future)+'</span></div><div class="asset-name">'+esc(a.name)+'</div><div class="price">'+(q?'$'+Number(q.price).toFixed(2):'—')+'</div><svg class="sparkline" id="spark-'+esc(a.symbol)+'" viewBox="0 0 180 45" aria-label="'+esc(a.symbol)+'最近一年价格趋势"></svg><div class="tiny">'+(q?'行情 '+dt(q.observed_at):'行情不可用')+'</div><div class="tiny">'+esc(a.mechanism)+'</div></button>';}).join('');
  document.querySelectorAll('.asset-card').forEach(el=>el.addEventListener('click',()=>{$('asset-filter').value=el.dataset.symbol;renderFiltered();}));
  data.assets.forEach(a=>sparkline($('spark-'+a.symbol),marketSeries?.[a.symbol]?.map(x=>x.close)||[]));
  const success=Object.values(data.sources).filter(s=>['ok','cached'].includes(s.status)).length;
  $('kpi-grid').innerHTML=[['采集来源',success+' / '+Object.keys(data.sources).length,'已返回真实数据'],['历史遥感样本',research?.usable_observations??'—','合格局部样本'],['历史决策',research?.satellite_decisions?.length??'—','固定每月20日'],['当前观察',data.alerts.length,'无自动资金执行']].map(([label,value,sub])=>'<div class="kpi"><span>'+esc(label)+'</span><strong>'+esc(value)+'</strong><small>'+esc(sub)+'</small></div>').join('');
  $('research-message').textContent=data.research.message;
  $('backtest-panel').innerHTML='<div class="stat-row"><span>卫星优势</span><strong>尚未验证</strong></div><div class="stat-row"><span>执行假设</span><strong>下一开盘 · 无杠杆</strong></div><div class="stat-row"><span>双边成本</span><strong>20 bps / 0.20%</strong></div><p>卫星规则与行情基线分开列出。历史可用时间为保守重建，不能当成真实前瞻结果。</p>';
  $('source-table').innerHTML=Object.entries(data.sources).map(([name,s])=>'<tr><td>'+esc(name)+'</td><td>'+badge(s.status)+'</td><td>'+dt(s.checked_at)+'</td><td>'+(s.error?esc(s.error):s.observation_quality?badge(s.observation_quality):s.truncated?'事件结果达到上限，可能截断':'<a target="_blank" rel="noopener" href="'+esc(safeURL(s.endpoint))+'">来源 ↗</a>')+'</td></tr>').join('');
  renderFiltered();
  updateResearchOptions();
}
function renderFiltered(){
  const regions=selectedRegions(),ids=new Set(regions.map(r=>r.id));
  document.querySelectorAll('.asset-card').forEach((el,i)=>el.classList.toggle('selected',data.assets[i].symbol===$('asset-filter').value));
  $('satellite-grid').innerHTML=regions.map(r=>{const s=data.satellites[r.id];return '<article class="satellite-card"><div class="sat-head">'+esc(r.name)+'</div><div class="sat-visual"><canvas id="ndvi-'+esc(r.id)+'" width="32" height="32"></canvas><small>Sentinel-2 · NDVI 样本</small></div><div class="sat-details">'+(s?'<div class="sat-values"><span>'+(s.median_ndvi===null?'—':Number(s.median_ndvi).toFixed(3))+' <small>NDVI</small></span><span>'+Math.round(s.clear_fraction*100)+'% <small>有效</small></span></div>'+badge(s.quality)+'<p>观测 '+dt(s.observed_at)+'<br>首次可用 '+dt(s.available_at)+'</p><a target="_blank" rel="noopener" href="'+esc(safeURL(s.url))+'">像元来源 ↗</a>':'暂无有效影像')+'</div></article>';}).join('');
  regions.forEach(r=>{drawNDVI(r.id,data.satellites[r.id]?.grid);const card=$('ndvi-'+r.id).closest('.satellite-card');const observations=Object.values(satelliteHistory?.observations||{}).filter(o=>o.region_id===r.id&&o.status==='usable').sort((a,b)=>a.observed_at.localeCompare(b.observed_at));if(observations.length){const el=document.createElement('div');el.className='ndvi-history';el.innerHTML='<span>历史局部 NDVI · '+observations.length+' 次合格观测</span><svg viewBox="0 0 180 45"></svg>';card.append(el);sparkline(el.querySelector('svg'),observations.map(o=>o.median_ndvi));}});
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
function sparkline(svg,values){if(values.length<2){svg.innerHTML='';return;}let lo=Math.min(...values),hi=Math.max(...values);if(lo===hi)hi=lo+1;const points=values.map((v,i)=>(i/(values.length-1)*180).toFixed(2)+','+(42-(v-lo)/(hi-lo)*38).toFixed(2)).join(' ');svg.innerHTML='<polyline points="'+points+'" fill="none" stroke="'+(values.at(-1)>=values[0]?'#b4f098':'#efad8d')+'" stroke-width="1.6"/>';}
const pct=x=>x===null||x===undefined?'—':(x*100).toFixed(2)+'%';
const num=x=>x===null||x===undefined?'—':Number(x).toFixed(2);
function updateResearchOptions(){const type=$('strategy-select').value,old=$('research-symbol').value;const results=research?.[type]||[];$('research-symbol').innerHTML=results.map(r=>'<option value="'+esc(r.symbol)+'">'+esc(r.symbol)+'</option>').join('');if(results.some(r=>r.symbol===old))$('research-symbol').value=old;renderResearch();}
function renderResearch(){
  const type=$('strategy-select').value,results=research?.[type]||[],r=results.find(x=>x.symbol===$('research-symbol').value),m=r?.metrics||{};
  $('backtest-period').textContent=r?.start_date?r.start_date+' → '+r.end_date:'等待历史研究结果';
  $('research-metrics').innerHTML=[['成本后收益',pct(m.net_return)],['年化收益',pct(m.cagr)],['最大回撤',pct(m.max_drawdown)],['Sharpe',num(m.sharpe)],['交易次数',m.closed_trades??'—'],['胜率',pct(m.win_rate)]].map(([label,value])=>'<div class="metric"><span>'+label+'</span><strong>'+value+'</strong></div>').join('');
  lineChart($('equity-chart'),r?.curve||[],[{key:'equity',color:'#b4f098'},{key:'benchmark',color:'#8fbde0'}],false);
  lineChart($('drawdown-chart'),r?.curve||[],[{key:'drawdown',color:'#efad8d'}],true);
  $('backtest-caveat').textContent=type==='satellite_exploration'?'卫星探索：两块局部地表样本，无作物分类及天气基线；可用时间采用“拍摄后48小时与目录创建时间的较晚者”。样本少，未证明样本外优势。':'行情基线：SMA20/60固定参数，只使用前一日已完成价格。此结果不包含卫星信息，未优化参数，未认证样本外表现。';
  $('results-table').innerHTML=results.map(x=>{const v=x.metrics||{};return '<tr><td>'+esc(x.symbol)+' · '+(type==='market_baseline'?'SMA 基线':'NDVI 探索')+'</td><td class="'+(v.net_return>=0?'positive':'negative')+'">'+pct(v.net_return)+'</td><td>'+pct(v.buy_hold_return)+'</td><td>'+pct(v.max_drawdown)+'</td><td>'+num(v.sharpe)+'</td><td>'+(v.closed_trades??'—')+' / '+pct(v.win_rate)+'</td></tr>';}).join('');
  $('strategy-method').textContent=type==='satellite_exploration'?'每年5–8月固定20日决策，选18日前已拍摄、场景云量≤30%、目录已创建且有效像元≥25%的最近图块；Iowa与Illinois两样本的平均NDVI比上一年同月下降≥0.10时，下一开盘做多CORN或SOYB，持有10个交易日后在下一开盘退出。所有结果为回顾性探索；盈亏包含双边20bps成本，空仓收益为0。':'20日收盘均价高于60日均价时下一开盘全额买入，否则空仓。无杠杆；每次买卖各10bps成本；现金利息、分红、税费和固定数据成本未计入。净值按每日收盘盯市，结束时平仓。';
  $('trade-ledger').innerHTML=(r?.trades||[]).map(t=>'<tr><td>'+dt(t.entry_at)+'</td><td>'+dt(t.exit_at)+'</td><td>'+num(t.entry_price)+'</td><td>'+num(t.exit_price)+'</td><td class="'+(t.net_return>=0?'positive':'negative')+'">'+pct(t.net_return)+'</td></tr>').join('')||'<tr><td colspan="5">没有符合规则的交易；收益为零或数据尚不足。</td></tr>';
  $('decision-ledger').innerHTML=(research?.satellite_decisions||[]).map(d=>'<tr><td>'+d.year+'-'+String(d.month).padStart(2,'0')+'</td><td>'+d.current_ndvi.toFixed(4)+'</td><td>'+d.previous_year_ndvi.toFixed(4)+'</td><td>'+d.delta.toFixed(4)+'</td><td>'+(d.triggered?'是':'否 · 空仓')+'</td></tr>').join('')||'<tr><td colspan="5">尚无可比较的历史样本。</td></tr>';
}
function lineChart(svg,curve,series,percent){
  const W=800,H=percent?230:300,left=58,right=20,top=18,bottom=34;
  if(curve.length<2){svg.innerHTML='<text x="400" y="120" text-anchor="middle" fill="#92a79d">暂无足够数据</text>';return;}
  const values=curve.flatMap(p=>series.map(s=>p[s.key])).filter(Number.isFinite);let lo=Math.min(...values),hi=Math.max(...values);if(percent){hi=Math.max(0,hi);lo=Math.min(-.01,lo);}if(lo===hi){lo-=.01;hi+=.01;}const margin=(hi-lo)*.08;lo-=margin;hi+=margin;
  const x=i=>left+i/(curve.length-1)*(W-left-right),y=v=>top+(hi-v)/(hi-lo)*(H-top-bottom);let html='';
  for(let i=0;i<5;i++){const v=lo+(hi-lo)*i/4,yy=y(v);html+='<path d="M'+left+','+yy+'H'+(W-right)+'" stroke="#293d34"/><text x="'+(left-8)+'" y="'+(yy+4)+'" text-anchor="end" fill="#92a79d" font-size="11">'+(percent?(v*100).toFixed(1)+'%':v.toFixed(2))+'</text>';}
  for(let i=0;i<4;i++){const idx=Math.round(i/3*(curve.length-1));html+='<text x="'+x(idx)+'" y="'+(H-10)+'" text-anchor="middle" fill="#92a79d" font-size="11">'+curve[idx].date+'</text>';}
  for(const s of series){const points=curve.map((p,i)=>x(i).toFixed(1)+','+y(p[s.key]).toFixed(1)).join(' ');if(percent)html+='<polygon points="'+x(0)+','+y(0)+' '+points+' '+x(curve.length-1)+','+y(0)+'" fill="'+s.color+'20"/>';html+='<polyline points="'+points+'" fill="none" stroke="'+s.color+'" stroke-width="2"/>';}
  const last=curve.at(-1);html+='<text x="'+(W-right)+'" y="14" text-anchor="end" fill="#b4f098" font-size="11">末值 '+(percent?pct(last[series[0].key]):num(last[series[0].key]))+'</text>';svg.innerHTML=html;
}
$('strategy-select').addEventListener('change',updateResearchOptions);$('research-symbol').addEventListener('change',renderResearch);
$('refresh').addEventListener('click',refresh);$('asset-filter').addEventListener('change',()=>data&&renderFiltered());refresh();setInterval(refresh,60000);

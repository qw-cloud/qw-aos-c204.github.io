(function(){
  var latest=null, history=[];
  var rows=document.getElementById('fieldRows');
  var sort=document.getElementById('sortField');
  var historyField=document.getElementById('historyField');

  function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
  function state(v){return v>=60?'good':v>=42?'neutral':'bad';}
  function fmt(v,d){return (v===null||v===undefined||Number.isNaN(Number(v)))?'—':Number(v).toFixed(d===undefined?0:d);}
  function outlook(v,base){
    if(v===null||v===undefined||base===null||base===undefined) return ['flat','Insufficient history'];
    var diff=v-base;
    if(diff>2) return ['up','▲ '+fmt(diff,1)];
    if(diff<-2) return ['down','▼ '+fmt(Math.abs(diff),1)];
    return ['flat','→ Stable'];
  }

  function renderSummary(){
    var fields=latest.fields||[];
    var valid=fields.filter(function(f){return f.jobs!==null&&f.jobs!==undefined;});
    var avgTiming=fields.length?fields.reduce(function(a,f){return a+(f.timing_score||50)},0)/fields.length:50;
    var avgSent=fields.length?fields.reduce(function(a,f){return a+(f.sentiment_score||50)},0)/fields.length:50;
    var conf=latest.model&&latest.model.confidence!==undefined?latest.model.confidence:5;
    document.getElementById('marketScore').textContent=fmt(avgTiming,0);
    document.getElementById('marketGauge').style.setProperty('--score',clamp(avgTiming,0,100));
    document.getElementById('marketRegime').textContent=avgTiming>=62?'Favorable':avgTiming>=45?'Neutral / mixed':'Tight market';
    document.getElementById('confidenceBar').querySelector('i').style.width=clamp(conf,0,100)+'%';
    document.getElementById('confidenceText').textContent=fmt(conf,0)+'%';
    document.getElementById('trackedFields').textContent=fields.length;
    document.getElementById('totalJobs').textContent=valid.length?valid.reduce(function(a,f){return a+Number(f.jobs||0)},0).toLocaleString():'—';
    document.getElementById('sentimentScore').textContent=fmt(avgSent,0)+'/100';
    document.getElementById('macroValue').textContent=latest.macro&&latest.macro.education_openings_rate!==null?fmt(latest.macro.education_openings_rate,1)+'%':'—';
    document.getElementById('freshness').textContent='Updated '+(latest.generated_at||'—').replace('T',' ').replace('Z',' UTC');
  }

  function renderRows(){
    var mode=sort.value;
    var data=(latest.fields||[]).slice().sort(function(a,b){
      var key=mode==='jobs'?'jobs':mode==='sentiment'?'sentiment_score':mode==='pressure'?'pressure_index':'timing_score';
      return Number(b[key]||0)-Number(a[key]||0);
    });
    rows.innerHTML='';
    data.forEach(function(f){
      var o=outlook(f.forecast_30d,f.timing_score);
      var el=document.createElement('div');el.className='field-row';
      el.innerHTML=
        '<div class="field-name"><strong>'+f.name+'</strong><small>'+((f.source_note||'daily public signal'))+'</small></div>'+
        '<div class="metric"><strong>'+fmt(f.jobs,0)+'</strong><small>'+((f.job_momentum===null||f.job_momentum===undefined)?'warming up':((f.job_momentum>=0?'+':'')+fmt(f.job_momentum,1)+'% vs baseline'))+'</small></div>'+
        '<div class="score-pill '+state(f.sentiment_score||50)+'"><i class="dot"></i><span>'+fmt(f.sentiment_score,0)+'</span></div>'+
        '<div class="metric"><strong>'+fmt(f.pressure_index,0)+'</strong><div class="mini-bar"><i style="width:'+clamp(f.pressure_index||50,0,100)+'%"></i></div></div>'+
        '<div class="score-pill '+state(f.timing_score||50)+'"><i class="dot"></i><strong>'+fmt(f.timing_score,0)+'</strong></div>'+
        '<div class="outlook '+o[0]+'">'+o[1]+'</div>';
      rows.appendChild(el);
    });
  }

  function initFieldPicker(){
    historyField.innerHTML='';
    (latest.fields||[]).forEach(function(f){
      var opt=document.createElement('option');opt.value=f.slug;opt.textContent=f.name;historyField.appendChild(opt);
    });
    if((latest.fields||[]).some(function(f){return f.slug==='economics-finance'}))historyField.value='economics-finance';
  }

  function historySeries(slug){
    return history.map(function(d){
      var f=(d.fields||[]).find(function(x){return x.slug===slug});
      return f?{date:d.date,value:f.timing_score}:null;
    }).filter(Boolean);
  }

  function renderHistory(){
    var host=document.getElementById('historyChart');
    var series=historySeries(historyField.value);
    if(series.length<2){host.innerHTML='<div class="empty-state">The chart will populate after two or more daily snapshots. Forecast confidence rises as the panel grows.</div>';return;}
    var W=760,H=325,p=28;
    var min=Math.max(0,Math.min.apply(null,series.map(function(d){return d.value}))-8);
    var max=Math.min(100,Math.max.apply(null,series.map(function(d){return d.value}))+8);
    if(max-min<12){min=Math.max(0,min-6);max=Math.min(100,max+6);}
    function x(i){return p+(W-2*p)*(i/(series.length-1));}
    function y(v){return H-p-(H-2*p)*((v-min)/(max-min||1));}
    var pts=series.map(function(d,i){return x(i)+','+y(d.value)}).join(' ');
    var area='M '+x(0)+' '+(H-p)+' L '+series.map(function(d,i){return x(i)+' '+y(d.value)}).join(' L ')+' L '+x(series.length-1)+' '+(H-p)+' Z';
    var grid=[0,.25,.5,.75,1].map(function(t){var yy=p+(H-2*p)*t;var val=max-(max-min)*t;return '<line x1="'+p+'" y1="'+yy+'" x2="'+(W-p)+'" y2="'+yy+'" class="chart-grid"/><text x="4" y="'+(yy+3)+'" class="chart-label">'+fmt(val,0)+'</text>';}).join('');
    host.innerHTML='<svg class="svg-chart" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none"><defs><linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#7ee6b8" stop-opacity=".22"/><stop offset="100%" stop-color="#7ee6b8" stop-opacity="0"/></linearGradient></defs>'+grid+'<path d="'+area+'" class="chart-area"/><polyline points="'+pts+'" class="chart-line"/></svg>';
  }

  function renderDrivers(){
    var fields=latest.fields||[];
    var avgJob=fields.length?fields.reduce(function(a,f){return a+(f.job_momentum||0)},0)/fields.length:null;
    var avgSent=fields.length?fields.reduce(function(a,f){return a+(f.sentiment_score||50)},0)/fields.length:50;
    var macro=latest.macro&&latest.macro.education_openings_rate;
    var drv=document.getElementById('drivers');
    drv.innerHTML=
      '<div class="driver"><span>Vacancy momentum</span><strong>'+((avgJob===null)?'Warming up':((avgJob>=0?'+':'')+fmt(avgJob,1)+'%'))+'</strong><p>Field-level job counts versus each discipline’s own rolling baseline.</p></div>'+
      '<div class="driver"><span>Hiring sentiment</span><strong>'+fmt(avgSent,0)+'/100</strong><p>Headline language around hiring, freezes, cuts, expansion and recruiting.</p></div>'+
      '<div class="driver"><span>Education macro</span><strong>'+(macro===null||macro===undefined?'—':fmt(macro,1)+'% openings rate')+'</strong><p>U.S. private educational-services JOLTS signal from FRED/BLS.</p></div>';
    var market=fields.length?fields.reduce(function(a,f){return a+(f.timing_score||50)},0)/fields.length:50;
    var f30=latest.model&&latest.model.market_forecast_30d!==undefined?latest.model.market_forecast_30d:market;
    var f90=latest.model&&latest.model.market_forecast_90d!==undefined?latest.model.market_forecast_90d:market;
    document.getElementById('forecast30').textContent=fmt(f30,0);
    document.getElementById('forecast90').textContent=fmt(f90,0);
    document.getElementById('forecastNote').textContent=(latest.model&&latest.model.note)||'Forecasts remain deliberately conservative until the repository has accumulated enough daily history.';
  }

  Promise.all([
    fetch('./data/latest.json',{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error('latest');return r.json()}),
    fetch('./data/history.json',{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error('history');return r.json()})
  ]).then(function(v){
    latest=v[0];history=Array.isArray(v[1])?v[1]:[];
    renderSummary();renderRows();initFieldPicker();renderHistory();renderDrivers();
  }).catch(function(){
    document.getElementById('freshness').textContent='Data temporarily unavailable';
    rows.innerHTML='<div style="padding:30px;color:var(--muted);font-size:11px">The dashboard shell is online, but the daily data file could not be loaded.</div>';
  });

  sort.addEventListener('change',renderRows);
  historyField.addEventListener('change',renderHistory);
})();
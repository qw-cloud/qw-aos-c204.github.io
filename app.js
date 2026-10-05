(function(){
  var root = document.documentElement;
  var body = document.body;
  var themeToggle = document.getElementById('themeToggle');
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.metric-tab'));
  var chart = document.getElementById('benchmarkChart');
  var chartMetric = document.getElementById('chartMetric');
  var navLinks = Array.prototype.slice.call(document.querySelectorAll('.nav-link'));
  var playButton = document.getElementById('playPipeline');
  var steps = Array.prototype.slice.call(document.querySelectorAll('.pipe-step'));
  var links = Array.prototype.slice.call(document.querySelectorAll('.pipe-link'));
  var timer = null;

  var models = [
    {name:'Logistic',accuracy:90.80,precision:82.80,recall:78.60},
    {name:'Random Forest',accuracy:95.08,precision:93.01,recall:87.90},
    {name:'XGBoost',accuracy:95.73,precision:94.20,recall:90.10},
    {name:'LightGBM',accuracy:95.55,precision:93.70,recall:89.80},
    {name:'SVM · RBF',accuracy:95.72,precision:94.10,recall:90.40},
    {name:'KNN',accuracy:94.75,precision:88.90,recall:91.60},
    {name:'Basic CNN',accuracy:97.02,precision:92.39,recall:95.92},
    {name:'Deep CNN',accuracy:90.20,precision:99.79,recall:60.82},
    {name:'Custom ResNet',accuracy:98.62,precision:97.36,recall:97.12}
  ];

  function renderChart(metric){
    chart.innerHTML = '';
    var best = Math.max.apply(null, models.map(function(m){return m[metric];}));
    models.forEach(function(model, i){
      var row = document.createElement('div');
      row.className = 'bar-row' + (model[metric] === best ? ' best' : '');
      var label = document.createElement('span');
      label.className = 'bar-label';
      label.textContent = model.name;
      var track = document.createElement('div');
      track.className = 'bar-track';
      var fill = document.createElement('div');
      fill.className = 'bar-fill';
      track.appendChild(fill);
      var value = document.createElement('span');
      value.className = 'bar-value';
      value.textContent = model[metric].toFixed(2) + '%';
      row.appendChild(label); row.appendChild(track); row.appendChild(value);
      chart.appendChild(row);
      window.setTimeout(function(){ fill.style.width = Math.max(0, Math.min(100, model[metric])) + '%'; }, 40 + i * 35);
    });
    chartMetric.textContent = metric.toUpperCase() + ' / %';
  }

  tabs.forEach(function(tab){
    tab.addEventListener('click', function(){
      tabs.forEach(function(t){t.classList.remove('active');});
      tab.classList.add('active');
      renderChart(tab.getAttribute('data-metric'));
    });
  });

  themeToggle.addEventListener('click', function(){
    body.classList.toggle('light');
    themeToggle.textContent = body.classList.contains('light') ? '◑' : '◐';
  });

  function activatePipeline(index){
    steps.forEach(function(step, i){ step.classList.toggle('active', i <= index); });
    links.forEach(function(link, i){ link.classList.toggle('active', i < index); });
  }

  playButton.addEventListener('click', function(){
    if(timer){ window.clearInterval(timer); timer = null; activatePipeline(0); playButton.textContent = 'Play pipeline ▶'; return; }
    var i = 0;
    activatePipeline(0);
    playButton.textContent = 'Stop ×';
    timer = window.setInterval(function(){
      i += 1;
      activatePipeline(i);
      if(i >= steps.length - 1){
        window.clearInterval(timer); timer = null;
        window.setTimeout(function(){ playButton.textContent = 'Replay pipeline ↻'; }, 350);
      }
    }, 650);
  });

  steps.forEach(function(step, index){
    step.addEventListener('click', function(){ activatePipeline(index); });
  });

  var observer = new IntersectionObserver(function(entries){
    entries.forEach(function(entry){
      if(entry.isIntersecting){
        navLinks.forEach(function(link){link.classList.remove('active');});
        var target = navLinks.find(function(link){return link.getAttribute('href') === '#' + entry.target.id;});
        if(target){target.classList.add('active');}
      }
    });
  }, {rootMargin:'-35% 0px -55% 0px',threshold:0});

  ['overview','benchmark','diagnostics','pipeline'].forEach(function(id){
    var el = document.getElementById(id);
    if(el){observer.observe(el);}
  });

  renderChart('accuracy');
})();
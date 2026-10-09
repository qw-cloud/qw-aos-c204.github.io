"""Reproducible exploratory research. No result here certifies a trading edge."""
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
import math
import numpy as np

from .core import ROOT, load, now, parse, request_json, sample_item, save, stamp

UTC=timezone.utc


def monthly_sample(region, year, month):
    decision=datetime(year,month,20,23,59,tzinfo=UTC)
    # Only images acquired by the 18th may enter the 20th's fixed decision.
    end=datetime(year,month,18,23,59,tzinfo=UTC)
    query={"collections":["sentinel-2-l2a"],"bbox":region["bbox"],"limit":40,
           "datetime":f"{year}-{month:02}-01T00:00:00Z/{stamp(end)}",
           "sortby":[{"field":"properties.datetime","direction":"desc"}]}
    obj=request_json("https://earth-search.aws.element84.com/v1/search",query)
    candidates=[]
    for f in obj.get("features",[]):
        b=f['bbox'];r=region['bbox'];p=f['properties']
        if not (b[0]<=r[0] and b[1]<=r[1] and b[2]>=r[2] and b[3]>=r[3]):continue
        if p.get('eo:cloud_cover',100)>30:continue
        created=p.get('created')
        if not created:continue
        assumed=max(parse(p['datetime'])+timedelta(hours=48),parse(created))
        if assumed>decision:continue
        candidates.append((f,assumed))
    if not candidates:
        return {"region_id":region['id'],"year":year,"month":month,"decision_at":stamp(decision),
                "status":"no_eligible_image","reason":"No sufficiently clear, catalog-created image before the fixed decision"}
    # Deterministic most recent eligible image, rather than hindsight selection by returns.
    f,assumed=candidates[0]
    s=sample_item(region,f)
    return {k:v for k,v in {**s,"year":year,"month":month,"decision_at":stamp(decision),
                           "assumed_available_at":stamp(assumed),"retrieved_at":stamp(),
                           "status":"usable" if s['clear_fraction']>=.25 and s['median_ndvi'] is not None else "insufficient_clear_pixels"}.items()
            if k not in ('grid','thumbnail','cached')}


def collect_history(root=ROOT):
    root=Path(root);config=load(root/'config.json',{})
    history=load(root/'data/satellite_history.json',{"observations":{},"errors":{}})
    pending=[]
    for year in range(2023,now().year+1):
        for month in (5,6,7,8):
            if datetime(year,month,21,tzinfo=UTC)>now():continue
            for region in config['regions']:
                if region['id'] not in ('iowa','illinois'):continue
                key=f"{region['id']}:{year}:{month}"
                if key not in history['observations']:pending.append((key,region,year,month))
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(monthly_sample,r,y,m):key for key,r,y,m in pending}
        for f in as_completed(futures):
            key=futures[f]
            try:
                history['observations'][key]=f.result();history['errors'].pop(key,None)
                print(key,history['observations'][key]['status'],flush=True)
            except Exception as exc:
                history['errors'][key]={"error":f"{type(exc).__name__}: {str(exc)[:200]}","checked_at":stamp()}
                print(key,'failed',flush=True)
            history['generated_at']=stamp();save(root/'data/satellite_history.json',history)
    history['protocol']={"years":"2023 onward","months":[5,6,7,8],"decision_day":20,"latest_acquisition_day":18,
                         "assumed_latency_hours":48,"maximum_scene_cloud_percent":30,"minimum_clear_fraction":.25,
                         "regions":["iowa","illinois"],"historical_first_publication_verified":False}
    history['generated_at']=stamp();save(root/'data/satellite_history.json',history)
    return history


def simulate(bars, targets, start_index=0, round_trip_cost_bps=20):
    """Unlevered, long/flat, next-open execution and daily close marking."""
    if round_trip_cost_bps<0:raise ValueError('Costs must be nonnegative')
    data=bars[start_index:]
    if len(data)<2:return {"status":"insufficient_history","trades":[],"curve":[],"metrics":{}}
    c=round_trip_cost_bps/20000
    cash=1.0;shares=0.0;entry=None;trades=[];curve=[];daily=[];yearly=defaultdict(lambda:1.0)
    peak=1.0;max_dd=0.0;previous=1.0;benchmark_peak=1.0;benchmark_shares=1/(data[0]['open']*(1+c))
    for j,b in enumerate(data):
        absolute=start_index+j;target=int(targets[absolute])
        if target not in (0,1):raise ValueError('Only unlevered long/flat targets are supported')
        if shares and not target:
            cash=shares*b['open']*(1-c);shares=0.0
            trades.append({**entry,"exit_at":b['session_open_at'],"exit_price":b['open'],"net_return":cash/entry['capital']-1,"forced_end":False})
            entry=None
        if not shares and target:
            entry={"entry_at":b['session_open_at'],"entry_price":b['open'],"capital":cash}
            shares=cash/(b['open']*(1+c));cash=0.0
        equity=cash+shares*b['close']
        if j==len(data)-1 and shares:
            cash=shares*b['close']*(1-c);shares=0.0;equity=cash
            trades.append({**entry,"exit_at":b['session_close_at'],"exit_price":b['close'],"net_return":cash/entry['capital']-1,"forced_end":True})
        r=equity/previous-1;daily.append(r);yearly[b['date'][:4]]*=1+r;previous=equity
        peak=max(peak,equity);dd=equity/peak-1;max_dd=min(max_dd,dd)
        benchmark=benchmark_shares*b['close']*(1-c if j==len(data)-1 else 1)
        benchmark_peak=max(benchmark_peak,benchmark)
        curve.append({"date":b['date'],"equity":round(equity,7),"drawdown":round(dd,7),
                      "benchmark":round(benchmark,7),"position":target})
    days=(datetime.fromisoformat(data[-1]['date'])-datetime.fromisoformat(data[0]['date'])).days
    std=float(np.std(daily,ddof=1)) if len(daily)>1 else 0
    metrics={"net_return":equity-1,"buy_hold_return":curve[-1]['benchmark']-1,
             "cagr":equity**(365.25/days)-1 if days>0 and equity>0 else None,
             "max_drawdown":max_dd,"sharpe":float(np.mean(daily))/std*math.sqrt(252) if std>0 else None,
             "closed_trades":len(trades),"win_rate":sum(t['net_return']>0 for t in trades)/len(trades) if trades else None,
             "exposure":sum(int(targets[start_index+j]) for j in range(len(data)))/len(data),
             "sessions":len(data),"year_returns":{y:v-1 for y,v in sorted(yearly.items())}}
    return {"status":"exploratory","start_date":data[0]['date'],"end_date":data[-1]['date'],"metrics":metrics,
            "curve":curve,"trades":trades,"round_trip_cost_bps":round_trip_cost_bps,
            "return_convention":"ETF price returns; no dividends, cash interest, taxes, fixed data costs, or leverage",
            "drawdown_convention":"daily close marks; intraday drawdowns can be larger","out_of_sample_certified":False}


def trend_baseline(bars,cost=20):
    if len(bars)<61:return {"status":"insufficient_history","metrics":{},"curve":[],"trades":[]}
    # Today at open uses only the previous 60 completed closes.
    targets=[0]*len(bars)
    for i in range(60,len(bars)):
        fast=sum(b['close'] for b in bars[i-20:i])/20
        slow=sum(b['close'] for b in bars[i-60:i])/60
        targets[i]=int(fast>slow)
    return {"strategy":"SMA20 / SMA60 long-flat","source":"market_only_not_satellite",**simulate(bars,targets,60,cost)}


def satellite_signals(history):
    obs=history.get('observations',{});signals=[];decisions=[]
    years=sorted({o['year'] for o in obs.values()})
    for year in years:
        if year<2024:continue
        for month in (5,6,7,8):
            current=[obs.get(f'{r}:{year}:{month}') for r in ('iowa','illinois')]
            previous=[obs.get(f'{r}:{year-1}:{month}') for r in ('iowa','illinois')]
            if not all(o and o.get('status')=='usable' for o in current+previous):continue
            decision=parse(current[0]['decision_at'])
            if any(parse(o['assumed_available_at'])>decision for o in current+previous):continue
            current_ndvi=sum(o['median_ndvi'] for o in current)/2
            previous_ndvi=sum(o['median_ndvi'] for o in previous)/2
            delta=current_ndvi-previous_ndvi
            record={"decision_at":stamp(decision),"year":year,"month":month,"current_ndvi":round(current_ndvi,4),
                    "previous_year_ndvi":round(previous_ndvi,4),"delta":round(delta,4),"triggered":delta<=-.10,
                    "item_ids":[o['item_id'] for o in current]}
            decisions.append(record)
            if record['triggered']:
                for symbol in ('CORN','SOYB'):signals.append({"symbol":symbol,"available_at":stamp(decision),"direction":1,
                                                           "basis":"two local samples NDVI year-on-year drop >=0.10",**record})
    return signals,decisions


def satellite_backtest(bars,signals,symbol,cost=20):
    targets=[0]*len(bars)
    start=next((i for i,b in enumerate(bars) if b['date']>='2024-05-20'),len(bars))
    for s in signals:
        if s['symbol']!=symbol:continue
        entry=next((i for i,b in enumerate(bars) if parse(b['session_open_at'])>parse(s['available_at'])),None)
        if entry is None:continue
        for i in range(entry,min(entry+10,len(bars))):targets[i]=1
    return {"strategy":"Local NDVI year-on-year drop, long 10 sessions","source":"historical_satellite_exploration",**simulate(bars,targets,start,cost),
            "availability_convention":"max(acquisition + 48h, catalog created), fixed monthly decision; not verified historical first publication",
            "limitations":"Two local land-cover samples, no crop mask or weather baseline; few seasonal observations; not certified out-of-sample"}


def build_research_report(root=ROOT):
    root=Path(root);config=load(root/'config.json',{});history=load(root/'data/satellite_history.json',{})
    signals,decisions=satellite_signals(history)
    baseline=[];geo=[];series={}
    for a in config['assets']:
        payload=load(root/'data/prices'/(a['symbol']+'.json'),{})
        bars=sorted(payload.get('bars',[]),key=lambda b:b['session_open_at'])
        b=trend_baseline(bars);b['symbol']=a['symbol'];baseline.append(b)
        series[a['symbol']]=[{"date":x['date'],"close":x['close']} for x in bars[-252:]]
        if a['symbol'] in ('CORN','SOYB'):
            g=satellite_backtest(bars,signals,a['symbol']);g['symbol']=a['symbol']
            g['cost_sensitivity']={str(c):satellite_backtest(bars,signals,a['symbol'],c)['metrics'].get('net_return') for c in (5,20,50)}
            geo.append(g)
    save(root/'data/market_series.json',series)
    result={"status":"exploratory_actual_data","generated_at":stamp(),"market_baseline":baseline,"satellite_exploration":geo,
            "satellite_decisions":decisions,"observations_count":len(history.get('observations',{})),
            "usable_observations":sum(o.get('status')=='usable' for o in history.get('observations',{}).values()),
            "directional_rule_threshold":-.10,"no_parameter_search":True,
            "warning":"Retrospective exploration, not proven satellite alpha. Prices are indicative ETF history; satellite availability is reconstructed."}
    save(root/'data/research_results.json',result)
    return {k:v for k,v in result.items() if k not in ('market_baseline','satellite_exploration')}

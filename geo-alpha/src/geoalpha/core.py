from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[2]
HEADERS = {"User-Agent": "GeoAlpha/0.2 (public geospatial research)", "Accept": "application/json"}


def now():
    return datetime.now(UTC)


def stamp(value=None):
    return (value or now()).isoformat().replace("+00:00", "Z")


def parse(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("Timestamp must include a timezone")
    return result.astimezone(UTC)


def age_hours(value, at=None):
    return ((at or now()) - parse(value)).total_seconds() / 3600


def load(path, default):
    try:
        return json.loads(Path(path).read_text())
    except FileNotFoundError:
        return default


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")))
    temp.replace(path)


def request_json(url, payload=None, retries=2):
    data = None if payload is None else json.dumps(payload).encode()
    headers = dict(HEADERS)
    if payload is not None:
        headers["Content-Type"] = "application/json"
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=25) as r:
                raw = r.read(8_000_001)
                if len(raw) > 8_000_000:
                    raise ValueError("Response exceeds safety size limit")
                return json.loads(raw)
        except (OSError, ValueError) as exc:
            if attempt == retries:
                raise exc
            time.sleep(0.5 * (attempt + 1))


def contains(bbox, lon, lat):
    return bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]


def intersect_bbox(a, b):
    return not (a[2] < b[0] or b[2] < a[0] or a[3] < b[1] or b[3] < a[1])


def geometry_bbox(geometry):
    def points(v):
        if isinstance(v, list) and len(v) >= 2 and isinstance(v[0], (int, float)):
            yield v[:2]
        elif isinstance(v, list):
            for child in v:
                yield from points(child)
    p = list(points(geometry.get("coordinates", [])))
    if not p:
        return None
    return [min(v[0] for v in p), min(v[1] for v in p), max(v[0] for v in p), max(v[1] for v in p)]


def eonet():
    url = "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&days=30&limit=250"
    obj = request_json(url)
    if not isinstance(obj.get("events"), list):
        raise ValueError("EONET events schema missing")
    events = []
    for item in obj["events"]:
        geometries = item.get("geometry", [])
        if not geometries:
            continue
        g = max(geometries, key=lambda x: x.get("date", ""))
        box = geometry_bbox(g)
        if box is None:
            continue
        events.append({"id":item["id"], "title":item["title"], "observed_at":g["date"],
                       "bbox":box,"coordinates":g.get("coordinates"),"geometry_type":g.get("type"),
                       "categories":[c["id"] for c in item.get("categories",[])],
                       "sources":item.get("sources",[]),"url":item.get("link",url),
                       "source_kind":"curated_event_catalog_not_satellite_detection"})
    return {"events":events,"url":url,"truncated":len(obj["events"]) >= 250}


def nhc():
    url = "https://www.nhc.noaa.gov/CurrentStorms.json"
    obj = request_json(url)
    if not isinstance(obj.get("activeStorms"), list):
        raise ValueError("NHC activeStorms schema missing")
    storms = []
    for s in obj["activeStorms"]:
        lon, lat = float(s["longitudeNumeric"]), float(s["latitudeNumeric"])
        storms.append({"id":s["id"],"title":s["name"],"observed_at":s["lastUpdate"],"bbox":[lon,lat,lon,lat],
                       "wind_knots":float(s.get("intensity") or 0),
                       "url":s.get("forecastGraphics",{}).get("url",url),
                       "advisory_url":s.get("publicAdvisory",{}).get("url",url),
                       "source_kind":"official_storm_advisory_not_raw_satellite"})
    return {"storms":storms,"url":url}


def market(symbol, history_range="5y"):
    last_error = None
    for host in ("query1", "query2"):
        url = f"https://{host}.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?range={history_range}&interval=1d"
        try:
            obj = request_json(url, retries=1)
            result = obj["chart"]["result"][0]
            meta = result["meta"]
            bars = []
            quote = result["indicators"]["quote"][0]
            completed_at = now()
            for i, t in enumerate(result.get("timestamp", [])):
                if not all(quote.get(k,[None] * (i+1))[i] is not None for k in ("open","high","low","close")):
                    continue
                # Include only completed daily sessions in research bars. Live price is separate.
                session_open = datetime.fromtimestamp(t,UTC)
                session_close = session_open + timedelta(hours=6,minutes=30)
                if session_close >= completed_at:
                    continue
                bars.append({"date":session_open.astimezone(__import__('zoneinfo').ZoneInfo('America/New_York')).date().isoformat(),
                             "session_open_at":stamp(session_open),"session_close_at":stamp(session_close),
                             **{k:float(quote[k][i]) for k in ("open","high","low","close")}})
            observed = datetime.fromtimestamp(meta["regularMarketTime"],UTC)
            if observed > completed_at + timedelta(minutes=5):
                raise ValueError("Quote timestamp lies in the future")
            return {"symbol":symbol,"price":float(meta["regularMarketPrice"]),"currency":meta.get("currency","USD"),
                    "observed_at":stamp(observed),"instrument":"ETF","quote_type":"public indicative quote; delay not guaranteed",
                    "url":url,"bars":bars,"exchange_timezone":meta.get("exchangeTimezoneName")}
        except (OSError,ValueError,KeyError,TypeError,IndexError) as exc:
            last_error = exc
    raise ValueError(f"Yahoo indicative quotes unavailable: {last_error}")


def reflectance(array, asset, rescaled=False):
    """Earth Search may already apply BOA offsets; honor its product property."""
    band = asset.get("raster:bands",[{}])[0]
    offset = 0.0 if rescaled else float(band.get("offset",0))
    return array * float(band.get("scale",0.0001)) + offset


def compute_ndvi(red, nir, scl, red_asset, nir_asset, rescaled=False):
    import numpy as np
    r = reflectance(red.astype(float),red_asset,rescaled)
    n = reflectance(nir.astype(float),nir_asset,rescaled)
    valid = ((red > 0) & (nir > 0) & np.isin(scl,[4,5]) & ((n+r)>0.001))
    ndvi = np.full(red.shape,np.nan)
    ndvi[valid] = (n[valid]-r[valid])/(n[valid]+r[valid])
    valid &= (ndvi >= -1) & (ndvi <= 1)
    values = ndvi[valid]
    return {"median_ndvi":round(float(np.median(values)),4) if values.size else None,
            "clear_fraction":round(float(valid.mean()),4),"vegetation_fraction":round(float((scl==4).mean()),4),
            "grid":[[round(float(ndvi[y,x]),3) if valid[y,x] else None for x in range(red.shape[1])] for y in range(red.shape[0])]}


def sample_item(region, f):
    """Read actual pixels of one fixed region and one catalog item."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.transform import from_bounds
    from rasterio.vrt import WarpedVRT
    checked = stamp()
    arrays = {}
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",GDAL_HTTP_TIMEOUT="25",GDAL_HTTP_MAX_RETRY="2"):
        for band in ("red","nir","scl"):
            with rasterio.open(f["assets"][band]["href"]) as src:
                with WarpedVRT(src,crs="EPSG:4326",transform=from_bounds(*region["bbox"],32,32),width=32,height=32,
                               resampling=Resampling.nearest,src_nodata=0,nodata=0) as v:
                    arrays[band] = v.read(1)
    rescaled = f["properties"].get("earthsearch:boa_offset_applied",False)
    if not isinstance(rescaled,bool):
        raise ValueError("Unrecognized BOA offset metadata")
    stats = compute_ndvi(arrays["red"],arrays["nir"],arrays["scl"],f["assets"]["red"],f["assets"]["nir"],rescaled)
    available = stamp()
    return {"region_id":region["id"],"item_id":f["id"],"observed_at":f["properties"]["datetime"],
            "catalog_created_at":f["properties"].get("created"),"checked_at":checked,"available_at":available,
            "cloud_cover_scene":f["properties"].get("eo:cloud_cover"),"assets":{k:f["assets"][k]["href"] for k in ("red","nir","scl")},
            "thumbnail":f["assets"].get("thumbnail",{}).get("href"),"rescaled_boa":rescaled,
            "url":f"https://earth-search.aws.element84.com/v1/collections/sentinel-2-l2a/items/{f['id']}",
            "sample_grid_size":32,"scope":"local_land_cover_not_crop_classified","cached":False,**stats}


def satellite(region, previous=None, check_hours=6):
    if previous and age_hours(previous["checked_at"]) < check_hours:
        return {**previous,"cached":True}
    query = {"collections":["sentinel-2-l2a"],"bbox":region["bbox"],"limit":8,
             "datetime":f"{stamp(now()-timedelta(days=45))}/{stamp()}",
             "sortby":[{"field":"properties.datetime","direction":"desc"}]}
    obj = request_json("https://earth-search.aws.element84.com/v1/search",query)
    features = obj.get("features",[])
    if not features:
        raise ValueError("No Sentinel-2 item covering region in last 45 days")
    full = [f for f in features if f["bbox"][0] <= region["bbox"][0] and f["bbox"][1] <= region["bbox"][1]
            and f["bbox"][2] >= region["bbox"][2] and f["bbox"][3] >= region["bbox"][3]]
    f = (full or features)[0]
    if previous and f["id"] == previous.get("item_id"):
        return {**previous,"checked_at":stamp(),"cached":True}
    return sample_item(region,f)


def quality(s, config, at=None):
    if s is None:
        return "unavailable"
    hours = age_hours(s["observed_at"],at)
    if hours < -1:
        return "invalid_future_timestamp"
    if hours > config["gates"]["satellite_max_age_days"]*24:
        return "stale"
    if s["clear_fraction"] < config["gates"]["minimum_clear_fraction"] or s["median_ndvi"] is None:
        return "insufficient_clear_pixels"
    return "usable_observation"


def build_alerts(config, satellites, events, storms, at=None):
    at = at or now()
    alerts = []
    for region in config["regions"]:
        symbols = [a["symbol"] for a in config["assets"] if region["id"] in a["regions"]]
        for source,records,limit in (("NASA EONET",events,config["gates"]["event_max_age_hours"]),
                                    ("NOAA NHC",storms,config["gates"]["nhc_max_age_hours"])):
            for event in records:
                if source == "NASA EONET" and "prescribed" in event.get("title", "").lower():
                    # Controlled burns are catalogued as fires, but are not a supply-disruption alert.
                    continue
                hours = age_hours(event["observed_at"],at)
                if hours < -1 or hours > limit or not intersect_bbox(region["exposure_bbox"],event["bbox"]):
                    continue
                alerts.append({"id":f"{source}:{event['id']}:{region['id']}","region_id":region["id"],"title":event["title"],
                               "symbols":symbols,"source":source,"observed_at":event["observed_at"],"url":event["url"],
                               "status":"watch","direction":0,"reason":"地理范围重叠；供需方向与价格优势尚未验证",
                               "source_kind":event["source_kind"],"expires_at":stamp(parse(event["observed_at"])+timedelta(hours=limit))})
    return alerts


def run(root=ROOT):
    root = Path(root)
    config = load(root/"config.json",{})
    data = root/"data"
    previous = load(data/"latest.json",{})
    previous_sources = previous.get("sources",{})
    started = stamp()
    results,health = {},{}
    tasks = {"eonet":eonet,"nhc":nhc}
    tasks.update({f"market:{a['symbol']}":lambda symbol=a["symbol"]:market(symbol) for a in config["assets"]})
    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(func):name for name,func in tasks.items()}
        for future in as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
                finished = stamp()
                results[name] = result
                health[name] = {"status":"ok","checked_at":finished,"last_success_at":finished,
                                "endpoint":result["url"],"truncated":result.get("truncated",False)}
            except Exception as exc:
                health[name] = {"status":"unavailable","checked_at":stamp(),"last_success_at":previous_sources.get(name,{}).get("last_success_at"),
                                "error":f"{type(exc).__name__}: {str(exc)[:220]}"}
    satellites = {}
    observations = load(data/"observations.json",{})
    for region in config["regions"]:
        key = "satellite:"+region["id"]
        try:
            old = previous.get("satellites",{}).get(region["id"])
            s = satellite(region,old,config["satellite_check_hours"])
            item_key = region["id"]+":"+s["item_id"]
            if item_key in observations:
                s["available_at"] = observations[item_key]["available_at"]
            s["quality"] = quality(s,config)
            satellites[region["id"]] = s
            health[key] = {"status":"cached" if s["cached"] else "ok","checked_at":s["checked_at"],
                           "last_success_at":stamp(),"endpoint":s["url"],"observation_quality":s["quality"]}
            observations.setdefault(item_key,{k:v for k,v in s.items() if k not in ("grid","thumbnail","assets","cached")})
        except Exception as exc:
            health[key] = {"status":"unavailable","checked_at":stamp(),"error":f"{type(exc).__name__}: {str(exc)[:220]}"}
            old = previous.get("satellites",{}).get(region["id"])
            if old:
                satellites[region["id"]] = {**old,"quality":"source_unavailable","cached":True}
    events = results.get("eonet",{}).get("events",[])
    storms = results.get("nhc",{}).get("storms",[])
    quotes = {a["symbol"]:results.get("market:"+a["symbol"]) for a in config["assets"]}
    for symbol,quote in quotes.items():
        if quote:
            save(data/"prices"/(symbol+".json"),quote)
    finished = stamp()
    alerts = build_alerts(config,satellites,events,storms)
    snapshot = {"schema_version":1,"generated_at":finished,"started_at":started,
                "mode":"observation_and_paper_research","refresh_minutes":config["refresh_minutes"],
                "sources":health,"regions":config["regions"],"assets":config["assets"],"satellites":satellites,
                "quotes":{k:({x:y for x,y in v.items() if x!='bars'} if v else None) for k,v in quotes.items()},
                "events":events,"storms":storms,"alerts":alerts,
                "research":{"status":"not_validated","directional_model_validated":False,
                            "message":"未建立作物分类/供给模型，未证明价格预测优势；当前所有预警均为观察，非买卖指令。"}}
    save(data/"observations.json",observations)
    save(data/"latest.json",snapshot)
    # Compact timestamped snapshots retain first-seen evidence without duplicating imagery grids.
    compact = {**snapshot,"satellites":{k:{x:y for x,y in v.items() if x not in ('grid','thumbnail','assets')} for k,v in satellites.items()}}
    save(data/"archive"/(now().strftime("%Y%m%dT%H%M%SZ")+".json"),compact)
    history = load(data/"alerts.json",{})
    for a in alerts:
        old = history.get(a["id"],{})
        history[a["id"]] = {**a,"first_seen_at":old.get("first_seen_at",finished),"last_seen_at":finished,
                              "available_at":old.get("available_at",finished)}
    save(data/"alerts.json",history)
    return snapshot


def replay(signals, bars, symbol, hold=5, cost_bps=20):
    """Daily research fills after availability. Requires explicit externally validated directions."""
    if hold < 1 or cost_bps < 0:
        raise ValueError("Invalid holding period or costs")
    ordered = sorted(bars,key=lambda b:b["session_open_at"])
    trades = []
    occupied_until = None
    for s in sorted(signals,key=lambda x:x["available_at"]):
        if s.get("symbol") != symbol or s.get("direction") not in (-1,1) or s.get("validated") is not True:
            continue
        available = parse(s["available_at"])
        if occupied_until and available <= occupied_until:
            continue
        entry = next((i for i,b in enumerate(ordered) if parse(b["session_open_at"]) > available),None)
        if entry is None or entry+hold-1 >= len(ordered):
            continue
        first,last = ordered[entry],ordered[entry+hold-1]
        occupied_until = parse(last["session_close_at"])
        gross = s["direction"]*(last["close"]/first["open"]-1)
        trades.append({"available_at":s["available_at"],"entry_at":first["session_open_at"],"exit_at":last["session_close_at"],
                       "direction":s["direction"],"entry_price":first["open"],"exit_price":last["close"],
                       "net_return":gross-cost_bps/10000})
    equity,peak,drawdown = 1.0,1.0,0.0
    for t in trades:
        equity *= 1+t["net_return"]
        peak = max(peak,equity)
        drawdown = min(drawdown,equity/peak-1)
    return {"symbol":symbol,"status":"research_only" if trades else "not_ready","trades":trades,
            "net_return":equity-1 if trades else None,"trade_close_drawdown":drawdown if trades else None,
            "win_rate":sum(t['net_return']>0 for t in trades)/len(trades) if trades else None,
            "limitations":"ETF indicative daily OHLC; closes-only drawdown; no intraday execution proof; excludes fixed data costs"}


def report(root=ROOT):
    root = Path(root)
    config = load(root/"config.json",{})
    # Built-in watch alerts never become directional trades by assumption.
    signals = load(root/"data"/"research_signals.json",[])
    results = [replay(signals,load(root/"data"/"prices"/(a["symbol"]+".json"),{}).get("bars",[]),a["symbol"],
                      config["research"]["holding_sessions"],config["research"]["round_trip_cost_bps"]) for a in config["assets"]]
    obj = {"generated_at":stamp(),"status":"not_ready" if not any(r['trades'] for r in results) else "research_only",
           "reason":"仅观察信号尚不具备经验证的多空方向，故不生成虚构绩效。","results":results}
    from .research import build_research_report
    obj["baseline"] = build_research_report(root)
    save(root/"data"/"backtest.json",obj)
    return obj

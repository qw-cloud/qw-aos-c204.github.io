#!/usr/bin/env python3
"""
Academic Market Timing daily collector.

No paid APIs or secrets are required. The script uses:
- jobs.ac.uk public search page for discipline-level live vacancy counts
- Google News RSS for hiring-expansion / hiring-stress headline sentiment
- optional Reddit RSS for community sentiment when available
- FRED's public CSV endpoint for the U.S. private educational-services JOLTS job-openings rate

The model is intentionally transparent. "Competition pressure" is a market-tightness proxy,
not applicants-per-opening. Forecasts stay close to neutral until enough history accumulates.
"""
from __future__ import annotations

import csv
import io
import json
import math
import re
import statistics
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
LATEST = DATA / "latest.json"
HISTORY = DATA / "history.json"

UA = "AcademicMarketTiming/1.0 (+https://github.com/qw-cloud/qw-aos-c204.github.io)"

FIELDS = [
    {"slug":"computer-science-ai","name":"Computer Science & AI","jobs_label":"Computer Sciences","query":"computer science AI faculty hiring university"},
    {"slug":"health-medical","name":"Health & Medical","jobs_label":"Health & Medical","query":"medical school health faculty hiring university"},
    {"slug":"engineering","name":"Engineering & Technology","jobs_label":"Engineering & Technology","query":"engineering faculty hiring university"},
    {"slug":"physical-environmental","name":"Physical & Environmental Sciences","jobs_label":"Physical & Environmental Sciences","query":"physics chemistry environmental science faculty hiring university"},
    {"slug":"biology","name":"Biological Sciences","jobs_label":"Biological Sciences","query":"biology life sciences faculty hiring university"},
    {"slug":"math-statistics","name":"Mathematics & Statistics","jobs_label":"Mathematics & Statistics","query":"mathematics statistics faculty hiring university"},
    {"slug":"psychology","name":"Psychology","jobs_label":"Psychology","query":"psychology faculty hiring university"},
    {"slug":"business-management","name":"Business & Management","jobs_label":"Business & Management Studies","query":"business school management faculty hiring university"},
    {"slug":"social-sciences","name":"Sociology, Demography & Social Sciences","jobs_label":"Social Sciences","query":"sociology demography social science faculty hiring university"},
    {"slug":"economics-finance","name":"Economics & Finance","jobs_label":"Economics","query":"economics finance faculty hiring university"},
    {"slug":"politics-government","name":"Politics & Government","jobs_label":"Politics & Government","query":"political science politics faculty hiring university"},
    {"slug":"humanities","name":"Humanities","jobs_label":"Humanities","query":"humanities history literature philosophy faculty hiring university"},
]

POSITIVE = {
    "hire":1.0,"hiring":1.0,"recruit":0.8,"recruiting":0.8,"opening":0.7,"openings":0.7,
    "expand":1.0,"expansion":1.0,"growth":0.8,"search":0.35,"vacancy":0.5,"vacancies":0.5,
    "investment":0.5,"new faculty":1.2,"faculty search":1.0,"adds faculty":1.2
}
NEGATIVE = {
    "freeze":-1.5,"freezes":-1.5,"hiring freeze":-1.8,"cut":-1.0,"cuts":-1.0,
    "layoff":-1.5,"layoffs":-1.5,"deficit":-0.8,"budget crisis":-1.2,"retrenchment":-1.3,
    "closure":-1.5,"closures":-1.5,"cancel":-0.8,"cancels":-0.8,"paused":-0.9,
    "decline":-0.7,"shortfall":-0.8,"austerity":-1.1
}

def fetch(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept":"text/html,application/xml,text/xml,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")

def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(hi, v))

def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def scrape_jobs_counts():
    html = fetch("https://www.jobs.ac.uk/search/list.html")
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    # The page exposes a full discipline facet list with "Discipline 123".
    labels = [
        "Agriculture, Food & Veterinary","Architecture, Building & Planning","Biological Sciences",
        "Business & Management Studies","Computer Sciences","Creative Arts & Design","Economics",
        "Education Studies (inc. TEFL)","Engineering & Technology","Health & Medical",
        "Historical & Philosophical Studies","Information Management & Librarianship",
        "Languages, Literature & Culture","Law","Mathematics & Statistics","Media & Communications",
        "Physical & Environmental Sciences","Politics & Government","Psychology","Social Sciences",
        "Sport & Leisure"
    ]
    out = {}
    for label in labels:
        m = re.search(re.escape(label) + r"\s+(\d{1,5})\b", text, re.I)
        if m:
            out[label] = int(m.group(1))
    if not out:
        raise RuntimeError("Could not parse jobs.ac.uk discipline counts")
    # Humanities is a transparent composite proxy rather than a native facet.
    out["Humanities"] = (
        out.get("Historical & Philosophical Studies", 0)
        + out.get("Languages, Literature & Culture", 0)
    )
    return out

def rss_titles(url):
    try:
        raw = fetch(url)
        root = ET.fromstring(raw)
        titles = []
        for item in root.findall(".//item")[:40]:
            title = item.findtext("title") or ""
            if title.strip():
                titles.append(title.strip())
        return titles
    except Exception:
        return []

def google_news_titles(query):
    q = urllib.parse.quote(query + ' ("faculty" OR "professor" OR university) (hiring OR jobs OR freeze OR cuts OR recruitment)')
    return rss_titles("https://news.google.com/rss/search?q=" + q + "&hl=en-US&gl=US&ceid=US:en")

def reddit_titles(query):
    # Optional community layer. It is deliberately non-fatal because Reddit can rate-limit RSS.
    q = urllib.parse.quote(query)
    urls = [
        "https://www.reddit.com/r/AskAcademia/search.rss?q=" + q + "&restrict_sr=1&sort=new&t=month",
        "https://www.reddit.com/r/academia/search.rss?q=" + q + "&restrict_sr=1&sort=new&t=month",
    ]
    titles = []
    for u in urls:
        titles += rss_titles(u)
        time.sleep(0.15)
    return titles[:40]

def lexicon_score(titles):
    if not titles:
        return 50.0, 0
    vals = []
    for t in titles:
        s = " " + re.sub(r"[^a-z0-9 ]+", " ", t.lower()) + " "
        score = 0.0
        for phrase, w in POSITIVE.items():
            if phrase in s: score += w
        for phrase, w in NEGATIVE.items():
            if phrase in s: score += w
        vals.append(score)
    avg = statistics.fmean(vals) if vals else 0.0
    return clamp(50 + 18 * math.tanh(avg / 1.4)), len(titles)

def field_sentiment(field):
    news = google_news_titles(field["query"])
    community = reddit_titles(field["query"].split()[0] + " faculty jobs")
    ns, nn = lexicon_score(news)
    cs, cn = lexicon_score(community)
    if cn:
        score = 0.72 * ns + 0.28 * cs
    else:
        score = ns
    return round(score, 1), {"news_items":nn,"community_items":cn}

def fred_macro():
    # BLS/JOLTS private educational services job-openings rate via FRED, percent.
    series = "JTU6100JOR"
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=" + series
    raw = fetch(url)
    rows = list(csv.DictReader(io.StringIO(raw)))
    vals = []
    for row in rows:
        try:
            vals.append((row["DATE"], float(row[series])))
        except Exception:
            pass
    if not vals:
        return {"education_openings_rate":None,"series":series,"macro_score":50.0,"note":"FRED series unavailable"}
    recent = vals[-24:]
    current = vals[-1][1]
    hist = [v for _,v in recent]
    mu = statistics.fmean(hist)
    sd = statistics.pstdev(hist) or 1.0
    z = (current - mu) / sd
    score = clamp(50 + 12 * z)
    return {
        "education_openings_rate":round(current,2),
        "series":series,
        "observation_date":vals[-1][0],
        "macro_score":round(score,1),
        "note":"FRED/BLS JOLTS private educational services job-openings rate"
    }

def prior_series(history, slug, key):
    vals=[]
    for d in history:
        f=next((x for x in d.get("fields",[]) if x.get("slug")==slug),None)
        if f is not None and f.get(key) is not None:
            vals.append(float(f[key]))
    return vals

def job_signal(current, previous):
    if current is None:
        return 50.0, None
    if len(previous) < 3:
        return 50.0, None
    baseline = statistics.fmean(previous[-30:])
    if baseline <= 0:
        return 50.0, None
    pct = 100.0 * (current - baseline) / baseline
    score = clamp(50 + 30 * math.tanh(pct / 20.0))
    return score, pct

def linear_forecast(vals, horizon):
    if len(vals) < 5:
        return vals[-1] if vals else 50.0
    ys = vals[-30:]
    xs = list(range(len(ys)))
    mx = statistics.fmean(xs); my = statistics.fmean(ys)
    denom = sum((x-mx)**2 for x in xs) or 1
    slope = sum((x-mx)*(y-my) for x,y in zip(xs,ys))/denom
    slope = max(-0.45, min(0.45, slope))
    return clamp(ys[-1] + slope * horizon)

def main():
    DATA.mkdir(parents=True, exist_ok=True)
    history = load_json(HISTORY, [])
    today = datetime.now(timezone.utc).date().isoformat()

    try:
        counts = scrape_jobs_counts()
        jobs_ok = True
    except Exception as e:
        print("jobs.ac.uk warning:", e)
        counts = {}
        jobs_ok = False

    try:
        macro = fred_macro()
        macro_ok = macro.get("education_openings_rate") is not None
    except Exception as e:
        print("FRED warning:", e)
        macro = {"education_openings_rate":None,"series":"JTU6100JOR","macro_score":50.0,"note":str(e)}
        macro_ok = False

    fields=[]
    sentiment_success=0
    for field in FIELDS:
        jobs = counts.get(field["jobs_label"])
        previous_jobs = prior_series(history, field["slug"], "jobs")
        supply_score, momentum = job_signal(jobs, previous_jobs)

        try:
            sentiment, coverage = field_sentiment(field)
            if coverage["news_items"] or coverage["community_items"]:
                sentiment_success += 1
        except Exception as e:
            print("sentiment warning", field["slug"], e)
            sentiment, coverage = 50.0, {"news_items":0,"community_items":0}

        macro_score = float(macro.get("macro_score",50.0))
        timing = clamp(0.55*supply_score + 0.28*sentiment + 0.17*macro_score)

        # Pressure is the inverse of timing opportunities. It is explicitly a proxy.
        pressure = clamp(100 - timing)

        prior_timing = prior_series(history, field["slug"], "timing_score")
        all_timing = prior_timing + [timing]
        f30 = linear_forecast(all_timing, 30)
        f90 = linear_forecast(all_timing, 90)

        fields.append({
            "slug":field["slug"],"name":field["name"],"jobs":jobs,
            "sentiment_score":round(sentiment,1),
            "pressure_index":round(pressure,1),
            "timing_score":round(timing,1),
            "forecast_30d":round(f30,1),"forecast_90d":round(f90,1),
            "job_momentum":None if momentum is None else round(momentum,2),
            "source_note":"jobs.ac.uk + news sentiment",
            "coverage":coverage
        })
        time.sleep(0.2)

    existing_days = len({d.get("date") for d in history if d.get("date")})
    source_health = (1 if jobs_ok else 0) + (1 if macro_ok else 0) + (1 if sentiment_success >= len(FIELDS)//2 else 0)
    confidence = clamp(5 + min(65, existing_days*2.5) + source_health*10)

    market_now = statistics.fmean([f["timing_score"] for f in fields]) if fields else 50
    market_30 = statistics.fmean([f["forecast_30d"] for f in fields]) if fields else 50
    market_90 = statistics.fmean([f["forecast_90d"] for f in fields]) if fields else 50

    if existing_days < 5:
        note = "Early-stage signal: fewer than five historical snapshots. Forecasts are intentionally conservative."
    elif existing_days < 30:
        note = "Developing signal: the repository is building a useful daily baseline; forecast confidence is still moderate."
    else:
        note = "Mature daily panel: timing forecasts use up to the latest 30 observations with bounded trend extrapolation."

    snapshot = {
        "generated_at":datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),
        "date":today,"status":"live_snapshot",
        "macro":{k:v for k,v in macro.items() if k!="macro_score"},
        "model":{
            "confidence":round(confidence,1),
            "market_score":round(market_now,1),
            "market_forecast_30d":round(market_30,1),
            "market_forecast_90d":round(market_90,1),
            "history_days":existing_days+1,
            "note":note
        },
        "sources":{
            "jobs_ac_uk":jobs_ok,"fred":macro_ok,
            "sentiment_fields_with_coverage":sentiment_success
        },
        "fields":fields
    }

    # Replace today's snapshot if rerun, otherwise append. Keep two years.
    compact = {"date":today,"fields":[
        {k:f.get(k) for k in ("slug","jobs","sentiment_score","pressure_index","timing_score")}
        for f in fields
    ]}
    history = [d for d in history if d.get("date") != today]
    history.append(compact)
    history = sorted(history, key=lambda d:d.get("date",""))[-730:]

    LATEST.write_text(json.dumps(snapshot,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    HISTORY.write_text(json.dumps(history,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print("Updated", today, "market score", round(market_now,1), "confidence", round(confidence,1))

if __name__ == "__main__":
    main()

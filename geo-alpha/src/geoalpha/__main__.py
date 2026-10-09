import argparse
import json
from .core import ROOT, report, run

parser = argparse.ArgumentParser(description="GeoAlpha public-data monitor")
parser.add_argument("command",choices=["update","backtest","history"])
parser.add_argument("--root",default=str(ROOT))
args = parser.parse_args()
if args.command == "history":
    from .research import collect_history
    result = collect_history(args.root)
    print(json.dumps({"observations":len(result["observations"]),"errors":len(result["errors"])}))
    raise SystemExit(0)
result = run(args.root) if args.command == "update" else report(args.root)
if args.command == "update":
    print(json.dumps({"generated_at":result["generated_at"],"sources":{k:v["status"] for k,v in result["sources"].items()},"alerts":len(result["alerts"])},ensure_ascii=False))
else:
    from .core import load
    from pathlib import Path
    research = load(Path(args.root)/"data/research_results.json",{})
    print(json.dumps({"validated_signal_status":result["status"],"validated_trades":sum(len(r['trades']) for r in result['results']),"satellite_decisions":len(research.get("satellite_decisions",[])),"satellite_trades":sum(len(r["trades"]) for r in research.get("satellite_exploration",[])),"market_baseline_trades":sum(len(r["trades"]) for r in research.get("market_baseline",[]))}))

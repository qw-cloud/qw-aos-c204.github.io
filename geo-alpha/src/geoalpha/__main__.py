import argparse
import json
from .core import ROOT, report, run

parser = argparse.ArgumentParser(description="GeoAlpha public-data monitor")
parser.add_argument("command",choices=["update","backtest"])
parser.add_argument("--root",default=str(ROOT))
args = parser.parse_args()
result = run(args.root) if args.command == "update" else report(args.root)
if args.command == "update":
    print(json.dumps({"generated_at":result["generated_at"],"sources":{k:v["status"] for k,v in result["sources"].items()},"alerts":len(result["alerts"])},ensure_ascii=False))
else:
    print(json.dumps({"status":result["status"],"trades":sum(len(r['trades']) for r in result['results'])}))
"""Export everything the Chip Advisor frontend reads as static JSON in app/static/data/ (for Vercel).

Run from repo root after src/build_tables.py:  python app/export_static.py
Same numbers as app/server.py (it reuses its functions): 32 advice files, the rusher list, the replayed plays.
"""
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import server  # noqa: E402

OUT = server.STATIC / "data"


def dump(obj, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    r = server.edge.groupby("rusher_name").agg(rate=("rusher_base_pressure_rate", "median"), n=("pressure", "size"))
    r = r[r.n >= 30].sort_values("n", ascending=False)
    dump({"rushers": dict(zip(r.index, pd.cut(r.rate, server.BINS, labels=server.QUARTILES).astype(str)))}, OUT / "meta.json")
    plays = set()
    for sit in ["all", "early", "short", "long"]:
        for qi, q in enumerate(server.QUARTILES):
            for player in server.TYPES:
                a = server.advice(sit, q, player, None)
                dump(a, OUT / "advice" / f"{sit}_{qi}_{player}.json")
                plays |= {(p["g"], p["p"], p["chipper"], p["rusher"]) for p in a["plays"]}
    for g, p, chipper, rusher in sorted(plays):
        dump(server.play(g, p, chipper, rusher), OUT / "plays" / f"{g}_{p}_{chipper}.json")
    print(f"{len(plays)} actions, {sum(f.stat().st_size for f in OUT.rglob('*.json')) / 1e6:.1f} Mo -> {OUT}")

"""Chip Advisor: web app for coaches (Python stdlib server + pandas, frontend in app/static/).

Run from repo root:  python app/server.py   then open http://localhost:8000
Reads outputs/*.csv (python src/build_tables.py) for observed rates and data/ for play replays.
Observed rates only, no trained model. Coach briefing: Mistral (app/llm.py, key in .env).
"""
import json
import os
import sys
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
STATIC = (ROOT / "app" / "static").resolve()
sys.path.insert(0, str(ROOT / "app"))
from llm import coach_brief  # noqa: E402

SHORT_YD = 3        # 3e/4e et court = yardsToGo <= 3
LONG_CHIP_S = 0.6   # contact long = chip > 0,6 s
MIN_N = 30          # below this, the verdict is flagged as a trend
QUARTILES = ["Faible", "Moyen", "Bon", "Élite"]
TYPES = {"TE": "inline_TE", "RB": "backfield"}
FEATURED = (2021101000, 3729)  # NYJ, 2e et 2 : the chipping TE is open when the sack lands
SNAP_EV = {"ball_snap", "autoevent_ballsnap"}
END_EV = {"pass_forward": "Passe", "autoevent_passforward": "Passe", "qb_sack": "Sack", "qb_strip_sack": "Sack",
          "run": "Course", "pass_shovel": "Passe", "fumble": "Fumble"}
DOWN = {1: "1er", 2: "2e", 3: "3e", 4: "4e"}
TYPES_MIME = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
              ".js": "application/javascript; charset=utf-8", ".svg": "image/svg+xml"}


def fr(x):
    return f"{x:.1f}".replace(".", ",")


def num(x, d=4):
    return None if x is None or pd.isna(x) else round(float(x), d)


def wilson(k, n, z=1.96):
    if n == 0:
        return None, None
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def situation(df):
    third = df.down.isin([3, 4])
    return np.select([df.down.isin([1, 2]), third & (df.yardsToGo <= SHORT_YD), third], ["early", "short", "long"], "other")


edge = pd.read_csv(ROOT / "outputs" / "edge_rushers.csv")
chips = pd.read_csv(ROOT / "outputs" / "chips.csv")
edge = edge.join(chips.groupby(["gameId", "playId", "rusherId"]).chip_duration_s.max()
                 .rename_axis(["gameId", "playId", "nflId"]), on=["gameId", "playId", "nflId"])
_, BINS = pd.qcut(edge.rusher_base_pressure_rate, 4, retbins=True)
BINS[0], BINS[-1] = -np.inf, np.inf
for df in (edge, chips):
    df["situation"] = situation(df)
    df["quartile"] = pd.cut(df.rusher_base_pressure_rate, BINS, labels=QUARTILES).astype(str)
plays_tbl = pd.read_csv(ROOT / "data" / "plays.csv").set_index(["gameId", "playId"])
players_tbl = pd.read_csv(ROOT / "data" / "players.csv").set_index("nflId")
pff = pd.read_csv(ROOT / "data" / "pffScoutingData.csv", usecols=["gameId", "playId", "nflId", "pff_role"])
QB = pff[pff.pff_role == "Pass"].drop_duplicates(["gameId", "playId"]).set_index(["gameId", "playId"]).nflId


def outcome(res, yds):
    return {"S": f"sack, {abs(int(yds))} yd perdus", "C": f"passe complète, {int(yds)} yd", "I": "passe incomplète",
            "IN": "interception", "R": f"scramble, {int(yds)} yd"}.get(res, "")


def card(r, featured=False):
    kind = "sack" if r.passResult == "S" else "clean" if r.rusher_pressure == 0 else "pressure"
    return {"g": int(r.gameId), "p": int(r.playId), "chipper": int(r.nflId), "rusher": int(r.rusherId),
            "title": "Sack, TE libre ignoré" if featured else f"{r.possessionTeam} contre {r.defensiveTeam}",
            "sit": f"{DOWN.get(int(r.down), '')} et {int(r.yardsToGo)}, chip de {fr(r.chip_duration_s)} s",
            "kind": kind, "badge": {"sack": "Sack", "clean": "Aucune pression", "pressure": "Pression"}[kind]}


def meta():
    r = edge.groupby("rusher_name").agg(rate=("rusher_base_pressure_rate", "median"), n=("pressure", "size"))
    r = r[r.n >= 30].sort_values("n", ascending=False)
    return {"rushers": r.index.tolist()}


def advice(sit, q, player, rusher):
    if rusher and (edge.rusher_name == rusher).any():
        rate = edge.loc[edge.rusher_name == rusher, "rusher_base_pressure_rate"].median()
        q = str(pd.cut([rate], BINS, labels=QUARTILES)[0])
    e, c = edge[edge.quartile == q], chips[chips.quartile == q]
    if sit != "all":
        e, c = e[e.situation == sit], c[c.situation == sit]
    s = fr(LONG_CHIP_S)
    opts = [("none", "Sans chip", ~e.chipped, None),
            ("TE", "Chip TE", e.chip_type == "inline_TE", c.chip_type == "inline_TE"),
            ("RB", "Chip RB", e.chip_type == "backfield", c.chip_type == "backfield"),
            ("short", f"Contact ≤ {s} s", e.chipped & (e.chip_duration_s <= LONG_CHIP_S), c.chip_duration_s <= LONG_CHIP_S),
            ("long", f"Contact > {s} s", e.chipped & (e.chip_duration_s > LONG_CHIP_S), c.chip_duration_s > LONG_CHIP_S)]
    rows = {}
    for key, label, me, mc in opts:
        g = e[me]
        n, k = len(g), int(g.pressure.sum())
        lo, hi = wilson(k, n)
        cg = c[mc] if mc is not None else c.iloc[0:0]
        rows[key] = {"key": key, "label": label, "n": n, "rate": num(k / n) if n else None, "lo": num(lo), "hi": num(hi),
                     "release": num(cg.chipper_release_s.median()) if len(cg) else None}
    base, mine, short, long_ = rows["none"], rows[player], rows["short"], rows["long"]
    chip = bool(mine["n"] and base["n"] and mine["rate"] < base["rate"])
    length = "long" if short["n"] and long_["n"] and long_["rate"] < short["rate"] else "short"
    verdict = {"chip": chip, "length": length, "base": base["rate"], "mine": mine["rate"], "n": mine["n"],
               "fragile": min(base["n"], mine["n"]) < MIN_N,
               "release": long_["release"] if length == "long" else short["release"]}
    pool = c[(c.chip_type == TYPES[player]) & c.chip_duration_s.notna()]
    picks = pd.concat([pool[pool.passResult == "S"].head(2),
                       pool[(pool.rusher_pressure == 0) & (pool.passResult == "C")]
                       .sort_values("chip_duration_s", ascending=False).head(3),
                       pool[pool.rusher_pressure == 1].head(1)])
    picks = picks[~picks.set_index(["gameId", "playId"]).index.isin([FEATURED])].drop_duplicates(["gameId", "playId"])
    feat = chips[(chips.gameId == FEATURED[0]) & (chips.playId == FEATURED[1])].iloc[0]
    plays = [card(feat, featured=True)] + [card(r) for r in picks.itertuples()]
    return {"quartile": q, "verdict": verdict, "options": list(rows.values()), "plays": plays[:6]}


@lru_cache(maxsize=32)
def play(g, p, chipper, rusher):
    tr = pd.read_csv(ROOT / "data" / "tracking" / f"tracking_{g}.csv",
                     usecols=["playId", "nflId", "frameId", "team", "jerseyNumber", "playDirection", "x", "y", "event"])
    tr = tr[tr.playId == p].copy()
    if tr.playDirection.iloc[0] == "left":  # offense always moves toward +x
        tr["x"], tr["y"] = 120 - tr.x, 53.3 - tr.y
    ev = tr[tr.event.notna() & (tr.event != "None")].drop_duplicates("frameId")
    snap = int(ev[ev.event.isin(SNAP_EV)].frameId.min())
    ends = ev[(ev.frameId >= snap) & ev.event.isin(END_EV)]
    end = int(ends.frameId.iloc[0]) if len(ends) else int(tr.frameId.max())
    tr = tr[tr.frameId.between(max(1, snap - 5), min(int(tr.frameId.max()), end + 10))]
    ball = tr[tr.team == "football"].drop_duplicates("frameId").set_index("frameId")
    ppl = tr[tr.team != "football"].assign(nflId=lambda d: d.nflId.astype(int))
    ids = sorted(ppl.nflId.unique())
    px = ppl.pivot(index="frameId", columns="nflId", values="x").reindex(columns=ids)
    py = ppl.pivot(index="frameId", columns="nflId", values="y").reindex(columns=ids)
    frames = [{"t": round((f - snap) / 10, 2),
               "p": [None if np.isnan(a) else [round(a, 2), round(b, 2)] for a, b in zip(px.loc[f].values, py.loc[f].values)],
               "b": [round(ball.x[f], 2), round(ball.y[f], 2)] if f in ball.index else None} for f in px.index]
    pl = plays_tbl.loc[(g, p)]
    info = ppl.drop_duplicates("nflId").set_index("nflId")
    qb = QB.get((g, p))
    players = [{"num": int(info.jerseyNumber[i]), "side": "off" if info.team[i] == pl.possessionTeam else "def",
                "role": "chipper" if i == chipper else "rusher" if i == rusher else "qb" if i == qb else "",
                "pos": players_tbl.officialPosition.get(i, ""), "name": players_tbl.displayName.get(i, "")} for i in ids]
    los = float(ball.x.get(snap, ball.x.iloc[0]))
    ch = chips[(chips.gameId == g) & (chips.playId == p) & (chips.nflId == chipper)].iloc[0]
    m = {"title": f"{pl.possessionTeam} contre {pl.defensiveTeam}",
         "sub": f"{DOWN.get(int(pl.down), '')} et {int(pl.yardsToGo)}, {outcome(pl.passResult, pl.playResult)}",
         "los": los, "fd": los + float(pl.yardsToGo), "chip_start": num(ch.chip_start_s),
         "release": num(ch.chipper_release_s), "end_t": round((end - snap) / 10, 2),
         "end_label": END_EV[ends.event.iloc[0]] if len(ends) else "Fin"}
    return {"meta": m, "players": players, "frames": frames}


class Handler(BaseHTTPRequestHandler):
    def send(self, body, ctype, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def json(self, obj, code=200):
        self.send(json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8", code)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path == "/api/meta":
                return self.json(meta())
            if u.path == "/api/advice":
                return self.json(advice(q.get("sit", "all"), q.get("q", "Élite"), q.get("player", "TE"), q.get("rusher")))
            if u.path == "/api/play":
                return self.json(play(int(q["g"]), int(q["p"]), int(q["chipper"]), int(q["rusher"])))
        except Exception as exc:
            return self.json({"error": f"{type(exc).__name__}: {exc}"}, 500)
        path = (STATIC / ("index.html" if u.path == "/" else u.path.removeprefix("/static/"))).resolve()
        if not path.is_relative_to(STATIC) or not path.is_file():
            return self.send_error(404)
        self.send(path.read_bytes(), TYPES_MIME.get(path.suffix, "application/octet-stream"))

    def do_POST(self):
        if self.path != "/api/brief":
            return self.send_error(404)
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        text, source = coach_brief(body.get("facts", ""), body.get("fallback", ""))
        self.json({"text": text, "source": source})

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Chip Advisor : http://localhost:{port}")
    ThreadingHTTPServer(("", port), Handler).serve_forever()

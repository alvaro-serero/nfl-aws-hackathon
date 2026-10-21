"""Build the two analysis tables for the chip study (NFL BDB 2023 data).

Run from repo root:  python src/build_tables.py
Outputs:
  outputs/chips.csv         one row per chip (chipper -> chipped rusher)
  outputs/edge_rushers.csv  one row per edge rusher per play, chipped or not (comparison group)

Definitions (tune the constants below if needed):
  - snap   = first frame tagged ball_snap / autoevent_ballsnap
  - end    = first pass_forward / sack / run / shovel / fumble frame after snap (else last frame)
  - contact: chipper within CONTACT_YD of the chipped rusher, searched in the first CHIP_WINDOW_S after snap
  - chip_duration_s = first-to-last contact frame span; chipper_release_s = last contact frame (time after snap)
  - rusher "arrives" when he gets within NEAR_QB_YD of the QB; time_to_qb_s is NaN if he never does
"""
import glob
from multiprocessing import Pool

import numpy as np
import pandas as pd

DATA, OUT = "data", "outputs"
FPS = 10
CONTACT_YD = 1.5
CHIP_WINDOW_S = 3.0
NEAR_QB_YD = 2.0
EDGE_POS = {"LEO", "REO", "LOLB", "ROLB", "LE", "RE"}
SNAP_EV = {"ball_snap", "autoevent_ballsnap"}
END_EV = {"pass_forward", "autoevent_passforward", "qb_sack", "qb_strip_sack", "run", "pass_shovel", "fumble"}
PLAY_COLS = ["gameId", "playId", "quarter", "down", "yardsToGo", "gameClock", "possessionTeam", "defensiveTeam",
             "absoluteYardlineNumber", "offenseFormation", "personnelO", "defendersInBox", "pff_passCoverage",
             "pff_passCoverageType", "pff_playAction", "dropBackType", "passResult", "playResult", "target"]


def chip_type(pos):
    if pos.startswith("TE"):
        return "inline_TE"
    if pos.startswith(("HB", "FB")):
        return "backfield"
    return "slot_wide"


def abbr(name):
    first, _, last = name.partition(" ")
    return f"{first[0]}.{last}" if last else name


def pair(tracks, play, a, b, f0, f1):
    """Frames f0..f1 where both players are tracked: returns aligned DataFrame."""
    ta, tb = tracks.get((play, a)), tracks.get((play, b))
    if ta is None or tb is None:
        return None
    m = ta.merge(tb, on="frameId", suffixes=("_a", "_b"))
    m = m[(m.frameId >= f0) & (m.frameId <= f1)]
    m["d"] = np.hypot(m.x_a - m.x_b, m.y_a - m.y_b)
    return m


def process_game(args):
    path, edges_g, chips_g = args
    tr = pd.read_csv(path, usecols=["playId", "nflId", "frameId", "x", "y", "s", "event"])
    ev = tr.loc[tr.event != "None", ["playId", "frameId", "event"]].drop_duplicates()
    snap = ev[ev.event.isin(SNAP_EV)].groupby("playId").frameId.min()
    last = tr.groupby("playId").frameId.max()
    ends = ev[ev.event.isin(END_EV)].join(snap.rename("snap"), on="playId")
    end = ends[ends.frameId >= ends.snap].groupby("playId").frameId.min()
    tracks = {k: g[["frameId", "x", "y", "s"]].sort_values("frameId")
              for k, g in tr.dropna(subset=["nflId"]).groupby(["playId", "nflId"])}

    def window(play):
        if play not in snap.index:
            return None
        s0 = snap[play]
        return s0, end.get(play, last[play])

    edge_rows = []
    for r in edges_g.itertuples():
        w = window(r.playId)
        m = pair(tracks, r.playId, r.nflId, r.qbId, *w) if w else None
        if m is None or m.empty:
            continue
        near = m[m.d < NEAR_QB_YD]
        edge_rows.append({"gameId": r.gameId, "playId": r.playId, "nflId": r.nflId,
                          "throw_time_s": (w[1] - w[0]) / FPS,
                          "min_dist_qb": m.d.min(),
                          "time_to_qb_s": (near.frameId.iloc[0] - w[0]) / FPS if len(near) else np.nan,
                          "rusher_avg_speed": m.s_a.mean()})

    chip_rows = []
    for r in chips_g.itertuples():
        w = window(r.playId)
        if not w:
            continue
        m = pair(tracks, r.playId, r.nflId, r.rusherId, w[0], min(w[1], w[0] + CHIP_WINDOW_S * FPS))
        if m is None or m.empty:
            continue
        c = m[m.d < CONTACT_YD]
        row = {"gameId": r.gameId, "playId": r.playId, "nflId": r.nflId, "rusherId": r.rusherId,
               "min_dist_chipper_rusher": m.d.min(), "chip_detected": len(c) > 0}
        if len(c):
            f_first, f_last = c.frameId.iloc[0], c.frameId.iloc[-1]
            # m.s_b is the rusher's speed (b = rusher)
            pre = m[(m.frameId >= f_first - 5) & (m.frameId < f_first)].s_b
            during = m[(m.frameId >= f_first) & (m.frameId <= f_last)].s_b
            row.update({"chip_start_s": (f_first - w[0]) / FPS,
                        "chip_duration_s": (f_last - f_first + 1) / FPS,
                        "chipper_release_s": (f_last - w[0]) / FPS,
                        "rusher_speed_pre": pre.mean() if len(pre) else np.nan,
                        "rusher_speed_min_during": during.min()})
            row["rusher_speed_drop"] = row["rusher_speed_pre"] - row["rusher_speed_min_during"]
        chip_rows.append(row)
    return edge_rows, chip_rows


def main():
    pff = pd.read_csv(f"{DATA}/pffScoutingData.csv")
    plays = pd.read_csv(f"{DATA}/plays.csv")
    players = pd.read_csv(f"{DATA}/players.csv")[["nflId", "displayName", "officialPosition"]]

    # target receiver parsed from the play description (column not provided)
    rx = r"pass (?:incomplete )?(?:short|deep) (?:left|middle|right) (?:to|intended for) ([A-Z][\w'.-]*\.[\w'.-]+)"
    plays["target"] = plays.playDescription.str.extract(rx)[0].str.rstrip(".")

    pff["pressure"] = (pff[["pff_hit", "pff_hurry", "pff_sack"]].fillna(0).sum(axis=1) > 0).astype(int)
    qb = pff[pff.pff_role == "Pass"].drop_duplicates(["gameId", "playId"])[["gameId", "playId", "nflId"]] \
        .rename(columns={"nflId": "qbId"})
    play_pressure = pff.groupby(["gameId", "playId"]).pressure.max().rename("play_pressure").reset_index()

    # chips
    chips = pff[pff.pff_blockType == "CH"][["gameId", "playId", "nflId", "pff_positionLinedUp",
                                            "pff_nflIdBlockedPlayer", "pff_backFieldBlock"]] \
        .rename(columns={"pff_nflIdBlockedPlayer": "rusherId", "pff_positionLinedUp": "chipper_pos"})
    chips = chips.dropna(subset=["rusherId"])
    chips["rusherId"] = chips.rusherId.astype(int)
    chips["chip_type"] = chips.chipper_pos.map(chip_type)

    # edge rushers (comparison group) with leave-one-out baseline pressure rate per rusher
    rush = pff[pff.pff_role == "Pass Rush"].copy()
    g = rush.groupby("nflId").pressure
    rush["rusher_n_rushes"] = g.transform("size")
    rush["rusher_base_pressure_rate"] = (g.transform("sum") - rush.pressure) / (rush.rusher_n_rushes - 1)
    edges = rush[rush.pff_positionLinedUp.isin(EDGE_POS)][
        ["gameId", "playId", "nflId", "pff_positionLinedUp", "pressure", "pff_hit", "pff_sack",
         "rusher_n_rushes", "rusher_base_pressure_rate"]].rename(columns={"pff_positionLinedUp": "rusher_pos"})
    edges = edges.merge(qb, on=["gameId", "playId"])
    chip_map = chips.drop_duplicates(["gameId", "playId", "rusherId"])[["gameId", "playId", "rusherId", "chip_type"]] \
        .rename(columns={"rusherId": "nflId"})
    edges = edges.merge(chip_map, on=["gameId", "playId", "nflId"], how="left")
    edges["chipped"] = edges.chip_type.notna()

    # tracking, one game per worker
    jobs = []
    for path in sorted(glob.glob(f"{DATA}/tracking/tracking_*.csv")):
        gid = int(path.split("_")[-1].split(".")[0])
        jobs.append((path, edges[edges.gameId == gid], chips[chips.gameId == gid]))
    with Pool() as pool:
        res = pool.map(process_game, jobs)
    edge_feat = pd.DataFrame([r for e, _ in res for r in e])
    chip_feat = pd.DataFrame([r for _, c in res for r in c])

    ctx = plays[PLAY_COLS].merge(play_pressure, on=["gameId", "playId"], how="left")

    edges = edges.merge(edge_feat, on=["gameId", "playId", "nflId"], how="left").merge(ctx, on=["gameId", "playId"])
    edges = edges.merge(players.rename(columns={"displayName": "rusher_name"})[["nflId", "rusher_name"]], on="nflId")
    edges.to_csv(f"{OUT}/edge_rushers.csv", index=False)

    rusher_cols = edges[["gameId", "playId", "nflId", "rusher_pos", "pressure", "pff_hit", "pff_sack",
                         "rusher_base_pressure_rate", "min_dist_qb", "time_to_qb_s", "throw_time_s"]] \
        .rename(columns={"nflId": "rusherId", "pressure": "rusher_pressure", "pff_hit": "rusher_hit",
                         "pff_sack": "rusher_sack"})
    chips = chips.merge(chip_feat, on=["gameId", "playId", "nflId", "rusherId"], how="left") \
        .merge(rusher_cols, on=["gameId", "playId", "rusherId"], how="left") \
        .merge(ctx, on=["gameId", "playId"]) \
        .merge(players.rename(columns={"displayName": "chipper_name", "officialPosition": "chipper_off_pos"}),
               on="nflId") \
        .merge(players.rename(columns={"nflId": "rusherId", "displayName": "rusher_name"})[["rusherId", "rusher_name"]],
               on="rusherId", how="left")
    chips["chipper_targeted"] = (chips.chipper_name.map(abbr) == chips.target).astype(object)
    chips.loc[~chips.passResult.isin(["C", "I", "IN"]), "chipper_targeted"] = np.nan
    chips.to_csv(f"{OUT}/chips.csv", index=False)

    print(f"edge_rushers.csv: {len(edges)} rows, chipped={edges.chipped.sum()}")
    print(f"chips.csv: {len(chips)} rows, contact detected={chips.chip_detected.sum()}")


if __name__ == "__main__":
    main()

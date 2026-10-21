"""Question du coach : sur les actions avec chip, gagne-t-on plus de yards, et le QB est-il moins sous pression ?"""
import numpy as np
import pandas as pd

D = "data"
plays = pd.read_csv(f"{D}/plays.csv")
pff = pd.read_csv(f"{D}/pffScoutingData.csv")
plays = plays[~plays.playDescription.str.contains("No Play")]  # actions annulées par une pénalité

press_cols = ["pff_hurry", "pff_hit", "pff_sack"]
by_play = pff.groupby(["gameId", "playId"]).agg(
    chip=("pff_blockType", lambda b: (b == "CH").any()),
    n_rush=("pff_role", lambda r: (r == "Pass Rush").sum()),
    n_block=("pff_role", lambda r: (r == "Pass Block").sum()),
)
by_play["pressure"] = pff.groupby(["gameId", "playId"])[press_cols].max().max(axis=1) > 0
p = plays.merge(by_play, on=["gameId", "playId"])
p["sack"] = p.passResult.eq("S")
need = p.yardsToGo * p.down.map({1: 0.4, 2: 0.6, 3: 1.0, 4: 1.0})
p["success"] = p.prePenaltyPlayResult >= need  # taux de réussite standard
p["situation"] = np.select([p.down <= 2, p.yardsToGo <= 4], ["1er/2e down", "3e/4e et court"], "3e/4e et long")

agg = dict(actions=("chip", "size"), yards=("prePenaltyPlayResult", "mean"), reussite=("success", "mean"),
           pression=("pressure", "mean"), sack=("sack", "mean"))
print("== Toutes les actions de passe")
print(p.groupby("chip").agg(**agg).round(3).to_string())
print("\n== Par situation")
print(p.groupby(["situation", "chip"]).agg(**agg).round(3).to_string())
print("\n== Par nombre de pass rushers (le chip sert surtout contre 4-5 rushers)")
print(p[p.n_rush.between(4, 6)].groupby(["n_rush", "chip"]).agg(**agg).round(3).to_string())

# Même pass rusher, chippé ou non : neutralise la qualité du rusher
rush = pff[pff.pff_role == "Pass Rush"][["gameId", "playId", "nflId"] + press_cols]
chipped = pff[pff.pff_blockType == "CH"][["gameId", "playId", "pff_nflIdBlockedPlayer"]].rename(
    columns={"pff_nflIdBlockedPlayer": "nflId"}).drop_duplicates().assign(chipped=True)
rush = rush.merge(chipped, on=["gameId", "playId", "nflId"], how="left").fillna({"chipped": False})
rush["pressure"] = rush[press_cols].max(axis=1) > 0
per = rush.groupby(["nflId", "chipped"]).pressure.agg(["mean", "size"]).unstack()
per = per[(per[("size", True)] >= 10) & (per[("size", False)] >= 30)]
diff = per[("mean", True)] - per[("mean", False)]
rng = np.random.default_rng(0)
ci = np.percentile([rng.choice(diff.values, len(diff)).mean() for _ in range(2000)], [2.5, 97.5])
print(f"\n== Même rusher, chippé vs non chippé ({len(per)} rushers avec >= 10 chips et >= 30 rushs sans chip)")
print("taux de pression du rusher : chippé %.3f | non chippé %.3f | écart %.3f (IC95 %.3f à %.3f)"
      % (per[("mean", True)].mean(), per[("mean", False)].mean(), diff.mean(), *ci))
print("rushers qui mettent moins de pression quand ils sont chippés :", round((diff < 0).mean(), 3))

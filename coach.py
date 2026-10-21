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

# À situation égale (reprend .kiro/ref/controle.py) : post-stratification down × distance (1-3, 4-6, 7-10, 11+)
# × nombre de rushers (≤3, 4, 5, 6+), pondérée par la répartition des actions avec chip ; IC95 par bootstrap
rush["chipped"] = rush.chipped.eq(True)  # pandas 3 : après fillna la colonne reste en object
others = rush[~rush.chipped].groupby(["gameId", "playId"]).agg(n_other=("pressure", "size"),
                                                                 p_other=("pressure", "sum"))
q = p[p.down >= 1].merge(others, on=["gameId", "playId"], how="left").fillna({"n_other": 0, "p_other": 0})
q["dist"] = pd.cut(q.yardsToGo, [0, 3, 6, 10, 99], labels=False)  # down 0 = transformation à 2 points, exclu
q["rushers"] = q.n_rush.clip(3, 6) - 3
s = (q.down.astype(int) - 1) * 16 + q.dist.astype(int) * 4 + q.rushers.astype(int)
c = q.chip.to_numpy()
K = 64


def ps(num, den, s, c):
    """Taux avec chip, taux sans chip repondéré sur les strates des actions avec chip, part des actions chip gardées."""
    dc, dn = np.bincount(s[c], den[c], K), np.bincount(s[~c], den[~c], K)
    nc, nn = np.bincount(s[c], num[c], K), np.bincount(s[~c], num[~c], K)
    ok = (dc > 0) & (dn > 0)
    w = dc[ok] / dc[ok].sum()
    return (nc[ok] / dc[ok] * w).sum(), (nn[ok] / dn[ok] * w).sum(), dc[ok].sum() / dc.sum()


def report(name, num, den):
    num, den, ss = np.asarray(num, float), np.asarray(den, float), s.to_numpy()
    raw_c, raw_n = num[c].sum() / den[c].sum(), num[~c].sum() / den[~c].sum()
    rc, rn, cov = ps(num, den, ss, c)
    rng = np.random.default_rng(0)
    boot = []
    for _ in range(2000):
        i = rng.integers(0, len(num), len(num))
        bc, bn, _ = ps(num[i], den[i], ss[i], c[i])
        boot.append(bc - bn)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    verdict = "écart NON significatif (IC95 contient 0)" if lo <= 0 <= hi else "écart significatif"
    print(f"== {name}")
    print(f"   brut      : chip {raw_c:.3f} | sans chip {raw_n:.3f} | écart {raw_c - raw_n:+.3f}")
    print(f"   contrôlé  : chip {rc:.3f} | sans chip {rn:.3f} | écart {rc - rn:+.3f} (IC95 {lo:+.3f} à {hi:+.3f}),"
          f" relatif {(rc - rn) / rn:+.0%} ; {verdict} ; {cov:.0%} des actions chip dans des strates comparables")


print(f"\n== À situation égale : {c.sum()} actions avec chip, {(~c).sum()} sans ; {len(q)} actions de passe")
report("Sacks par action", q.sack, np.ones(len(q)))
report("Pression par action (au moins un hurry, hit ou sack)", q.pressure, np.ones(len(q)))
report("Report : pression par rusher NON chippé", q.p_other, q.n_other)

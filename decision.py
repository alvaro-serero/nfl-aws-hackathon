"""Le chip oublié : sur les actions avec chip, le TE/RB qui a chippé était-il la meilleure option du QB ?

Pour chaque receveur, au moment de la décision (lancer, ou sack) : profondeur, séparation au défenseur en couverture
le plus proche, et depuis combien de temps il est démarqué. Un modèle simple (complétion ~ profondeur + séparation)
donne la valeur de chaque option ; on compare l'option « joueur qui chippe » à l'option réellement choisie.
"""
import glob
import os
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

D = "data"
SNAP = {"ball_snap", "autoevent_ballsnap"}
THROW = {"pass_forward", "autoevent_passforward"}
SACK = {"qb_sack", "qb_strip_sack"}
OPEN = 3.0  # yards : seuil « démarqué »
CACHE = "decision_state.parquet"  # état des receveurs au moment de la décision (lecture du tracking ~45 s)

games = pd.read_csv(f"{D}/games.csv", usecols=["gameId", "week"])
plays = pd.read_csv(f"{D}/plays.csv")
pff = pd.read_csv(f"{D}/pffScoutingData.csv")
players = pd.read_csv(f"{D}/players.csv", usecols=["nflId", "officialPosition", "displayName"])

# Receveurs : routes + joueurs qui chippent ou font un set & release avant de partir en route
rec = pff[(pff.pff_role == "Pass Route") | pff.pff_blockType.isin(["CH", "SR"])]
cov = pff[pff.pff_role == "Coverage"]
pressure = pff.groupby(["gameId", "playId"])[["pff_hurry", "pff_hit", "pff_sack"]].max().max(axis=1).rename("pressure")


# ---------- 1. Tracking : état de chaque receveur au moment de la décision ----------
rows = []
paths = [] if os.path.exists(CACHE) else sorted(glob.glob(f"{D}/tracking/*.csv"))
for path in paths:
    t = pd.read_csv(path, usecols=["gameId", "playId", "nflId", "frameId", "x", "y", "playDirection", "event"])
    gid = t.gameId.iat[0]
    ball = t[t.nflId.isna()]
    first = lambda ev: ball[ball.event.isin(ev)].groupby("playId").frameId.min()
    snap, throw, sack = first(SNAP), first(THROW), first(SACK)
    r_g, c_g = rec[rec.gameId == gid], cov[cov.gameId == gid]
    for pid, g in t[t.nflId.notna()].groupby("playId"):
        if pid not in snap.index:
            continue
        s0 = snap[pid]
        end = throw.get(pid, sack.get(pid, np.nan))  # décision = lancer, sinon sack
        if np.isnan(end):
            continue
        g = g[(g.frameId >= s0) & (g.frameId <= end)]
        pos = g.pivot_table(index="frameId", columns="nflId", values=["x", "y"])
        r_ids = [i for i in r_g[r_g.playId == pid].nflId if i in pos["x"]]
        d_ids = [i for i in c_g[c_g.playId == pid].nflId if i in pos["x"]]
        if not r_ids or not d_ids:
            continue
        rx, ry = pos["x"][r_ids].values, pos["y"][r_ids].values
        dx, dy = pos["x"][d_ids].values, pos["y"][d_ids].values
        sep = np.hypot(rx[:, :, None] - dx[:, None, :], ry[:, :, None] - dy[:, None, :]).min(axis=2)
        sign = 1 if g.playDirection.iat[0] == "right" else -1
        los = ball[(ball.playId == pid) & (ball.frameId == s0)].x.iat[0]
        depth = (rx - los) * sign  # profondeur image par image
        for j, rid in enumerate(r_ids):
            # démarqué = >= 3 yd du défenseur le plus proche ET au-delà de la ligne de scrimmage
            closed = np.where((sep[:, j] < OPEN) | (depth[:, j] < 0))[0]
            streak = len(sep) - 1 - closed[-1] if len(closed) else len(sep) - 1
            rows.append(dict(gameId=gid, playId=pid, nflId=rid, thrown=pid in throw.index,
                             t_decision=(end - s0) / 10, depth=depth[-1, j],
                             sep=sep[-1, j], open_for=streak / 10))

state = pd.read_parquet(CACHE) if not paths else pd.DataFrame(rows)
state.to_parquet(CACHE)
f = state.merge(rec[["gameId", "playId", "nflId", "pff_blockType"]], on=["gameId", "playId", "nflId"])
f = f.merge(players, on="nflId").merge(games, on="gameId").join(pressure, on=["gameId", "playId"])
f = f.merge(plays[["gameId", "playId", "possessionTeam", "down", "yardsToGo", "passResult", "playResult",
                   "playDescription", "pff_passCoverageType"]], on=["gameId", "playId"])
f["chip"] = f.pff_blockType.eq("CH")


# Cible : abréviation « P.Nom » trouvée la première dans playDescription après « pass »
def abbr(name):
    first, _, last = name.partition(" ")
    return f"{first[0]}.{last}"


after = f.playDescription.str.split(" pass ", n=1).str[1].fillna("")
f["pos_desc"] = [a.find(b) if b in a else 10**6 for a, b in zip(after, f.displayName.map(abbr))]
best = f.groupby(["gameId", "playId"]).pos_desc.transform("min")
f["targeted"] = f.thrown & (f.pos_desc == best) & (best < 10**6)
f["no_play"] = f.playDescription.str.contains("No Play")  # action annulée par une pénalité
f = f.drop(columns=["pos_desc", "playDescription"])


# ---------- 2. Modèle de valeur d'une option ----------
def X(d):
    s = d.sep.clip(upper=10)
    return np.column_stack([d.depth, s, d.depth * s, d.depth ** 2])


tg = f[f.targeted & f.passResult.isin(["C", "I", "IN"]) & ~f.no_play].copy()
tg["complete"] = tg.passResult.eq("C")
train, test = tg[tg.week <= 6], tg[tg.week > 6]
m_train = LogisticRegression(max_iter=1000).fit(X(train), train.complete)
m = m_train
test = test.assign(p=m.predict_proba(X(test))[:, 1])
print("== Calibration (entraîné semaines 1-6, testé 7-8) : complétion prédite vs réelle")
print(test.groupby(pd.qcut(test.p, 5)).agg(pred=("p", "mean"), reel=("complete", "mean"), n=("p", "size")).round(3).to_string())
m = LogisticRegression(max_iter=1000).fit(X(tg), tg.complete)

# Yards après la décision pour les passes complétées, par tranche de profondeur
bins = [-20, 0, 5, 10, 20, 60]
comp = tg[tg.complete].assign(extra=lambda d: d.playResult - d.depth, b=lambda d: pd.cut(d.depth, bins))
extra_by_bin = {b: g.extra.values for b, g in comp.groupby("b", observed=True)}
NEED = {1: 0.4, 2: 0.6, 3: 1.0, 4: 1.0}  # taux de réussite standard : 40 / 60 / 100 % des yards à faire


def value(d):
    p = m.predict_proba(X(d))[:, 1]
    b = pd.cut(d.depth, bins)
    ey = np.array([pp * (dd + extra_by_bin[bb].mean()) for pp, dd, bb in zip(p, d.depth, b)])
    need = d.yardsToGo * d.down.map(NEED)
    ps = np.array([pp * np.mean(dd + extra_by_bin[bb] >= nn) for pp, dd, bb, nn in zip(p, d.depth, b, need)])
    return d.assign(p_comp=p, exp_yards=ey, p_success=ps)


f = value(f)
f.to_parquet("decision.parquet")


# ---------- 3. Actions avec chip : option « joueur qui chippe » vs option choisie ----------
chip_plays = f[f.chip & f.officialPosition.isin(["TE", "RB"])]
tgt = f[f.targeted].set_index(["gameId", "playId"])[["exp_yards", "p_success", "officialPosition"]]
duel = chip_plays[chip_plays.thrown & ~chip_plays.targeted].join(tgt, on=["gameId", "playId"], rsuffix="_tgt").dropna(subset=["exp_yards_tgt"])
duel["gap_yards"] = duel.exp_yards - duel.exp_yards_tgt
duel["gap_success"] = duel.p_success - duel.p_success_tgt

rng = np.random.default_rng(0)
boot = lambda s: np.percentile([rng.choice(s, len(s)).mean() for _ in range(2000)], [2.5, 97.5]).round(2)
print(f"\n== {len(duel)} actions où le joueur qui chippe n'est pas ciblé")
print("joueur qui chippe meilleure option (yards attendus) :", round((duel.gap_yards > 0).mean(), 3))
print("écart moyen de yards attendus : %.2f, IC95 %s" % (duel.gap_yards.mean(), boot(duel.gap_yards.values)))
print("écart moyen de proba de réussite : %.3f, IC95 %s" % (duel.gap_success.mean(), boot(duel.gap_success.values)))
print("démarqué depuis (s) au lancer, médiane :", duel.open_for.median(), "| part démarqué depuis >= 0,5 s :",
      round((duel.open_for >= 0.5).mean(), 3))

print("\n== Par situation (écart de proba de réussite, chippeur - cible)")
duel["situation"] = np.select([(duel.down >= 3) & (duel.yardsToGo <= 4), duel.down >= 3], ["3e/4e et court", "3e/4e et long"], "1er/2e down")
for col in ["situation", "pff_passCoverageType", "pressure"]:
    print(duel.groupby(col).agg(n=("gap_success", "size"), gap_success=("gap_success", "mean"),
                                chippeur_meilleur=("gap_success", lambda s: (s > 0).mean())).round(3).to_string())

sacks = f[~f.thrown & f.passResult.eq("S")].assign(
    open_past=lambda d: (d.sep >= OPEN) & (d.depth >= 0), open_1s=lambda d: d.open_for >= 1)
chip_s = sacks[sacks.chip & sacks.officialPosition.isin(["TE", "RB"])]
same = sacks[sacks.set_index(["gameId", "playId"]).index.isin(chip_s.set_index(["gameId", "playId"]).index) & ~sacks.chip]
# autres receveurs repondérés sur la distribution de profondeur des joueurs qui chippent
dbins = [-20, 0, 3, 6, 10, 60]
w = pd.cut(chip_s.depth, dbins).value_counts(normalize=True)
oth = sacks[~sacks.chip].groupby(pd.cut(sacks[~sacks.chip].depth, dbins), observed=True)[["open_past", "open_1s"]].mean()
sp = chip_s.groupby(["gameId", "playId"]).agg(res=("playResult", "first"), ey=("exp_yards", "mean"))
print(f"\n== Sacks avec chip (TE/RB) : {len(sp)} actions, {len(chip_s)} joueurs qui chippent")
print("démarqué au-delà de la ligne au sack : chippeur %.3f | autres, mêmes actions %.3f | autres, profondeur égale %.3f"
      % (chip_s.open_past.mean(), same.open_past.mean(), (oth.open_past * w).sum()))
print("démarqué depuis >= 1 s au-delà de la ligne : chippeur %.3f | autres, mêmes actions %.3f | autres, profondeur égale %.3f"
      % (chip_s.open_1s.mean(), same.open_1s.mean(), (oth.open_1s * w).sum()))
print("sack moyen : %.2f yd | passe au chippeur, borne haute : %.2f yd attendus" % (sp.res.mean(), sp.ey.mean()))

print("\n== Validation vs NGS (80,2 % de réception après un chip)")
ct = chip_plays[chip_plays.targeted & chip_plays.passResult.isin(["C", "I", "IN"])]
r = ct.passResult.eq("C").mean()
print("réception réelle après un chip : %.3f (IC95 %.2f-%.2f), n = %d | prédite par le modèle semaines 1-6 : %.3f"
      % (r, r - 1.96 * np.sqrt(r * (1 - r) / len(ct)), r + 1.96 * np.sqrt(r * (1 - r) / len(ct)), len(ct),
         m_train.predict_proba(X(ct))[:, 1].mean()))
tt = f[f.thrown].groupby(["gameId", "playId"]).agg(t=("t_decision", "first"), chip=("chip", "any"))
print("temps avant le lancer (s), MÉDIANE sans/avec chip :", tt.groupby("chip").t.median().to_dict())

print("\n== Réussite laissée sur la table par équipe (somme des écarts positifs de proba de réussite)")
team = duel.assign(lost=duel.gap_success.clip(lower=0)).groupby("possessionTeam").agg(
    actions=("lost", "size"), reussites_laissees=("lost", "sum")).sort_values("reussites_laissees", ascending=False)
print(team.round(2).head(8).to_string())
duel.to_parquet("duel.parquet")

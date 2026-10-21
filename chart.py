"""Graphique phare : en temps normal le QB a raison d'ignorer le joueur qui chippe ; sur un sack, c'est sa soupape."""
import matplotlib.pyplot as plt
import pandas as pd

f = pd.read_parquet("decision.parquet")
duel = pd.read_parquet("duel.parquet")
sacks = f[~f.thrown & f.passResult.eq("S")].assign(open_1s=lambda d: d.open_for >= 1)
chip = sacks[sacks.chip & sacks.officialPosition.isin(["TE", "RB"])]
other = sacks[~sacks.chip]
# autres receveurs repondérés sur la distribution de profondeur des joueurs qui chippent
dbins = [-20, 0, 3, 6, 10, 60]
w = pd.cut(chip.depth, dbins).value_counts(normalize=True)
other_eq = (other.groupby(pd.cut(other.depth, dbins), observed=True).open_1s.mean() * w).sum()
per_play = chip.groupby(["gameId", "playId"]).agg(open_1s=("open_1s", "any"), res=("playResult", "first"))

fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 5.5))
BLUE, GOLD, GREY = "#1f77b4", "#d4a017", "#9e9e9e"


def bars(ax, labels, vals, colors):
    ax.bar(labels, vals, color=colors)
    for i, v in enumerate(vals):
        ax.text(i, v + 1, f"{v:.0f} %", ha="center", fontsize=13, weight="bold")
    ax.set_ylim(0, max(vals) + 12)
    ax.spines[["top", "right"]].set_visible(False)


# 1. Passes lancées : probabilité de réussite de l'option choisie vs celle du joueur qui chippe
bars(a1, ["Cible choisie\npar le QB", "TE/RB qui\na chippé"],
     [duel.p_success_tgt.mean() * 100, duel.p_success.mean() * 100], [BLUE, GOLD])
a1.set_title(f"Passe lancée ({len(duel)} cas) : le QB a raison\nde chercher plus loin", fontsize=13)
a1.set_ylabel("Probabilité de réussite de l'action (modèle)")

# 2. Sacks : démarqué depuis >= 1 s au-delà de la ligne
bars(a2, [f"TE/RB qui\na chippé (n={len(chip)})", "Autres receveurs\nà profondeur égale"],
     [chip.open_1s.mean() * 100, other_eq * 100], [GOLD, GREY])
a2.set_title(f"Sur {len(per_play)} sacks avec chip : dans {per_play.open_1s.sum()}, il était démarqué\n"
             f"depuis ≥ 1 s au-delà de la ligne (sack moyen {per_play.res.mean():.1f} yd)", fontsize=13)
a2.set_ylabel("% démarqués (≥ 3 yd) depuis ≥ 1 s au moment du sack")

fig.suptitle("Le chip oublié : le TE/RB qui chippe n'est pas une option manquée, c'est une soupape anti-sack",
             fontsize=14, weight="bold")
fig.tight_layout()
fig.savefig("insight.png", dpi=150)
print("insight.png écrit ;", per_play.open_1s.sum(), "sacks sur", len(per_play), "; autres à profondeur égale",
      round(other_eq, 3))

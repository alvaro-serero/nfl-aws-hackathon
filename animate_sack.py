"""Animation d'UN sack avec chip : NYJ, 2e et 2 (2021-10-10).

Le TE Ryan Griffin (NYJ) chippe le rusher qui finira par sacker, puis sort en route, démarqué au-delà du 1er down,
pendant que Zach Wilson se fait sacker. Sorties : chip_sack.html (plotly) et chip_sack.png.
Variante de animate_chip.py (même style). Lancer depuis team-repo/ : python animate_sack.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go

# --- Action à animer ---
GAME_ID, PLAY_ID, CHIPPER_ID = 2021101000, 3729, 40149
SORTIE = "chip_sack"

# --- Chargement ---
play = pd.read_csv("data/plays.csv").query("gameId == @GAME_ID and playId == @PLAY_ID").iloc[0]
players = pd.read_csv("data/players.csv")
pff = pd.read_csv("data/pffScoutingData.csv").query("gameId == @GAME_ID and playId == @PLAY_ID")
trk = pd.read_csv(f"data/tracking/tracking_{GAME_ID}.csv").query("playId == @PLAY_ID").copy()

# Normalisation : l'attaque va toujours vers la droite
los = play.absoluteYardlineNumber
if (trk.playDirection == "left").any():
    left = trk.playDirection == "left"
    trk.loc[left, "x"] = 120 - trk.loc[left, "x"]
    trk.loc[left, "y"] = 53.3 - trk.loc[left, "y"]
    los = 120 - los
down1 = los + play.yardsToGo  # ligne du 1er down

# Snap et fin de la décision : premier frame du sack (ou dernier frame s'il n'y en a pas)
snap = trk[trk.event.isin(["ball_snap", "autoevent_ballsnap"])].frameId.min()
sacks = trk[trk.event.isin(["qb_sack", "qb_strip_sack"])]
fin = sacks.frameId.min() if len(sacks) else trk.frameId.max()
frames = range(snap, trk.frameId.max() + 1)

# Acteurs : chippeur, rusher chippé (PFF), QB, défenseurs en couverture
assert pff.set_index("nflId").loc[CHIPPER_ID, "pff_blockType"] == "CH"
rusher = int(pff.set_index("nflId").loc[CHIPPER_ID, "pff_nflIdBlockedPlayer"])
qb = int(pff[pff.pff_role == "Pass"].nflId.iloc[0])
nom = players.set_index("nflId").displayName[CHIPPER_ID].split()[-1]
cov_ids = pff[pff.pff_role == "Coverage"].nflId

# Séparation du chippeur = distance au défenseur Coverage le plus proche, par frame
ev = trk[trk.nflId == CHIPPER_ID].set_index("frameId")[["x", "y"]]
cov = trk[trk.nflId.isin(cov_ids)].join(ev, on="frameId", rsuffix="_ev")
sep = np.hypot(cov.x - cov.x_ev, cov.y - cov.y_ev).groupby(cov.frameId).min().loc[snap:]


def depuis(ligne):
    """Secondes écoulées depuis que le chippeur est démarqué (>= 3 yd) au-delà de `ligne` (0 si ce n'est pas le cas)."""
    libre = (sep >= 3) & (ev.x.loc[sep.index] > ligne)
    return ((libre.groupby((~libre).cumsum()).cumsum() - 1).clip(lower=0)) / 10


libre_los, libre_down = depuis(los), depuis(down1)

# Fenêtre d'affichage et textes
poss = play.possessionTeam
xmin, xmax = trk.x.min() - 3, trk.x.max() + 3
titre = f"{play.down}e et {play.yardsToGo} : la soupape oubliée"
msg = (f"Sack {play.playResult:.0f} yd : {nom} démarqué de {sep[fin]:.1f} yd,\n"
       f"au-delà du 1er down depuis {libre_down[fin]:.1f} s")
# (id, étiquette, couleur de l'anneau, taille, position du texte)
marks = [(CHIPPER_ID, "TE qui a chippé", "gold", 30, "bottom center"),
         (rusher, "rusher chippé", "white", 24, "top center"),
         (qb, "QB sacké", "cyan", 24, "bottom center")]
DECALAGE = {"top center": ((0, 30), "center"), "bottom center": ((0, -30), "center")}  # étiquettes matplotlib
BLEU, ROUGE, MARRON = "#1f77b4", "#d62728", "#8B4513"


# --- Animation plotly ---
def traces(f):
    """Les traces plotly d'un frame (même ordre à chaque frame)."""
    d = trk[trk.frameId == f]
    off, dfn, ball = d[d.team == poss], d[~d.team.isin([poss, "football"])], d[d.team == "football"]
    pt = lambda i: d[d.nflId == i].iloc[0]
    joueurs = lambda g, nom, c: go.Scatter(
        x=g.x, y=g.y, name=nom, mode="markers+text", text=g.jerseyNumber.astype(int).astype(str),
        textfont=dict(color="white", size=9), marker=dict(size=17, color=c, line=dict(color="white", width=1)))
    ang = np.linspace(0, 2 * np.pi, 60)
    e = pt(CHIPPER_ID)
    out = [joueurs(off, f"Attaque ({poss})", BLEU), joueurs(dfn, f"Défense ({play.defensiveTeam})", ROUGE),
           go.Scatter(x=ball.x, y=ball.y, name="Ballon", mode="markers",
                      marker=dict(size=11, color=MARRON, symbol="diamond", line=dict(color="white", width=1)))]
    for i, label, c, size, pos in marks:  # anneaux + étiquettes
        p = pt(i)
        out.append(go.Scatter(x=[p.x], y=[p.y], mode="markers+text", text=[label], textposition=pos,
                              textfont=dict(color=c, size=14), showlegend=False,
                              marker=dict(size=size, color="rgba(0,0,0,0)", line=dict(color=c, width=4))))
    # cercle de séparation + textes (jauge en haut, annotation à partir du sack)
    out.append(go.Scatter(x=e.x + sep[f] * np.cos(ang), y=e.y + sep[f] * np.sin(ang), mode="lines",
                          line=dict(color="gold", dash="dot", width=2), showlegend=False))
    out.append(go.Scatter(x=[(xmin + xmax) / 2] * 2, y=[51.5, 47.8], mode="text", showlegend=False,
                          text=[f"{nom} : séparation {sep[f]:.1f} yd<br>"
                                f"démarqué (≥ 3 yd) au-delà de la ligne : {libre_los[f]:.1f} s",
                                msg.replace("\n", "<br>") if f >= fin else ""],
                          textfont=dict(color=["white", "gold"], size=14)))
    return out


# Terrain : lignes tous les 5 yd, numéros tous les 10 yd, ligne de scrimmage et 1er down
lignes = [x for x in range(int(xmin) // 5 * 5 + 5, int(xmax) + 1, 5) if 10 <= x <= 110]
yard = lambda x: x - 10 if x <= 60 else 110 - x  # numéro de yard affiché sur le terrain
shapes = [dict(type="line", x0=x, x1=x, y0=0, y1=53.3, line=dict(color="rgba(255,255,255,0.6)", width=1), layer="below")
          for x in lignes]
shapes += [dict(type="line", x0=x, x1=x, y0=0, y1=53.3, line=dict(color=c, width=3), layer="below")
           for x, c in [(los, "deepskyblue"), (down1, "yellow")]]
notes = [dict(x=x, y=25, text=str(yard(x)), showarrow=False, font=dict(color="rgba(255,255,255,0.5)", size=26))
         for x in lignes if x % 10 == 0 and x < xmax - 3]
notes += [dict(x=los, y=1.5, text="ligne de scrimmage", xanchor="right", showarrow=False,
               font=dict(color="deepskyblue", size=11)),
          dict(x=down1, y=1.5, text="1er down", xanchor="left", showarrow=False, font=dict(color="yellow", size=11))]

fig = go.Figure(data=traces(snap), frames=[go.Frame(name=str(f), data=traces(f)) for f in frames])
H = 820  # hauteur de la figure ; la largeur suit le rapport 1:1 du terrain
fig.update_layout(
    title=dict(text=titre, font=dict(size=15)),
    width=int((H - 200) * (xmax - xmin) / 53.3) + 80, height=H, margin=dict(l=40, r=40, t=70, b=130),
    plot_bgcolor="#2e7d32",
    xaxis=dict(range=[xmin, xmax], visible=False), yaxis=dict(range=[0, 53.3], visible=False, scaleanchor="x"),
    legend=dict(orientation="h", y=-0.03), shapes=shapes, annotations=notes,
    updatemenus=[dict(type="buttons", direction="right", x=1.0, xanchor="right", y=1.0, yanchor="bottom", buttons=[
        dict(label="Play", method="animate",
             args=[None, dict(frame=dict(duration=120, redraw=True), fromcurrent=True, transition=dict(duration=0))]),
        dict(label="Pause", method="animate",
             args=[[None], dict(mode="immediate", frame=dict(duration=0, redraw=False), transition=dict(duration=0))])])],
    sliders=[dict(currentvalue=dict(visible=False), pad=dict(t=40), steps=[
        dict(method="animate", label=f"{(f - snap) / 10:.1f}s",
             args=[[str(f)], dict(mode="immediate", frame=dict(duration=0, redraw=True), transition=dict(duration=0))])
        for f in frames])])
fig.write_html(f"{SORTIE}.html", include_plotlyjs=True, auto_play=False)

# --- Image statique matplotlib au frame du sack ---
d = trk[trk.frameId == fin]
snap_to_fin = trk[trk.frameId.between(snap, fin)]
fig, ax = plt.subplots(figsize=(8.5, 9.5))
ax.set_facecolor("#2e7d32")
ax.set(xlim=(xmin, xmax), ylim=(0, 53.3), aspect="equal", xticks=[], yticks=[])
for x in lignes:
    ax.axvline(x, color="white", alpha=0.4, lw=1)
    if x % 10 == 0 and x < xmax - 3:
        ax.text(x, 25, str(yard(x)), color="white", alpha=0.4, fontsize=26, ha="center")
ax.axvline(los, color="deepskyblue", lw=3)
ax.axvline(down1, color="yellow", lw=3)
ax.text(los - 0.3, 1, "ligne de scrimmage", color="deepskyblue", fontsize=9, ha="right")
ax.text(down1 + 0.3, 1, "1er down", color="yellow", fontsize=9, ha="left")

for g, c, nom_g in [(d[d.team == poss], BLEU, f"Attaque ({poss})"),
                    (d[~d.team.isin([poss, "football"])], ROUGE, f"Défense ({play.defensiveTeam})")]:
    ax.scatter(g.x, g.y, s=230, c=c, edgecolor="white", label=nom_g, zorder=3)
    for r in g.itertuples():
        ax.text(r.x, r.y, int(r.jerseyNumber), color="white", fontsize=7, ha="center", va="center", zorder=4)
b = d[d.team == "football"]
ax.scatter(b.x, b.y, s=90, c=MARRON, marker="D", edgecolor="white", label="Ballon", zorder=5)

# Trajectoires du snap au sack (chippeur et QB), anneaux, étiquettes
for i, label, c, size, pos in marks:
    p = d[d.nflId == i].iloc[0]
    if i != rusher:
        t = snap_to_fin[snap_to_fin.nflId == i]
        ax.plot(t.x, t.y, color=c, lw=2.5, zorder=2)
    ax.scatter(p.x, p.y, s=size * 25, facecolors="none", edgecolors=c, linewidths=3, zorder=6)
    ax.annotate(label, (p.x, p.y), xytext=DECALAGE[pos][0], textcoords="offset points",
                color=c, fontsize=11, fontweight="bold", ha=DECALAGE[pos][1], va="center", zorder=7,
                bbox=dict(boxstyle="round", fc="black", alpha=0.55, ec="none"))

# Moment du chip : frame où le chippeur est le plus près du rusher
e, r = ev.loc[snap:fin], trk[trk.nflId == rusher].set_index("frameId")[["x", "y"]].loc[snap:fin]
chip = np.hypot(e.x - r.x, e.y - r.y).idxmin()
ax.scatter(e.x[chip], e.y[chip], s=120, c="white", marker="X", edgecolor="black", zorder=6)
ax.annotate("chip", (e.x[chip], e.y[chip]), xytext=(12, -4), textcoords="offset points", color="white",
            fontsize=10, fontweight="bold", zorder=7)

# Cercle de séparation du chippeur + annotation du sack
ev_t = d[d.nflId == CHIPPER_ID].iloc[0]
ax.add_patch(plt.Circle((ev_t.x, ev_t.y), sep[fin], fill=False, ec="gold", ls="--", lw=2, zorder=2))
ax.text(ev_t.x + sep[fin] * 0.707, ev_t.y + sep[fin] * 0.707, f"{sep[fin]:.1f} yd", color="gold", fontsize=11,
        fontweight="bold", ha="center", va="center", bbox=dict(boxstyle="round", fc="black", alpha=0.55, ec="none"), zorder=8)
ax.text((xmin + xmax) / 2, 49.5, msg, color="gold", fontsize=12, fontweight="bold", ha="center", va="center",
        bbox=dict(boxstyle="round", fc="black", alpha=0.6, ec="none"), zorder=8)
ax.set_title(titre, fontsize=15, fontweight="bold")
ax.legend(loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.07), frameon=False)
fig.savefig(f"{SORTIE}.png", dpi=150, bbox_inches="tight")

print(f"snap={snap} sack={fin} séparation au sack={sep[fin]:.2f} yd | démarqué au-delà de la ligne de scrimmage depuis "
      f"{libre_los[fin]:.1f} s, au-delà du 1er down depuis {libre_down[fin]:.1f} s | chip frame={chip} | "
      f"x chippeur={ev.x[fin]:.2f} (ligne {los:.0f}, 1er down {down1:.0f}) | rusher={rusher}")

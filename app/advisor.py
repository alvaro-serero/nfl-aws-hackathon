"""Chip Advisor: chip the edge rusher or not, with whom, for how long, and the backup read.

Run from repo root:  streamlit run app/advisor.py
Reads outputs/edge_rushers.csv and outputs/chips.csv (python src/build_tables.py). Observed rates, no trained model.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "app"))
from llm import coach_phrase  # noqa: E402

OUT = ROOT / "outputs"
SHORT_YD = 3        # 3e/4e et court = yardsToGo <= 3
LONG_CHIP_S = 0.6   # chip long = contact > 0,6 s
MIN_N = 30          # below this, the rate is flagged as fragile
SITUATIONS = ["Toutes", "1er/2e down", "3e/4e et court", "3e/4e et long"]
QUARTILES = ["Q1 (faible)", "Q2", "Q3", "Q4 (élite)"]
PLAYERS = {"TE": "inline_TE", "RB": "backfield"}
HIGHLIGHT, MUTED = "#2a78d6", "#b5b4ad"

# Headline numbers of each stage. Preliminary values from PLAN.md until results/A.md and results/B.md are merged.
ETAGES = [
    ("1. Le rusher", "-26 %", "de pression du rusher chippé, même rusher (IC95 -6,0 à -1,3 pts)"),
    ("2. Le comment", "8,5 %", "de pression si le chip dure > 1 s, contre 12,9 % entre 0,3 et 0,6 s"),
    ("3. L'action", "+0,5 s", "pour lancer, +0,8 yd, mais pas moins de sacks"),
    ("4. Le QB", "36 / 88", "sacks avec chip où le joueur qui a chippé était démarqué"),
]


def fr(x, digits=1):
    return f"{x:.{digits}f}".replace(".", ",")


def wilson(k, n, z=1.96):
    if n == 0:
        return np.nan, np.nan
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def situation(df):
    third = df.down.isin([3, 4])
    return np.select([df.down.isin([1, 2]), third & (df.yardsToGo <= SHORT_YD), third], SITUATIONS[1:], "Autre")


@st.cache_data
def load():
    edge = pd.read_csv(OUT / "edge_rushers.csv")
    chips = pd.read_csv(OUT / "chips.csv")
    dur = (chips.groupby(["gameId", "playId", "rusherId"]).chip_duration_s.max()
           .rename_axis(["gameId", "playId", "nflId"]))
    edge = edge.join(dur, on=["gameId", "playId", "nflId"])
    chips["chipper_targeted"] = chips.chipper_targeted.astype(str).eq("True").astype(float)
    _, bins = pd.qcut(edge.rusher_base_pressure_rate, 4, retbins=True)
    bins[0], bins[-1] = -np.inf, np.inf
    for df in (edge, chips):
        df["situation"] = situation(df)
        df["quartile"] = pd.cut(df.rusher_base_pressure_rate, bins, labels=QUARTILES)
    return edge, chips, bins


def options(e, c):
    """(label, edge-row mask, chip-row mask) for every option shown to the coach."""
    s = fr(LONG_CHIP_S)
    return [
        ("Sans chip", ~e.chipped, None),
        ("Chip inline TE", e.chip_type == "inline_TE", c.chip_type == "inline_TE"),
        ("Chip backfield (RB)", e.chip_type == "backfield", c.chip_type == "backfield"),
        (f"Chip court (≤ {s} s)", e.chipped & (e.chip_duration_s <= LONG_CHIP_S), c.chip_duration_s <= LONG_CHIP_S),
        (f"Chip long (> {s} s)", e.chipped & (e.chip_duration_s > LONG_CHIP_S), c.chip_duration_s > LONG_CHIP_S),
    ]


def table(e, c):
    rows = []
    for label, me, mc in options(e, c):
        g = e[me]
        n, k = len(g), int(g.pressure.sum())
        lo, hi = wilson(k, n)
        cg = c[mc] if mc is not None else c.iloc[0:0]
        rows.append({
            "Option": label, "n": n,
            "Pression du rusher": k / n if n else np.nan, "ic_lo": lo, "ic_hi": hi,
            "Coup sur le QB": g.pff_hit.mean(), "Sack": g.pff_sack.mean(),
            "Pression de l'action": g.play_pressure.mean(),
            "Sortie en route (s)": cg.chipper_release_s.median() if len(cg) else np.nan,
            "Ciblé ensuite": cg.chipper_targeted.mean() if len(cg) else np.nan,
        })
    return pd.DataFrame(rows).set_index("Option")


def recommendation(t, player):
    base, mine = t.loc["Sans chip"], t.iloc[1 if player == "TE" else 2]
    court, long_ = t.iloc[3], t.iloc[4]
    pct = lambda r: f"{fr(100 * r['Pression du rusher'])} %"
    lines = []
    if mine.n == 0 or base.n == 0:
        lines.append(f"**Pas assez d'actions** avec un chip {player} dans cette situation pour conclure.")
    elif mine["Pression du rusher"] < base["Pression du rusher"]:
        delta = 100 * (mine["Pression du rusher"] - base["Pression du rusher"])
        lines.append(f"**Chipper avec le {player}** : le rusher visé met la pression sur {pct(mine)} des actions, "
                     f"contre {pct(base)} sans chip ({fr(delta)} pts).")
    else:
        lines.append(f"**Pas de gain observé du chip {player} ici** : {pct(mine)} de pression contre {pct(base)} sans chip.")
    if court.n == 0 or long_.n == 0:
        lines.append("**Durée du chip** : pas assez d'actions dans cette situation pour comparer court et long.")
    elif long_["Pression du rusher"] < court["Pression du rusher"]:
        lines.append(f"**Tenir le chip plus de {fr(LONG_CHIP_S)} s** : {pct(long_)} contre {pct(court)} pour un chip court, "
                     f"au prix d'une sortie en route plus tardive ({fr(long_['Sortie en route (s)'])} s contre "
                     f"{fr(court['Sortie en route (s)'])} s après le snap).")
    else:
        lines.append(f"**Un chip court suffit** : {pct(court)} de pression contre {pct(long_)} pour un chip long, "
                     f"et le joueur part en route plus tôt ({fr(court['Sortie en route (s)'])} s après le snap).")
    lines.append("**Lecture de secours** : si rien n'est ouvert vers 3 s, lâcher le ballon au joueur qui a chippé.")
    fragile = [o for o in [base.name, mine.name, court.name, long_.name] if t.loc[o, "n"] < MIN_N]
    return lines, fragile


def chart(t, player):
    focus = t.index[1 if player == "TE" else 2]
    t = t.iloc[::-1]
    colors = [HIGHLIGHT if o == focus else MUTED for o in t.index]
    fig = go.Figure(go.Bar(
        x=100 * t["Pression du rusher"], y=t.index, orientation="h", marker_color=colors,
        error_x=dict(type="data", symmetric=False, array=100 * (t.ic_hi - t["Pression du rusher"]),
                     arrayminus=100 * (t["Pression du rusher"] - t.ic_lo), thickness=1.5, width=4),
        customdata=np.c_[t.n, 100 * t.ic_lo, 100 * t.ic_hi],
        hovertemplate="%{y}<br>Pression : %{x:.1f} %<br>IC95 : %{customdata[1]:.1f} - %{customdata[2]:.1f} %"
                      "<br>n = %{customdata[0]}<extra></extra>",
        text=[f"{fr(100 * v)} %  (n={n})" for v, n in zip(t["Pression du rusher"], t.n)],
        textposition="inside", insidetextanchor="start", constraintext="none",
        textfont=dict(color=["white" if o == focus else "#0b0b0b" for o in t.index]),
    ))
    fig.update_layout(height=300, margin=dict(l=10, r=20, t=10, b=30), bargap=0.3,
                      xaxis=dict(title="Pression du rusher visé (%), IC95", rangemode="tozero", showgrid=True),
                      yaxis=dict(showgrid=False))
    return fig


st.set_page_config(page_title="Chip Advisor", page_icon="🏈", layout="wide")
edge, chips, bins = load()

st.title("🏈 Chip Advisor")
st.markdown("Le chip marche. Voici **comment** le faire (type et durée) et **quoi faire ensuite** : le joueur qui a "
            "chippé est la soupape anti-sack vers 3 s.")
for col, (title, value, caption) in zip(st.columns(4), ETAGES):
    col.metric(title, value)
    col.caption(caption)

with st.sidebar:
    st.header("La situation")
    sit = st.radio("Down et distance", SITUATIONS, index=0,
                   help=f"Court = {SHORT_YD} yards ou moins à gagner.")
    mode = st.radio("Edge rusher", ["Par quartile de qualité", "Par nom"], horizontal=True)
    rusher = None
    if mode == "Par nom":
        names = edge.rusher_name.value_counts().index.tolist()
        rusher = st.selectbox("Rusher adverse", names)
        rate = edge.loc[edge.rusher_name == rusher, "rusher_base_pressure_rate"].median()
        quart = str(pd.cut([rate], bins, labels=QUARTILES)[0])
        st.caption(f"Taux de pression habituel : {fr(100 * rate)} % → **{quart}**")
    else:
        quart = st.select_slider("Qualité du rusher (taux de pression habituel)", QUARTILES, value=QUARTILES[-1])
    player = st.radio("Joueur disponible pour chipper", list(PLAYERS), horizontal=True)
    st.caption("Taux observés, semaines 1 à 8 de 2021 (NGS + PFF). Pas de modèle : chaque chiffre est un comptage.")

e = edge[edge.quartile == quart]
c = chips[chips.quartile == quart]
if sit != "Toutes":
    e, c = e[e.situation == sit], c[c.situation == sit]
t = table(e, c)

tab_conseil, tab_anim, tab_preuves = st.tabs(["Conseil", "Animation d'un sack", "Preuves"])

with tab_conseil:
    st.subheader(f"{sit} · rusher {quart} · {player} disponible")
    lines, fragile = recommendation(t, player)
    st.success("\n\n".join(lines))
    if fragile:
        st.warning(f"Échantillon faible (n < {MIN_N}) pour : {', '.join(fragile)}. À prendre avec prudence.")
    if rusher:
        r = edge[edge.rusher_name == rusher]
        rc = r[r.chipped]
        st.caption(f"{rusher} : {len(r)} rushes, pression sur {fr(100 * r.pressure.mean())} % ; chippé {len(rc)} fois"
                   + (f", pression sur {fr(100 * rc.pressure.mean())} % de ces actions." if len(rc) else "."))

    left, right = st.columns([3, 2])
    with left:
        st.plotly_chart(chart(t, player), width="stretch")
    with right:
        st.markdown("**Le prix du chip** : le chip déplace la pression, il ne la supprime pas.")
        play_no, play_chip = e[~e.chipped].play_pressure.mean(), e[e.chipped].play_pressure.mean()
        st.markdown(f"Pression de l'action : {fr(100 * play_no)} % sans chip, {fr(100 * play_chip)} % avec chip.")
        st.markdown(f"Le joueur qui chippe part en route à {fr(t.iloc[1]['Sortie en route (s)'])} s (TE) ou "
                    f"{fr(t.iloc[2]['Sortie en route (s)'])} s (RB) après le snap.")

    show = t.drop(columns=["ic_lo", "ic_hi"])
    pcts = ["Pression du rusher", "Coup sur le QB", "Sack", "Pression de l'action", "Ciblé ensuite"]
    st.dataframe(show.style.format({**{k: lambda v: "" if pd.isna(v) else f"{fr(100 * v)} %" for k in pcts},
                                    "Sortie en route (s)": lambda v: "" if pd.isna(v) else fr(v, 2)}),
                 width="stretch")

    st.info("**Lecture de secours (étage 4)** · Sur 88 sacks avec chip, le TE/RB qui avait chippé était démarqué "
            "(≥ 3 yd) au-delà de la ligne depuis au moins 1 s dans **36 cas**, alors que chaque sack a coûté 7,4 yards. "
            "Règle de progression : quand rien n'est ouvert vers 3 s, lâcher le ballon au joueur qui a chippé "
            "(82 % de réception, IC95 76-88 %). En temps normal, le QB a raison de l'ignorer : l'option choisie vaut "
            "4,0 yards attendus de plus.")

    if st.button("✍️ Reformuler pour le coach (Amazon Bedrock)"):
        facts = (f"Situation : {sit}. Rusher adverse : {quart}" + (f" ({rusher})" if rusher else "")
                 + f". Joueur disponible : {player}.\n" + "\n".join(lines).replace("**", "")
                 + "\nTableau :\n" + show.round(3).to_string())
        text, source = coach_phrase(facts, " ".join(lines).replace("**", ""))
        st.markdown(f"> {text}")
        st.caption(f"Source : {source}")

with tab_anim:
    st.markdown("NYJ, 2e et 2 : le TE qui a chippé le futur sackeur est démarqué au-delà du 1er down depuis 3,9 s.")
    anim = ROOT / "chip_sack.html"
    if anim.exists():
        st.iframe(anim, height=840)
    else:
        st.info("chip_sack.html introuvable (généré par animate_sack.py, branche B).")

with tab_preuves:
    for name in ["A", "B"]:
        md = ROOT / "results" / f"{name}.md"
        with st.expander(f"Chiffres clés de la branche {name}", expanded=md.exists()):
            st.markdown(md.read_text() if md.exists() else "Pas encore fusionnée : chiffres préliminaires de PLAN.md.")
    figs = sorted((ROOT / "figures").glob("*.png")) + [p for p in [ROOT / "insight.png", ROOT / "chip_sack.png"] if p.exists()]
    for col, fig in zip(st.columns(2) * len(figs), figs):
        col.image(str(fig), caption=fig.name, width="stretch")

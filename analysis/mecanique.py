"""Branche A : quel chip protège le mieux, et à quel prix pour la route ?

Lancer depuis la racine du dépôt (après `python src/build_tables.py`) :
    python analysis/mecanique.py

Partie 1 : deux régressions logistiques avec IC 95 % par bootstrap groupé par match.
  - Régression 1 (outputs/edge_rushers.csv) : pression de l'edge rusher ~ type de chip (référence : non chippé)
    + qualité du rusher + yardsToGo + 3e/4e down + play action. Pas de throw_time_s (conséquence du chip).
  - Régression 2 (outputs/chips.csv, contact détecté) : pression du rusher chippé ~ durée du chip + type de chip
    (référence : TE en ligne) + qualité du rusher + même contexte.
Partie 2 : figures/A_type.png (pression par type), figures/A_duree.png (compromis protection / sortie en route),
  figures/A_quartile.png (chippé vs non chippé selon la qualité du rusher).
"""
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # pas de fenêtre : le script tourne sans intervention
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

OUT = Path("outputs")
FIG = Path("figures")
SEED = 2021
N_BOOT = 500
CHIP_TYPES = ["inline_TE", "backfield", "slot_wide"]
CONTEXT = ["rusher_base_pressure_rate", "yardsToGo", "late_down", "play_action"]

EDGE_COLS = ["gameId", "pressure", "chip_type", "chipped", "rusher_base_pressure_rate", "yardsToGo", "down",
             "pff_playAction", "play_pressure"]
CHIP_COLS = ["gameId", "chip_detected", "chip_type", "chip_duration_s", "chipper_release_s", "rusher_pressure",
             "rusher_base_pressure_rate", "yardsToGo", "down", "pff_playAction", "passResult", "chipper_targeted",
             "play_pressure", "throw_time_s"]
RESULTS = Path("results")


# ---------------------------------------------------------------- chargement
def to_bool(s):
    """bool / 0-1 / 'True'-'False' -> float 1.0 / 0.0, NaN conservé."""
    mapped = s.map(lambda v: {"true": 1.0, "false": 0.0, "1": 1.0, "0": 0.0, "1.0": 1.0, "0.0": 0.0}
                   .get(str(v).strip().lower(), np.nan) if pd.notna(v) else np.nan)
    return mapped.astype(float)


def load(name, cols):
    path = OUT / name
    if not path.exists():
        sys.exit(f"[erreur] {path} introuvable. Créer le dossier outputs/ puis lancer : python src/build_tables.py")
    df = pd.read_csv(path, low_memory=False)
    missing = [c for c in cols if c not in df.columns]
    if missing:
        sys.exit(f"[erreur] colonnes absentes de {path} : {missing}. Relancer : python src/build_tables.py")
    return df


def prepare(df, name):
    n0 = len(df)
    df = df.copy()
    df["late_down"] = df["down"].isin([3, 4]).astype(float)
    df["play_action"] = to_bool(df["pff_playAction"])
    df = df[np.isfinite(df["rusher_base_pressure_rate"])]
    print(f"{name:<18} lues={n0:>6}  exclues={n0 - len(df):>5}  retenues={len(df):>6}")
    if df.empty:
        sys.exit(f"[erreur] {name} est vide après filtrage.")
    return df


def load_tables():
    edges = load("edge_rushers.csv", EDGE_COLS)
    chips = load("chips.csv", CHIP_COLS)
    chips = chips[to_bool(chips["chip_detected"]) == 1]          # contact détecté uniquement
    for t in CHIP_TYPES:                                          # indicatrices du type de chip
        edges[t] = (edges["chip_type"] == t).astype(float)
        chips[t] = (chips["chip_type"] == t).astype(float)
    edges["chipped"] = to_bool(edges["chipped"])
    chips["chipper_targeted"] = to_bool(chips["chipper_targeted"])
    return prepare(edges, "edge_rushers.csv"), prepare(chips, "chips.csv")


# ---------------------------------------------------------------- régressions
class Logit:
    """Logit sans pénalité par Newton-Raphson (IRLS) : ~6 itérations, assez rapide pour 500 tirages bootstrap.
    Même interface que scikit-learn (coef_, intercept_, predict_proba)."""

    def fit(self, X, y, n_iter=25, tol=1e-8):
        X = np.column_stack([np.ones(len(X)), np.asarray(X, float)])
        y = np.asarray(y, float)
        beta = np.zeros(X.shape[1])
        for _ in range(n_iter):
            p = 1 / (1 + np.exp(-X @ beta))
            w = p * (1 - p)
            step = np.linalg.solve((X * w[:, None]).T @ X + 1e-9 * np.eye(X.shape[1]), X.T @ (y - p))
            beta += step
            if np.abs(step).max() < tol:
                break
        self.intercept_, self.coef_ = beta[:1], beta[None, 1:]
        return self

    def predict_proba(self, X):
        p = 1 / (1 + np.exp(-(np.asarray(X, float) @ self.coef_[0] + self.intercept_[0])))
        return np.column_stack([1 - p, p])


def fit_logit(X, y):
    return Logit().fit(X, y)


def cluster_bootstrap(df, features, target, valid, n_boot=N_BOOT, seed=SEED):
    """Rééchantillonne les matchs (gameId) avec remise. Renvoie (coefs (n_valides x p), n_ignorés)."""
    rng = np.random.default_rng(seed)
    X, y = df[features].to_numpy(float), df[target].to_numpy(float)
    groups = list(df.reset_index(drop=True).groupby("gameId").indices.values())
    coefs, skipped = [], 0
    for _ in range(n_boot):
        idx = np.concatenate([groups[i] for i in rng.integers(0, len(groups), len(groups))])
        if not valid(X[idx], y[idx]):
            skipped += 1
            continue
        coefs.append(fit_logit(X[idx], y[idx]).coef_[0])
    return np.array(coefs), skipped


def run_logit(df, features, target, valid, label):
    d = df.dropna(subset=features + [target])
    if len(d) < len(df):
        print(f"  {len(df) - len(d)} lignes exclues (valeurs manquantes)")
    model = fit_logit(d[features], d[target])
    boot, skipped = cluster_bootstrap(d, features, target, valid)
    lo, hi = np.percentile(boot, [2.5, 97.5], axis=0)
    res = pd.DataFrame({"coef": model.coef_[0], "OR": np.exp(model.coef_[0]),
                        "OR_lo": np.exp(lo), "OR_hi": np.exp(hi)}, index=features)
    print(f"\n=== {label} : n={len(d)}, matchs={d.gameId.nunique()}, "
          f"tirages valides={len(boot)}/{N_BOOT} (ignorés : {skipped})")
    if len(boot) < 0.8 * N_BOOT:
        print("  [attention] moins de 400 tirages valides")
    return model, d, res, boot


def effect_points(model, d, features, col, rows, base, new):
    """Effet moyen (points de %) sur `rows` : proba prédite avec col=new(col) moins proba avec col=base(col)."""
    X0 = d.loc[rows, features].copy()
    X1 = X0.copy()
    X0[col], X1[col] = base(X0[col]), new(X1[col])
    return 100 * (model.predict_proba(X1)[:, 1] - model.predict_proba(X0)[:, 1]).mean()


def regression_type(edges):
    """Régression 1 : pression ~ type de chip (réf. non chippé) + qualité + contexte."""
    feats = CHIP_TYPES + CONTEXT
    for t in CHIP_TYPES:
        if edges[t].sum() < 30:
            print(f"  [attention] {t} : seulement {int(edges[t].sum())} lignes")

    def valid(X, y):  # 0 et 1 présents, et chaque type de chip présent
        return 0 < y.sum() < len(y) and (X[:, :3].sum(axis=0) > 0).all()

    model, d, res, boot = run_logit(edges, feats, "pressure", valid, "Régression 1 : type de chip (edge_rushers)")
    print(f"  référence non chippé : n={int((d[CHIP_TYPES].sum(axis=1) == 0).sum())}")
    print(f"  {'type':<10} {'n':>5} {'OR':>6} {'IC 95 %':>15} {'effet (pts)':>12}")
    for t in CHIP_TYPES:
        r = res.loc[t]
        pts = effect_points(model, d, feats, t, d[t] == 1, base=lambda s: 0.0, new=lambda s: 1.0)
        res.loc[t, "pts"] = pts
        res.loc[t, "n"] = int(d[t].sum())
        sig = "" if r.OR_lo <= 1 <= r.OR_hi else " *"
        print(f"  {t:<10} {int(d[t].sum()):>5} {r.OR:>6.2f} [{r.OR_lo:>5.2f} ; {r.OR_hi:>5.2f}] {pts:>+11.1f}{sig}")
    print("  (OR < 1 = moins de pression ; effet = écart ajusté en points, à rusher et situation égaux ;"
          " * = IC exclut 1)")
    return res


def regression_duree(chips):
    """Régression 2 : pression du rusher chippé ~ durée + type (réf. TE en ligne) + qualité + contexte."""
    feats = ["chip_duration_s", "backfield", "slot_wide"] + CONTEXT

    def valid(X, y):  # 0 et 1 présents, et les trois types présents
        n_bf, n_sw = X[:, 1].sum(), X[:, 2].sum()
        return 0 < y.sum() < len(y) and n_bf > 0 and n_sw > 0 and n_bf + n_sw < len(y)

    model, d, res, boot = run_logit(chips, feats, "rusher_pressure", valid,
                                    "Régression 2 : durée du chip (chips)")
    r = res.loc["chip_duration_s"]
    pts = effect_points(model, d, feats, "chip_duration_s", d.index, base=lambda s: s, new=lambda s: s + 0.5)
    res.loc["chip_duration_s", "pts_per_half_s"] = pts
    sig = "exclut 1 (significatif à 5 %)" if not (r.OR_lo <= 1 <= r.OR_hi) else "contient 1 (non significatif)"
    print(f"  durée : OR par seconde = {r.OR:.2f} [{r.OR_lo:.2f} ; {r.OR_hi:.2f}], IC {sig}")
    print(f"  soit {pts:+.1f} pts de pression pour 0,5 s de chip en plus (moyenne sur les chips observés)")
    for t in ["backfield", "slot_wide"]:
        rr = res.loc[t]
        print(f"  {t:<10} vs TE en ligne : OR = {rr.OR:.2f} [{rr.OR_lo:.2f} ; {rr.OR_hi:.2f}]")

    # Robustesse : une passe rapide coupe le chip (durée tronquée). L'effet tient-il sans cette troncature ?
    long_play = d[d.throw_time_s >= 3.0]
    robust = {"n": len(d), "games": d.gameId.nunique(),
              "OR_throw3": float(np.exp(fit_logit(long_play[feats], long_play.rusher_pressure).coef_[0][0])),
              "n_throw3": len(long_play),
              "OR_ctrl_throw": float(np.exp(fit_logit(d[feats + ["throw_time_s"]], d.rusher_pressure).coef_[0][0]))}
    print(f"  robustesse : OR durée = {robust['OR_throw3']:.2f} sur les actions de 3 s ou plus "
          f"(n={robust['n_throw3']}), {robust['OR_ctrl_throw']:.2f} en contrôlant le temps avant la passe")
    return res, robust


# ---------------------------------------------------------------- figures
DUR_BINS = [0, 0.3, 0.6, 1.0, np.inf]                      # ]a ; b] : 0,3 s tombe dans « ≤ 0,3 s »
DUR_LABELS = ["≤ 0,3 s", "0,3 à 0,6 s", "0,6 à 1,0 s", "> 1,0 s"]
TYPE_LABELS = {"none": "Non chippé", "inline_TE": "TE en ligne", "backfield": "Running back\n(backfield)",
               "slot_wide": "Receveur\nslot / large"}
GREY, BLUE, ORANGE = "#9e9e9e", "#1f5fa8", "#e07b00"
SMALL_N = 30


def fr(x, d=1):
    """Nombre au format français : virgule décimale, espace pour les milliers, vrai signe moins."""
    return f"{x:,.{d}f}".replace(",", " ").replace(".", ",").replace("-", "−")


def fr_axis(ax, d=0, which="y"):
    """Graduations au format français (virgule décimale)."""
    axis = ax.yaxis if which == "y" else ax.xaxis
    axis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=6, steps=[1, 2, 2.5, 5, 10]))
    axis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: fr(v, d)))


def small_n_note(*tables):
    """Mention des barres hachurées seulement s'il y en a."""
    return " Barres hachurées : moins de 30 actions." if any((t.n < SMALL_N).any() for t in tables) else ""


def add_duration_bucket(chips):
    chips = chips.copy()
    chips["dur_bucket"] = pd.cut(chips["chip_duration_s"], DUR_BINS, right=True, labels=DUR_LABELS)
    return chips


def rate_ci(df, cat, val, cats, n_boot=N_BOOT, seed=SEED):
    """Taux de `val` par catégorie `cat` + IC 95 % par bootstrap groupé par match (vectorisé)."""
    d = df.dropna(subset=[val])
    agg = d.groupby(["gameId", cat], observed=False)[val].agg(["sum", "count"]).unstack(cat).fillna(0)
    S = agg["sum"].reindex(columns=cats, fill_value=0).to_numpy()
    C = agg["count"].reindex(columns=cats, fill_value=0).to_numpy()
    idx = np.random.default_rng(seed).integers(0, len(S), (n_boot, len(S)))
    with np.errstate(invalid="ignore", divide="ignore"):
        boot = S[idx].sum(axis=1) / C[idx].sum(axis=1)        # (n_boot, k), NaN si catégorie vide
        rate = S.sum(axis=0) / C.sum(axis=0)
    all_nan = np.isnan(boot).all(axis=0)
    lo, hi = np.full(len(cats), np.nan), np.full(len(cats), np.nan)
    if (~all_nan).any():
        lo[~all_nan], hi[~all_nan] = np.nanpercentile(boot[:, ~all_nan], [2.5, 97.5], axis=0)
    return pd.DataFrame({"rate": 100 * rate, "lo": 100 * lo, "hi": 100 * hi, "n": C.sum(axis=0).astype(int)},
                        index=cats)


def style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, alpha=0.3)
    ax.set_axisbelow(True)


def bars_with_ci(ax, x, r, colors, width=0.7, inside=False):
    """Barres + IC 95 % + étiquettes « 12 % / n = 499 » (au-dessus, ou en bas dans la barre si `inside`).
    Barres hachurées si n < 30."""
    yerr = np.vstack([r.rate - r.lo, r.hi - r.rate]).clip(min=0)
    bars = ax.bar(x, r.rate.fillna(0), width, color=colors, yerr=np.nan_to_num(yerr), capsize=5,
                  error_kw={"elinewidth": 1.2, "ecolor": "#333333"})
    for b, (_, row) in zip(bars, r.iterrows()):
        if row.n < SMALL_N:
            b.set_hatch("//")
            b.set_edgecolor("white")
        txt = f"{fr(row.rate, 0)} %\nn = {fr(row.n, 0)}" if row.n else "n = 0"
        cx = b.get_x() + b.get_width() / 2
        if inside and row.n:
            ax.text(cx, ax.get_ylim()[1] * 0.02, txt, ha="center", va="bottom", fontsize=9, color="white",
                    fontweight="bold", bbox={"facecolor": b.get_facecolor(), "edgecolor": "none", "pad": 1.5})
        else:
            top = row.hi if np.isfinite(row.hi) else (row.rate if np.isfinite(row.rate) else 0)
            ax.text(cx, top + 0.4, txt, ha="center", va="bottom", fontsize=9)
    return bars


def plot_type(edges, res1):
    """A_type.png : taux de pression brut par type de chip, avec l'effet ajusté de la régression 1."""
    d = edges.assign(cat=edges["chip_type"].fillna("none"))
    cats = ["none"] + CHIP_TYPES
    r = rate_ci(d, "cat", "pressure", cats)
    fig, ax = plt.subplots(figsize=(9, 5.8))
    x = np.arange(len(cats))
    bars_with_ci(ax, x, r, [GREY] + [BLUE] * 3)
    for i, t in enumerate(CHIP_TYPES, start=1):              # effet ajusté (régression 1) dans la barre
        row = res1.loc[t]
        sig = not (row.OR_lo <= 1 <= row.OR_hi)
        ax.text(i, 1.0, f"effet ajusté\n{fr(row.pts)} pts" + ("" if sig else "\n(non signif.)"),
                ha="center", va="bottom", color="white", fontsize=9, fontweight="bold")
    ax.set_xticks(x, [TYPE_LABELS[c] for c in cats])
    ax.set_ylabel("Taux de pression de l'edge rusher (%)")
    ax.set_ylim(0, max(r.hi.max(), r.rate.max()) * 1.3)
    fr_axis(ax)
    ax.set_title("Chipper l'edge rusher réduit sa pression, surtout avec un TE ou un running back",
                 fontsize=12, fontweight="bold", loc="left")
    fig.text(0.01, 0.01, "Barres : taux observé, IC 95 % (bootstrap par match). « Effet ajusté » : écart de pression "
             "estimé à qualité de rusher, down, distance\net play action égaux (régression logistique). "
             "Semaines 1 à 8 de 2021, edge rushers uniquement.", fontsize=7.5, color="#555555")
    style(ax)
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.savefig(FIG / "A_type.png", dpi=150)
    plt.close(fig)
    return r


def plot_duree(chips):
    """A_duree.png : barres = pression du rusher chippé, points = sortie en route (médiane), par durée du chip."""
    d = add_duration_bucket(chips.dropna(subset=["chip_duration_s"]))
    r = rate_ci(d, "dur_bucket", "rusher_pressure", DUR_LABELS)
    release = d.groupby("dur_bucket", observed=False)["chipper_release_s"].median().reindex(DUR_LABELS)
    fig, ax = plt.subplots(figsize=(9, 5.8))
    x = np.arange(len(DUR_LABELS))
    ax.set_ylim(0, max(r.hi.max(), r.rate.max()) * 1.35)    # avant les barres : position des étiquettes internes
    bars_with_ci(ax, x, r, [BLUE] * len(x), inside=True)
    ax.set_ylabel("Pression du rusher chippé (%)", color=BLUE)
    fr_axis(ax)
    ax.set_xticks(x, DUR_LABELS)
    ax.set_xlabel("Durée du contact entre le joueur qui chippe et le rusher")
    style(ax)

    ax2 = ax.twinx()
    ok = release.notna().to_numpy()
    ax2.plot(x[ok], release[ok], "o-", color=ORANGE, lw=2.5, ms=9, zorder=5)
    for xi, v in zip(x[ok], release[ok]):
        ax2.annotate(f"{fr(v, 2)} s", (xi, v), textcoords="offset points", xytext=(0, 10), ha="center",
                     color=ORANGE, fontweight="bold", fontsize=9)
    ax2.set_ylabel("Départ en route (médiane, s après le snap)", color=ORANGE)
    ax2.set_ylim(0, np.nanmax(release.to_numpy()) * 1.4)
    fr_axis(ax2, d=1)
    ax2.spines[["top"]].set_visible(False)

    handles = [plt.Rectangle((0, 0), 1, 1, color=BLUE), plt.Line2D([], [], color=ORANGE, marker="o", lw=2.5)]
    ax.legend(handles, ["Pression du rusher chippé (IC 95 %)", "Départ en route du joueur qui chippe"],
              loc="upper left", frameon=False, fontsize=9)
    ax.set_title("Un chip plus long protège mieux, mais le joueur part plus tard en route",
                 fontsize=12, fontweight="bold", loc="left")
    fig.text(0.01, 0.01, "Chips avec contact détecté (joueur à moins de 1,5 yd du rusher dans les 3 s après le snap) "
             "sur un edge rusher. IC 95 % par bootstrap par match." + small_n_note(r), fontsize=7.5, color="#555555")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIG / "A_duree.png", dpi=150)
    plt.close(fig)
    return r.assign(release_median=release.to_numpy())


def plot_quartile(edges):
    """A_quartile.png : pression chippé vs non chippé selon le quartile de qualité du rusher (Q4 = élite)."""
    q, bins = pd.qcut(edges["rusher_base_pressure_rate"], 4, labels=False, retbins=True, duplicates="drop")
    d = edges.assign(q=q, status=np.where(edges["chipped"] == 1, "chip", "none"))
    k = len(bins) - 1
    b = [fr(100 * v, 0) for v in bins]
    ranges = [f"moins de {b[1]} %"] + [f"{b[i]} à {b[i + 1]} %" for i in range(1, k - 1)] + [f"{b[k - 1]} % et plus"]
    labels = [f"Q{i + 1}{' élite' if i == k - 1 else ''}\n{ranges[i]}" for i in range(k)]
    rows = []
    for i in range(len(labels)):
        r = rate_ci(d[d.q == i], "status", "pressure", ["none", "chip"])
        rows.append(r.assign(q=i))
    r = pd.concat(rows)
    fig, ax = plt.subplots(figsize=(9, 5.8))
    x, w = np.arange(len(labels)), 0.38
    bars_with_ci(ax, x - w / 2, r.loc["none"], GREY, width=w)
    bars_with_ci(ax, x + w / 2, r.loc["chip"], BLUE, width=w)
    ax.set_xticks(x, labels)
    ax.set_xlabel("Qualité de l'edge rusher (taux de pression habituel, hors action courante)")
    ax.set_ylabel("Taux de pression de l'edge rusher (%)")
    ax.set_ylim(0, r.hi.max() * 1.3)
    fr_axis(ax)
    ax.legend([plt.Rectangle((0, 0), 1, 1, color=GREY), plt.Rectangle((0, 0), 1, 1, color=BLUE)],
              ["Non chippé", "Chippé"], loc="upper left", frameon=False)
    ax.set_title("Chippé, l'edge rusher met moins de pression, quel que soit son niveau",
                 fontsize=12, fontweight="bold", loc="left")
    fig.text(0.01, 0.01, "IC 95 % par bootstrap par match. Pris un par un, les écarts par quartile ne sont pas "
             "significatifs : l'effet d'ensemble est testé par la régression (A_type.png)." + small_n_note(r),
             fontsize=7.5, color="#555555")
    style(ax)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(FIG / "A_quartile.png", dpi=150)
    plt.close(fig)
    return r


def print_rates(title, r, extra=None):
    print(f"\n=== {title}")
    for k, row in r.iterrows():
        line = f"  {str(k).replace(chr(10), ' '):<24} {fr(row.rate):>6} % [{fr(row.lo):>5} ; {fr(row.hi):>5}]  n={int(row.n)}"
        if extra is not None:
            line += f"  {extra(k, row)}"
        print(line)


# ---------------------------------------------------------------- coût route, pression de l'action, rapport
MD_TYPE = {"inline_TE": "TE en ligne", "backfield": "Running back (backfield)", "slot_wide": "Receveur slot / large"}
COACH_TYPE = {"inline_TE": "le TE en ligne", "backfield": "le running back", "slot_wide": "le receveur du slot"}


def route_cost(chips, by, cats):
    """Coût pour la route : départ en route médian, taux de ciblage (passes C/I/IN seulement), pression du rusher."""
    g = chips.groupby(by, observed=False)
    return pd.DataFrame({"n": g.size(),
                         "release": g["chipper_release_s"].median(),
                         "n_pass": g["chipper_targeted"].count(),         # NaN hors C/I/IN (build_tables.py)
                         "targeted": 100 * g["chipper_targeted"].mean(),
                         "pressure": 100 * g["rusher_pressure"].mean()}).reindex(cats)


def play_pressure_check(chips):
    """Limite : la pression de l'action entière (n'importe quel défenseur) selon la durée du chip."""
    g = chips.dropna(subset=["play_pressure"]).groupby("dur_bucket", observed=False)["play_pressure"]
    r = pd.DataFrame({"rate": 100 * g.mean(), "n": g.size()}).reindex(DUR_LABELS)
    overall = 100 * chips["play_pressure"].mean()
    spread = r.rate.max() - r.rate.min()
    print("\n=== Limite : pression de l'action entière selon la durée du chip")
    for k, row in r.iterrows():
        flag = "  (effectif faible)" if 0 < row.n < SMALL_N else ""
        print(f"  {k:<12} {fr(row.rate):>6} %  n={int(row.n)}{flag}")
    print(f"  ensemble     {fr(overall):>6} %  n={int(chips.play_pressure.notna().sum())}  "
          f"(écart max entre durées : {fr(spread)} pts)")
    return r, overall, spread


def md_route_table(rc, labels):
    lines = ["| | Chips | Départ en route (médiane) | Ciblé ensuite (passes) | Pression du rusher chippé |",
             "|---|---|---|---|---|"]
    for k, row in rc.iterrows():
        flag = " (effectif faible)" if row.n < SMALL_N else ""
        lines.append(f"| {labels.get(k, k)}{flag} | {int(row.n)} | {fr(row.release, 2)} s | "
                     f"{fr(row.targeted)} % (n = {int(row.n_pass)}) | {fr(row.pressure)} % |")
    return "\n".join(lines)


def key_numbers(res1, r_type, res2, rc_dur):
    """Les 3 chiffres clés, en texte, réutilisés dans la console et dans results/A.md."""
    best = res1.loc[CHIP_TYPES, "OR"].idxmin()
    b = res1.loc[best]
    without_chip = r_type.loc[best, "rate"] - b.pts                     # pression attendue des mêmes actions sans chip
    rel = 100 * b.pts / without_chip
    sig_types = [COACH_TYPE[t] for t in CHIP_TYPES if not (res1.loc[t, "OR_lo"] <= 1 <= res1.loc[t, "OR_hi"])]
    d = res2.loc["chip_duration_s"]
    mid, long_ = rc_dur.loc["0,3 à 0,6 s"], rc_dur.loc["> 1,0 s"]
    k1 = (f"Chip par un {MD_TYPE[best]} : {fr(b.pts)} pts de pression pour l'edge rusher visé "
          f"({fr(rel, 0)} %), OR = {fr(b.OR, 2)} [IC 95 % {fr(b.OR_lo, 2)} ; {fr(b.OR_hi, 2)}], n = {int(b.n)} chips"
          + ("" if b.OR_hi < 1 else " (non significatif à 5 %)"))
    k2 = (f"Durée du chip : OR = {fr(d.OR, 2)} par seconde de contact [IC 95 % {fr(d.OR_lo, 2)} ; {fr(d.OR_hi, 2)}], "
          f"soit {fr(d.pts_per_half_s)} pts de pression associés à 0,5 s de contact en plus"
          + ("" if d.OR_hi < 1 else " (non significatif à 5 %)"))
    k3 = (f"Coût pour la route : un chip de plus d'1 s fait partir le joueur en route à {fr(long_.release, 2)} s "
          f"après le snap, contre {fr(mid.release, 2)} s pour un chip de 0,3 à 0,6 s "
          f"(n = {int(long_.n)} et {int(mid.n)} chips)")
    return dict(best=best, sig_types=sig_types, k=[k1, k2, k3], mid=mid, long=long_, rel=rel)


def write_report(res1, r_type, res2, robust, rc_type, rc_dur, pp, pp_overall, pp_spread, kn):
    RESULTS.mkdir(exist_ok=True)
    who = " ou ".join(kn["sig_types"]) if kn["sig_types"] else COACH_TYPE[kn["best"]]
    coach = (f"Contre un edge rusher dangereux, faites chipper {who} plutôt qu'un receveur et demandez un "
             f"contact de plus d'une seconde : sa pression passe de {fr(kn['mid'].pressure)} % à "
             f"{fr(kn['long'].pressure)} %, mais le joueur part en route à {fr(kn['long'].release, 2)} s : "
             f"c'est une lecture tardive (soupape), pas une première option.")
    if not kn["sig_types"]:
        coach += " Attention : l'effet du type de chip n'est pas significatif à 5 %."
    pp_line = " ; ".join(f"{k} : {fr(r.rate)} % (n = {int(r.n)}{', effectif faible' if r.n < SMALL_N else ''})"
                         for k, r in pp.iterrows())
    if pp_spread <= 5:
        pp_text = (f"La pression de l'action entière reste autour de {fr(pp_overall, 0)} % quelle que soit la durée "
                   f"du chip ({pp_line}) : le chip déplace la pression, il ne la supprime pas.")
    else:
        lo_k, hi_k = pp.rate.idxmin(), pp.rate.idxmax()
        pp_text = (f"La pression de l'action entière varie de {fr(pp_spread)} pts selon la durée du chip "
                   f"(minimum {lo_k}, maximum {hi_k}) : {pp_line}.")
    t = res1.loc[CHIP_TYPES]
    reg1 = "\n".join(f"| {MD_TYPE[k]} | {int(r.n)} | {fr(r_type.loc[k, 'rate'])} % | {fr(r.pts)} pts | "
                     f"{fr(r.OR, 2)} [{fr(r.OR_lo, 2)} ; {fr(r.OR_hi, 2)}] |" for k, r in t.iterrows())
    text = f"""# Branche A : quel chip protège le mieux, et à quel prix pour la route ?

Généré par `python analysis/mecanique.py` (ne pas éditer à la main). Semaines 1 à 8 de 2021, edge rushers.

## 3 chiffres clés

1. {kn['k'][0]}.
2. {kn['k'][1]}.
3. {kn['k'][2]}.

## Pour le coach

{coach}

## Figures

- `figures/A_type.png` : pression de l'edge rusher selon le type de chip (TE, RB, receveur), avec l'effet ajusté.
- `figures/A_duree.png` : le compromis, la pression baisse quand le chip dure, le départ en route recule.
- `figures/A_quartile.png` : chippé contre non chippé, par niveau du rusher (Q4 = élite).

## Détail

Non chippé : {fr(r_type.loc['none', 'rate'])} % de pression (n = {fr(r_type.loc['none', 'n'], 0)}).

| Type de chip | Chips | Pression observée | Effet ajusté | OR [IC 95 %] |
|---|---|---|---|---|
{reg1}

Coût pour la route, par type de chip (chips avec contact détecté) :

{md_route_table(rc_type, MD_TYPE)}

Coût pour la route, par durée du contact :

{md_route_table(rc_dur, dict())}

## Limites

- Biais de sélection : on ne connaît pas l'appel de jeu, et les chips ne sont pas décidés au hasard (qui est chippé, quand).
- {pp_text}
- La durée est une association, pas une preuve : un rusher qui se dégage vite raccourcit aussi le contact. L'effet tient sur les actions de 3 s ou plus (OR = {fr(robust['OR_throw3'], 2)}, n = {robust['n_throw3']}) et en contrôlant le temps avant la passe (OR = {fr(robust['OR_ctrl_throw'], 2)}).
- Effectifs : {int(rc_dur.loc['≤ 0,3 s', 'n'])} chips de 0,3 s ou moins seulement ; ciblage calculé sur les seules passes (C, I, IN).
- Méthode : régressions logistiques, IC 95 % par bootstrap sur les matchs ({N_BOOT} tirages, graine {SEED}).
"""
    (RESULTS / "A.md").write_text(text, encoding="utf-8")
    return text


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # console Windows (cp1252) : « ≤ » sinon plante
    edges, chips = load_tables()
    res1 = regression_type(edges)
    res2, robust = regression_duree(chips)

    FIG.mkdir(exist_ok=True)
    r_type = plot_type(edges, res1)
    print_rates("Figure A_type.png : pression de l'edge rusher par type", r_type.rename(index=TYPE_LABELS))
    r_dur = plot_duree(chips)
    print_rates("Figure A_duree.png : pression du rusher chippé par durée", r_dur,
                lambda k, row: f"départ en route médian = {fr(row.release_median, 2)} s")
    r_q = plot_quartile(edges)
    print_rates("Figure A_quartile.png : pression par quartile de qualité (Q1 -> Q4 élite)",
                r_q.set_index(r_q.index + " Q" + (r_q.q + 1).astype(str)).sort_index(key=lambda s: s.str[-1]))
    print(f"\nFigures écrites : {FIG / 'A_type.png'}, {FIG / 'A_duree.png'}, {FIG / 'A_quartile.png'}")

    chips_b = add_duration_bucket(chips)
    rc_type = route_cost(chips_b, "chip_type", CHIP_TYPES)
    rc_dur = route_cost(chips_b, "dur_bucket", DUR_LABELS)
    print("\n=== Coût pour la route (départ médian, ciblage sur les passes)")
    for name, rc in [("par type", rc_type), ("par durée", rc_dur)]:
        for k, row in rc.iterrows():
            print(f"  {name:<9} {k:<12} n={int(row.n):>4}  départ={fr(row.release, 2)} s  "
                  f"ciblé={fr(row.targeted)} % (n={int(row.n_pass)})")
    pp, pp_overall, pp_spread = play_pressure_check(chips_b)

    kn = key_numbers(res1, r_type, res2, rc_dur)
    write_report(res1, r_type, res2, robust, rc_type, rc_dur, pp, pp_overall, pp_spread, kn)
    print(f"\n=== 3 chiffres clés (écrits dans {RESULTS / 'A.md'})")
    for i, k in enumerate(kn["k"], 1):
        print(f"  {i}. {k}")


if __name__ == "__main__":
    main()

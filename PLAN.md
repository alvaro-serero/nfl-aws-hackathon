# PLAN : le bilan complet du chip

Fin du hackathon vers 16 h 05. Ce fichier dit qui fait quoi, dans quels fichiers, et comment on fusionne sans conflit.

## L'histoire qu'on raconte (le pitch en une phrase)

> Le chip marche, voici **comment** le faire (type et durée) et **quoi faire ensuite** (le joueur qui a chippé est la
> soupape anti-sack vers 3 s). On le transforme en un outil de décision pour le coach.

Quatre étages, chacun appuyé sur un chiffre :

| Étage | Question | Statut | Source |
|---|---|---|---|
| 1. Le rusher | Le chip gêne-t-il le rusher visé ? | **Fait** : -26 %, même rusher chippé ou non (10,5 % contre 14,1 %, IC95 -6,0 à -1,3 pts) | `coach.py` |
| 2. Le comment | Quel type de chip, combien de temps ? | **Fait (A)** : TE en ligne -3,6 pts (OR 0,71) ; chip > 1 s : 8,5 % contre 12,9 %, mais départ en route à 2,20 s contre 1,50 s | `analysis/mecanique.py`, `results/A.md` |
| 3. L'action | Que devient l'action ? | **Fait** : lancer +0,5 s, +0,8 yd ; à situation égale, pas plus de sacks de façon significative (8,4 % contre 6,7 %, IC95 de l'écart -0,1 à +3,4 pts) | `coach.py`, `decision.py` |
| 4. Le QB | Faut-il lancer au joueur qui a chippé ? | **Fait (B)** : non en temps normal (+4,0 yd pour la cible choisie), oui sur les sacks (démarqué dans 36 des 88 sacks avec chip) | `decision.py`, `results/B.md` |
| → Outil | Chip ou pas, lequel, combien de temps, et le plan B | **Fait (C)** : app web Chip Advisor, https://chip-advisor-rouge.vercel.app | `app/` |

## Architecture du repo

```
data/                     # données organisateurs (ignoré par git : *.csv)
src/build_tables.py       # COMMUN, sur main : construit outputs/chips.csv et outputs/edge_rushers.csv (~20 s)
outputs/                  # tables générées (ignorées par git, chacun relance build_tables.py)
analysis/                 # NOUVEAU, branche A uniquement
  mecanique.py            #   type et durée du chip -> figures/A_*.png + results/A.md
figures/                  # NOUVEAU : A_*.png (branche A), B_*.png (branche B)
results/                  # NOUVEAU : A.md, B.md = les chiffres clés que la branche C reprend
app/                      # NOUVEAU, branche C uniquement : app web « Chip Advisor »
  server.py               #   serveur local (python app/server.py)
  export_static.py        #   exporte static/data/ pour Vercel
  static/                 #   front HTML/CSS/JS (verdict, comparaison, replay terrain des vraies actions)
  llm.py, api/brief.js    #   briefing du coach via Mistral (local / Vercel)
coach.py, decision.py, chart.py, animate_sack.py   # existants, branche B uniquement
insight.png, chip_sack.png, chip_sack.html         # existants, branche B uniquement
README.md, PLAN.md        # branche C uniquement (après le merge de A et B)
ideas.md                  # branche B uniquement
requirements.txt          # sur main, ne plus y toucher (ou une seule personne : C)
```

**Règle d'or : chaque branche ne modifie que ses propres fichiers.** Personne ne déplace ni ne renomme un fichier
existant avant la fin (ça crée des conflits). Si tu as besoin d'un chiffre d'une autre branche, lis son `results/X.md`.

## Les tables communes (`src/build_tables.py`)

Lancer `python src/build_tables.py` depuis la racine. Définitions en tête du script.

- `outputs/chips.csv` : une ligne par chip (1 565 ; contact détecté sur 1 527). Colonnes clés :
  `chip_type` (`inline_TE`, `backfield`, `slot_wide`), `chip_start_s`, `chip_duration_s`, `chipper_release_s`,
  `rusher_pressure`, `rusher_hit`, `rusher_sack`, `time_to_qb_s`, `min_dist_qb`, `rusher_base_pressure_rate`,
  `chipper_targeted`, `play_pressure`, `throw_time_s`, contexte (`down`, `yardsToGo`, `pff_passCoverage`, ...),
  `passResult`, `playResult`.
- `outputs/edge_rushers.csv` : une ligne par edge rusher et par action, chippé ou non (22 254 dont 1 449 chippés) :
  `chipped`, `chip_type`, `pressure`, `pff_hit`, `pff_sack`, `time_to_qb_s`, `rusher_base_pressure_rate`
  (taux de pression habituel du rusher, hors action courante), contexte.
- Contact = joueur qui chippe à moins de 1,5 yd du rusher dans les 3 s après le snap. Durée = du premier au dernier
  frame de contact. Ne pas utiliser `rusher_speed_drop` (biaisé par le moment du chip).

## Branche A : `feat/chip-mecanique` (type et durée du chip)

**Responsable : ______** · fichiers : `analysis/`, `figures/A_*`, `results/A.md`

Question : quel chip protège le mieux, et à quel prix pour la route ?

Chiffres préliminaires (à confirmer et à mettre en forme) :

| Type | n | Pression du rusher chippé | Sortie en route (médiane, s après snap) | Ciblé ensuite |
|---|---|---|---|---|
| inline_TE | 514 | 10,3 % | 1,5 | 16 % |
| backfield | 509 | 10,4 % | 2,2 | 11 % |
| slot_wide | 504 | 12,4 % | 1,4 | 15 % |

| Durée | n | Pression du rusher chippé | Sortie en route |
|---|---|---|---|
| ≤ 0,3 s | 52 | 11,4 % | 1,55 |
| 0,3-0,6 s | 705 | 12,9 % | 1,50 |
| 0,6-1,0 s | 565 | 9,7 % | 1,70 |
| > 1,0 s | 205 | 8,5 % | 2,20 |

Edge rushers chippés vs non chippés, par quartile de qualité : moins de pression dans les 4 quartiles
(élite : 14,7 % contre 16,9 %). Coups sur le QB : 1,7 % contre 2,6 %.

À faire, dans l'ordre :
1. `analysis/mecanique.py` : régression logistique sur `edge_rushers.csv` :
   `pressure ~ type de chip (3 indicatrices) + rusher_base_pressure_rate + yardsToGo + 3e/4e down + pff_playAction`.
   Ne pas mettre `throw_time_s` (c'est une conséquence du chip, pas une cause).
   Puis sur `chips.csv` : `rusher_pressure ~ chip_duration_s + chip_type + rusher_base_pressure_rate + contexte`.
2. Deux figures : `figures/A_type.png` (pression par type, avec IC) et `figures/A_duree.png` (le compromis :
   pression du rusher qui baisse, sortie en route qui recule, en fonction de la durée).
3. Vérifier la limite : la pression totale de l'action ne baisse pas (≈ 44 % quelle que soit la durée). Le dire
   honnêtement : le chip déplace la pression, il ne la supprime pas.
4. `results/A.md` : 3 chiffres clés + une phrase pour le coach + noms des figures.

## Branche B : `feat/decision-qb` (lancer au joueur qui a chippé ?)

**Responsable : Clément** (auteur de `decision.py`) · fichiers : `coach.py`, `decision.py`, `chart.py`,
`animate_sack.py`, `ideas.md`, `figures/B_*`, `results/B.md`

L'analyse existe déjà. À faire :
1. Découper le résultat « soupape sur les sacks » par **type de chip** (inline TE / backfield) avec la colonne
   `chip_type` de `outputs/chips.csv` (jointure sur `gameId`, `playId`, `nflId`). Ça relie l'étage 4 à la branche A.
2. Ajouter au moins le « 36 % contre 30 % sur les mêmes actions » comme limite assumée.
3. `results/B.md` : 3 chiffres clés + la règle pour le coach de QB + noms des figures (`insight.png`, `chip_sack.png`
   peuvent rester où ils sont).

## Branche C : `feat/app-pitch` (outil + pitch + AWS)

**Responsable : Alvaro** · fichiers : `app/`, puis `README.md` et `PLAN.md` après le merge de A et B

**Réalisé** : app web (HTML/JS + serveur Python) à la place de Streamlit, briefing via Mistral à la place de Bedrock,
déployée sur Vercel (https://chip-advisor-rouge.vercel.app).

1. `app/advisor.py` (Streamlit, `streamlit run app/advisor.py`). Pas de modèle à entraîner, des taux observés :
   - Entrées : situation (1er/2e down, 3e/4e et court, 3e/4e et long), qualité de l'edge rusher (quartile de
     `rusher_base_pressure_rate`, ou choix du rusher par nom), joueur disponible (TE ou RB).
   - Sortie : taux de pression observé **sans chip / chip inline TE / chip backfield / chip court / chip long**
     dans cette situation, avec le nombre d'actions (n) affiché, calculé à la volée depuis `outputs/*.csv`.
   - Encadré « lecture de secours » : le chiffre de la branche B (soupape démarquée sur 36 des 88 sacks).
   - Intégrer l'animation `chip_sack.html` (`st.components.v1.html`).
   - Tant que A et B ne sont pas fusionnées, utiliser les chiffres préliminaires de ce PLAN.
2. (Optionnel, si tout le reste marche à 15 h 30) `app/llm.py` : Amazon Bedrock (`boto3`, API `converse`,
   modèle via la variable d'environnement `BEDROCK_MODEL_ID`) reformule la recommandation en 2 phrases de coach.
   Prévoir un texte de secours sans appel si pas d'identifiants AWS.
3. Slides (5 max) : problème → étage 1 → étage 2 (type, durée) → étage 4 (soupape) → démo de l'outil → limites.
4. Après les merges : mettre à jour `README.md` (comment lancer, les 4 étages, figures).

## Git : démarrage et fusion

Démarrage (une seule personne, maintenant) :
```bash
git add src/build_tables.py requirements.txt PLAN.md && git commit -m "Tables communes du chip et plan" && git push
```
Puis chacun :
```bash
git pull && pip install -r requirements.txt && python src/build_tables.py
git checkout -b feat/chip-mecanique   # ou feat/decision-qb, feat/app-pitch
# ... travail, commits fréquents ...
git push -u origin <ta-branche>
```
Fusion (ordre fixe, une personne aux commandes, via PR GitHub ou en local) :
1. **15 h 30** : merge `feat/chip-mecanique` puis `feat/decision-qb` dans `main` (fichiers disjoints, pas de conflit).
2. La branche C fait `git pull origin main` (ou `git merge main`), reprend les chiffres de `results/A.md` et
   `results/B.md`, met à jour README, puis merge `feat/app-pitch` dans `main` vers **15 h 45**.
3. Personne ne pousse sur `main` directement après 15 h 30 sauf la personne aux commandes.

## Planning

| Heure | A | B | C |
|---|---|---|---|
| 14 h 50 | branche créée, tables générées | branche créée | branche créée, squelette Streamlit |
| 15 h 15 | régressions + 2 figures | découpage par type de chip | app qui tourne avec chiffres préliminaires, slides commencées |
| 15 h 30 | **gel** : `results/A.md` poussé, merge | **gel** : `results/B.md` poussé, merge | intègre A et B |
| 15 h 45 | relit les slides | relit les slides | merge final, README |
| 15 h 45-16 h | répétition du pitch (3 min) + démo | | |

## Limites à dire au jury (honnêteté = crédibilité)

- 8 semaines de 2021 ; pas d'info sur l'appel de jeu, donc biais de sélection sur qui est chippé et quand.
- Le chip réduit la pression du rusher visé mais pas forcément celle de l'action (elle arrive d'ailleurs).
- Tracking coupé ~0,4 s après le lancer : pas de YAC, et les coups sur le QB après le lancer sont mal captés.
- Échantillons limités : 88 sacks avec chip, ~200 passes vers le joueur qui a chippé.

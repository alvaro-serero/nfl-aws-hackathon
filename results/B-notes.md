# Notes de la branche B pour A, C et Alvaro (21/10, 15 h 30)

À lire avant de reprendre un chiffre de la branche B. La source de vérité est `results/B.md` : chaque chiffre y est
relié à la ligne imprimée par un script. Les trois branches modifient des fichiers disjoints : `git merge-tree` ne
trouve aucun conflit entre `main`, A, B et C (vérifié à 15 h 30).

## Pour C (`feat/app-pitch` : `app/`, puis `README.md` et `PLAN.md`)
1. Après la fusion de A et B, remplacer les valeurs préliminaires de `app/advisor.py` (commentaire ligne 27) par
   celles de `results/A.md` et `results/B.md`.
2. Étage 3 : ne plus écrire « plus de sacks ». À situation égale (down × distance × nombre de rushers), les sacks ne
   sont pas significativement plus nombreux : 8,4 % contre 6,7 %, +1,7 pt, IC95 -0,1 à +3,4 (`coach.py`). Le libellé
   actuel de l'app (« pas moins de sacks ») reste juste ; le tableau de `PLAN.md` (« mais plus de sacks ») est à
   corriger.
3. Étage 4 : « 36 des 88 sacks avec chip » compte des actions, « 36 % des 105 joueurs qui chippent » compte des
   joueurs. Ce sont deux mesures différentes : ne pas les relier par « soit ».
4. Le découpage de B par type de chip (slot/large 48 %, TE en ligne 32 %, backfield 24 %) est une piste, pas un
   résultat : les IC95 se chevauchent. Ne pas le mettre dans le conseil de l'app ni le présenter comme une conclusion.
5. Deux « -26 % » différents circulent : l'étage 1 (`coach.py`, même rusher chippé ou non, 10,5 % contre 14,1 %) et le
   chiffre clé 1 de A (TE en ligne contre edge rushers non chippés, effet ajusté de -3,6 pts). Citer la source de
   celui qu'on montre.
6. README, « Comment lancer » : `decision.py`, `analysis/mecanique.py` et l'app lisent `outputs/*.csv`. Il faut lancer
   `mkdir -p outputs && python src/build_tables.py` **avant** eux, et `decision.py` avant `chart.py`.

## Pour A (`feat/chip-mecanique`)
1. **Libellé à corriger** : `slot_wide` ne désigne pas des receveurs. Dans `outputs/chips.csv`, ce groupe compte
   302 TE, 86 RB et 123 WR sur 519 chips (`chipper_off_pos`) : c'est un **alignement** (slot ou large), pas un poste.
   « Receveur slot / large » et « plutôt qu'un receveur » (`results/A.md`, conseil au coach) deviennent « joueur
   aligné en slot ou large » et « plutôt qu'un joueur aligné en slot ou large ».
2. Le report de pression est mesuré de deux façons qui se complètent. Chez A, la pression de l'action reste à environ
   44 % quelle que soit la durée du chip. Chez B, à situation égale, les rushers non chippés mettent 27 % de pression
   en plus (14,8 % contre 11,7 %, IC95 de l'écart +1,8 à +4,3 pts, tous les rushers, `coach.py`). Au pitch, les
   montrer ensemble, chacun avec sa définition.

## Pour Alvaro (`src/build_tables.py`, sur `main`)
1. Le script écrit dans `outputs/` sans créer ce dossier : sur un clone neuf, il plante après environ 27 s. Ajouter
   `os.makedirs(OUT, exist_ok=True)` au début de `main()`, avec `import os`. En attendant : `mkdir -p outputs`.
2. À savoir : `build_tables.py` garde les actions annulées par une pénalité (« No Play »), alors que `coach.py` et
   `decision.py` les excluent.

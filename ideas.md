# Idées de projet — BDB Paris Side Quest

Testées sur les 122 matchs (39 000 routes de WR/TE/RB, 7 583 passes lancées, cible retrouvée dans 93 % des cas via
`playDescription`). Notes sur la grille du jury, pertinence football comptée double (départage + prix finaliste).

| # | Idée | Pertinence ×2 | Exécution | Communication | Originalité | Total /25 |
|---|---|---|---|---|---|---|
| 1 | **Le chip oublié** (TE/RB) | 10 | 4 | 5 | 5 | **24** |
| 2 | **Time-to-Win** (WR/TE) | 8 | 4 | 4 | 4 | **20** |
| 3 | **Le vrai mismatch du TE** (man) | 8 | 4 | 4 | 3 | **19** |

## 1. Le chip oublié (TE/RB)

**Décision** : un coach doit-il faire chipper son TE ou son RB avant de le lancer en route ?

| | Séparation au lancer | Démarqué ≥ 3 yd | Ciblé |
|---|---|---|---|
| TE qui chippe (`pff_blockType == "CH"`) | 5,3 yd | 75 % | 15,5 % |
| TE sans chip | 2,5 yd | 41 % | 19,8 % |
| RB qui chippe | 8,3 yd | 88 % | 11,6 % |
| RB sans chip | 5,9 yd | 76 % | 19,3 % |

- Quand on le cible quand même, le joueur qui a chippé est complété à **82 %**, contre 70 % sans chip (159 ciblages).
- **Insight** : chipper ne coûte pas de séparation, au contraire. Le joueur qui chippe devient le plus démarqué du terrain,
  parce que la défense l'oublie ; mais le QB l'oublie aussi.
- **Originalité** : NGS a publié le bénéfice du chip pour la protection (pression à 3,43 s contre 2,84 s), pas cet angle.
- **Échantillon** : 1 155 routes après un chip, 41 joueurs avec au moins 10 chips, 32 équipes.
- **Pre-mortem** : il est démarqué parce qu'il part tard et court (dans le flat), donc « ouvert mais inutile ».
  À tester en premier : comparer à profondeur égale.

## 2. Time-to-Win (WR/TE)

**Décision** : quel receveur bat son défenseur assez tôt pour le timing du QB (lancer médian à 2,6 s) ?

- Le Time-to-Open du document d'idées ne marche pas tel quel : le temps médian vaut 0 s, parce que les receveurs sont
  déjà à 2,5 yd de tout défenseur au snap (coussin).
- **Redéfinition** : temps pour se ré-ouvrir (≥ 2,5 yd) **après avoir été couvert**, face aux défenseurs en couverture seulement.
- 60 % des routes sont couvertes à un moment, et 21 % d'entre elles se ré-ouvrent avant le lancer
  (médiane : 2,0 s pour les TE, 2,2 s pour les WR).
- **Lien avec une issue réelle** : quand il est ciblé, un receveur ré-ouvert est complété à **65 %**, contre 43 % s'il ne s'est jamais ré-ouvert.
  Le taux de ciblage, lui, varie peu.
- **Pre-mortem** : le seuil de 2,5 yd est arbitraire, et la notion de « couvert » est floue en zone. Parade : se limiter au man.

## 3. Le vrai mismatch du TE (couverture man)

**Décision** : contre quel défenseur un coordinateur offensif doit-il chercher son TE ?

| Défenseur qui suit le TE | Séparation au lancer | Complété si ciblé |
|---|---|---|
| Safety | 1,27 yd | 49 % |
| Linebacker | 1,77 yd | 64 % |
| Cornerback | 1,72 yd | 55 % |

- **Insight** : contrairement à l'idée reçue, le linebacker n'est pas plus facile à battre en séparation qu'un cornerback ;
  la vraie bête noire du TE, c'est le safety.
- **Pre-mortem** : environ 100 ciblages par groupe, donc des marges d'erreur larges.

## Idées écartées

- **Release vs press** (WR extérieurs) : seulement 11 joueurs ont au moins 20 routes en press.
- **Hot route vs blitz** (5 rushers ou plus) : pas de signal net.
- **Soupape sous pression** (RB/TE) : aucune différence de séparation avec ou sans pression.
- **Démarqué ignoré** : 29 % des actions en ont un, surtout des RB en check-down ; trop bruité sans filtre de profondeur.

## Pièges des données

- `pff_role` vaut `Pass Route`, `Pass Block`, `Pass Rush`, `Coverage`, `Pass` (avec majuscule, contrairement au README).
- Snap : `ball_snap` ou `autoevent_ballsnap` ; lancer : `pass_forward` ou `autoevent_passforward`. Prendre les deux.
- Le tracking s'arrête 0,3 à 0,5 s après le lancer : rien après la réception (pas de YAC).
- Séparation : ne garder que les défenseurs `Coverage`, sinon les pass rushers faussent la mesure pour les TE.
- Le ballon correspond aux lignes où `nflId` est NA ; normaliser `playDirection` avant tout calcul de profondeur.

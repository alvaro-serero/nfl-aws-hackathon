# Idées de projet — BDB Paris Side Quest

Testées sur les 122 matchs (39 000 routes de WR/TE/RB, 7 583 passes lancées, cible retrouvée dans 93 % des cas via
`playDescription`). Notes sur la grille du jury, pertinence football comptée double (départage + prix finaliste).

| # | Idée | Pertinence ×2 | Exécution | Communication | Originalité | Total /25 |
|---|---|---|---|---|---|---|
| 1 | **Le chip oublié : soupape anti-sack** (TE/RB) | 10 | 4 | 5 | 3 | **22** |
| 2 | **Time-to-Win** (WR/TE) | 8 | 4 | 4 | 4 | **20** |
| 3 | **Le vrai mismatch du TE** (man) | 8 | 4 | 4 | 3 | **19** |

## 1. Le chip oublié (TE/RB) — idée retenue pour l'instant

**Décision (coach de QB)** : sur une action avec chip, quand le QB doit-il lancer au TE/RB qui a chippé ?

### Ce qui a été testé, dans l'ordre
1. **Première intuition (abandonnée)** : « le joueur qui chippe est le plus démarqué du terrain, et le QB l'oublie ».
   Il est bien démarqué au lancer (TE : 5,3 yd contre 2,5 yd sans chip) mais **court** (TE : 1,9 yd de profondeur
   contre 5,9 yd) ; il n'est démarqué au-delà de la ligne du 1er down que dans 2 % des cas (12 % sans chip).
2. **À profondeur égale** : il reste plus démarqué (+1,55 yd) et ciblé 32 % moins souvent que prévu (159 contre 234,
   z = -5,5). Ce n'est pas faute d'options : 4,8 receveurs en route avec ou sans chip.
3. **Analyse de décision** (`decision.py`) : un modèle de complétion (profondeur + séparation, entraîné semaines 1-6,
   calibré semaines 7-8) donne la valeur de chaque option ; on compare, dans la même action, l'option « chippeur » à
   l'option choisie par le QB.

### Résultat
- **En temps normal, le QB a raison de l'ignorer** : sur 928 passes où il n'est pas ciblé, l'option choisie vaut
  +3,4 yards attendus (IC95 : 3,2 à 3,7) et +6,9 pts de probabilité de réussite. Sur 3e et long : +16 pts.
- **Mais sur les sacks, c'est la soupape** : sur 97 sacks avec chip, le joueur qui chippe était démarqué (≥ 3 yd) au
  moment du sack dans **65 %** des cas, contre 39 % pour les autres receveurs ; démarqué depuis ≥ 1 s au-delà de la
  ligne : 37 % contre 24 % (z ≈ 3). Une passe vers lui valait ≈ +6 yards attendus (72 % de complétion), au lieu d'un
  sack moyen de -7,4 yards.
- **Recommandation** : faire du joueur qui a chippé la lecture de secours de la progression ; vers 3 s, lâcher le
  ballon vers lui plutôt que de le garder.

### Validation externe (nos chiffres retrouvent ceux de NGS)
- Réception après un chip : 82,4 % réels, 82,3 % prédits par le modèle ; NGS publie 80,2 %.
- Temps avant le lancer : 3,1 s avec chip contre 2,6 s sans, soit la « demi-seconde » de NGS.

### Originalité : déjà connu ou pas ?
- **Le concept est connu des coachs** : le « checkdown » (passe courte au RB/TE en dernier recours, souvent sous
  pression) et le « check-release » (le RB bloque puis sort en route) sont des principes enseignés partout
  ([Checkdown](https://en.wikipedia.org/wiki/Checkdown), [Fox Sports, hot reads](https://amp.foxsports.com/stories/other/overcoming-the-blitz)).
  Dire « le RB est une soupape » n'est donc pas nouveau.
- **Ce qui est publié sur le chip** : NGS (bénéfice en protection, +0,5 s, 80,2 % de réception, passes plus profondes
  sur les actions avec chip : 9,3 contre 7,2 air yards) et PFF (« chip percentage » des pass rushers).
  ([NFL.com](https://www.nfl.com/_amp/the-secret-weapon-nfl-offenses-are-using-to-buy-qbs-an-extra-half-second),
  [PFF](https://www.pff.com/news/nfl-chip-percentage-week-5))
- **Ce qu'on n'a trouvé nulle part** : la mesure, au tracking, de la soupape après un chip au moment du sack (65 % contre
  39 %), et la comparaison de décision « chippeur contre cible choisie » dans la même action.
- **BDB 2023** : thème protection / pass rush ; aucun notebook sur le chip trouvé, mais la recherche est polluée par
  « chip » (les puces de tracking). Pas une preuve d'absence.
- **Verdict** : principe connu, **quantification nouvelle**. Originalité notée 3/5 (au lieu de 4). À présenter comme
  « on mesure, pour la première fois au tracking, ce que coûte de ne pas utiliser la soupape après un chip ».

### Limites
- Modèle simple : ignore la vitesse de retour du défenseur et la visibilité du QB sous pression.
- 8 semaines de 2021, 97 sacks avec chip.

### Livrables prêts (non poussés, relecture `critic` en cours)
`decision.py` (analyse), `chart.py` → `insight.png`, `animate_chip.py` / `animate_sack.py` → animations, `README.md`.

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

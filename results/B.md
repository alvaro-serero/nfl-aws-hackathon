# Branche B : faut-il lancer au joueur qui a chippé ?

## 3 chiffres clés
1. **En temps normal, non** : la cible choisie vaut +4,0 yd attendus de plus que le TE/RB qui a chippé (IC95 3,7 à 4,3 ; 928 passes). Source : `decision.py`, « == 928 actions où le joueur qui chippe n'est pas ciblé » et « écart moyen de yards attendus : -3.98, IC95 [-4.26 -3.71] ».
2. **Sur un sack, oui** : dans 36 des 88 sacks avec chip, le joueur qui a chippé était démarqué (≥ 3 yd) au-delà de la ligne depuis ≥ 1 s, soit 36 % des 105 joueurs qui chippent contre 23 % des autres receveurs à profondeur égale ; sack moyen -7,4 yd. Par type de chip (105 des 105 joueurs typés) : slot_wide 48 % (n = 42), inline_TE 32 % (n = 34), backfield 24 % (n = 29). Sources : `chart.py`, « 36 sacks sur 88 » ; `decision.py`, « démarqué depuis >= 1 s au-delà de la ligne : chippeur 0.362 | autres, mêmes actions 0.299 | autres, profondeur égale 0.231 », « sack moyen : -7.38 yd », « type de chip trouvé dans outputs/chips.csv : 105 des 105 joueurs qui chippent » et le tableau `chip_type` (backfield 29 0.241, inline_TE 34 0.324, slot_wide 42 0.476).
3. **À situation égale, le chip n'ajoute pas de sacks de façon significative** : 8,4 % contre 6,7 % (+1,7 pt, IC95 -0,1 à +3,4 : l'écart n'est pas significatif) ; la pression se reporte sur les rushers non chippés : 14,8 % contre 11,7 % (+27 %, significatif). Source : `coach.py`, lignes « contrôlé » sous « == Sacks par action » (chip 0.084 | sans chip 0.067 | écart +0.017 (IC95 -0.001 à +0.034)) et sous « == Report : pression par rusher NON chippé » (chip 0.148 | sans chip 0.117, relatif +27%).

## Règle pour le coach de QB
Progression normale d'abord (la cible choisie vaut +4,0 yd). Vers 3 s, si la poche se referme, regarder le joueur qui a chippé avant de subir le sack : c'est la soupape (démarqué dans 36 des 88 sacks avec chip). Tendance à confirmer : plus souvent libre aligné en slot/large (48 %) que dans le backfield (24 %).

## Limites
- 36 % contre 30 % sur les mêmes actions : face aux autres receveurs des mêmes sacks, l'écart n'est que de 6 pts (pas d'IC calculé), contre 13 pts à profondeur égale. Source : `decision.py`, « autres, mêmes actions 0.299 ».
- Petits effectifs : 88 sacks, 29 à 42 joueurs par type de chip (aucun sous-groupe < 20, mais pas d'IC par type) ; 8 semaines de 2021 ; modèle de valeur simple (profondeur + séparation) ; tracking coupé ~0,4 s après le lancer.
- Validation externe : réception après un chip 82,4 % (IC95 76-88 %, n = 159), cohérente avec les 80,2 % publiés par NGS. Source : `decision.py`, « réception réelle après un chip : 0.824 (IC95 0.76-0.88), n = 159 ».

## Figures
`insight.png` (`chart.py`) ; `chip_sack.png` et `chip_sack.html` (`animate_sack.py`).

# Branche A : quel chip protège le mieux, et à quel prix pour la route ?

Généré par `python analysis/mecanique.py` (ne pas éditer à la main). Semaines 1 à 8 de 2021, edge rushers.

## 3 chiffres clés

1. Chip par un TE en ligne : −3,6 pts de pression pour l'edge rusher visé (−26 %), OR = 0,71 [IC 95 % 0,53 ; 0,90], n = 499 chips.
2. Durée du chip : OR = 0,54 par seconde de contact [IC 95 % 0,29 ; 0,88], soit −2,6 pts de pression associés à 0,5 s de contact en plus.
3. Coût pour la route : un chip de plus d'1 s fait partir le joueur en route à 2,20 s après le snap, contre 1,50 s pour un chip de 0,3 à 0,6 s (n = 189 et 667 chips).

## Pour le coach

Contre un edge rusher dangereux, faites chipper le TE en ligne ou le running back plutôt qu'un receveur et demandez un contact de plus d'une seconde : sa pression passe de 12,9 % à 8,5 %, mais le joueur part en route à 2,20 s : c'est une lecture tardive (soupape), pas une première option.

## Figures

- `figures/A_type.png` : pression de l'edge rusher selon le type de chip (TE, RB, receveur), avec l'effet ajusté.
- `figures/A_duree.png` : le compromis, la pression baisse quand le chip dure, le départ en route recule.
- `figures/A_quartile.png` : chippé contre non chippé, par niveau du rusher (Q4 = élite).

## Détail

Non chippé : 12,8 % de pression (n = 20 790).

| Type de chip | Chips | Pression observée | Effet ajusté | OR [IC 95 %] |
|---|---|---|---|---|
| TE en ligne | 499 | 10,2 % | −3,6 pts | 0,71 [0,53 ; 0,90] |
| Running back (backfield) | 446 | 10,1 % | −3,3 pts | 0,72 [0,51 ; 0,97] |
| Receveur slot / large | 504 | 12,3 % | −1,7 pts | 0,86 [0,65 ; 1,06] |

Coût pour la route, par type de chip (chips avec contact détecté) :

| | Chips | Départ en route (médiane) | Ciblé ensuite (passes) | Pression du rusher chippé |
|---|---|---|---|---|
| TE en ligne | 493 | 1,50 s | 16,5 % (n = 424) | 10,3 % |
| Running back (backfield) | 441 | 2,20 s | 11,3 % (n = 382) | 10,4 % |
| Receveur slot / large | 491 | 1,40 s | 14,5 % (n = 401) | 12,4 % |

Coût pour la route, par durée du contact :

| | Chips | Départ en route (médiane) | Ciblé ensuite (passes) | Pression du rusher chippé |
|---|---|---|---|---|
| ≤ 0,3 s | 44 | 1,35 s | 23,1 % (n = 39) | 11,4 % |
| 0,3 à 0,6 s | 667 | 1,50 s | 13,2 % (n = 559) | 12,9 % |
| 0,6 à 1,0 s | 525 | 1,70 s | 15,1 % (n = 451) | 9,7 % |
| > 1,0 s | 189 | 2,20 s | 12,7 % (n = 158) | 8,5 % |

## Limites

- Biais de sélection : on ne connaît pas l'appel de jeu, et les chips ne sont pas décidés au hasard (qui est chippé, quand).
- La pression de l'action entière reste autour de 44 % quelle que soit la durée du chip (≤ 0,3 s : 45,5 % (n = 44) ; 0,3 à 0,6 s : 44,4 % (n = 667) ; 0,6 à 1,0 s : 42,3 % (n = 525) ; > 1,0 s : 44,4 % (n = 189)) : le chip déplace la pression, il ne la supprime pas.
- La durée est une association, pas une preuve : un rusher qui se dégage vite raccourcit aussi le contact. L'effet tient sur les actions de 3 s ou plus (OR = 0,49, n = 971) et en contrôlant le temps avant la passe (OR = 0,39).
- Effectifs : 44 chips de 0,3 s ou moins seulement ; ciblage calculé sur les seules passes (C, I, IN).
- Méthode : régressions logistiques, IC 95 % par bootstrap sur les matchs (500 tirages, graine 2021).

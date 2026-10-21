# Le chip — BDB Paris Side Quest

Décision d'équipe (14 h 20) : on part sur une stat liée au chip (`pff_blockType == "CH"` : un TE ou un RB donne un coup
à un pass rusher avant de partir en route). Les idées non liées au chip (Time-to-Win, mismatch du TE, release vs press,
etc.) sont retirées ; elles restent dans l'historique git (commit `268a685`).

## Ce qu'on sait, du rusher à la décision du QB

| Étage | Question | Résultat | Script | Déjà publié ? |
|---|---|---|---|---|
| 1. Le rusher visé | Le chip gêne-t-il le rusher qu'il touche ? | **Oui** : même rusher, pression sur 10,5 % de ses rushs chippés contre 14,1 % sinon (**-26 %**, IC95 -6,0 à -1,3 pts ; 55 rushers ; 67 % moins efficaces) | `coach.py` | NGS publie le **temps** avant pression (3,43 s contre 2,84 s), pas le **taux** de pression du même rusher |
| 2. L'action | Que devient l'action avec un chip ? | Le QB lance plus tard (**médiane 3,1 s contre 2,6 s**) et plus loin : **+0,8 yd** par action (7,3 contre 6,6) ; mais pression 43 % contre 35 % ; **sacks à situation égale 8,4 % contre 6,7 %** (+1,7 pt, IC95 -0,1 à +3,4 : non significatif) | `coach.py`, `decision.py` | NGS : +0,5 s et 9,3 contre 7,2 air yards |
| 3. La décision du QB | Doit-il lancer au joueur qui a chippé ? | **En temps normal, non** : la cible choisie vaut **+4,0 yd** attendus (IC95 3,7 à 4,3 ; 928 passes). **Sur un sack, oui** : dans **36 des 88 sacks** avec chip, le TE/RB qui a chippé était démarqué (≥ 3 yd) au-delà de la ligne depuis ≥ 1 s (36 % contre 23 % des autres receveurs à profondeur égale) ; sack moyen -7,4 yd | `decision.py` | Non trouvé |

## Est-ce cohérent ?

Oui, les trois étages racontent une seule histoire :

1. Le chip **fait son travail** sur le rusher visé (-26 % de pression) et achète ~0,5 s.
2. Le QB **utilise ce temps pour chercher plus loin** : plus de yards quand ça passe (+0,8 yd), c'est le bon réflexe
   en temps normal (étage 3 : +4,0 yd pour la cible choisie).
3. Mais l'action dure plus longtemps, la pression finit par arriver d'ailleurs, et elle **finit plus souvent en sack**.
   Dans 36 de ces sacks, la soupape (le joueur qui a chippé) était ouverte depuis plus d'une seconde.

Les deux paradoxes apparents s'expliquent :
- **Plus de pression avec chip alors que le rusher visé en met moins** : le chip est appelé dans les situations
  difficiles (33 % de 3e et long contre 18 % sans chip) et l'action dure plus longtemps. C'est un biais de sélection,
  d'où la comparaison « même rusher » de l'étage 1.
- **Plus de yards mais moins de réussite** (44 % contre 49 %) : passes plus profondes, donc plus de variance, et plus
  de 3e et long.

**Message pour le coach** : le chip achète du temps ; garder le joueur qui a chippé comme lecture de secours vers 3 s
transforme une partie des sacks (-7,4 yd) en passes courtes (≈ 80 % de réception selon NGS, 82 % chez nous).

## Validation externe

- Réception après un chip : 82,4 % (IC95 76-88 %, n = 159), 82,6 % prédits par le modèle entraîné sur les semaines
  1-6 ; NGS publie 80,2 %.
- Temps avant le lancer : +0,5 s avec chip, comme NGS.
- Relecture `critic` : signe de la profondeur, temps démarqué, absence de fuite du modèle et cibles vérifiés ;
  l'ancien « 65 % contre 39 % » (joueurs derrière la ligne comptés comme démarqués) a été abandonné.

## Originalité

- **Connu** : le « checkdown » et le « check-release » (le RB/TE comme soupape) sont des principes de coaching ;
  NGS a publié le temps avant pression, les air yards et le taux de réception après un chip.
- **Nouveau** (non trouvé ailleurs) : la pression du **même rusher** chippé ou non, et la mesure au tracking de la
  soupape ouverte pendant les sacks avec chip.
- À présenter comme « on mesure le bilan complet du chip, du rusher à la décision du QB », pas comme « on découvre
  la soupape ».

## Limites

- Modèle de valeur simple (profondeur + séparation), sans la vitesse de retour du défenseur ni la visibilité du QB.
- 8 semaines de 2021 ; 88 sacks avec chip ; 55 rushers pour la comparaison « même rusher ».
- Sur les mêmes actions (receveurs plus profonds), l'écart « soupape » se réduit à 36 % contre 30 % (non significatif).
- Étage 2 : pression et yards en comparaison brute, biaisée par la situation ; les sacks sont comparés à situation
  égale (down × distance × nombre de rushers, `coach.py`).

## Livrables

`decision.py` (étage 3), `coach.py` (étages 1-2), `chart.py` → `insight.png`, `animate_sack.py` → `chip_sack.png` /
`chip_sack.html`, `README.md`.

## Pièges des données

- `pff_role` vaut `Pass Route`, `Pass Block`, `Pass Rush`, `Coverage`, `Pass` (avec majuscule, contrairement au README).
- Snap : `ball_snap` ou `autoevent_ballsnap` ; lancer : `pass_forward` ou `autoevent_passforward`. Prendre les deux.
- Le tracking s'arrête 0,3 à 0,5 s après le lancer : rien après la réception (pas de YAC).
- Séparation : ne garder que les défenseurs `Coverage`, sinon les pass rushers faussent la mesure pour les TE.
- Le ballon correspond aux lignes où `nflId` est NA ; normaliser `playDirection` avant tout calcul de profondeur.
- Exclure les actions annulées par une pénalité (`playDescription` contient « No Play »).

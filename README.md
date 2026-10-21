# Le chip : la soupape anti-sack du TE et du RB

Avec le tracking NGS et les étiquettes PFF, nous mesurons ce que rapporte le chip : le coup qu'un TE ou un RB donne à un pass rusher avant de partir en route.
Il réduit la pression du rusher visé (-26 % avec un TE en ligne), mais la pression arrive d'ailleurs et l'action ne finit pas significativement plus souvent en sack.
Règle pour le coach de QB : vers 3 s, regarder le joueur qui a chippé, démarqué depuis plus d'une seconde dans 36 des 88 sacks avec chip.
Limites : 8 semaines de 2021, appel de jeu inconnu, petits échantillons.

![Pression du rusher selon le type de chip](figures/A_type.png)
![Décision du QB : le joueur qui a chippé est la soupape sur les sacks](insight.png)

## Comment lancer

```bash
pip install -r requirements.txt
python src/build_tables.py && python analysis/mecanique.py && python decision.py && python coach.py && python chart.py
streamlit run app/advisor.py   # outil interactif « Chip Advisor »
```

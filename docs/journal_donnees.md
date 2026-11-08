# Journal de travail : données, rendements et momentum (tâches 1 à 3)

**Auteur :** Abraham Adegoke
**Date :** 8 novembre 2026
**Protocole :** Data Audit & Cleaning V1.4
**Statut :** tâches 1, 2 et 3 du plan de projet terminées

---

## Résumé

Les données Datastream brutes des 8 ETF ont été auditées, nettoyées puis transformées en rendements totaux quotidiens et mensuels. Le signal de momentum 12–1 a ensuite été calculé pour chaque fin de mois. Chaque décision est consignée dans le rapport qualité. Les règles de nettoyage sont regroupées dans un module réutilisable (`src/data.py`), et 7 tests automatiques vérifient qu'elles sont bien appliquées.

| Tâche du plan | Statut |
|---|---|
| 1. Dépôt GitHub partagé, environnement Python, fichier requirements, formats de données | Terminé |
| 2. Prix quotidiens des 8 ETF : aligner les dates, vérifier les trous, doublons, ajustements et sauts inhabituels, sauvegarder les données | Terminé |
| 3. Rendements et momentum 12–1, en n'utilisant que l'information disponible à chaque rebalancement | Terminé |

---

## 1. Mise en place du projet

- Dépôt GitHub : `AbrahamAdegoke/conviction-budget-fund`.
- Environnement conda `qarm` (Python 3.11). Les dépendances sont dans `requirements.txt` : pandas, numpy, openpyxl, pandas_market_calendars, scipy, pytest, jupyter, streamlit et plotly.
- Structure :

```text
data/raw/         fichiers bruts Datastream et FRED (jamais modifiés)
data/processed/   données nettoyées, rendements et signal momentum
data/reports/     rapport qualité des données
src/              code réutilisable (data.py)
notebooks/        01_data_audit.ipynb
tests/            tests automatiques (test_data.py)
docs/             plan de projet et journaux
```

## 2. Sources de données

| Fichier | Contenu | Source |
|---|---|---|
| `data/raw/ETF.xlsx`, feuille `Price` | Prix quotidiens des 8 ETF | Datastream |
| `data/raw/ETF.xlsx`, feuille `Total return index` | Total Return Index quotidien (RI, dividendes réinvestis) | Datastream |
| `data/raw/dgs1mo.csv` | Taux du Trésor américain à 1 mois (DGS1MO, % annualisé) | FRED |

Les 8 ETF sont SPY, EFA, EEM, IEF, LQD, TLT, VNQ et GLD. L'ordre des colonnes diffère entre les deux feuilles, donc chaque colonne est associée à son ticker par un mot-clé du nom Datastream.

**Pourquoi le prix et le RI :** les rendements sont calculés sur le RI, qui intègre les distributions réinvesties, contrairement à la série de prix. L'écart entre leurs performances sert à contrôler la cohérence des données.

## 3. Audit des données (notebook `01_data_audit.ipynb`)

| Contrôle | Résultat | Décision |
|---|---|---|
| Dates invalides ou en double | Aucune (5 178 lignes, du 01/01/2007 au 04/11/2026) | — |
| Valeurs non numériques | Aucune | — |
| Dates hors séances NYSE | 186 dates (jours fériés américains), dont 185 sont des copies exactes de la veille | Retirées : seules les séances NYSE officielles sont gardées |
| Séances NYSE manquantes | Aucune | — |
| Valeurs manquantes sur les séances NYSE | Aucune | — |
| Valeurs nulles ou négatives | Aucune | — |
| Séries figées (5 rendements nuls ou plus d'affilée) | Aucune | — |
| Rendements quotidiens supérieurs à 15 % en valeur absolue | 9 cas : EFA, EEM et VNQ entre octobre 2008 et mars 2009, VNQ le 16 mars 2020 | Gardés : vrais mouvements de crise, confirmés par le prix et par SPY |
| Écart annuel RI moins prix | SPY 2,06 %, EFA 3,14 %, EEM 2,20 %, IEF 2,47 %, LQD 3,98 %, TLT 3,11 %, VNQ 4,32 %, GLD 0,00 % | Cohérent avec les rendements en dividendes, aucun écart négatif |
| Taux sans risque DGS1MO | 38 séances NYSE sans taux (jours fériés du marché obligataire), jamais plus d'une d'affilée ; valeurs entre 0,00 et 6,02 % | Le dernier taux publié sera reporté ; transformation reportée |

Échantillon final : **4 992 séances NYSE**, du 03/01/2007 au 04/11/2026.

Règles de nettoyage (V1.4) :
- les prix ne sont jamais interpolés ni recopiés du jour précédent ;
- une séance avec une valeur manquante, nulle ou négative pour un ETF est exclue pour tous les ETF (aucun cas dans les données actuelles) ;
- chaque contrôle est consigné dans `data/reports/data_quality_report.csv`, avec les colonnes Check, Ticker, Dates, Detected, Kept, Excluded, Corrected et Justification.

## 4. Rendements

| Sortie | Lignes | Période |
|---|---|---|
| Rendements simples quotidiens calculés sur le RI | 4 991 | du 04/01/2007 au 04/11/2026 |
| Rendements mensuels entre fins de mois NYSE | 237 | de février 2007 à octobre 2026 |

- Chaque rendement quotidien porte un indicateur `regular`, vrai quand ses deux dates sont des séances NYSE consécutives. Aucun rendement irrégulier.
- Les rendements mensuels utilisent la dernière séance NYSE de chaque mois. Une fin de mois manquante rendrait ce mois et le suivant indisponibles. Aucune fin de mois ne manque, et le mois incomplet de novembre 2026 est retiré.
- Contrôle : les rendements quotidiens cumulés redonnent les rendements mensuels, avec un écart maximal de 1,3e-15.

## 5. Momentum 12–1

Pour chaque ETF, à la fin du mois *t* :

> MOM(t) = RI(t−1) / RI(t−12) − 1

C'est la performance sur les 11 mois qui vont de la fin du mois *t−12* à la fin du mois *t−1*. Le mois le plus récent est volontairement exclu, car les rendements sur un mois ont tendance à se retourner. On utilise le RI pour que le momentum inclue les dividendes : avec le prix seul, les ETF obligataires paraîtraient moins performants qu'ils ne le sont.

**Convention de temps (à respecter dans Black-Litterman et le backtest) :**
- le signal étiqueté *t* est observé à la clôture du mois *t* et n'utilise aucune donnée postérieure à la fin du mois *t−1* ;
- le portefeuille est négocié à la séance suivante ;
- les poids décidés à *t* reçoivent les rendements du mois *t+1*.

**À préciser dans le moteur de backtest :** le prix d'exécution. Si les transactions se font à la clôture de la première séance de *t+1*, les nouveaux poids ne captent pas le rendement de cette première séance. Le backtest devra donc soit appliquer les anciens poids à ce premier jour et les nouveaux poids au reste du mois, soit documenter l'approximation retenue.

Résultats :
- premier signal en janvier 2008, dernier en octobre 2026, soit 226 mois ;
- contrôle : cumuler les rendements mensuels de *t−11* à *t−1* donne la même valeur (écart maximal de 8,9e-16, imposé par une assertion) ;
- le momentum de 0,0 % d'EFA en février 2008 a été vérifié. Les deux valeurs de fin de mois (192,73 le 28/02/2007 et le 31/01/2008) sont de vraies cotations, avec des rendements quotidiens non nuls. C'est donc une vraie coïncidence, et la valeur est gardée.

Dernier signal (octobre 2026, performance de fin octobre 2025 à fin septembre 2026) :

| EEM | EFA | SPY | VNQ | GLD | LQD | IEF | TLT |
|---|---|---|---|---|---|---|---|
| 23,13 % | 13,71 % | 13,02 % | 4,32 % | 3,46 % | −4,17 % | −4,42 % | −10,21 % |

## 6. Code réutilisable et tests

- `src/data.py` contient tout le pipeline : chargement, calendrier NYSE, règle d'exclusion, rendements quotidiens et mensuels, lecture des fichiers nettoyés. Sur les vraies données, il reproduit exactement les résultats du notebook (écart de 0,0).
- `tests/test_data.py` contient 7 tests sur des données fabriquées, dans lesquelles des défauts sont introduits volontairement :
  - données propres ;
  - valeur manquante ou non positive ;
  - séance NYSE absente ;
  - fin de mois manquante ;
  - date en double ;
  - rendement quotidien manquant dans un mois ;
  - colonne d'ETF inconnue ou manquante.

  Résultat : **7 passed** (`python -m pytest tests/test_data.py -v`).

## 7. Fichiers produits

| Fichier | Contenu |
|---|---|
| `data/processed/etf_daily_clean.csv` | Prix (`P_`) et RI (`RI_`) sur les séances NYSE |
| `data/processed/etf_daily_returns.csv` | Rendements quotidiens et indicateur `regular` |
| `data/processed/etf_monthly_returns.csv` | Rendements mensuels (`Month`, `MonthEnd`) |
| `data/processed/momentum_12_1.csv` | Momentum 12–1 par mois de décision (`Month`, `MonthEnd`, 8 ETF) |
| `data/reports/data_quality_report.csv` | Tous les contrôles et toutes les décisions |

Pour charger les données dans un autre module :

```python
from src.data import load_processed
clean, daily, monthly = load_processed()
```

## 8. Points ouverts pour le groupe

- **Taux sans risque :** la conversion de DGS1MO en taux mensuel est reportée à l'étape du backtest.
- **Licence Datastream :** les données Datastream obtenues via HEC sont stockées dans le dépôt. Un accès universitaire ne garantit pas le droit de publier les séries brutes ou transformées : le dépôt doit rester privé tant que les conditions de redistribution ne sont pas clarifiées.
- **Exécution du backtest :** convention de prix d'exécution à fixer (voir section 5).
- **Stratégie :** les tâches 1 à 3 fournissent des données fiables et un premier signal. La valeur ajoutée du momentum pour le portefeuille reste à démontrer par le backtest.
- **Prochaines étapes :**
  1. le module Black-Litterman : rendements implicites, vues momentum et distribution a posteriori, avec un test de référence sur l'exemple 4 de LN4 ;
  2. l'optimisation sous le budget de tracking error de 2 % ;
  3. le backtest walk-forward.
# Fintech Hackathon

## Setup

```bash
uv sync
```

## Générer les métriques

Place les CSV dans le dossier `data/` :

- `data/acme_jira_issues_mocked.csv`
- `data/acme_github_tokens.csv`

Puis lance :

```bash
uv run python api/csv_extraction.py
```

Output : `employee_metrics.jsonl` (une ligne par employé × mois)

## Données

Les deux CSV racontent une histoire : **l'usage IA seul ne suffit pas, c'est le contexte qui compte.**

### acme_jira_issues_mocked.csv

1079 tickets résolus (oct 2024 – mar 2025) avec assignee, statut, story points, dates.
Agrégés par employé × mois pour calculer :

- `tickets_resolved` : nombre de tickets fermés
- `bugs_closed` : bugs résolus (parmi les tickets)
- `story_points` : charge de travail complétée
- `time_to_completion` : durée moyenne de résolution

### acme_github_tokens.csv

Métriques GitHub par employé × mois :

- `merge_requests` : PRs mergées
- `lines_of_code` : volume de code livré
- `token_used` : tokens Claude consommés

### Profils types

| Profil | Token/mois | Tickets | Interprétation |
| --- | --- | --- | --- |
| **Lucas Bernard** | 115k–185k | 16–24 | Très bon + bcp IA → référence idéale |
| **Théo Moreau** | 59k–90k | 11–16 | Moyen + bcp IA → progression visible |
| **Remy Fontaine** | 33k–42k | 11–14 | Moyen + IA normale |
| **Camille Rousseau** | 97k–178k | 5–9 | Mauvais + bcp IA → outlier clé |
| **Jules Petit** | 2k–4k | 7–9 | Mauvais + peu IA |

**Le point clé** : Camille brûle autant de tokens que Lucas mais avec 3× moins de résultats.
Cela prouve que les tokens seuls ne suffisent pas — la productivité dépend du contexte (expérience, approche, qualité des requêtes).

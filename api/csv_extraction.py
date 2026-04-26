"""
csv_extraction.py
-----------------
Génère un JSONL avec une ligne par utilisateur par mois.

Sources :
  - JIRA_CSV  : export Jira (acme_jira_issues_mocked.csv)
  - GITHUB_CSV: métriques GitHub/tokens par mois (acme_github_tokens.csv)
"""

import csv
import json
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

JIRA_CSV   = Path("data/acme_jira_issues_mocked.csv")
GITHUB_CSV = Path("data/acme_github_tokens.csv")
OUTPUT     = Path("employee_metrics.jsonl")

RESOLVED_STATUSES = {"done", "terminé(e)", "terminé", "closed", "resolved"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_date(date_str: str | None) -> datetime | None:
    """Parse les formats de date Jira CSV (ex: '09/Oct/24 12:00 AM')."""
    if not date_str or date_str.strip() == "":
        return None
    for fmt in ("%d/%b/%y %I:%M %p", "%d/%b/%Y %I:%M %p"):
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def to_month_key(dt: datetime) -> str:
    """Convertit une datetime en clé mois au format 'MM/YYYY' (idem GitHub CSV)."""
    return dt.strftime("%m/%Y")

# ---------------------------------------------------------------------------
# Lecture du CSV Jira → métriques par (assignee, mois)
# ---------------------------------------------------------------------------

def build_jira_metrics_monthly(path: Path) -> dict[tuple, dict]:
    """
    Lit le CSV Jira et agrège par (assignee, mois de résolution).
    Les issues non résolues sont ignorées (pas de date de résolution).
    Retourne un dict : { (name, "MM/YYYY"): { tickets_resolved, ... } }
    """
    data: dict[tuple, dict] = defaultdict(lambda: {
        "tickets_resolved": 0,
        "bugs_closed": 0,
        "story_points": 0.0,
        "completion_times": [],
    })

    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for issue in reader:
            assignee   = issue.get("Assignee", "").strip()
            status     = issue.get("Status", "").strip().lower()
            issue_type = issue.get("Issue Type", "").strip().lower()
            resolved   = issue.get("Resolved", "").strip()
            created    = issue.get("Created", "").strip()
            sp_raw     = issue.get("Story Points", "").strip()

            if not assignee:
                continue

            is_resolved = status in RESOLVED_STATUSES
            if not is_resolved:
                continue

            dt_resolved = parse_date(resolved)
            if not dt_resolved:
                continue

            month_key = to_month_key(dt_resolved)
            key = (assignee, month_key)
            d = data[key]

            d["tickets_resolved"] += 1

            if "bug" in issue_type:
                d["bugs_closed"] += 1

            if sp_raw:
                try:
                    d["story_points"] += float(sp_raw)
                except ValueError:
                    pass

            dt_created = parse_date(created)
            if dt_created and dt_resolved >= dt_created:
                days = (dt_resolved - dt_created).total_seconds() / 86400
                d["completion_times"].append(round(days, 2))

    print(f"  → {len(data)} paires (employé, mois) chargées depuis {path}")
    return dict(data)

# ---------------------------------------------------------------------------
# Lecture du CSV GitHub → métriques par (assignee, mois)
# ---------------------------------------------------------------------------

def load_github_metrics_monthly(path: Path) -> dict[tuple, dict]:
    """
    Lit le CSV GitHub et retourne les métriques par (assignee, mois).
    Retourne un dict : { (name, "MM/YYYY"): { merge_requests, lines_of_code, token_usage } }
    """
    data: dict[tuple, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name  = row["assignee"].strip()
            raw_month = row["month"].strip()
            # normalise "1/2025" → "01/2025"
            m, y  = raw_month.split("/")
            month = f"{int(m):02d}/{y}"
            key   = (name, month)
            data[key] = {
                "merge_requests": int(row.get("merge_requests", 0) or 0),
                "lines_of_code":  int(row.get("lines_of_code", 0) or 0),
                "token_usage":    int(row.get("token_used", 0) or 0),
            }
    print(f"  → {len(data)} paires (employé, mois) chargées depuis {path}")
    return data

# ---------------------------------------------------------------------------
# Fusion et export
# ---------------------------------------------------------------------------

def merge_and_export(
    jira: dict[tuple, dict],
    github: dict[tuple, dict],
    output: Path,
) -> list[dict]:
    """
    Fusionne les métriques Jira et GitHub par (employé, mois),
    calcule les valeurs dérivées, et écrit le fichier JSONL.
    """
    all_keys = sorted(set(jira.keys()) & set(github.keys()), key=lambda k: (k[0], k[1]))

    results = []
    for (name, month) in all_keys:
        j = jira.get((name, month), {})
        g = github.get((name, month), {})

        resolved = j.get("tickets_resolved", 0)
        mr       = g.get("merge_requests", 0)

        completion_times = j.get("completion_times", [])
        avg_ttc = round(statistics.mean(completion_times), 2) if completion_times else None

        mr_per_ticket = round(mr / resolved, 2) if resolved > 0 else None

        results.append({
            "name":                      name,
            "month":                     month,
            "token_usage":               g.get("token_usage") or None,
            "tickets_resolved":          resolved,
            "time_to_completion":        f"{avg_ttc} days" if avg_ttc is not None else None,
            "merge_requests_per_ticket": mr_per_ticket,
            "bugs_closed":               j.get("bugs_closed", 0),
            "story_points":              int(j.get("story_points", 0)),
            "lines_of_code":             g.get("lines_of_code") or None,
            "merge_requests":            mr,
        })

    with open(output, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    return results

# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    print("=== Extraction CSV : Jira + GitHub (par employé × mois) ===\n")

    print("1. Chargement et agrégation du CSV Jira...")
    jira = build_jira_metrics_monthly(JIRA_CSV)

    print("\n2. Chargement du CSV GitHub/tokens...")
    github = load_github_metrics_monthly(GITHUB_CSV)

    print("\n3. Fusion et export JSONL...")
    results = merge_and_export(jira, github, OUTPUT)
    print(f"   → {len(results)} lignes exportées dans {OUTPUT}\n")

    print("=== Aperçu (3 premières lignes) ===")
    for r in results[:3]:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()

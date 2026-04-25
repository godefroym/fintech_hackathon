"""
jira_metrics_extractor.py
=========================
Extrait les métriques Jira par employé depuis un projet open source
et produit une liste JSON au format attendu par l'équipe LLM.

Format de sortie (par employé) :
{
    "name": "Nabil Cheickh",
    "token_usage": null,           # mocké — Jira ne capture pas ça
    "tickets_resolved": 13,
    "tickets_reopened": 25,
    "comments_for_clarification": 30,
    "time_to_completion": "3.5 days",
    "merge_requests_per_ticket": 2.5,
    "bugs_closed": 12,
    "story_points": 35,
    "lines_of_code": 1200,         # mocké — Jira ne capture pas ça
    "merge_requests": null         # optionnel / mocké selon dispo
}

Prérequis :
    pip install requests python-dotenv

Variables d'environnement (fichier .env) :
    JIRA_BASE_URL   = https://your-domain.atlassian.net
    JIRA_EMAIL      = you@example.com
    JIRA_API_TOKEN  = <votre token API Atlassian>
    JIRA_PROJECT    = KEY_DU_PROJET   (ex: "MYPROJ")
"""

import os
import json
import math
import statistics
from datetime import datetime, timezone
from collections import defaultdict

import requests
from requests.auth import HTTPBasicAuth

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optionnel


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

JIRA_BASE_URL  = os.environ.get("JIRA_BASE_URL", "https://issues.apache.org/jira")
JIRA_EMAIL     = os.environ.get("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN", "")
JIRA_PROJECT   = os.environ.get("JIRA_PROJECT", "KAFKA")

# Valeurs mockées (Jira ne les capture pas)
TOKEN_USAGE_MOCK   = None   # sera rempli par un autre membre de l'équipe
LINES_OF_CODE_MOCK = None   # sera rempli via l'API GitHub par un autre membre

# Auth optionnelle : Apache est public (sans auth), Jira Cloud nécessite email+token
AUTH    = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN) if JIRA_EMAIL and JIRA_API_TOKEN else None
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

# Détection automatique de la version API :
# - Apache/instances publiques → API v2 (GET /rest/api/2/search?jql=...)
# - Jira Cloud Atlassian       → API v3 (POST /rest/api/3/search/jql)
USE_API_V2 = "atlassian.net" not in JIRA_BASE_URL

PAGE_SIZE = 100  # max autorisé par l'API Jira



# ---------------------------------------------------------------------------
# Helpers API
# ---------------------------------------------------------------------------

def jira_get(endpoint: str, params: dict = None) -> dict:
    """GET générique vers l'API Jira v3."""
    url = f"{JIRA_BASE_URL}/rest/api/3{endpoint}"
    resp = requests.get(url, headers=HEADERS, auth=AUTH, params=params)
    resp.raise_for_status()
    return resp.json()


def fetch_all_issues(project_key: str, extra_fields: list[str] = None) -> list[dict]:
    """
    Récupère TOUTES les issues d'un projet via pagination automatique.
    Supporte automatiquement :
      - API v2 (Apache, instances publiques) : GET /rest/api/2/search?jql=...
      - API v3 (Jira Cloud Atlassian)        : POST /rest/api/3/search/jql
    """
    base_fields = [
        "summary", "status", "assignee", "reporter",
        "resolutiondate", "created", "updated",
        "issuetype", "comment", "resolution",
        "customfield_10016",   # Story Points (Jira Software)
        "customfield_10028",   # Story Points (variante)
    ]
    if extra_fields:
        base_fields.extend(extra_fields)

    all_issues = []
    start_at = 0
    next_page_token = None

    while True:
        if USE_API_V2:
            # API v2 : GET avec paramètres dans l'URL (Apache, instances publiques)
            url = f"{JIRA_BASE_URL}/rest/api/2/search"
            params = {
                "jql": f"project = {project_key} ORDER BY created ASC",
                "startAt": start_at,
                "maxResults": PAGE_SIZE,
                "fields": ",".join(base_fields),
                "expand": "changelog",
            }
            resp = requests.get(url, headers=HEADERS, auth=AUTH, params=params)
            resp.raise_for_status()
            data = resp.json()

            issues = data.get("issues", [])
            all_issues.extend(issues)

            total = data.get("total", 0)
            start_at += len(issues)
            print(f"  Fetched {start_at}/{total} issues...")

            if start_at >= total or not issues:
                break
        else:
            # API v3 : POST avec body JSON (Jira Cloud atlassian.net)
            # Pagination via nextPageToken (startAt déprécié)
            url = f"{JIRA_BASE_URL}/rest/api/3/search/jql"
            payload = {
                "jql": f"project = {project_key} ORDER BY created ASC",
                "maxResults": PAGE_SIZE,
                "fields": base_fields,
                "expand": "changelog",
            }
            if next_page_token:
                payload["nextPageToken"] = next_page_token

            resp = requests.post(url, headers=HEADERS, auth=AUTH, json=payload)
            if not resp.ok:
                print(f"  ERROR {resp.status_code}: {resp.text}")
            resp.raise_for_status()
            data = resp.json()

            issues = data.get("issues", [])
            all_issues.extend(issues)

            print(f"  Fetched {len(all_issues)} issues...")

            next_page_token = data.get("nextPageToken")
            if not issues or not next_page_token:
                break

    return all_issues


def detect_story_points_field(issues: list[dict]) -> str | None:
    """
    Story Points est un custom field dont l'ID varie selon l'instance Jira.
    On teste les IDs courants et on renvoie le premier qui contient une valeur.
    """
    candidates = [
        "customfield_10016",   # Jira Software (le plus courant)
        "customfield_10028",   # autre variante fréquente
        "customfield_10014",
        "story_points",
    ]
    for issue in issues[:20]:  # on sonde les 20 premières issues
        fields = issue.get("fields", {})
        for candidate in candidates:
            if fields.get(candidate) is not None:
                print(f"  ✓ Story Points field détecté : {candidate}")
                return candidate
    print("  ⚠️  Story Points field non détecté — sera None pour toutes les issues.")
    return None


# ---------------------------------------------------------------------------
# Calcul des métriques par assignee
# ---------------------------------------------------------------------------

def parse_jira_date(date_str: str | None) -> datetime | None:
    """Parse une date ISO Jira (ex: '2024-03-15T10:23:00.000+0000')."""
    if not date_str:
        return None
    # Normalise le format
    date_str = date_str.replace("+0000", "+00:00")
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None


def count_comments_for_clarification(comments: list[dict]) -> int:
    """
    Heuristique : compte les commentaires contenant des mots-clés
    typiques d'une demande de précision/clarification.
    Adaptez cette liste selon votre workflow.
    """
    keywords = [
        "clarif", "précis", "comprendr", "pouvez-vous", "can you clarify",
        "please clarify", "what do you mean", "unclear", "question",
        "besoin de plus", "need more info", "need more details",
        "could you explain", "pourquoi", "why", "?",
    ]
    count = 0
    for comment in comments:
        body = ""
        # Le body est en Atlassian Document Format (ADF) ou texte brut
        raw = comment.get("body", "")
        if isinstance(raw, dict):
            # ADF : on extrait le texte récursivement
            body = extract_text_from_adf(raw).lower()
        elif isinstance(raw, str):
            body = raw.lower()
        if any(kw.lower() in body for kw in keywords):
            count += 1
    return count


def extract_text_from_adf(node: dict) -> str:
    """Extrait le texte brut d'un nœud Atlassian Document Format."""
    text = ""
    if node.get("type") == "text":
        text += node.get("text", "")
    for child in node.get("content", []):
        text += extract_text_from_adf(child)
    return text


def count_reopenings(changelog: dict) -> int:
    """
    Compte les transitions vers un statut 'Reopened' / 'To Do' / 'Open'
    après une résolution, via le changelog de l'issue.
    """
    reopenings = 0
    reopen_statuses = {"reopened", "to do", "open", "backlog", "in progress"}
    resolved_statuses = {"done", "resolved", "closed"}

    histories = changelog.get("histories", [])
    last_was_resolved = False

    for history in sorted(histories, key=lambda h: h.get("created", "")):
        for item in history.get("items", []):
            if item.get("field") == "status":
                to_status = (item.get("toString") or "").lower()
                from_status = (item.get("fromString") or "").lower()

                if from_status in resolved_statuses and to_status in reopen_statuses:
                    reopenings += 1
                    last_was_resolved = False
                elif to_status in resolved_statuses:
                    last_was_resolved = True

    return reopenings


def compute_time_to_completion_days(created: str, resolution_date: str) -> float | None:
    """
    Calcule le temps entre la création et la résolution d'une issue (en jours).
    """
    dt_created = parse_jira_date(created)
    dt_resolved = parse_jira_date(resolution_date)
    if dt_created and dt_resolved:
        delta = dt_resolved - dt_created
        return round(delta.total_seconds() / 86400, 2)
    return None


# ---------------------------------------------------------------------------
# Agrégation principale
# ---------------------------------------------------------------------------

def build_employee_metrics(issues: list[dict], sp_field: str | None) -> list[dict]:
    """
    Agrège les issues par assignee et calcule toutes les métriques.
    Retourne la liste JSON finale.
    """
    # Structure par assignee
    data = defaultdict(lambda: {
        "tickets_resolved": 0,
        "tickets_reopened": 0,
        "bugs_closed": 0,
        "story_points": 0,
        "comments_for_clarification": 0,
        "completion_times": [],   # liste des durées en jours (pour la moyenne)
        "merge_requests": 0,      # mocké à 0 — pas dans Jira natif
        "merge_requests_per_ticket_raw": [],
    })

    for issue in issues:
        fields = issue.get("fields", {})
        changelog = issue.get("changelog", {})

        # Assignee
        assignee_obj = fields.get("assignee")
        if not assignee_obj:
            continue  # on ignore les issues non assignées
        assignee_name = assignee_obj.get("displayName", "Unknown")

        d = data[assignee_name]

        # Statut
        status_name = (fields.get("status") or {}).get("name", "").lower()
        issue_type  = (fields.get("issuetype") or {}).get("name", "").lower()
        resolution  = fields.get("resolution")

        # tickets_resolved : résolution définie OU statut Done/Terminé
        is_resolved = resolution is not None or status_name in {"done", "terminé(e)", "terminé", "closed", "resolved"}
        if is_resolved:
            d["tickets_resolved"] += 1

        # bugs_closed : issues de type Bug résolues
        if "bug" in issue_type and is_resolved:
            d["bugs_closed"] += 1

        # tickets_reopened : via le changelog
        d["tickets_reopened"] += count_reopenings(changelog)

        # Story points
        if sp_field:
            sp_value = fields.get(sp_field)
            if sp_value is not None:
                try:
                    d["story_points"] += float(sp_value)
                except (TypeError, ValueError):
                    pass

        # Comments for clarification
        comments = (fields.get("comment") or {}).get("comments", [])
        d["comments_for_clarification"] += count_comments_for_clarification(comments)

        # time_to_completion
        if is_resolved:
            ttc = compute_time_to_completion_days(
                fields.get("created"), fields.get("resolutiondate")
            )
            if ttc is not None:
                d["completion_times"].append(ttc)

    # Formatage final
    results = []
    for name, d in data.items():
        avg_ttc = None
        if d["completion_times"]:
            avg_ttc = round(statistics.mean(d["completion_times"]), 2)

        resolved = d["tickets_resolved"]
        mr = d["merge_requests"]
        mr_per_ticket = round(mr / resolved, 2) if resolved > 0 else None

        results.append({
            "name": name,
            "token_usage": TOKEN_USAGE_MOCK,          # mocké
            "tickets_resolved": resolved,
            "tickets_reopened": d["tickets_reopened"],
            "comments_for_clarification": d["comments_for_clarification"],
            "time_to_completion": f"{avg_ttc} days" if avg_ttc is not None else None,
            "merge_requests_per_ticket": mr_per_ticket,
            "bugs_closed": d["bugs_closed"],
            "story_points": int(d["story_points"]),
            "lines_of_code": LINES_OF_CODE_MOCK,      # mocké — viendra de GitHub
            "merge_requests": mr,                      # mocké à 0 (pas dans Jira natif)
        })

    # Trier par nom pour lisibilité
    results.sort(key=lambda x: x["name"])
    return results


# ---------------------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------------------

def main():
    print(f"=== Extraction Jira : projet '{JIRA_PROJECT}' ===\n")

    print("1. Récupération des issues (avec pagination)...")
    issues = fetch_all_issues(JIRA_PROJECT)
    print(f"   → {len(issues)} issues récupérées.\n")

    if not issues:
        print("Aucune issue trouvée. Vérifiez JIRA_PROJECT et vos credentials.")
        return

    print("2. Détection du champ Story Points...")
    sp_field = detect_story_points_field(issues)
    print()

    print("3. Calcul des métriques par employé...")
    metrics = build_employee_metrics(issues, sp_field)
    print(f"   → {len(metrics)} employés trouvés.\n")

    print("4. Export JSONL...")
    output_path = "employee_metrics.jsonl"
    with open(output_path, "w", encoding="utf-8") as f:
        for metric in metrics:
            f.write(json.dumps(metric, ensure_ascii=False) + "\n")

    print(f"   → Fichier généré : {output_path}\n")
    print("=== Aperçu (2 premières lignes) ===")
    for metric in metrics[:2]:
        print(json.dumps(metric, ensure_ascii=False))


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Interactive Scatter plot: Story Points vs Token Cost
Affiche tous les mois avec un sélecteur de mois
Uses Plotly for interactive hover tooltips
"""

import csv
import numpy as np
import plotly.graph_objects as go
from pathlib import Path

# Configuration
COST_PER_MTOK = 9.0
MONTHS_ORDER = ["10/2024", "11/2024", "12/2024", "01/2025", "02/2025", "03/2025"]

def load_all_data(csv_path):
    """Load all data from CSV, grouped by month"""
    data_by_month = {m: [] for m in MONTHS_ORDER}
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            month = row["month"]
            if month in data_by_month:
                cost = int(row["token_used"]) / 1e6 * COST_PER_MTOK
                sp = int(row["story_points_delivered"])
                data_by_month[month].append({
                    "name": row["assignee"],
                    "cost": cost,
                    "sp": sp,
                })
    for month in data_by_month:
        data_by_month[month].sort(key=lambda x: x["cost"])
    return data_by_month

def categorize_points(data):
    """Categorize points into main trend and outliers based on statistical deviation"""
    costs = np.array([d["cost"] for d in data])
    sps = np.array([d["sp"] for d in data])

    z = np.polyfit(costs, sps, 1)
    slope, intercept = z[0], z[1]

    fitted = intercept + slope * costs
    residuals = sps - fitted
    residual_std = np.std(residuals)

    main, outliers_above, outliers_below = [], [], []

    for d in data:
        fitted_sp = intercept + slope * d["cost"]
        residual = d["sp"] - fitted_sp
        z_score = abs(residual) / residual_std if residual_std > 0 else 0

        if z_score > 1.5:
            if residual > 0:
                outliers_above.append(d)
            else:
                outliers_below.append(d)
        else:
            main.append(d)

    return main, outliers_above, outliers_below, slope, intercept

def create_plot(csv_path, output_path="scatter_plot.html"):
    """Create and save the interactive scatter plot with month selector"""

    data_by_month = load_all_data(csv_path)

    # Axes globaux pour garder une échelle stable
    all_costs = [d["cost"] for month_data in data_by_month.values() for d in month_data]
    all_sps   = [d["sp"]   for month_data in data_by_month.values() for d in month_data]
    x_min, x_max = min(all_costs) - 200, max(all_costs) + 200
    y_min, y_max = min(all_sps)   - 5,   max(all_sps)   + 5

    fig = go.Figure()
    traces_per_month = 4  # trend + main + above + below

    for month in MONTHS_ORDER:
        data = data_by_month[month]
        if not data:
            # Ajouter 4 traces vides pour maintenir l'indexation
            for _ in range(traces_per_month):
                fig.add_trace(go.Scatter(x=[], y=[], visible=False, showlegend=False))
            continue

        main, outliers_above, outliers_below, slope, intercept = categorize_points(data)
        is_first = (month == MONTHS_ORDER[0])

        # Trace 1 : droite de tendance
        x_trend = np.array([x_min, x_max])
        y_trend = intercept + slope * x_trend
        fig.add_trace(go.Scatter(
            x=x_trend, y=y_trend,
            mode='lines',
            name='Tendance linéaire',
            line=dict(color='rgba(0,0,0,0.15)', width=1.5, dash='dash'),
            hoverinfo='skip',
            visible=is_first,
            showlegend=is_first
        ))

        # Trace 2 : tendance principale
        fig.add_trace(go.Scatter(
            x=[d["cost"] for d in main],
            y=[d["sp"]   for d in main],
            mode='markers',
            name=f'Tendance principale ({len(main)} devs)',
            marker=dict(size=8, color='#378ADD', opacity=0.7),
            text=[d["name"] for d in main],
            hovertemplate='<b>%{text}</b><br>Cost: $%{x:.0f}<br>Story Points: %{y}<extra></extra>',
            visible=is_first,
            showlegend=is_first
        ))

        # Trace 3 : efficaces (au-dessus)
        fig.add_trace(go.Scatter(
            x=[d["cost"] for d in outliers_above],
            y=[d["sp"]   for d in outliers_above],
            mode='markers',
            name=f'Efficaces ({len(outliers_above)})',
            marker=dict(size=10, color='#1D9E75', opacity=0.85),
            text=[d["name"] for d in outliers_above],
            hovertemplate='<b>%{text}</b><br>Cost: $%{x:.0f}<br>Story Points: %{y}<extra></extra>',
            visible=is_first,
            showlegend=is_first
        ))

        # Trace 4 : coûteux (en-dessous)
        fig.add_trace(go.Scatter(
            x=[d["cost"] for d in outliers_below],
            y=[d["sp"]   for d in outliers_below],
            mode='markers',
            name=f'Coûteux ({len(outliers_below)})',
            marker=dict(size=10, color='#E24B4A', opacity=0.85),
            text=[d["name"] for d in outliers_below],
            hovertemplate='<b>%{text}</b><br>Cost: $%{x:.0f}<br>Story Points: %{y}<extra></extra>',
            visible=is_first,
            showlegend=is_first
        ))

    # Boutons de sélection du mois
    n_months = len(MONTHS_ORDER)
    buttons = []
    for i, month in enumerate(MONTHS_ORDER):
        visibility = [False] * (n_months * traces_per_month)
        for j in range(traces_per_month):
            visibility[i * traces_per_month + j] = True

        n_devs = len(data_by_month[month])
        buttons.append(dict(
            label=month,
            method="update",
            args=[
                {"visible": visibility},
                {"title": {"text": f"Story Points vs Token Cost — {month}<br><sub>{n_devs} developers</sub>",
                            "font": {"size": 16, "color": "#2C2C2A"}}}
            ]
        ))

    n_first = len(data_by_month[MONTHS_ORDER[0]])
    fig.update_layout(
        title=dict(
            text=f"Story Points vs Token Cost — {MONTHS_ORDER[0]}<br><sub>{n_first} developers</sub>",
            font=dict(size=16, color="#2C2C2A")
        ),
        updatemenus=[dict(
            type="buttons",
            direction="right",
            x=0.0,
            y=1.13,
            xanchor="left",
            buttons=buttons,
            bgcolor="white",
            bordercolor="#5F5E5A",
            font=dict(size=11)
        )],
        xaxis=dict(
            title=dict(text="Token cost (USD, Opus 4.7)", font=dict(size=12, color="#5F5E5A")),
            tickfont=dict(size=11, color="#5F5E5A"),
            showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.06)',
            zeroline=False, range=[x_min, x_max]
        ),
        yaxis=dict(
            title=dict(text="Story points delivered", font=dict(size=12, color="#5F5E5A")),
            tickfont=dict(size=11, color="#5F5E5A"),
            showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.06)',
            zeroline=False, range=[y_min, y_max]
        ),
        hovermode='closest',
        plot_bgcolor='white',
        paper_bgcolor='white',
        height=700,
        width=1200,
        legend=dict(
            x=0.02, y=0.98,
            bgcolor='rgba(255,255,255,0.95)',
            bordercolor='#5F5E5A', borderwidth=1,
            font=dict(size=10, color="#2C2C2A")
        )
    )

    fig.write_html(output_path)
    print(f"✅ Interactive scatter plot saved: {output_path}")
    fig.show()

if __name__ == "__main__":
    csv_files = list(Path(".").glob("**/acme_github_tokens.csv"))

    if not csv_files:
        print("❌ Fichier acme_github_tokens.csv non trouvé")
        exit(1)

    csv_path = csv_files[0]
    print(f"📁 Reading from: {csv_path}")

    create_plot(str(csv_path))

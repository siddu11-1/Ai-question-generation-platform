"""
=============================================================================
utils/analytics.py
Description:
    Generates visual analytics charts using Plotly for:
    - Student score trends over time
    - Score distribution histogram
    - Difficulty breakdown pie chart
    - Feedback ratings bar chart
    - Leaderboard table

    All functions return Plotly figures ready for st.plotly_chart()
=============================================================================
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd


# ─────────────────────────────────────────────
# SCORE TREND LINE CHART
# ─────────────────────────────────────────────

def score_trend_chart(sessions: list) -> go.Figure:
    """
    Plots a student's exam scores over time as a line chart.

    Args:
        sessions: list of exam session dicts with 'started_at', 'score', 'bank_name'

    Returns:
        Plotly Figure object
    """
    if not sessions:
        return _empty_chart("No exam data yet.")

    df = pd.DataFrame(sessions)
    df["started_at"] = pd.to_datetime(df["started_at"])
    df = df.sort_values("started_at")

    fig = go.Figure()

    # Score line
    fig.add_trace(go.Scatter(
        x=df["started_at"],
        y=df["score"],
        mode="lines+markers",
        name="Score (%)",
        line=dict(color="#4a6fa5", width=3),
        marker=dict(size=8, color="#4a6fa5"),
        hovertemplate="<b>%{x|%d %b %Y}</b><br>Score: %{y:.1f}%<extra></extra>"
    ))

    # 60% pass threshold line
    fig.add_hline(
        y=60, line_dash="dash", line_color="red",
        annotation_text="Pass Threshold (60%)",
        annotation_position="bottom right"
    )

    fig.update_layout(
        title="📈 Your Score Progress Over Time",
        xaxis_title="Date",
        yaxis_title="Score (%)",
        yaxis=dict(range=[0, 105]),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=350,
        margin=dict(l=40, r=20, t=50, b=40)
    )

    return fig


# ─────────────────────────────────────────────
# SCORE DISTRIBUTION HISTOGRAM
# ─────────────────────────────────────────────

def score_distribution_chart(performance: list) -> go.Figure:
    """
    Shows distribution of all student average scores (for admin/trainer view).

    Args:
        performance: list of dicts with 'avg_score', 'username'

    Returns:
        Plotly Figure
    """
    if not performance:
        return _empty_chart("No data available.")

    scores = [p["avg_score"] for p in performance if p["avg_score"] is not None]

    fig = px.histogram(
        x=scores,
        nbins=10,
        title="📊 Score Distribution Across Students",
        labels={"x": "Average Score (%)", "y": "Number of Students"},
        color_discrete_sequence=["#4a6fa5"]
    )

    fig.add_vline(
        x=60, line_dash="dash", line_color="red",
        annotation_text="Pass Threshold"
    )

    fig.update_layout(
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=320,
        margin=dict(l=40, r=20, t=50, b=40)
    )

    return fig


# ─────────────────────────────────────────────
# DIFFICULTY BREAKDOWN PIE CHART
# ─────────────────────────────────────────────

def difficulty_pie_chart(breakdown: dict) -> go.Figure:
    """
    Shows the proportion of Easy / Moderate / Hard questions in a bank.

    Args:
        breakdown: dict like {'easy': 5, 'moderate': 10, 'hard': 3}

    Returns:
        Plotly Pie Figure
    """
    labels = list(breakdown.keys())
    values = list(breakdown.values())

    if not any(values):
        return _empty_chart("No questions in this bank yet.")

    color_map = {
        "easy":     "#27ae60",   # green
        "moderate": "#f39c12",   # orange
        "hard":     "#c0392b"    # red
    }
    colors = [color_map.get(l, "#95a5a6") for l in labels]

    fig = go.Figure(data=[go.Pie(
        labels=[l.capitalize() for l in labels],
        values=values,
        marker=dict(colors=colors),
        hole=0.4,
        hovertemplate="<b>%{label}</b><br>Questions: %{value}<br>%{percent}<extra></extra>"
    )])

    fig.update_layout(
        title="🎯 Question Difficulty Breakdown",
        height=300,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="white"
    )

    return fig


# ─────────────────────────────────────────────
# FEEDBACK RATINGS BAR CHART
# ─────────────────────────────────────────────

def feedback_bar_chart(summary: list) -> go.Figure:
    """
    Displays average feedback ratings per category.

    Args:
        summary: list of dicts with 'category', 'count', 'avg_rating'

    Returns:
        Plotly Bar Figure
    """
    if not summary:
        return _empty_chart("No feedback yet.")

    df = pd.DataFrame(summary)

    fig = go.Figure()

    # Bar for avg rating
    fig.add_trace(go.Bar(
        x=df["category"],
        y=df["avg_rating"],
        name="Avg Rating",
        marker_color=["#4a6fa5", "#27ae60", "#f39c12", "#9b59b6"],
        text=[f"{r:.1f} ⭐" for r in df["avg_rating"]],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Avg Rating: %{y:.2f}/5<extra></extra>"
    ))

    fig.update_layout(
        title="💬 Feedback Ratings by Category",
        xaxis_title="Category",
        yaxis_title="Average Rating (out of 5)",
        yaxis=dict(range=[0, 5.5]),
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=320,
        margin=dict(l=40, r=20, t=50, b=60)
    )

    return fig


# ─────────────────────────────────────────────
# LEADERBOARD CHART
# ─────────────────────────────────────────────

def leaderboard_chart(performance: list, top_n: int = 10) -> go.Figure:
    """
    Horizontal bar chart showing top N students by average score.

    Args:
        performance: list of dicts with 'username', 'avg_score'
        top_n: number of top students to show

    Returns:
        Plotly Figure
    """
    # Filter students who have taken at least one exam
    active = [p for p in performance if p.get("total_exams", 0) > 0 and p["avg_score"] is not None]
    top    = sorted(active, key=lambda x: x["avg_score"], reverse=True)[:top_n]

    if not top:
        return _empty_chart("No exam data yet.")

    usernames = [p["username"] for p in top]
    scores    = [p["avg_score"] for p in top]

    # Color: gold for 1st, silver for 2nd, bronze for 3rd, blue for rest
    bar_colors = []
    for i in range(len(top)):
        if i == 0:   bar_colors.append("#FFD700")  # Gold
        elif i == 1: bar_colors.append("#C0C0C0")  # Silver
        elif i == 2: bar_colors.append("#CD7F32")  # Bronze
        else:        bar_colors.append("#4a6fa5")  # Blue

    fig = go.Figure(go.Bar(
        x=scores,
        y=usernames,
        orientation="h",
        marker_color=bar_colors,
        text=[f"{s:.1f}%" for s in scores],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Avg Score: %{x:.1f}%<extra></extra>"
    ))

    fig.update_layout(
        title=f"🏆 Top {len(top)} Student Leaderboard",
        xaxis_title="Average Score (%)",
        xaxis=dict(range=[0, 110]),
        yaxis=dict(autorange="reversed"),   # highest score at top
        plot_bgcolor="white",
        paper_bgcolor="white",
        height=max(300, len(top) * 40),
        margin=dict(l=100, r=60, t=50, b=40)
    )

    return fig


# ─────────────────────────────────────────────
# PASS/FAIL DONUT CHART
# ─────────────────────────────────────────────

def pass_fail_donut(sessions: list) -> go.Figure:
    """
    Shows ratio of passed vs failed exams for a student or overall.

    Args:
        sessions: list of exam session dicts with 'passed' field

    Returns:
        Plotly Figure
    """
    if not sessions:
        return _empty_chart("No exams yet.")

    passed = sum(1 for s in sessions if s.get("passed") == 1)
    failed = len(sessions) - passed

    fig = go.Figure(data=[go.Pie(
        labels=["Passed", "Failed"],
        values=[passed, failed],
        hole=0.55,
        marker=dict(colors=["#27ae60", "#e74c3c"]),
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b>: %{value} exams (%{percent})<extra></extra>"
    )])

    fig.update_layout(
        title="✅ Pass / Fail Ratio",
        annotations=[dict(text=f"{passed}/{len(sessions)}", x=0.5, y=0.5,
                          font_size=20, showarrow=False)],
        height=280,
        margin=dict(l=20, r=20, t=50, b=20),
        paper_bgcolor="white"
    )

    return fig


# ─────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────

def _empty_chart(message: str) -> go.Figure:
    """Returns a blank figure with a centered message."""
    fig = go.Figure()
    fig.add_annotation(
        text=message, x=0.5, y=0.5, xref="paper", yref="paper",
        showarrow=False, font=dict(size=14, color="gray")
    )
    fig.update_layout(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        height=250,
        paper_bgcolor="white"
    )
    return fig

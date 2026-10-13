"""
Visualization & Insight Layer

Purpose:
This module converts quantitative risk metrics into visual intuition.

Why visualization matters:
Risk numbers alone are hard to interpret.
Visuals help identify concentration, tail risk,
and diversification effects quickly.

Design choices:
- Visuals are explanatory, not decorative.
- Each chart corresponds to a specific analytical question.
- Plots fail loudly when inputs are invalid.
- Every function returns its figure; the caller shows or saves it.
"""

import pandas as pd #type:ignore
import numpy as np #type:ignore
import plotly.graph_objects as go  # type: ignore
from plotly.subplots import make_subplots  # type: ignore
import plotly.express as px  # type: ignore

def plot_normalized_prices(clean_prices, benchmark_clean, benchmark_name="Benchmark"):
    """
    clean_prices    : DataFrame (index = Date, columns = asset prices)
    benchmark_clean : Series or DataFrame (benchmark prices)
    """

    # ---- Normalize to base 100 ----
    norm_assets = (clean_prices / clean_prices.iloc[0]) * 100
    norm_benchmark = (benchmark_clean / benchmark_clean.iloc[0]) * 100

    aligned = pd.concat(
        [norm_assets, norm_benchmark],
        axis=1,
        join="inner"
    ).dropna()

    assets = aligned.iloc[:, :-1]
    benchmark = aligned.iloc[:, -1]

    fig = go.Figure()

    # ---- Color palette for assets ----
    colors = px.colors.qualitative.Set2  # clean, non-garish palette

    # ---- Asset price paths ----
    for i, asset in enumerate(assets.columns):
        fig.add_trace(
            go.Scatter(
                x=aligned.index,
                y=assets[asset],
                mode="lines",
                line=dict(
                    width=1.4,
                    color=colors[i % len(colors)]
                ),
                opacity=0.75,
                name=asset
            )
        )

    # ---- Benchmark (dominant reference) ----
    fig.add_trace(
        go.Scatter(
            x=aligned.index,
            y=benchmark,
            mode="lines",
            line=dict(width=3, color="#111827"),  # near-black
            name=benchmark_name
        )
    )

    # ---- Layout & grid ----
    fig.update_layout(
        title="Normalized Asset Prices vs Market (Base = 100)",
        xaxis_title="Date",
        yaxis_title="Normalized Price (Base = 100)",
        template="plotly_white",
        height=900,        # increased size
        width=1500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.05,
            xanchor="right",
            x=1
        )
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(0,0,0,0.12)"
    )

    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(0,0,0,0.12)"
    )

    return fig

def plot_drawdowns_comparison(asset_drawdowns, portfolio_drawdowns):

    assets = asset_drawdowns.columns.tolist()
    n = len(assets)

    fig = make_subplots(
        rows=n + 1,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=min(0.04, 0.5 / n),  # must shrink as rows grow
        subplot_titles=["Portfolio"] + assets
    )

    # ---------- Portfolio ----------
    fig.add_trace(
        go.Scatter(
            x=portfolio_drawdowns.index,
            y=portfolio_drawdowns.values * 100,
            fill="tozeroy",
            line=dict(color="#1d4ed8", width=2.6),  # dark blue
            name="Portfolio"
        ),
        row=1, col=1
    )

    fig.add_trace(
        go.Scatter(
            x=[portfolio_drawdowns.idxmin()],
            y=[portfolio_drawdowns.min() * 100],
            mode="markers+text",
            marker=dict(color="black", size=8),
            text=[f"Max DD: {portfolio_drawdowns.min()*100:.1f}%"],
            textposition="top left",
            cliponaxis=False,
            showlegend=False
        ),
        row=1, col=1
    )

    # ---------- Assets ----------
    for i, asset in enumerate(assets, start=2):
        series = asset_drawdowns[asset] * 100

        fig.add_trace(
            go.Scatter(
                x=series.index,
                y=series.values,
                fill="tozeroy",
                line=dict(color="#2563eb", width=1.2),
                opacity=0.5,
                showlegend=False
            ),
            row=i, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=[series.idxmin()],
                y=[series.min()],
                mode="markers",
                marker=dict(color="black", size=8),
                showlegend=False
            ),
            row=i, col=1
        )

    # ---------- Layout ----------
    fig.update_layout(
        title="Portfolio vs Asset Drawdowns — Peak-to-Trough Risk",
        height=140 * (n + 1),
        width=1500,
        template="plotly_white",
        showlegend=False,
        font=dict(size=11),  # smaller overall font
    )

    fig.update_annotations(font=dict(size=10))  # smaller asset titles

    floor = float(min(asset_drawdowns.min().min(), portfolio_drawdowns.min())) * 100 - 5
    fig.update_yaxes(range=[floor, 0], showgrid=True, gridcolor="rgba(0,0,0,0.08)")
    fig.update_xaxes(showgrid=True, gridcolor="rgba(0,0,0,0.08)")

    for r in range(1, n + 1):
        fig.update_xaxes(showticklabels=False, row=r, col=1)

    fig.add_annotation(
        text="Drawdown (%)",
        xref="paper", yref="paper",
        x=-0.055, y=0.5,
        showarrow=False,
        textangle=-90,
        font=dict(size=11)
    )

    return fig

def plot_correlation_heatmap(corr_matrix):
    """
    corr_matrix : DataFrame (index & columns = asset names)
    """

    fig = go.Figure(
        data=go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns,
            y=corr_matrix.index,
            zmin=-1,
            zmax=1,
            colorscale="RdBu",
            reversescale=True,
            colorbar=dict(title="Correlation")
        )
    )

    # Add correlation values inside cells
    fig.update_traces(
        text=np.round(corr_matrix.values, 2),
        texttemplate="%{text}",
        textfont=dict(size=11)
    )

    fig.update_layout(
        title="Asset Return Correlation Matrix",
        width=max(800, 60 * len(corr_matrix) + 300),
        height=max(800, 60 * len(corr_matrix) + 200),
        template="plotly_white"
    )

    return fig

def plot_risk_contribution(portfolio_weights, asset_risk_contribution, label="Asset"):

    weights = pd.Series(portfolio_weights)
    risk = asset_risk_contribution

    weight_pct = weights * 100
    risk_pct = risk / risk.sum() * 100

    df = pd.DataFrame({
        "Weight (%)": weight_pct,
        "Risk (%)": risk_pct
    })

    # Split risk into base + excess
    df["Risk Base"] = df[["Weight (%)", "Risk (%)"]].min(axis=1)
    df["Risk Excess"] = (df["Risk (%)"] - df["Weight (%)"]).clip(lower=0)

    df = df.sort_values("Risk (%)", ascending=False)

    fig = go.Figure()

    # ---- Weight bar (left) ----
    fig.add_bar(
        x=df.index,
        y=df["Weight (%)"],
        name="Portfolio Weight (%)",
        marker_color="#93c5fd",
        offsetgroup="weight"
    )

    # ---- Risk base (blue, right) ----
    fig.add_bar(
        x=df.index,
        y=df["Risk Base"],
        name="Risk Contribution (%)",
        marker_color="#1d4ed8",
        offsetgroup="risk"
    )

    # ---- Risk excess (red cap, stacked on risk) ----
    fig.add_bar(
        x=df.index,
        y=df["Risk Excess"],
        base=df["Risk Base"],
        name="Excess Risk over Weight",
        marker_color="#dc2626",
        offsetgroup="risk",
        showlegend=True
    )

    fig.update_layout(
        title=f"Portfolio Weight vs Risk Contribution by {label} (Excess Risk Highlighted)",
        barmode="group",
        template="plotly_white",
        height=520,
        width=max(950, 60 * len(df)),
        yaxis_title="Percentage (%)",
        xaxis_title=label,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.05,
            xanchor="right",
            x=1
        )
    )

    fig.update_yaxes(
    showgrid=True,
    gridcolor="rgba(0,0,0,0.1)",
    zeroline=False  # 🔴 turn off zeroline
    )

    fig.update_xaxes(
    showline=True,
    linewidth=1,
    linecolor="black",
    layer="below traces"  # 🔑 prevents bar overlap
    )

    return fig

def plot_stress_test(scenario_losses, portfolio_max_drawdown):
    """
    scenario_losses        : dict (scenario label -> portfolio return, e.g. -0.15)
    portfolio_max_drawdown : float

    Only losses belong here. A stressed volatility is not a loss and is
    reported separately.
    """

    # ---------- Prepare data ----------
    stress_losses = (pd.Series(scenario_losses) * 100).sort_values()

    palette = ["#64748b", "#dc2626", "#f59e0b", "#7c3aed", "#0891b2", "#be185d"]
    colors = {label: palette[i % len(palette)] for i, label in enumerate(scenario_losses)}

    # ---------- Create figure ----------
    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=stress_losses.values,
            y=stress_losses.index,
            orientation="h",
            marker=dict(
                color=[colors[i] for i in stress_losses.index],
                line=dict(width=0)
            ),
            text=[f"{v:.1f}%" for v in stress_losses.values],
            textposition="outside",
            textfont=dict(size=14),
            hovertemplate="%{y}<br>Loss: %{x:.1f}%<extra></extra>"
        )
    )

    # ---------- Historical max drawdown reference ----------
    fig.add_vline(
    x=portfolio_max_drawdown * 100,
    line=dict(color="#0f172a", dash="dash", width=2),
    annotation_text="Historical Max Drawdown",
    annotation_font=dict(size=13),
    annotation_position="top right",
    annotation_xshift=8  # 🔹 small horizontal nudge
    )


    # ---------- Layout polish ----------
    fig.update_layout(
    title=dict(
        text="Portfolio Stress Losses vs Historical Risk",
        x=0.02,
        font=dict(size=22)
    ),
    xaxis_title="Portfolio Loss (%)",
    template="plotly_white",
    height=140 + 70 * len(stress_losses),
    width=1000,
    showlegend=False,

    # 🔹 Increased left margin for label breathing room
    margin=dict(l=260, r=40, t=80, b=60),

    # 🔹 Light modern background
    paper_bgcolor="#f8fafc",   # very light slate
    plot_bgcolor="#ffffff",

    font=dict(size=14)
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(0,0,0,0.18)",  # slightly stronger grid
        zeroline=False
    )

    fig.update_yaxes(
    showgrid=False,
    tickfont=dict(size=15),
    automargin=True
    )

    return fig

def plot_asset_risk_return(annual_vol, sharpe, beta):
    df = pd.DataFrame({
        "Volatility": annual_vol * 100,
        "Sharpe": sharpe,
        "Beta": beta.abs()
    }).dropna()  # zero-volatility holdings (cash) have no Sharpe ratio

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df["Volatility"],
            y=df["Sharpe"],
            mode="markers+text",
            text=df.index,
            textposition="top center",
            marker=dict(
                size=df["Beta"].clip(0.3, 3) * 20,
                color=df["Beta"],
                colorscale="Viridis",
                showscale=True,
                colorbar=dict(title="|Beta|"),
                line=dict(width=1, color="white"),
                opacity=0.9
            ),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Volatility: %{x:.1f}%<br>"
                "Sharpe: %{y:.2f}<br>"
                "Beta: %{marker.color:.2f}<extra></extra>"
            )
        )
    )

    fig.update_layout(
        title="Asset Risk–Return Profile",
        xaxis_title="Annual Volatility (%)",
        yaxis_title="Sharpe Ratio",
        template="plotly_white",
        height=500,
        width=800
    )

    return fig

def plot_max_drawdown_comparison(asset_max_drawdown, portfolio_max_drawdown):
    """
    asset_max_drawdown      : Series (asset -> max drawdown)
    portfolio_max_drawdown  : float
    """

    # ---------- Prepare data ----------
    dd = asset_max_drawdown.copy() * 100
    dd["Portfolio"] = portfolio_max_drawdown * 100

    dd = dd.sort_values()  # worst drawdown first

    # dark = portfolio, red = fell further than the portfolio, slate = held up better
    colors = [
        "#0f172a" if name == "Portfolio" else "#dc2626" if v < dd["Portfolio"] else "#64748b"
        for name, v in dd.items()
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=dd.values,
            y=dd.index,
            orientation="h",
            marker=dict(color=colors),
            text=[f"{v:.1f}%" for v in dd.values],
            textposition="outside",
            hovertemplate="%{y}<br>Max DD: %{x:.1f}%<extra></extra>"
        )
    )

    # ---------- Layout ----------
    fig.update_layout(
        title="Maximum Drawdown Comparison",
        xaxis_title="Max Drawdown (%)",
        template="plotly_white",
        height=max(420, 34 * len(dd) + 140),
        width=1000,
        paper_bgcolor="#f8fafc",
        plot_bgcolor="#ffffff",
        margin=dict(l=260, r=60, t=70, b=50),
        font=dict(size=14)
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor="rgba(0,0,0,0.18)",
        zeroline=False,
        range=[dd.min() * 1.18, 0]  # room for the outside value labels
    )

    fig.update_yaxes(showgrid=False)

    return fig

def plot_diversification_benefit(
    annual_vol,
    portfolio_weights,
    annual_portfolio_vol
):
    """
    annual_vol        : Series (asset annual vol)
    portfolio_weights : dict
    annual_pf_vol     : float
    """

    weights = pd.Series(portfolio_weights)

    weighted_avg_vol = (annual_vol * weights).sum() * 100
    portfolio_vol = annual_portfolio_vol * 100

    data = {
        "Weighted Avg Asset Vol": weighted_avg_vol,
        "Actual Portfolio Vol": portfolio_vol
    }

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=list(data.keys()),
            y=list(data.values()),
            marker_color=["#94a3b8", "#2563eb"],  # grey vs blue
            text=[f"{v:.1f}%" for v in data.values()],
            textposition="outside",
            hovertemplate="%{x}<br>Volatility: %{y:.1f}%<extra></extra>"
        )
    )

    fig.update_layout(
        title="Diversification Benefit — Volatility Reduction",
        yaxis_title="Annual Volatility (%)",
        template="plotly_white",
        height=380,
        width=700,
        paper_bgcolor="#f8fafc",
        plot_bgcolor="#ffffff",
        margin=dict(l=80, r=40, t=70, b=60),
        font=dict(size=14)
    )

    fig.update_yaxes(
        showgrid=True,
        gridcolor="rgba(0,0,0,0.18)",
        zeroline=False
    )

    return fig


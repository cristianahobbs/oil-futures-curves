"""Futures curve explorer.

    streamlit run app.py

Pick a commodity and any date since the 1980s to see the first four contracts that day, compare it
with another date, and see today's full curve and the carry history.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

import curves as cv
from data import COMMODITIES, DATA, load_futures, load_live_curves

SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
MUTED = "#898781"
GRID = "rgba(137,135,129,0.25)"
pio.templates["curves"] = go.layout.Template(layout=dict(
    font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif', size=13),
    colorway=SERIES, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(showgrid=False, linecolor=MUTED, zeroline=False),
    yaxis=dict(gridcolor=GRID, zeroline=False),
    legend=dict(orientation="h", yanchor="bottom", y=1.01, xanchor="left", x=0),
    margin=dict(l=10, r=10, t=40, b=10), hovermode="x unified",
))
pio.templates.default = "plotly+curves"

st.set_page_config(page_title="Energy futures curves", layout="wide")


@st.cache_data
def futures() -> pd.DataFrame:
    return load_futures()


@st.cache_data(ttl=3600)
def live() -> pd.DataFrame:
    return load_live_curves()


def curve_on(prices: pd.DataFrame, root: str, day: date) -> tuple[pd.Timestamp, pd.Series] | None:
    cols = [f"{root}{k}" for k in range(1, 5)]
    px = prices.loc[: pd.Timestamp(day), cols].dropna()
    if px.empty:
        return None
    return px.index[-1], px.iloc[-1]


def delivery_months(root: str, settle: pd.Timestamp) -> list[str]:
    """Label contracts 1-4 with their delivery month on that settlement date."""
    out, p = [], settle.to_period("M")
    while len(out) < 4:
        p += 1
        if cv.expiry(root, p.year, p.month) >= settle:
            out.append(p.strftime("%b %Y"))
    return out


prices = futures()
st.title("Energy futures curves")
st.caption("NYMEX settlements for the first four contracts from EIA (to April 2024); today's curve from Yahoo "
           "Finance. Contango: later contracts cost more. Backwardation: they cost less.")

root = st.radio("Commodity", list(COMMODITIES), horizontal=True,
                format_func=lambda r: COMMODITIES[r]["name"])
first = prices[f"{root}1"].first_valid_index().date()
last = prices[f"{root}4"].last_valid_index().date()
presets = {"Custom": None, "Jul 2008 peak": date(2008, 7, 3), "Apr 2020 negative WTI": date(2020, 4, 20),
           "Mar 2022 Russia shock": date(2022, 3, 8), "Latest EIA date": last}

c1, c2 = st.columns(2)
with c1:
    preset = st.selectbox("Jump to", list(presets))
    day_a = st.date_input("Date", presets[preset] or date(2020, 4, 20), min_value=first, max_value=last,
                          key=f"date_{preset}")
with c2:
    compare = st.checkbox("Compare with a second date", value=True)
    day_b = st.date_input("Second date", date(2022, 3, 8), min_value=first, max_value=last, disabled=not compare)

tab_curve, tab_today, tab_carry = st.tabs(["Curve on a date", "Today's full curve", "Carry history"])
unit = COMMODITIES[root]["unit"]

with tab_curve:
    fig = go.Figure()
    for i, d in enumerate([day_a] + ([day_b] if compare else [])):
        got = curve_on(prices, root, d)
        if got is None:
            st.warning(f"No data on or before {d}.")
            continue
        settle, row = got
        c = cv.carry(prices.loc[[settle]], root).iloc[0]
        fig.add_trace(go.Scatter(
            x=["1st", "2nd", "3rd", "4th"], y=row.to_numpy(), mode="lines+markers",
            name=f"{settle:%d %b %Y} ({cv.curve_state(c)}, carry {c:+.0%})",
            customdata=delivery_months(root, settle), line=dict(width=2.5, color=SERIES[i]),
            marker=dict(size=9, line=dict(width=2, color="white")),
            hovertemplate="%{customdata}: %{y:.3f}<extra></extra>"))
    fig.update_layout(yaxis_title=unit, xaxis_title="Contract", height=440, hovermode="closest")
    st.plotly_chart(fig, width="stretch")
    st.caption("Carry is the annualised slope between the 2nd and 4th contracts, the signal tested in the "
               "backtest. Positive = backwardation.")

with tab_today:
    lv = live()
    as_of = (DATA / "live_curves_as_of.txt")
    st.caption(f"Last refreshed {as_of.read_text().strip() if as_of.exists() else 'unknown'} "
               "by the daily update job.")
    curve = lv[root].dropna()
    fig = go.Figure(go.Scatter(x=curve.index, y=curve, mode="lines+markers", line=dict(width=2.5),
                               hovertemplate="%{x|%b %Y}: %{y:.3f}<extra></extra>"))
    fig.update_layout(yaxis_title=unit, xaxis_title="Delivery month", height=420, hovermode="closest")
    st.plotly_chart(fig, width="stretch")

with tab_carry:
    c = cv.carry(prices, root).dropna()
    c = c.groupby(c.index.to_period("M")).last()
    c.index = c.index.to_timestamp()
    fig = go.Figure(go.Bar(x=c.index, y=c, marker_color=[SERIES[0] if v > 0 else SERIES[1] for v in c],
                           hovertemplate="%{x|%b %Y}: %{y:.1%}<extra></extra>"))
    fig.update_layout(yaxis_tickformat=".0%", height=420, showlegend=False, bargap=0,
                      title="Month-end carry: blue = backwardation, orange = contango")
    st.plotly_chart(fig, width="stretch")

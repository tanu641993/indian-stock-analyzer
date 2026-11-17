# app.py
import streamlit as st
import pandas as pd
import sys
import os

SRC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC_PATH not in sys.path:
    sys.path.append(SRC_PATH)

from scoring import ScoringEngine

st.set_page_config(page_title="Quant Research Platform", page_icon="🏆", layout="wide")

@st.cache_data(ttl=3600)
def get_data():
    engine = ScoringEngine()
    df = engine.rank_all()
    engine.close()
    return df

df = get_data()

st.sidebar.header("🎯 Strategy Selection")
strategy = st.sidebar.radio(
    "Choose Ranking Model:",
    ["Compounder Rank", "Growth Rank", "Value Rank", "Potential Multibaggers"]
)

st.title(f"📈 {strategy}")

# Map the radio buttons to the dataframe columns
score_col = {
    "Compounder Rank": "Compounder_Score",
    "Growth Rank": "Growth_Score",
    "Value Rank": "Value_Score",
    "Potential Multibaggers": "Multibagger_Score"
}[strategy]

# app.py (Bottom Section)

# ... (keep the top part of app.py the same) ...

# Filter out stocks with a 0 score for multibaggers
if strategy == "Potential Multibaggers":
    display_df = df[df["Multibagger_Score"] > 0].copy()
else:
    display_df = df.copy()

# Map the sidebar selection to the correct column
score_col = {
    "Master Investment Score": "Master_Score",
    "Compounder Rank": "Compounder_Score",
    "Growth Rank": "Growth_Score",
    "Value Rank": "Value_Score",
    "Potential Multibaggers": "Multibagger_Score"
}[strategy]

# Sort by the selected score
display_df = display_df.sort_values(by=score_col, ascending=False)

# Format the display
display_columns = ["Symbol", "Sector", "Master_Score", "Compounder_Score", "Growth_Score", "Value_Score", "Multibagger_Score"]

st.dataframe(
    display_df[display_columns],
    use_container_width=True,
    hide_index=True
)

st.markdown("---")
st.info(f"💡 **Currently viewing:** {strategy}. The **Master_Score** is the final 100-point combined ranking.")
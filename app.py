# ... (Keep the top of app.py exactly the same) ...

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

# ---------------------------------------------------------
# NEW: ADD VERDICT / RECOMMENDATION COLUMN
# ---------------------------------------------------------
def get_verdict(score):
    if score >= 75:
        return "🟢 STRONG BUY (Long Term)"
    elif score >= 60:
        return "🟡 BUY / HOLD"
    elif score >= 45:
        return "🟠 WATCHLIST"
    else:
        return "🔴 AVOID"

# We base the verdict on the Master_Score since it represents overall quality
display_df["Verdict"] = display_df["Master_Score"].apply(get_verdict)

# ---------------------------------------------------------
# NEW: STYLE THE DATAFRAME (COLOR HIGHLIGHTS)
# ---------------------------------------------------------
def color_master_score(val):
    if val >= 75:
        color = '#d4edda' # Light Green
        text_color = '#155724' # Dark Green
    elif val >= 60:
        color = '#fff3cd' # Light Yellow
        text_color = '#856404' # Dark Yellow
    elif val >= 45:
        color = '#ffe5b4' # Light Orange
        text_color = '#856404' 
    else:
        color = '#f8d7da' # Light Red
        text_color = '#721c24' # Dark Red
    
    return f'background-color: {color}; color: {text_color}; font-weight: bold;'

# Apply the styling to the Master_Score column
styled_df = display_df.style.map(color_master_score, subset=["Master_Score"])

# Format the display
st.dataframe(
    styled_df,
    column_config={
        "Master_Score": st.column_config.ProgressColumn(
            "Master Score",
            help="The final 100-point combined ranking",
            format="%f",
            min_value=0,
            max_value=100,
        ),
        "Compounder_Score": st.column_config.NumberColumn("Compounder (/40)"),
        "Growth_Score": st.column_config.NumberColumn("Growth (/20)"),
        "Value_Score": st.column_config.NumberColumn("Value (/10)"),
        "Multibagger_Score": st.column_config.NumberColumn("Multibagger (/100)"),
    },
    use_container_width=True,
    hide_index=True
)

st.markdown("---")
st.info(f"💡 **Currently viewing:** {strategy}. The **Master Score** acts as your Long-Term Buy indicator. Scores above 70 (Green) are fundamentally strong.")
# app.py

import streamlit as st
import pandas as pd
import sys
import os
import re
import sqlite3
from pypdf import PdfReader
import plotly.express as px

# ---------------------------------------------------------
# 1. PATH SETUP & IMPORTS
# ---------------------------------------------------------
SRC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if SRC_PATH not in sys.path:
    sys.path.append(SRC_PATH)

from scoring import ScoringEngine

# Define DB Path for raw queries
DB_PATH = os.path.join(SRC_PATH, "..", "database", "stocks.db")

st.set_page_config(page_title="StockIQ", page_icon="📈", layout="wide")

# ---------------------------------------------------------
# 2. GLOBAL HELPER FUNCTIONS
# ---------------------------------------------------------
def get_verdict(score):
    if score >= 75: return "🟢 STRONG BUY (Long Term)"
    elif score >= 60: return "🟡 BUY / HOLD"
    elif score >= 45: return "🟠 WATCHLIST"
    else: return "🔴 AVOID"

# ---------------------------------------------------------
# 3. SIDEBAR NAVIGATION
# ---------------------------------------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", ["📈 Stock Screener", "🪙 Commodity Dashboard", "📁 My Portfolio"])

# =========================================================
# PAGE 1: STOCK SCREENER
# =========================================================
if page == "📈 Stock Screener":
    @st.cache_data(ttl=3600)
    def get_data():
        engine = ScoringEngine()
        df = engine.rank_all()
        engine.close()
        return df

    try:
        df = get_data()
    except Exception as e:
        st.error(f"⚠️ Error loading database: {e}")
        st.stop()

    st.sidebar.markdown("---")
    st.sidebar.header("🎯 Strategy Selection")
    strategy = st.sidebar.radio("Choose Ranking Model:", ["Master Investment Score", "Compounder Rank", "Growth Rank", "Value Rank", "Potential Multibaggers"])

    st.sidebar.header("🔍 Filter Options")
    all_sectors = sorted(df["Sector"].dropna().unique().tolist())
    selected_sectors = st.sidebar.multiselect("Select Sectors:", options=all_sectors, default=all_sectors)
    min_score = st.sidebar.slider("Minimum Master Score:", min_value=0, max_value=100, value=45, step=5)
    
    all_verdicts = ["🟢 STRONG BUY (Long Term)", "🟡 BUY / HOLD", "🟠 WATCHLIST", "🔴 AVOID"]
    selected_verdicts = st.sidebar.multiselect("Show Verdicts:", options=all_verdicts, default=all_verdicts)

    st.title(f"📈 {strategy}")

    score_col = {"Master Investment Score": "Master_Score", "Compounder Rank": "Compounder_Score", "Growth Rank": "Growth_Score", "Value Rank": "Value_Score", "Potential Multibaggers": "Multibagger_Score"}[strategy]

    display_df = df.copy()
    if selected_sectors: display_df = display_df[display_df["Sector"].isin(selected_sectors)]
    else: display_df = display_df.iloc[0:0]

    display_df = display_df[display_df["Master_Score"] >= min_score]
    display_df["Verdict"] = display_df["Master_Score"].apply(get_verdict)
    
    if selected_verdicts: display_df = display_df[display_df["Verdict"].isin(selected_verdicts)]
    else: display_df = display_df.iloc[0:0]

    if strategy == "Potential Multibaggers": display_df = display_df[display_df["Multibagger_Score"] > 0]
    display_df = display_df.sort_values(by=score_col, ascending=False)

    if display_df.empty:
        st.warning("⚠️ No stocks match your current filters.")
    else:
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# =========================================================
# PAGE 2: COMMODITY DASHBOARD
# =========================================================
elif page == "🪙 Commodity Dashboard":
    st.title("🪙 Commodity Dashboard")
    st.info("Commodity tracking dashboard")

# =========================================================
# PAGE 3: MY PORTFOLIO (CDSL PARSER)
# =========================================================
elif page == "📁 My Portfolio":
    st.title("📁 My Portfolio Dashboard")
    
    col1, col2 = st.columns([2, 1])
    with col1:
        uploaded_file = st.file_uploader("Upload CDSL PDF Report", type=["pdf"])
    with col2:
        password = st.text_input("PDF Password", type="password", help="Usually PAN + DOB")

    if uploaded_file is not None and password:
        try:
            reader = PdfReader(uploaded_file)
            if reader.is_encrypted:
                reader.decrypt(password)
            
            full_text = ""
            for page_obj in reader.pages:
                full_text += page_obj.extract_text() + "\n"
            
            st.success("✅ PDF Successfully Unlocked!")

            # Load full database data for scores
            @st.cache_data(ttl=3600)
            def get_portfolio_data():
                engine = ScoringEngine()
                df = engine.rank_all()
                engine.close()
                return df
            
            db_df = get_portfolio_data()
            
            # Find stocks
            found_symbols = []
            for symbol in db_df['Symbol']:
                if re.search(r'\b' + re.escape(symbol) + r'\b', full_text):
                    found_symbols.append(symbol)
            
            if not found_symbols:
                st.warning("⚠️ Could not find any stocks from our database in this PDF.")
            else:
                # Filter the main dataframe to only the stocks found in the PDF
                port_df = db_df[db_df['Symbol'].isin(found_symbols)].copy()
                port_df["Verdict"] = port_df["Master_Score"].apply(get_verdict)
                
                # --- PORTFOLIO METRICS ---
                st.markdown("### 📊 Portfolio Health Summary")
                avg_score = port_df["Master_Score"].mean()
                good_stocks = len(port_df[port_df["Master_Score"] >= 60])
                bad_stocks = len(port_df[port_df["Master_Score"] < 60])
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Average Portfolio Score", f"{avg_score:.1f} / 100")
                c2.metric("Good Quality Stocks", good_stocks, delta_color="normal")
                c3.metric("Poor Quality Stocks", bad_stocks, delta_color="inverse")

                # --- SECTOR ALLOCATION PIE CHART ---
                st.markdown("### 🍩 Sector Allocation")
                sector_counts = port_df["Sector"].value_counts().reset_index()
                sector_counts.columns = ["Sector", "Count"]
                fig_pie = px.pie(sector_counts, names="Sector", values="Count", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_pie, use_container_width=True)

                # --- BAR CHART ---
                st.markdown("### 🟢🔴 Portfolio Quality Chart")
                port_df_sorted = port_df.sort_values(by="Master_Score", ascending=False)
                def get_color(score):
                    return "🟢 Good (>60)" if score >= 60 else "🔴 Bad (<60)"
                
                port_df_sorted["Color_Status"] = port_df_sorted["Master_Score"].apply(get_color)
                
                fig = px.bar(
                    port_df_sorted, x="Symbol", y="Master_Score", color="Color_Status",
                    color_discrete_map={"🟢 Good (>60)": "#28a745", "🔴 Bad (<60)": "#dc3545"},
                    text="Master_Score", title="Quality Score of Your Holdings"
                )
                fig.update_layout(yaxis_title="Master Score (0-100)", xaxis_title="Stock Symbol")
                st.plotly_chart(fig, use_container_width=True)
                
                # --- DEEP DIVE METRICS ---
                st.markdown("### 🔬 Deep Dive: Why did they score this way?")
                st.markdown("This table shows the underlying fundamental metrics driving the Master Score.")
                
                # Prepare detailed table
                detail_df = port_df_sorted[[
                    "Symbol", "Sector", "Master_Score", "Verdict", 
                    "Compounder_Score", "Growth_Score", "Value_Score"
                ]].copy()
                
                st.dataframe(
                    detail_df,
                    column_config={
                        "Master_Score": st.column_config.ProgressColumn("Master Score", format="%f", min_value=0, max_value=100),
                        "Compounder_Score": st.column_config.NumberColumn("Compounder (/40)"),
                        "Growth_Score": st.column_config.NumberColumn("Growth (/20)"),
                        "Value_Score": st.column_config.NumberColumn("Value (/10)"),
                    },
                    use_container_width=True, hide_index=True
                )
                
                with st.expander("View Raw Financial Data (ROE, PE, Debt, etc.)"):
                    # FIX: Fetch raw data from DB directly since port_df doesn't have it
                    conn = sqlite3.connect(DB_PATH)
                    placeholders = ','.join('?' * len(found_symbols))
                    raw_query = f"SELECT symbol AS Symbol, roe, roce, debt_to_equity, pe, pb FROM fundamentals WHERE symbol IN ({placeholders})"
                    raw_data = pd.read_sql(raw_query, conn, params=found_symbols)
                    conn.close()

                    if not raw_data.empty:
                        # Format decimals as percentages
                        raw_data["roe"] = raw_data["roe"].apply(lambda x: f"{x*100:.1f}%" if pd.notnull(x) else "N/A")
                        raw_data["roce"] = raw_data["roce"].apply(lambda x: f"{x*100:.1f}%" if pd.notnull(x) else "N/A")
                        st.dataframe(raw_data, use_container_width=True, hide_index=True)
                    else:
                        st.write("No raw data available.")

                st.info("💡 **Note on low scores:** If a stock scores low, check the 'Raw Financial Data'. If fields say 'N/A', Yahoo Finance lacks data for that company, and the scoring engine heavily penalizes missing data.")

        except Exception as e:
            st.error("❌ Failed to read PDF. Check password.")
            st.info(f"Error: {e}")
    elif uploaded_file is not None and not password:
        st.warning("⚠️ Please enter the PDF password.")
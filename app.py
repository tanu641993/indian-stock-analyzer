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

DB_PATH = os.path.join(SRC_PATH, "..", "database", "stocks.db")

st.set_page_config(page_title="StockIQ", page_icon="📈", layout="wide")

# ---------------------------------------------------------
# 2. GLOBAL HELPER FUNCTIONS & SECTOR MAPPING
# ---------------------------------------------------------
def get_verdict(score):
    if score >= 75: return "🟢 STRONG BUY (Long Term)"
    elif score >= 60: return "🟡 BUY / HOLD"
    elif score >= 45: return "🟠 WATCHLIST"
    else: return "🔴 AVOID"

def map_indian_sector(row):
    symbol = row['Symbol']
    yf_sector = row['Sector']
    
    # --- CUSTOM HOSPITALITY MAPPING ---
    # Add any hospitality/restaurant tickers you have in your DB here
    hospitality_stocks = [
        'INDHOTEL', 'LEMONTREE', 'CHALET', 'EIHOTEL', 'JUNIPER', 
        'ITCHOTELS', 'WESTLIFE', 'DEVYANI', 'SAPPHIRE', 'BARBEQUE'
    ]
    if symbol in hospitality_stocks:
        return "Hospitality & Tourism"

    if pd.isna(yf_sector): return "Other"
    
    s = str(yf_sector).lower()
    if "financial" in s or "bank" in s: return "Banking & Financial Services"
    elif "energy" in s or "oil" in s or "gas" in s: return "Oil & Gas"
    elif "health" in s or "pharma" in s: return "Health & Pharma"
    elif "industrial" in s or "defence" in s: return "Electronics & Defence Manufacturing"
    elif "consumer cyclical" in s or "auto" in s: return "Automobiles"
    elif "technology" in s: return "Technology & IT"
    elif "basic materials" in s: return "Metals & Materials"
    else: return "Other"

# ---------------------------------------------------------
# 3. SIDEBAR NAVIGATION
# ---------------------------------------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to:", ["📈 Stock Screener", "🏢 Sector Analysis", "🪙 Commodity Dashboard", "📁 My Portfolio"])

@st.cache_data(ttl=3600)
def get_data():
    engine = ScoringEngine()
    df = engine.rank_all()
    engine.close()
    
    # Apply the custom mapping (row by row so it can read the Symbol)
    df["Indian_Sector"] = df.apply(map_indian_sector, axis=1)
    df["Verdict"] = df["Master_Score"].apply(get_verdict)
    return df

try:
    df = get_data()
except Exception as e:
    st.error(f"⚠️ Error loading database: {e}")
    st.stop()

# =========================================================
# PAGE 1: STOCK SCREENER
# =========================================================
if page == "📈 Stock Screener":
    st.sidebar.markdown("---")
    st.sidebar.header("🎯 Strategy Selection")
    strategy = st.sidebar.radio("Choose Ranking Model:", ["Master Investment Score", "Compounder Rank", "Growth Rank", "Value Rank", "Potential Multibaggers"])

    st.sidebar.header("🔍 Filter Options")
    all_sectors = sorted(df["Indian_Sector"].dropna().unique().tolist())
    selected_sectors = st.sidebar.multiselect("Select Sectors:", options=all_sectors, default=all_sectors)
    min_score = st.sidebar.slider("Minimum Master Score:", min_value=0, max_value=100, value=45, step=5)
    
    all_verdicts = ["🟢 STRONG BUY (Long Term)", "🟡 BUY / HOLD", "🟠 WATCHLIST", "🔴 AVOID"]
    selected_verdicts = st.sidebar.multiselect("Show Verdicts:", options=all_verdicts, default=all_verdicts)

    st.title(f"📈 {strategy}")

    score_col = {"Master Investment Score": "Master_Score", "Compounder Rank": "Compounder_Score", "Growth Rank": "Growth_Score", "Value Rank": "Value_Score", "Potential Multibaggers": "Multibagger_Score"}[strategy]

    display_df = df.copy()
    if selected_sectors: display_df = display_df[display_df["Indian_Sector"].isin(selected_sectors)]
    else: display_df = display_df.iloc[0:0]

    display_df = display_df[display_df["Master_Score"] >= min_score]
    
    if selected_verdicts: display_df = display_df[display_df["Verdict"].isin(selected_verdicts)]
    else: display_df = display_df.iloc[0:0]

    if strategy == "Potential Multibaggers": display_df = display_df[display_df["Multibagger_Score"] > 0]
    display_df = display_df.sort_values(by=score_col, ascending=False)

    if display_df.empty:
        st.warning("⚠️ No stocks match your current filters.")
    else:
        st.dataframe(display_df, use_container_width=True, hide_index=True)

# =========================================================
# PAGE 2: SECTOR ANALYSIS
# =========================================================
elif page == "🏢 Sector Analysis":
    st.title("🏢 Indian Sector Analysis")
    st.markdown("Explore the best long-term stocks grouped by specific Indian market sectors.")

    sectors = sorted(df["Indian_Sector"].unique().tolist())
    selected_sector = st.selectbox("Select a Sector to Analyze:", sectors)
    
    if selected_sector:
        sector_df = df[df["Indian_Sector"] == selected_sector].copy()
        sector_df = sector_df.sort_values(by="Master_Score", ascending=False)
        
        # --- TOP 3 LONG-TERM BUYS SECTION ---
        st.markdown(f"### 🏆 Top 3 Long-Term Buys in {selected_sector}")
        
        top_buys = sector_df[sector_df["Master_Score"] >= 60].head(3)
        
        if top_buys.empty:
            st.warning(f"⚠️ No strong 'Buy' recommendations in {selected_sector} right now. The top stocks in this sector are currently scoring below 60.")
            top_buys = sector_df.head(3)
        else:
            cols = st.columns(3)
            for idx, (_, row) in enumerate(top_buys.iterrows()):
                with cols[idx]:
                    st.metric(
                        label=f"#{idx+1}: {row['Symbol']}",
                        value=f"{row['Master_Score']} / 100",
                        delta=row['Verdict'],
                        delta_color="normal" if row['Master_Score'] >= 60 else "inverse"
                    )
                    st.caption(f"Compounder: {row['Compounder_Score']} | Growth: {row['Growth_Score']}")

        st.markdown("---")
        
        # --- SECTOR OVERVIEW METRICS ---
        st.markdown(f"### 📊 {selected_sector} Overview")
        avg_score = sector_df["Master_Score"].mean()
        total_stocks = len(sector_df)
        
        c1, c2 = st.columns(2)
        c1.metric("Average Sector Score", f"{avg_score:.1f} / 100")
        c2.metric("Total Stocks in Sector", total_stocks)
        
        st.markdown("---")
        
        # --- BAR CHART ---
        st.markdown(f"### 📈 Quality Score of All Stocks in {selected_sector}")
        
        def get_color(score):
            return "🟢 Good (>60)" if score >= 60 else "🔴 Weak (<60)"
            
        sector_df["Color_Status"] = sector_df["Master_Score"].apply(get_color)
        
        fig = px.bar(
            sector_df.head(15),
            x="Symbol", y="Master_Score", color="Color_Status",
            color_discrete_map={"🟢 Good (>60)": "#28a745", "🔴 Weak (<60)": "#dc3545"},
            text="Master_Score", title=f"Top 15 Stocks in {selected_sector}"
        )
        fig.update_layout(yaxis_title="Master Score (0-100)", xaxis_title="Stock Symbol")
        st.plotly_chart(fig, use_container_width=True)

        # --- DETAILED TABLE ---
        st.markdown("### 📋 Full Sector Breakdown")
        st.dataframe(
            sector_df[["Symbol", "Master_Score", "Verdict", "Compounder_Score", "Growth_Score", "Value_Score"]],
            column_config={
                "Master_Score": st.column_config.ProgressColumn("Master Score", format="%f", min_value=0, max_value=100),
            },
            use_container_width=True, hide_index=True
        )

# =========================================================
# PAGE 3: COMMODITY DASHBOARD
# =========================================================
elif page == "🪙 Commodity Dashboard":
    st.title("🪙 Commodity Dashboard")
    st.info("Commodity tracking dashboard")

# =========================================================
# PAGE 4: MY PORTFOLIO (CDSL PARSER)
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

            found_symbols = []
            for symbol in df['Symbol']:
                if re.search(r'\b' + re.escape(symbol) + r'\b', full_text):
                    found_symbols.append(symbol)
            
            if not found_symbols:
                st.warning("⚠️ Could not find any stocks from our database in this PDF.")
            else:
                port_df = df[df['Symbol'].isin(found_symbols)].copy()
                
                st.markdown("### 📊 Portfolio Health Summary")
                avg_score = port_df["Master_Score"].mean()
                good_stocks = len(port_df[port_df["Master_Score"] >= 60])
                bad_stocks = len(port_df[port_df["Master_Score"] < 60])
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Average Portfolio Score", f"{avg_score:.1f} / 100")
                c2.metric("Good Quality Stocks", good_stocks, delta_color="normal")
                c3.metric("Poor Quality Stocks", bad_stocks, delta_color="inverse")

                st.markdown("### 🍩 Sector Allocation")
                sector_counts = port_df["Indian_Sector"].value_counts().reset_index()
                sector_counts.columns = ["Sector", "Count"]
                fig_pie = px.pie(sector_counts, names="Sector", values="Count", hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
                fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig_pie, use_container_width=True)

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
                
                st.markdown("### 🔬 Deep Dive: Why did they score this way?")
                detail_df = port_df_sorted[["Symbol", "Indian_Sector", "Master_Score", "Verdict", "Compounder_Score", "Growth_Score", "Value_Score"]].copy()
                st.dataframe(detail_df, use_container_width=True, hide_index=True)

                with st.expander("View Raw Financial Data (ROE, PE, Debt, etc.)"):
                    conn = sqlite3.connect(DB_PATH)
                    placeholders = ','.join('?' * len(found_symbols))
                    raw_query = f"SELECT symbol AS Symbol, roe, roce, debt_to_equity, pe, pb FROM fundamentals WHERE symbol IN ({placeholders})"
                    raw_data = pd.read_sql(raw_query, conn, params=found_symbols)
                    conn.close()

                    if not raw_data.empty:
                        raw_data["roe"] = raw_data["roe"].apply(lambda x: f"{x*100:.1f}%" if pd.notnull(x) else "N/A")
                        raw_data["roce"] = raw_data["roce"].apply(lambda x: f"{x*100:.1f}%" if pd.notnull(x) else "N/A")
                        st.dataframe(raw_data, use_container_width=True, hide_index=True)

        except Exception as e:
            st.error("❌ Failed to read PDF. Check password.")
            st.info(f"Error: {e}")
    elif uploaded_file is not None and not password:
        st.warning("⚠️ Please enter the PDF password.")
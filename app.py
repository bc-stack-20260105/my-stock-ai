import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np

# --- 1. 頁面基礎設定 ---
st.set_page_config(page_title="AI 股票決策系統 V2", layout="wide")

# --- 2. 核心計算邏輯 ---
def calculate_advanced_data(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    close_price = df['Close']
    
    # 技術指標
    df['SMA_5'] = close_price.rolling(window=5).mean()
    df['SMA_20'] = close_price.rolling(window=20).mean()
    
    delta = close_price.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI_14'] = 100 - (100 / (1 + (gain / loss)))
    
    # AI 壓力與支撐 (60日)
    df['Support'] = close_price.rolling(window=60).min()
    df['Resistance'] = close_price.rolling(window=60).max()
    
    # ATR (簡單波動率) 用於計算停損
    high_low = df['High'] - df['Low']
    df['ATR'] = high_low.rolling(window=14).mean()
    
    return df

# --- 3. 側邊欄：推薦與控制 ---
st.sidebar.header("🔍 市場掃描儀")

# A. 推薦名單區塊
st.sidebar.subheader("🔥 熱門推薦觀察")
recommend_list = {
    "美股龍頭": ["AAPL", "NVDA", "TSLA", "MSFT", "GOOGL", "AMZN"],
    "台股精選": ["2330.TW", "2454.TW", "2317.TW", "2308.TW", "2382.TW"],
    "ETF 參考": ["VOO", "QQQ", "0050.TW", "0056.TW"]
}

category = st.sidebar.selectbox("選擇推薦類別", list(recommend_list.keys()))
rec_stock = st.sidebar.radio("推薦清單 (點擊即分析)", recommend_list[category])

st.sidebar.divider()

# B. 自選管理區塊
st.sidebar.subheader("📝 自定義查詢")
manual_input = st.sidebar.text_input("輸入股票代碼:").upper()

# 最終分析目標決策邏輯
if manual_input:
    target_stock = manual_input
else:
    target_stock = rec_stock

time_range = st.sidebar.selectbox("分析週期", ("6mo", "1y", "2y"), index=0)

# --- 4. 主程式邏輯 ---
try:
    data = yf.download(target_stock, period=time_range)
    
    if data.empty:
        st.error(f"無法獲取 {target_stock} 的資料。")
    else:
        df = calculate_advanced_data(data)
        ticker_info = yf.Ticker(target_stock).info
        
        last_p = float(df['Close'].iloc[-1])
        rsi_now = float(df['RSI_14'].iloc[-1])
        support_p = float(df['Support'].iloc[-1])
        resist_p = float(df['Resistance'].iloc[-1])
        atr_now = float(df['ATR'].iloc[-1])
        pe = ticker_info.get('trailingPE')

        st.title(f"🚀 {ticker_info.get('longName', target_stock)} AI 深度分析")

        # 面板 A: 核心指標
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("當前股價", f"${last_p:.2f}")
        c2.metric("AI 支撐位", f"${support_p:.2f}")
        c3.metric("AI 壓力位", f"${resist_p:.2f}")
        c4.metric("本益比 (PE)", f"{pe:.2f}" if pe else "N/A")

        st.divider()

        # 面板 B: 技術圖表
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_width=[0.3, 0.7])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_hline(y=resist_p, line_dash="dash", line_color="red", annotation_text="壓力", row=1, col=1)
        fig.add_hline(y=support_p, line_dash="dash", line_color="green", annotation_text="支撐", row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI_14'], name="RSI", line=dict(color='purple')), row=2, col=1)
        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # 面板 C: AI 停損與決策
        st.subheader("🤖 AI 風險控管與建議")
        col_eval, col_risk = st.columns(2)

        with col_eval:
            st.markdown("### 📊 綜合評分")
            score = 0
            if last_p > float(df['SMA_20'].iloc[-1]): score += 50
            if 30 < rsi_now < 40: score += 50
            
            st.write(f"**AI 投資信心分數：{score} / 100**")
            if score >= 70: st.success("🎯 建議佈局")
            elif score >= 50: st.warning("⚖️ 中性看待")
            else: st.error("🚨 風險偏高")

        with col_risk:
            st.markdown("### 🛡️ 風險防禦線 (基於 ATR 波動率)")
            # 停損建議：目前價格 - 2倍 ATR
            stop_loss = last_p - (atr_now * 2)
            st.write(f"**建議保守停損位：${stop_loss:.2f}**")
            st.caption("註：停損位是根據過去14天平均波動幅度(ATR)計算，適合短中線防守。")

except Exception as e:
    st.error(f"系統錯誤: {e}")
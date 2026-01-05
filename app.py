import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# --- 1. 頁面基礎設定 ---
st.set_page_config(page_title="Stock AI System", layout="wide")

# --- 2. 初始化狀態 ---
if 'history' not in st.session_state:
    st.session_state.history = ["2330.TW"]

if 'current_stock' not in st.session_state:
    st.session_state.current_stock = "2330.TW"

# --- 3. 定義回呼函數 (解決按鈕卡住) ---
def select_stock(ticker):
    st.session_state.current_stock = ticker
    st.session_state.ticker_input = "" 

# --- 4. 核心計算邏輯 ---
def calculate_advanced_data(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    close_price = df['Close']
    df['SMA_20'] = close_price.rolling(window=20).mean()
    delta = close_price.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI_14'] = 100 - (100 / (1 + (gain / loss)))
    df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()
    return df

# --- 5. 側邊欄：控制中心 ---
st.sidebar.header("🔍 控制中心")
manual_input = st.sidebar.text_input("輸入股票代碼 (例: NVDA, AAPL):", key="ticker_input").upper()

# 這裡更新為您要求的週期選項
time_range = st.sidebar.selectbox(
    "分析週期", 
    ("1d", "3d", "1w", "1mo", "3mo", "6mo", "1y", "2y", "5y"), 
    index=4 # 預設顯示 3mo
)

if manual_input and manual_input != st.session_state.current_stock:
    st.session_state.current_stock = manual_input
    if manual_input in st.session_state.history:
        st.session_state.history.remove(manual_input)
    st.session_state.history.insert(0, manual_input)
    st.session_state.history = st.session_state.history[:10]

st.sidebar.divider()

if st.session_state.history:
    st.sidebar.subheader("🕒 最近查詢紀錄")
    for idx, item in enumerate(st.session_state.history):
        col_name, col_del = st.sidebar.columns([4, 1])
        col_name.button(f"📈 {item}", key=f"hist_{item}_{idx}", on_click=select_stock, args=(item,))
        if col_del.button("❌", key=f"del_{item}_{idx}"):
            st.session_state.history.remove(item)
            if item == st.session_state.current_stock:
                st.session_state.current_stock = st.session_state.history[0] if st.session_state.history else "2330.TW"
            st.rerun()

target_stock = st.session_state.current_stock

# --- 6. 數據抓取 (根據週期自動切換解析度) ---
@st.cache_data(ttl=60) # 短週期快取縮短至 1 分鐘
def fetch_data(ticker, period):
    # 根據選定的週期自動決定數據間隔，確保短週期 K 線不留白
    interval_map = {
        "1d": "1m",   # 一天看 1 分鐘線
        "3d": "5m",   # 三天看 5 分鐘線
        "1w": "30m",  # 一週看 30 分鐘線
        "1mo": "1d",
        "3mo": "1d",
        "6mo": "1d",
        "1y": "1d",
        "2y": "1d",
        "5y": "1d"
    }
    return yf.download(ticker, period=period, interval=interval_map.get(period, "1d"), progress=False)

# --- 7. 主程式顯示邏輯 ---
try:
    data = fetch_data(target_stock, time_range)
    if data.empty:
        st.warning(f"目前無法取得 {target_stock} 數據，請檢查代碼或稍後再試。")
    else:
        df = calculate_advanced_data(data)
        ticker_info = yf.Ticker(target_stock).info
        display_name = ticker_info.get('longName') or ticker_info.get('shortName') or target_stock
        
        last_p = float(df['Close'].iloc[-1])
        rsi_now = float(df['RSI_14'].iloc[-1])
        atr_now = float(df['ATR'].iloc[-1])
        sma_20_now = float(df['SMA_20'].iloc[-1])
        
        st.title(f"📊 {display_name} ({time_range}) 分析報告")

        # 頂部數據看板
        c1, c2, c3 = st.columns(3)
        c1.metric("當前價格", f"${last_p:.2f}")
        c2.metric("RSI (14)", f"{rsi_now:.2f}")
        c3.metric("建議停損位", f"${(last_p - atr_now*2):.2f}")

        # K 線圖與指標
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_width=[0.3, 0.7])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name="20MA", line=dict(color='cyan')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI_14'], name="RSI指標", line=dict(color='purple')), row=2, col=1)
        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # --- AI 建議與警告區 ---
        st.subheader("🤖 AI 投資建議與警告")
        if last_p < sma_20_now:
            if rsi_now < 30:
                st.success(f"🎯 **抄底訊號**：目前股價在 20MA 下方且 RSI ({rsi_now:.1f}) 嚴重超跌，反彈機率高。")
            else:
                st.warning(f"⚠️ **空頭警訊**：股價在 20MA 下方但 RSI 尚未超跌，不建議在此買入。")
        else:
            if rsi_now > 70:
                st.error(f"🚨 **追高警告**：股價在 20MA 上方且 RSI ({rsi_now:.1f}) 已過熱，防範回檔。")
            else:
                st.info("⚖️ **趨勢穩健**：股價站穩 20MA 且指標中性，適合續抱。")

        # --- 監控節奏建議 ---
        st.divider()
        st.subheader("📅 投資監控節奏建議")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info("🕒 **一週一次 (週末)**")
            st.markdown("* **週期**：選 **1y** 或 **5y**。\n* **重點**：確認長線大趨勢，20MA 是否持續向上。")
        with col2:
            st.info("📅 **三天一次**")
            st.markdown("* **週期**：選 **3mo** 或 **3d**。\n* **重點**：觀察 RSI 是否開始在超賣/超買區反轉。")
        with col3:
            st.info("🔔 **一天一次 (收盤後)**")
            st.markdown(f"* **週期**：選 **1mo** 或 **1d**。\n* **重點**：檢查股價是否跌破 **${(last_p - atr_now*2):.2f}**。")

        # --- 診斷教室 ---
        st.divider()
        st.subheader("💡 指標診斷教室：20MA 下方可以買嗎？")
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.markdown("""
            #### ❌ 為什麼「只看 20MA 下方」就買很危險？
            * **趨勢向下**：20MA 下方代表空頭慣性，買入容易「接掉下來的刀子」。
            * **慣性壓制**：20MA 是月線成本，彈回 20MA 往往會有解套壓力。
            """)
        with col_t2:
            st.markdown("""
            #### ✅ 什麼時候才是正確的買點？
            * **組合拳判斷**：股價在 20MA 下方 **且** RSI 跌破 30 (超跌)。
            * **最強買點**：等待股價重新 **「帶量站回 20MA」**，代表趨勢確立。
            """)

        # --- SOP 指南 ---
        with st.expander("📝 系統核心操作指南 (SOP)"):
            st.markdown(f"""
            1. **確認大趨勢**：先看 **1y**，確認股價與 20MA 的關係。
            2. **尋找買賣點**：看 **3mo/1mo**。RSI < 30 找反彈；RSI > 70 防回檔。
            3. **短線精研**：點選左側 **1d/3d** 觀看當前精細走勢。
            4. **嚴格停損**：跌破建議位階必須離場。
            """)

except Exception as e:
    st.error("⚠️ 數據請求過於頻繁，請等待 1 分鐘後重新整理頁面。")

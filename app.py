import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd

# --- 1. 頁面基礎設定 ---
st.set_page_config(page_title="Stock AI Pro System", layout="wide")

# --- 2. 持久化自選清單與狀態管理 ---
# 使用 Session State 儲存清單，確保在當前工作階段中可增刪
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = ["2330.TW", "NVDA", "AAPL", "8358.TWO"]

if 'current_stock' not in st.session_state:
    st.session_state.current_stock = "2330.TW"

# 定義功能函數
def select_stock(ticker):
    st.session_state.current_stock = ticker
    st.session_state.ticker_input = "" 

def add_to_watchlist(ticker):
    ticker = ticker.upper().strip()
    if ticker and ticker not in st.session_state.watchlist:
        st.session_state.watchlist.insert(0, ticker)
        st.success(f"✅ 已加入清單: {ticker}")
    elif ticker in st.session_state.watchlist:
        st.info("💡 該股票已在清單中")

def remove_from_watchlist(ticker):
    if ticker in st.session_state.watchlist:
        st.session_state.watchlist.remove(ticker)
        if st.session_state.current_stock == ticker:
            st.session_state.current_stock = st.session_state.watchlist[0] if st.session_state.watchlist else ""
        st.rerun()

# --- 3. 側邊欄：自選管理中心 ---
st.sidebar.header("⭐ 我的自選清單")

# 新增股票功能
new_stock = st.sidebar.text_input("➕ 新增代碼 (如: TSLA):", key="ticker_input").upper()
if st.sidebar.button("確認新增"):
    add_to_watchlist(new_stock)

st.sidebar.divider()

# 顯示自選清單與切換按鈕
if st.session_state.watchlist:
    for ticker in st.session_state.watchlist:
        col_btn, col_del = st.sidebar.columns([4, 1])
        col_btn.button(f"📊 {ticker}", key=f"sel_{ticker}", on_click=select_stock, args=(ticker,), use_container_width=True)
        if col_del.button("🗑️", key=f"del_{ticker}"):
            remove_from_watchlist(ticker)
else:
    st.sidebar.write("清單空空的，快新增股票吧！")

st.sidebar.divider()

# 分析週期選單 (包含 1d, 3d, 1w)
time_range = st.sidebar.selectbox(
    "分析週期", 
    ("1d", "3d", "1w", "1mo", "3mo", "6mo", "1y", "2y", "5y"), 
    index=4
)

# --- 4. 數據抓取與核心計算 (加強快取防封鎖) ---
@st.cache_data(ttl=600)
def fetch_data(ticker, period):
    inv_map = {"1d":"1m", "3d":"5m", "1w":"30m"}
    return yf.download(ticker, period=period, interval=inv_map.get(period, "1d"), progress=False)

def calculate_all(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    # 20MA
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    # RSI 14
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    df['RSI_14'] = 100 - (100 / (1 + (gain / loss)))
    # ATR (停損位)
    df['ATR'] = (df['High'] - df['Low']).rolling(window=14).mean()
    return df

# --- 5. 主畫面渲染 ---
target = st.session_state.current_stock

if not target:
    st.info("👈 請先在左側清單中新增或選擇股票。")
else:
    try:
        raw_data = fetch_data(target, time_range)
        if raw_data.empty:
            st.warning("⚠️ 數據請求過於頻繁或代碼有誤。請靜置 3 分鐘後重試。")
        else:
            df = calculate_all(raw_data)
            last_p = float(df['Close'].iloc[-1])
            rsi_now = float(df['RSI_14'].iloc[-1])
            sma_20 = float(df['SMA_20'].iloc[-1])
            atr_v = float(df['ATR'].iloc[-1])
            stop_loss = last_p - (atr_v * 2)

            st.title(f"🚀 {target} 深度 AI 分析報告")

            # 頂部看板
            c1, c2, c3 = st.columns(3)
            c1.metric("當前價格", f"${last_p:.2f}")
            c2.metric("RSI (14)", f"{rsi_now:.2f}")
            c3.metric("建議停損位", f"${stop_loss:.2f}")

            # K線圖
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_width=[0.3, 0.7])
            fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name="20MA", line=dict(color='cyan')), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df['RSI_14'], name="RSI", line=dict(color='purple')), row=2, col=1)
            fig.update_layout(height=550, template="plotly_dark", xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # --- 之前要求的建議與分析內容 (全部回歸) ---
            st.divider()
            st.subheader("🤖 AI 投資建議與診斷")
            if last_p < sma_20:
                if rsi_now < 30:
                    st.success(f"🎯 **抄底訊號**：股價在 20MA 下方且 RSI ({rsi_now:.1f}) 嚴重超跌，反彈機率高。")
                else:
                    st.warning(f"⚠️ **空頭警訊**：股價在 20MA 下方但 RSI 尚未超跌，不建議在此買入。")
            else:
                if rsi_now > 70:
                    st.error(f"🚨 **追高警告**：股價在 20MA 上方且 RSI ({rsi_now:.1f}) 已過熱，防範回檔。")
                else:
                    st.info("⚖️ **趨勢穩健**：股價站穩 20MA 且指標中性，適合續抱。")

            # 監控節奏建議
            st.subheader("📅 投資監控節奏建議")
            k1, k2, k3 = st.columns(3)
            k1.info("**一週一次**：選 1y 週期，確認 20MA 長線趨勢。")
            k2.info("**三天一次**：選 3mo 或 1w 週期，觀察指標轉折。")
            k3.info(f"**一天一次**：檢查是否維持在停損位 **${stop_loss:.2f}** 之上。")

            # 診斷教室
            st.divider()
            st.subheader("💡 指標診斷教室：20MA 下方可以買嗎？")
            col_t1, col_t2 = st.columns(2)
            col_t1.markdown("""
            #### ❌ 為什麼「20MA 下方」危險？
            * **成本壓制**：20MA 是月成本，線下代表多數人虧損。
            * **慣性向下**：趨勢未扭轉前，買入易「接掉下來的刀子」。
            """)
            col_t2.markdown("""
            #### ✅ 正確買點在哪裡？
            * **超跌組合**：20MA 下方 + RSI < 30 (短線反彈)。
            * **趨勢反轉**：等待股價重新 **「帶量站回 20MA」**。
            """)

            # SOP 指南
            with st.expander("📝 核心操作指南 (SOP)"):
                st.markdown(f"""
                1. **大趨勢確認**：先看 **1y**，確認 20MA 斜率方向。
                2. **尋找時機**：看 **3mo/1mo** 或您自訂的 **1d/3d** 週期。
                3. **嚴守紀律**：跌破建議停損位 **${stop_loss:.2f}** 必須果斷減碼。
                """)

    except Exception as e:
        st.error("⚠️ 系統請求過於頻繁，請點擊右上方選單 Reboot 或靜置 3 分鐘。")


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

# --- 3. 核心計算邏輯 ---
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

# --- 4. 側邊欄：輸入與紀錄 ---
st.sidebar.header("🔍 控制中心")

manual_input = st.sidebar.text_input("輸入股票代碼 (例: 2330.TW, NVDA, AAPL):", key="ticker_input").upper()

time_range = st.sidebar.selectbox(
    "分析週期", 
    ("1mo", "3mo", "6mo", "1y", "2y", "5y"), 
    index=2
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
        if col_name.button(f"📈 {item}", key=f"hist_{item}_{idx}"):
            st.session_state.current_stock = item
            st.rerun()
        if col_del.button("❌", key=f"del_{item}_{idx}"):
            st.session_state.history.remove(item)
            if item == st.session_state.current_stock:
                st.session_state.current_stock = st.session_state.history[0] if st.session_state.history else "2330.TW"
            st.rerun()

target_stock = st.session_state.current_stock

# --- 5. 主程式邏輯 ---
try:
    data = yf.download(target_stock, period=time_range)
    
    if data.empty:
        st.warning("請確保輸入正確的股票代碼。")
    else:
        df = calculate_advanced_data(data)
        ticker_info = yf.Ticker(target_stock).info
        display_name = ticker_info.get('longName') or ticker_info.get('shortName') or target_stock
        
        last_p = float(df['Close'].iloc[-1])
        rsi_now = float(df['RSI_14'].iloc[-1])
        atr_now = float(df['ATR'].iloc[-1])
        sma_20_now = float(df['SMA_20'].iloc[-1])
        
        st.title(f"📊 {display_name} ({time_range}) 分析報告")

        # Dashboard
        c1, c2, c3 = st.columns(3)
        c1.metric("當前股價", f"${last_p:.2f}")
        c2.metric("RSI (14)", f"{rsi_now:.2f}")
        c3.metric("建議停損位", f"${(last_p - atr_now*2):.2f}")

        # Chart
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1, row_width=[0.3, 0.7])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="K線"), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], name="20MA", line=dict(color='cyan')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI_14'], name="RSI指標", line=dict(color='purple')), row=2, col=1)
        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, width="stretch")

        # --- AI 建議與操作警告 ---
        st.subheader("🤖 AI 投資建議與警告")
        
        # 邏輯診斷
        if last_p < sma_20_now:
            if rsi_now < 30:
                st.success(f"🎯 **抄底訊號**：目前股價在 20MA 下方且 RSI ({rsi_now:.1f}) 嚴重超跌，反彈機率高，可分批布局。")
            else:
                st.warning(f"⚠️ **空頭警訊**：股價在 20MA 下方但 RSI 尚未過熱。這通常是空頭趨勢，**不建議在此買入**，除非 RSI 跌破 30。")
        else:
            if rsi_now > 70:
                st.error(f"🚨 **追高警告**：股價在 20MA 上方但 RSI ({rsi_now:.1f}) 已過熱，隨時可能回測 20MA，請勿在此追買。")
            else:
                st.info("⚖️ **趨勢穩健**：股價站穩 20MA 且指標中性，適合續抱或等待回測 20MA 支撐。")

        # --- 操作注意區 ---
        st.divider()
        st.subheader("💡 指標診斷教室：20MA 下方可以買嗎？")
        
        col_teach1, col_teach2 = st.columns(2)
        with col_teach1:
            st.markdown("""
            #### ❌ 為什麼「只看 20MA 下方」就買很危險？
            * **趨勢向下**：20MA 下方代表空頭慣性，若 20MA 線條斜率向下，買入容易「接掉下來的刀子」。
            * **慣性壓制**：20MA 是月線成本，跌破代表近一個月買的人都賠錢，股價彈回 20MA 往往會有解套壓力。
            """)
        with col_teach2:
            st.markdown("""
            #### ✅ 什麼時候才是正確的買點？
            * **組合拳判斷**：股價在 20MA 下方 **且** RSI 跌破 30 (超跌)。
            * **乖離過大**：當股價遠離 20MA 時，會產生引力彈回 20MA。
            * **最強買點**：等待股價重新 **「帶量站回 20MA」**，這才是空轉多的趨勢確立。
            """)

        # --- 操作說明區 (Expander) ---
        with st.expander("📝 系統核心操作指南 (SOP)"):
            st.markdown(f"""
            1. **確認大趨勢**：先看 **1y**，確認 20MA 方向。
            2. **尋找買賣點**：看 **3mo/1mo**，RSI < 30 買進，RSI > 70 賣出。
            3. **防護網設定**：若跌破 **${(last_p - atr_now*2):.2f}**，必須嚴格執行停損。
            """)

except Exception as e:
    st.info("請輸入正確的代碼以獲取 AI 分析資料。")


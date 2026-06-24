import streamlit as st
import yfinance as yf
import pandas as pd
import datetime

# 1. 页面基本配置
st.set_page_config(page_title="全球宏观与资产监测工具", layout="wide")
st.title("📊 全球宏观数据实时监测仪表盘")
st.caption("聚焦核心资产与全球指数，支持后续自主扩展")

# 2. 侧边栏：时间范围选择
st.sidebar.header("⚙️ 监测设置")
days_to_lookback = st.sidebar.slider("查看历史趋势天数", min_value=7, max_value=365, value=90)
start_date = (datetime.date.today() - datetime.timedelta(days=days_to_lookback)).strftime('%Y-%m-%d')
end_date = datetime.date.today().strftime('%Y-%m-%d')

# 3. 数据抓取核心逻辑
@st.cache_data(ttl=300) 
def load_data(tickers, start, end):
    data = yf.download(list(tickers.values()), start=start, end=end, threads=False)
    
    if len(tickers) == 1:
        df = pd.DataFrame(data['Close'])
        df.columns = list(tickers.keys())
    else:
        df = data['Close']
        inv_tickers = {v: k for k, v in tickers.items()}
        df = df.rename(columns=inv_tickers)
    return df

# 4. 定义当前监测的指标
MONITOR_TICKERS = {
    # --- 宏观风向标 ---
    "美元指数 (DXY)": "DX-Y.NYB",
    "美债十年期收益率": "^TNX", 
    "通胀保值美债 (TIP)": "TIP",          
    
    # --- 贵金属 ---
    "现货黄金 (XAU/USD)": "XAUUSD=X",
    "现货白银 (XAG/USD)": "XAGUSD=X",
    
    # --- 美股市场 ---
    "纳斯达克综合指数": "^IXIC",
    
    # --- 东亚核心市场 ---
    "上证综合指数 (中国)": "000001.SS",
    "恒生指数 (香港)": "^HSI",
    "日经225指数 (日本)": "^N225",
    "KOSPI指数 (韩国)": "^KS11",
    "台湾加权指数 (台湾)": "^TWII"
}

try:
    with st.spinner("正在获取全球最新市场数据..."):
        df_data = load_data(MONITOR_TICKERS, start_date, end_date)
    
    # 5. 顶部实时卡片展示
    st.subheader("🎯 核心资产今日动态")
    
    metrics_per_row = 4
    cols = st.columns(metrics_per_row)
    
    for i, col_name in enumerate(MONITOR_TICKERS.keys()):
        col = cols[i % metrics_per_row]
        
        if col_name in df_data.columns:
            series = df_data[col_name].dropna()
            
            if len(series) >= 2:
                current_val = series.iloc[-1]
                prev_val = series.iloc[-2]
                delta_val = current_val - prev_val
                delta_pct = (delta_val / prev_val) * 100
                
                col.metric(
                    label=col_name, 
                    value=f"{current_val:.2f}", 
                    delta=f"{delta_val:+.2f} ({delta_pct:+.2f}%)",
                    delta_color="normal" 
                )
            elif len(series) == 1:
                col.metric(label=col_name, value=f"{series.iloc[0]:.2f}")
            else:
                col.metric(label=col_name, value="暂无数据", delta="未开盘或无数据")

    st.markdown("---")

    # 6. 趋势图表展示
    st.subheader("📈 历史走势联动分析")
    
    selected_metric = st.selectbox("选择要查看历史趋势的资产：", list(MONITOR_TICKERS.keys()))
    if selected_metric in df_data.columns:
        st.line_chart(df_data[selected_metric])

    # 7. 🆕 新增：黄金反弹信号雷达站 (折叠面板，避免占用过多空间)
    st.markdown("---")
    st.subheader("💡 黄金反弹信号雷达站")
    
    with st.expander("点击展开：如何判断黄金是否到底？三步走判断法", expanded=True): # 默认展开，之后你自己看熟了可以改成 expanded=False
        st.markdown("""
        **黄金的定价逻辑核心：实际利率（美债）+ 美元强弱 + 避险情绪。**
        当你想判断黄金是否要反弹时，请打开上面的趋势图，重点观察以下三个指标的联动：
        
        ### 🟢 强烈看涨信号（顺风局）
        当以下条件**同时**满足时，黄金通常迎来大级别反弹：
        1. **美元指数 (DXY) 持续走弱（折线向下）：** 美元贬值，以美元计价的黄金相对变便宜，引发买盘。
        2. **美债十年期收益率回落（折线向下）：** 意味着市场预期美联储要降息，持有无息黄金的“机会成本”降低。
        3. **通胀保值美债 (TIP) 价格上涨（折线向上）：** TIP 价格和实际利率是反比关系。TIP 涨，说明实际利率在跌，这是黄金最强力的支撑。
        
        ### 🔴 强烈看跌信号（逆风局）
        如果黄金还在死扛，但出现了以下信号，千万别急着抄底：
        * **美元指数 (DXY) 强势突破（折线向上） + 美债收益率飙升（折线向上）。** 这说明市场在交易“美国经济强劲、美联储推迟降息”，黄金面临被机构抛售换取美元资产的极大压力。
        
        ### ⚠️ 震荡与背离（需要警惕）
        * **美元在涨，美债收益率也在涨，但黄金居然没跌（甚至还在涨）？** 这通常意味着爆发了**突发地缘政治危机（如战争）**，避险情绪暂时压过了宏观基本面。这种涨势往往较急，但如果冲突没扩大，后续一旦情绪消退，金价容易出现暴力补跌。
        """)

except Exception as e:
    st.error(f"数据加载失败，请检查网络连接或稍后再试。错误信息: {e}")
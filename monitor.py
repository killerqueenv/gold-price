import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import altair as alt

# 1. 页面基本配置
st.set_page_config(page_title="全球宏观与资产监测工具", layout="wide")
st.title("📊 全球宏观数据实时监测仪表盘")
st.caption("聚焦核心资产与全球指数，已加入国内人民币金价换算")

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

# 4. 抓取池（加入了汇率）
FETCH_TICKERS = {
    "美元指数 (DXY)": "DX-Y.NYB",
    "美债十年期收益率": "^TNX", 
    "通胀保值美债 (TIP)": "TIP",          
    "纽约期金 (美元/盎司)": "GC=F",     
    "纽约期银 (美元/盎司)": "SI=F",   
    "美元兑人民币 (USD/CNY)": "CNY=X",  # 🆕 抓取实时汇率用于计算
    "纳斯达克综合指数": "^IXIC",
    "上证综合指数 (中国)": "000001.SS",
    "恒生指数 (香港)": "^HSI",
    "日经225指数 (日本)": "^N225",
    "台湾加权指数 (台湾)": "^TWII"
}

try:
    with st.spinner("正在获取全球最新市场数据并进行汇率换算..."):
        df_data = load_data(FETCH_TICKERS, start_date, end_date)
        
        # 🆕 核心魔法：自动计算国内人民币金价
        if "纽约期金 (美元/盎司)" in df_data.columns and "美元兑人民币 (USD/CNY)" in df_data.columns:
            # 1盎司 = 31.1035克
            df_data["国内金价预估 (元/克)"] = (df_data["纽约期金 (美元/盎司)"] * df_data["美元兑人民币 (USD/CNY)"]) / 31.1035
            
        # 整理要在页面上展示的指标顺序 (把国内金价放在最前面)
        display_columns = ["国内金价预估 (元/克)"] + list(FETCH_TICKERS.keys())
        # 过滤掉抓取失败的列
        display_columns = [col for col in display_columns if col in df_data.columns]

    
    # 5. 顶部实时卡片展示
    st.subheader("🎯 核心资产今日动态")
    
    metrics_per_row = 4
    cols = st.columns(metrics_per_row)
    
    for i, col_name in enumerate(display_columns):
        col = cols[i % metrics_per_row]
        series = df_data[col_name].dropna()
        
        if len(series) >= 2:
            current_val = series.iloc[-1]
            prev_val = series.iloc[-2]
            delta_val = current_val - prev_val
            delta_pct = (delta_val / prev_val) * 100
            
            # 显示数字
            col.metric(
                label=col_name, 
                value=f"{current_val:.2f}", 
                delta=f"{delta_val:+.2f} ({delta_pct:+.2f}%)",
                delta_color="normal" 
            )
            
            # 绘制迷你趋势图
            spark_df = series.tail(30).reset_index()
            spark_df.columns = ['Date', 'Value']
            line_color = "#ff4b4b" if spark_df['Value'].iloc[-1] >= spark_df['Value'].iloc[0] else "#09ab3b"
            
            spark_chart = alt.Chart(spark_df).mark_line(color=line_color, strokeWidth=2).encode(
                x=alt.X('Date:T', axis=None), 
                y=alt.Y('Value:Q', axis=None, scale=alt.Scale(zero=False)), 
                tooltip=['Date:T', 'Value:Q']
            ).properties(height=60) 
            
            col.altair_chart(spark_chart, use_container_width=True)
            
        elif len(series) == 1:
            col.metric(label=col_name, value=f"{series.iloc[0]:.2f}")
        else:
            col.metric(label=col_name, value="暂无数据", delta="未开盘或无数据")

    st.markdown("---")

    # 6. 主趋势图表展示
    st.subheader("📈 历史走势联动分析")
    
    selected_metric = st.selectbox("选择要查看历史趋势的资产：", display_columns)
    
    chart_df = df_data[[selected_metric]].dropna().reset_index()
    chart_df.columns = ['Date', 'Value']
    
    main_chart = alt.Chart(chart_df).mark_line(color='#1f77b4', strokeWidth=2).encode(
        x=alt.X('Date:T', title='日期'),
        y=alt.Y('Value:Q', title='价格 / 指数点位', scale=alt.Scale(zero=False)), 
        tooltip=[alt.Tooltip('Date:T', title='日期'), alt.Tooltip('Value:Q', title='数值', format='.2f')]
    ).properties(height=400)
    
    st.altair_chart(main_chart, use_container_width=True)

    # 7. 黄金反弹信号雷达站
    st.markdown("---")
    st.subheader("💡 黄金反弹信号雷达站")
    
    with st.expander("点击展开：如何判断黄金是否到底？三步走判断法", expanded=False): 
        st.markdown("""
        **黄金的定价逻辑核心：实际利率（美债）+ 美元强弱 + 避险情绪。**
        当你想判断黄金是否要反弹时，请打开上面的趋势图，重点观察以下三个指标的联动：
        
        ### 🟢 强烈看涨信号（顺风局）
        当以下条件**同时**满足时，黄金通常迎来大级别反弹：
        1. **美元指数 (DXY) 持续走弱（折线向下）：** 美元贬值，引发买盘。
        2. **美债十年期收益率回落（折线向下）：** 意味着市场预期美联储要降息，持有无息黄金的“机会成本”降低。
        3. **通胀保值美债 (TIP) 价格上涨（折线向上）：** TIP 涨，说明实际利率在跌，这是黄金最强力的支撑。
        
        ### 🔴 强烈看跌信号（逆风局）
        * **美元指数强势突破 + 美债收益率飙升。** 这说明市场在交易“美国经济强劲、美联储推迟降息”，黄金面临被机构抛售的极大压力。
        """)

except Exception as e:
    st.error(f"数据加载失败，请检查网络连接或稍后再试。错误信息: {e}")

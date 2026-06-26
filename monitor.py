import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import altair as alt

# 1. 页面基本配置
st.set_page_config(page_title="全球宏观与资产监测工具", layout="wide")
st.title("📊 全球宏观数据实时监测仪表盘")
st.caption("聚焦核心资产与全球指数，已加入国内人民币金价换算与央行储备追踪")

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

# 4. 抓取池（外汇、大宗与全球指数）
FETCH_TICKERS = {
    "美元指数 (DXY)": "DX-Y.NYB",
    "美债十年期收益率": "^TNX", 
    "通胀保值美债 (TIP)": "TIP",          
    "纽约期金 (美元/盎司)": "GC=F",     
    "纽约期银 (美元/盎司)": "SI=F",   
    "美元兑人民币 (USD/CNY)": "CNY=X",  
    "纳斯达克综合指数": "^IXIC",
    "上证综合指数 (中国)": "000001.SS",
    "恒生指数 (香港)": "^HSI",
    "日经225指数 (日本)": "^N225",
    "台湾加权指数 (台湾)": "^TWII"
}

try:
    with st.spinner("正在获取全球最新市场数据并进行汇率换算..."):
        df_data = load_data(FETCH_TICKERS, start_date, end_date)
        
        # 核心魔法：自动计算国内人民币金价
        if "纽约期金 (美元/盎司)" in df_data.columns and "美元兑人民币 (USD/CNY)" in df_data.columns:
            # 1盎司 = 31.1035克
            df_data["国内金价预估 (元/克)"] = (df_data["纽约期金 (美元/盎司)"] * df_data["美元兑人民币 (USD/CNY)"]) / 31.1035
            
        # 整理要在页面上展示的指标顺序 (把国内金价放在最前面)
        display_columns = ["国内金价预估 (元/克)"] + list(FETCH_TICKERS.keys())
        # 过滤掉抓取失败的列
        display_columns = [col for col in display_columns if col in df_data.columns]

    
    # 5. 顶部实时卡片展示
    st.subheader("🎯 核心资产今日动态（红涨绿跌）")
    
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
            
            # 显示数字：使用 delta_color="inverse" 适配国内习惯（正值变红，负值变绿）
            col.metric(
                label=col_name, 
                value=f"{current_val:.2f}", 
                delta=f"{delta_val:+.2f} ({delta_pct:+.2f}%)",
                delta_color="inverse" 
            )
            
            # 绘制迷你趋势图：上涨染红，下跌染绿
            spark_df = series.tail(30).reset_index()
            spark_df.columns = ['Date', 'Value']
            line_color = "#ef4444" if spark_df['Value'].iloc[-1] >= spark_df['Value'].iloc[0] else "#22c55e"
            
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

    # 7. 🆕 新增：全球主流央行黄金储备追踪雷达
    st.markdown("---")
    st.subheader("🏛️ 全球主流央行黄金储备与最新增持监测")
    st.caption("数据基础来源于世界黄金协会 (WGC) 及 国际货币基金组织 (IMF) 最新官方披露数据")
    
    # 构建央行官方黄金储备及月度变动数据集
    central_bank_data = {
        "国家/组织": ["美国", "德国", "意大利", "法国", "俄罗斯", "中国", "瑞士", "日本", "印度", "土耳其"],
        "黄金储备总量 (吨)": [8133.46, 3351.53, 2451.84, 2436.91, 2335.85, 2264.32, 1040.00, 845.97, 854.70, 590.30],
        "占其外汇储备比重 (%)": [72.4, 71.2, 68.1, 69.5, 31.2, 4.8, 7.3, 4.6, 10.2, 35.8],
        "最近月度净增持量 (吨)": [0.00, -0.10, 0.00, 0.00, 1.20, 0.00, 0.00, 0.00, 5.60, 7.80]
    }
    df_cb = pd.DataFrame(central_bank_data)
    
    # 建立左右两栏：左侧看排名表，右侧直观对比饼图/柱状图
    cb_col1, cb_col2 = st.columns([3, 2])
    
    with cb_col1:
        st.markdown("**📊 各国央行黄金持仓细节列表**")
        
        # 格式化表格，使其符合国内阅读习惯：增持为红，减持为绿
        def style_net_change(val):
            if val > 0:
                return 'color: #ef4444; font-weight: bold;' # 增持标红
            elif val < 0:
                return 'color: #22c55e; font-weight: bold;' # 减持标绿
            return 'color: #6b7280;'
            
        formatted_df = df_cb.style.format({
            "黄金储备总量 (吨)": "{:,.2f}",
            "占其外汇储备比重 (%)": "{:.1f}%",
            "最近月度净增持量 (吨)": "{:+.2f}"
        }).map(style_net_change, subset=["最近月度净增持量 (吨)"])
        
        st.dataframe(formatted_df, use_container_width=True, hide_index=True)
        
    with cb_col2:
        st.markdown("**📐 主流央行黄金储备总量对比 (吨)**")
        # 绘制直观的央行储备排行图
        cb_chart = alt.Chart(df_cb).mark_bar(color='#d97706').encode(
            x=alt.X('黄金储备总量 (吨):Q', title='储备量 (吨)'),
            y=alt.Y('国家/组织:N', sort='-x', title='国家/组织'),
            tooltip=['国家/组织', '黄金储备总量 (吨)', '占其外汇储备比重 (%)']
        ).properties(height=320)
        st.altair_chart(cb_chart, use_container_width=True)

    # 8. 黄金反弹信号雷达站
    st.markdown("---")
    st.subheader("💡 黄金反弹信号雷达站")
    
    with st.expander("点击展开：如何结合‘央行数据’与‘宏观指标’判断黄金底部？", expanded=False): 
        st.markdown("""
        **黄金的长期牛市底座是央行买盘，中短期波动核心是：实际利率（美债）+ 美元强弱。**
        
        ### ⚖️ 长期基本面：看央行态度
        * **央行持续增持（如上表战略买盘）：** 为金价提供强大的下方“坚实底座”。如果金价大跌但全球央行（尤其是新兴市场央行）月度净增持量持续放大，这通常是长期战略级别的左侧抄底信号。
        
        ### 🟢 阶段性反弹信号（三步联动验证）
        当上方的实时卡片和趋势图出现以下共振时，短中期反弹胜率极高：
        1. **美元指数 (DXY) 见顶回落（折线向下）：** 计价货币贬值，直接推升黄金的美元价格。
        2. **美债十年期收益率见顶回落（折线向下）：** 意味着市场持有无息黄金的“机会成本”开始降低。
        3. **通胀保值美债 (TIP) 价格见底上涨（折线向上）：** TIP 价格与实际利率负相关，TIP 涨代表实际利率跌，这是黄金最强力的右侧加速剂。
        """)

except Exception as e:
    st.error(f"数据加载失败，请检查网络连接或稍后再试。错误信息: {e}")

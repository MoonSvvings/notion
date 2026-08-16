# ==============================================================================
# 노션 임베드용 SCHD & QQQ 실시간 대시보드 (커플링/디커플링 분석 추가)
# ==============================================================================
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 레이아웃 설정
st.set_page_config(page_title="SCHD & QQQ Valuation Dashboard", layout="wide")
st.subheader("SCHD vs QQQ 패밀리 실시간 대시보드 및 상관관계 분석")

# 1. 데이터 로딩 및 캐싱
@st.cache_data(ttl=86400)
def get_market_data():
    tickers = ["SCHD", "QQQ", "QLD", "TQQQ"]
    data = {}
    for t in tickers:
        hist = yf.Ticker(t).history(period="max")
        hist.index = hist.index.tz_localize(None)
        data[t] = hist['Close'] # 주가만 추출
    
    # 병합하여 하나의 데이터프레임으로 구성
    df_close = pd.DataFrame(data).dropna()
    
    # SCHD 배당금 별도 추출
    schd_div = yf.Ticker("SCHD").history(period="max")['Dividends']
    schd_div.index = schd_div.index.tz_localize(None)
    
    return df_close, schd_div

df_close, schd_div = get_market_data()

# 2. SCHD 배당금 분석 (TTM)
df_chart = pd.DataFrame({'Close': df_close['SCHD'], 'Dividends': schd_div})
div_only = df_chart[df_chart['Dividends'] > 0]['Dividends']
df_chart['TTM_Dividends'] = div_only.rolling(window=4).sum()
df_chart['TTM_Dividends'] = df_chart['TTM_Dividends'].ffill()
df_chart['Dividend_Yield'] = (df_chart['TTM_Dividends'] / df_chart['Close']) * 100

df_valid = df_chart.dropna(subset=['TTM_Dividends']).copy()

# 3. 주가 및 배당금 동일 스케일 정규화 (Base=100)
base_price_schd = df_valid['Close'].iloc[0]
df_valid['Norm_Price'] = (df_valid['Close'] / base_price_schd) * 100
df_valid['Norm_Div'] = (df_valid['TTM_Dividends'] / df_valid['TTM_Dividends'].iloc[0]) * 100

for ticker in ["QQQ", "QLD", "TQQQ"]:
    aligned_close = df_close[ticker].reindex(df_valid.index).ffill()
    base_price = aligned_close.dropna().iloc[0]
    df_valid[f'{ticker}_Norm'] = (aligned_close / base_price) * 100

# 4. QQQ vs SCHD 커플링/디커플링 롤링 상관계수 (90일 기준)
# 일일 수익률(Daily Returns) 계산
df_returns = df_close[["SCHD", "QQQ"]].pct_change().dropna()
# 90일 롤링 상관계수 계산 (-1.0 ~ 1.0)
df_valid['Rolling_Corr'] = df_returns['SCHD'].rolling(window=90).corr(df_returns['QQQ'])

# 5. 3단 콤보 차트 렌더링
fig = make_subplots(
    rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.08,
    subplot_titles=(
        '1. 주가 성장률 비교 (SCHD vs QQQ/QLD/TQQQ) 및 SCHD 배당 성장', 
        '2. SCHD 저평가 구간 포착 (배당수익률 밴드)',
        '3. SCHD vs QQQ 디커플링 분석 (90일 롤링 상관계수)'
    ),
    row_heights=[0.5, 0.25, 0.25]
)

# [1단] 주가 및 배당성장 차트
fig.add_trace(go.Scatter(x=df_valid.index, y=df_valid['QQQ_Norm'], name='QQQ (1배수)', line=dict(color='rgba(128, 128, 128, 0.8)', dash='dot')), row=1, col=1)
fig.add_trace(go.Scatter(x=df_valid.index, y=df_valid['QLD_Norm'], name='QLD (2배수)', line=dict(color='rgba(135, 206, 250, 0.8)', dash='dot')), row=1, col=1)
fig.add_trace(go.Scatter(x=df_valid.index, y=df_valid['TQQQ_Norm'], name='TQQQ (3배수)', line=dict(color='rgba(0, 0, 255, 0.7)', dash='dot')), row=1, col=1)
fig.add_trace(go.Scatter(x=df_valid.index, y=df_valid['Norm_Price'], name='SCHD 주가', line=dict(color='#1f77b4', width=2)), row=1, col=1)
fig.add_trace(go.Scatter(x=df_valid.index, y=df_valid['Norm_Div'], name='SCHD 배당금', line=dict(color='#ff7f0e', shape='hv', width=2)), row=1, col=1)

# [2단] 배당수익률 차트
fig.add_trace(go.Scatter(x=df_valid.index, y=df_valid['Dividend_Yield'], name='SCHD 배당수익률(%)', line=dict(color='#2ca02c')), row=2, col=1)
fig.add_hline(y=3.8, line_dash="solid", line_color="red", row=2, col=1)
fig.add_hline(y=4.0, line_dash="solid", line_color="purple", row=2, col=1)

# [3단] 롤링 상관계수 (커플링/디커플링 시각화)
# 상관계수가 양수면 붉은색(커플링), 음수면 푸른색(디커플링)으로 표현하기 위해 채우기(fill) 사용
fig.add_trace(go.Scatter(
    x=df_valid.index, 
    y=df_valid['Rolling_Corr'], 
    name='90일 상관계수', 
    line=dict(color='gray', width=1),
    fill='tozeroy', 
    fillcolor='rgba(128, 128, 128, 0.3)'
), row=3, col=1)

# 기준선(0) 추가: 0 아래로 내려가면 완벽한 디커플링
fig.add_hline(y=0, line_dash="solid", line_color="black", row=3, col=1)

# 레이아웃 및 Y축 스케일 설정
fig.update_yaxes(type="log", title_text="성장 (Log, Base 100)", row=1, col=1)
fig.update_yaxes(title_text="배당수익률 (%)", row=2, col=1)
fig.update_yaxes(title_text="상관계수 (-1 to 1)", range=[-1, 1], row=3, col=1)

fig.update_layout(height=950, hovermode='x unified', template='plotly_white')

# Streamlit 출력
st.plotly_chart(fig, use_container_width=True)

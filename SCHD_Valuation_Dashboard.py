# ==============================================================================
# 노션 임베드용 SCHD & QQQ 패밀리 실시간 대시보드 (Streamlit 버전)
# ==============================================================================
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 노션 화면에 꽉 차게 보이도록 레이아웃 설정
st.set_page_config(page_title="SCHD & QQQ Valuation Dashboard", layout="wide")
st.subheader("SCHD vs QQQ 패밀리 실시간 성장률 대시보드")

# 데이터 로딩 및 캐싱 (하루 단위로만 새로고침하여 로딩 속도 최적화)
@st.cache_data(ttl=86400)
def get_market_data():
    tickers = ["SCHD", "QQQ", "QLD", "TQQQ"]
    data = {}
    for t in tickers:
        hist = yf.Ticker(t).history(period="max")
        hist.index = hist.index.tz_localize(None)
        data[t] = hist
    return data

market_data = get_market_data()

# ---------------------------------------------------------
# 1. SCHD 데이터 전처리 (기준 데이터)
# ---------------------------------------------------------
df_schd = market_data["SCHD"].copy()
df_chart = df_schd[['Close', 'Dividends']].copy()

# 노이즈 없는 1년(TTM) 누적 배당금 및 배당수익률 산출
div_only = df_chart[df_chart['Dividends'] > 0]['Dividends']
df_chart['TTM_Dividends'] = div_only.rolling(window=4).sum()
df_chart['TTM_Dividends'] = df_chart['TTM_Dividends'].ffill()
df_chart['Dividend_Yield'] = (df_chart['TTM_Dividends'] / df_chart['Close']) * 100

# 누적 데이터가 부족한 첫 1년 제외하여 기준(Base) 설정
df_valid = df_chart.dropna(subset=['TTM_Dividends']).copy()

# SCHD 주가 vs 배당금 성장률 동일 스케일 정규화 (Base=100)
df_valid['Norm_Price'] = (df_valid['Close'] / df_valid['Close'].iloc[0]) * 100
df_valid['Norm_Div'] = (df_valid['TTM_Dividends'] / df_valid['TTM_Dividends'].iloc[0]) * 100

# ---------------------------------------------------------
# 2. QQQ, QLD, TQQQ 데이터 전처리 및 정규화
# ---------------------------------------------------------
start_date = df_valid.index[0] # SCHD와 동일한 시점부터 비교 시작

for ticker in ["QQQ", "QLD", "TQQQ"]:
    df_temp = market_data[ticker]['Close']
    
    # SCHD의 거래일(Index)에 맞춰 데이터 정렬 및 결측치 보간
    aligned_close = df_temp.reindex(df_valid.index).ffill()
    
    # SCHD와 동일한 출발선(100)에서 시작하도록 정규화
    base_price = aligned_close.dropna().iloc[0]
    df_valid[f'{ticker}_Norm'] = (aligned_close / base_price) * 100

# ---------------------------------------------------------
# 3. 2단 콤보 차트 렌더링
# ---------------------------------------------------------
fig = make_subplots(
    rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
    subplot_titles=('1. 주가 성장률 비교 (SCHD vs QQQ/QLD/TQQQ) 및 배당 성장', '2. SCHD 저평가 구간 포착 (배당수익률 밴드)'),
    row_heights=[0.6, 0.4]
)

# [상단 차트] QQQ 패밀리 추가 (점선 처리)
fig.add_trace(go.Scatter(x=df_valid.index, y=df_valid['QQQ_Norm'], name='QQQ (1배수)', line=dict(color='rgba(128, 128, 128, 0.8)', dash='dot')), row=1, col=1)
fig.add_trace(go.Scatter(x=df_valid.index, y=df_valid['QLD_Norm'], name='QLD (2배수)', line=dict(color='rgba(135, 206, 250, 0.8)', dash='dot')), row=1, col=1)
fig.add_trace(go.Scatter(x=df_valid.index, y=df_valid['TQQQ_Norm'], name='TQQQ (3배수)', line=dict(color='rgba(0, 0, 255, 0.7)', dash='dot')), row=1, col=1)

# [상단 차트] SCHD 주가 및 배당금 (실선 유지)
fig.add_trace(go.Scatter(x=df_valid.index, y=df_valid['Norm_Price'], name='SCHD 주가', line=dict(color='#1f77b4', width=2)), row=1, col=1)
fig.add_trace(go.Scatter(x=df_valid.index, y=df_valid['Norm_Div'], name='SCHD 배당금', line=dict(color='#ff7f0e', shape='hv', width=2)), row=1, col=1)

# [하단 차트] SCHD 배당수익률
fig.add_trace(go.Scatter(x=df_valid.index, y=df_valid['Dividend_Yield'], name='SCHD 배당수익률(%)', line=dict(color='#2ca02c')), row=2, col=1)

fig.add_hline(y=3.8, line_dash="solid", line_color="red", annotation_text="극저평가 진입 (3.8%)", row=2, col=1)
fig.add_hline(y=4.0, line_dash="solid", line_color="purple", annotation_text="강력 지지선 (4.0%)", row=2, col=1)

# ---------------------------------------------------------
# 4. 레이아웃 및 Y축 스케일 설정
# ---------------------------------------------------------
# 레버리지 종목의 거대한 변동성을 담기 위해 상단 차트 Y축을 로그 스케일로 변경
fig.update_yaxes(type="log", title_text="성장 지수 (Log Scale, Base=100)", row=1, col=1)
fig.update_yaxes(title_text="배당수익률 (%)", row=2, col=1)

fig.update_layout(height=800, hovermode='x unified', template='plotly_white')

# Streamlit에 차트 출력
st.plotly_chart(fig, use_container_width=True)

# ==============================================================================
# 노션 임베드용 SCHD 실시간 대시보드 (Streamlit 버전)
# ==============================================================================
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 노션 화면에 꽉 차게 보이도록 레이아웃 설정
st.set_page_config(page_title="SCHD Valuation Dashboard", layout="wide")
st.subheader("SCHD 실시간 가치평가 대시보드 (노이즈 제거판)")

# 데이터 로딩 및 캐싱 (하루 단위로만 새로고침하여 로딩 속도 최적화)
@st.cache_data(ttl=86400)
def get_schd_data():
    ticker = yf.Ticker("SCHD")
    hist = ticker.history(period="max")
    hist.index = hist.index.tz_localize(None)
    return hist

df = get_schd_data()
df_chart = df[['Close', 'Dividends']].copy()

# 노이즈 없는 1년(TTM) 누적 배당금 및 배당수익률 산출
div_only = df_chart[df_chart['Dividends'] > 0]['Dividends']
df_chart['TTM_Dividends'] = div_only.rolling(window=4).sum()
df_chart['TTM_Dividends'] = df_chart['TTM_Dividends'].ffill()
df_chart['Dividend_Yield'] = (df_chart['TTM_Dividends'] / df_chart['Close']) * 100
df_valid = df_chart.dropna(subset=['TTM_Dividends']).copy()

# 주가 vs 배당금 성장률 동일 스케일 정규화 (Base=100)
df_valid['Norm_Price'] = (df_valid['Close'] / df_valid['Close'].iloc[0]) * 100
df_valid['Norm_Div'] = (df_valid['TTM_Dividends'] / df_valid['TTM_Dividends'].iloc[0]) * 100

# 2단 콤보 차트 렌더링
fig = make_subplots(
    rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.1,
    subplot_titles=('1. 가격과 가치의 괴리 (주가 vs 배당금 성장)', '2. 저평가 구간 포착 (배당수익률 밴드)'),
    row_heights=[0.5, 0.5]
)

fig.add_trace(go.Scatter(x=df_valid.index, y=df_valid['Norm_Price'], name='주가', line=dict(color='#1f77b4')), row=1, col=1)
fig.add_trace(go.Scatter(x=df_valid.index, y=df_valid['Norm_Div'], name='배당금', line=dict(color='#ff7f0e', shape='hv')), row=1, col=1)
fig.add_trace(go.Scatter(x=df_valid.index, y=df_valid['Dividend_Yield'], name='배당수익률(%)', line=dict(color='#2ca02c')), row=2, col=1)

fig.add_hline(y=3.8, line_dash="solid", line_color="red", annotation_text="극저평가 진입 (3.8%)", row=2, col=1)
fig.add_hline(y=4.0, line_dash="solid", line_color="purple", annotation_text="강력 지지선 (4.0%)", row=2, col=1)

fig.update_layout(height=700, hovermode='x unified', template='plotly_white')

# Streamlit에 차트 출력
st.plotly_chart(fig, use_container_width=True)

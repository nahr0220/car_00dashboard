
# ======================================================================================
# app_streamlit_converted.py
# 자동차 이전등록 대시보드 (Streamlit Cloud 안정 버전)
# ======================================================================================

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path
from io import BytesIO

# ======================================================================================
# 1. Page Config
# ======================================================================================
st.set_page_config(
    page_title="자동차 이전등록 대시보드",
    layout="wide"
)

# ======================================================================================
# 2. Paths
# ======================================================================================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# ======================================================================================
# 3. CSS
# ======================================================================================
st.markdown(
    '''
    <style>
    .stApp { max-width: 1320px; margin: 0 auto; }
    .kpi-box {
        background:#F6F8FA;
        padding:18px;
        border-radius:12px;
        text-align:center;
    }
    .graph-box {
        background:#FFFFFF;
        padding:16px;
        border-radius:14px;
        margin-bottom:20px;
        box-shadow:0 2px 8px rgba(0,0,0,0.05);
    }
    .graph-header {
        font-size:18px;
        font-weight:600;
        margin-bottom:8px;
    }
    </style>
    ''',
    unsafe_allow_html=True
)

# ======================================================================================
# 4. Utilities
# ======================================================================================
def fatal(msg: str):
    st.error(msg)
    st.stop()

# ======================================================================================
# 5. Data Loaders (CSV only – Cloud safe)
# ======================================================================================
@st.cache_data(show_spinner=False)
def load_quarter_csv(year: int, quarter: int) -> pd.DataFrame:
    file_path = DATA_DIR / f"output_{year}_{quarter}분기.csv"

    if not file_path.exists():
        fatal(f"❌ 데이터 파일 없음: {file_path.name}")

    df = pd.read_csv(
        file_path,
        encoding="utf-8-sig",
        usecols=[
            "년도","월","이전등록유형",
            "중고차시장","유효시장","마케팅",
            "취득금액_범위","주행거리_범위",
            "나이","성별","시/도","구/군"
        ]
    )

    df["연월번호"] = df["년도"] * 100 + df["월"]
    df["연월라벨"] = (
        df["년도"].astype(str) + "-" + df["월"].astype(str).str.zfill(2)
    )

    return df

@st.cache_data(show_spinner=False)
def load_ap_csv() -> pd.DataFrame:
    ap_path = DATA_DIR / "AP_Sales_Summary.csv"
    if not ap_path.exists():
        fatal("❌ AP_Sales_Summary.csv 파일이 없습니다.")

    df_ap = pd.read_csv(ap_path)
    df_ap = df_ap[df_ap["년도"] >= 2024].copy()

    df_ap["연월번호"] = df_ap["년도"] * 100 + df_ap["월"]
    df_ap["연월라벨"] = (
        df_ap["년도"].astype(str) + "-" + df_ap["월"].astype(str).str.zfill(2)
    )

    return df_ap

# ======================================================================================
# 6. Header & Filters
# ======================================================================================
st.title("자동차 이전등록 대시보드")

f1, f2, f3 = st.columns([1,1,2])

with f1:
    year = st.selectbox("년도", [2024, 2025], index=0)

with f2:
    quarter = st.selectbox("분기", [1,2,3,4], index=0)

with f3:
    market = st.radio(
        "시장 구분",
        ["전체", "중고차시장", "유효시장", "마케팅"],
        horizontal=True
    )

# ======================================================================================
# 7. Load Data (after user selection)
# ======================================================================================
with st.spinner("데이터 로딩 중..."):
    df = load_quarter_csv(year, quarter)
    df_ap = load_ap_csv()

if market == "중고차시장":
    df = df[df["중고차시장"] == 1]
elif market == "유효시장":
    df = df[df["유효시장"] == 1]
elif market == "마케팅":
    df = df[df["마케팅"] == 1]

st.success(f"✅ {year}년 {quarter}분기 · {market} 데이터 {len(df):,}건")

# ======================================================================================
# 8. KPI
# ======================================================================================
k1, k2, k3 = st.columns(3)

with k1:
    st.markdown(
        f"<div class='kpi-box'>분기 누적 거래량<br><b>{len(df):,}</b></div>",
        unsafe_allow_html=True
    )

with k2:
    latest_month = df["월"].max()
    m_cnt = len(df[df["월"] == latest_month])
    st.markdown(
        f"<div class='kpi-box'>최근 월 거래량<br><b>{m_cnt:,}</b></div>",
        unsafe_allow_html=True
    )

with k3:
    used_ratio = (
        df["중고차시장"].mean() * 100 if len(df) else 0
    )
    st.markdown(
        f"<div class='kpi-box'>중고차 비중<br><b>{used_ratio:.1f}%</b></div>",
        unsafe_allow_html=True
    )

# ======================================================================================
# 9. Graph – 월별 거래 추이
# ======================================================================================
st.markdown("<div class='graph-box'><div class='graph-header'>월별 거래량</div></div>", unsafe_allow_html=True)

monthly = (
    df.groupby("연월라벨")
    .size()
    .reset_index(name="건수")
)

fig_month = px.bar(
    monthly,
    x="연월라벨",
    y="건수",
    text="건수"
)
fig_month.update_traces(texttemplate="%{text:,}", textposition="outside")
fig_month.update_layout(yaxis_tickformat=",d")

st.plotly_chart(fig_month, use_container_width=True)

# ======================================================================================
# 10. Graph – 연령대 분포
# ======================================================================================
st.markdown("<div class='graph-box'><div class='graph-header'>연령대 분포</div></div>", unsafe_allow_html=True)

age_df = df[df["나이"] != "법인및사업자"]
age_cnt = age_df["나이"].value_counts().reset_index()
age_cnt.columns = ["나이", "건수"]

fig_age = px.bar(
    age_cnt,
    x="건수",
    y="나이",
    orientation="h"
)
fig_age.update_layout(yaxis_categoryorder="total ascending")

st.plotly_chart(fig_age, use_container_width=True)

# ======================================================================================
# 11. Graph – AP 월별 추이
# ======================================================================================
st.markdown("<div class='graph-box'><div class='graph-header'>AP 월별 추이</div></div>", unsafe_allow_html=True)

ap_m = pd.merge(
    df_ap,
    df.groupby("연월번호").size().reset_index(name="전체건수"),
    on="연월번호",
    how="left"
)

ap_m["AP비중"] = ap_m["AP"] / ap_m["전체건수"] * 100

fig_ap = go.Figure()
fig_ap.add_bar(
    x=ap_m["연월라벨"],
    y=ap_m["AP"],
    name="AP 판매대수"
)
fig_ap.add_scatter(
    x=ap_m["연월라벨"],
    y=ap_m["AP비중"],
    name="AP 비중",
    yaxis="y2"
)

fig_ap.update_layout(
    yaxis2=dict(
        overlaying="y",
        side="right",
        title="AP 비중(%)"
    )
)

st.plotly_chart(fig_ap, use_container_width=True)

# ======================================================================================
# 12. Download – 요약 CSV
# ======================================================================================
st.markdown("<div class='graph-box'><div class='graph-header'>데이터 다운로드</div></div>", unsafe_allow_html=True)

summary = (
    df.groupby(["연월라벨","이전등록유형"])
    .size()
    .reset_index(name="건수")
)

csv_bytes = summary.to_csv(index=False).encode("utf-8-sig")

st.download_button(
    label="⬇️ 요약 CSV 다운로드",
    data=csv_bytes,
    file_name=f"이전등록_요약_{year}_{quarter}분기_{market}.csv",
    mime="text/csv"
)

# ======================================================================================
# END
# ======================================================================================

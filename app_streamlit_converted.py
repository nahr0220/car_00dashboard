import os
import json
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ------------------------------------------
# 데이터 설정
# ------------------------------------------
df = pd.read_csv('C:/Users/24100801/Desktop/output.csv')  # 원본 경로 그대로

# ================= AP 엑셀 데이터 추가 =================
df_ap = pd.read_excel(
    "C:/Users/24100801/Desktop/AP Sales Summary.xlsx",
    skiprows=1
)
df_ap.columns = ["년도", "월", "AP"]
# ★ 2024년 이후 데이터만 사용
df_ap = df_ap[df_ap["년도"] >= 2024].copy()
df_ap["연월번호"] = df_ap["년도"] * 100 + df_ap["월"]
df_ap["연월라벨"] = (
    df_ap["년도"].astype(str)
    + "-"
    + df_ap["월"].astype(str).str.zfill(2)
)

#--------------------------공통 전처리--------------------------------
# 연월번호: 2024년 3월 → 202403
df["연월번호"] = df["년도"] * 100 + df["월"]

# 연월 라벨: 2024-03
df["연월라벨"] = df["년도"].astype(str) + "-" + df["월"].astype(str).str.zfill(2)

# 연월 드롭다운 옵션
periods_sorted = (
    df[["연월번호", "연월라벨"]]
    .drop_duplicates()
    .sort_values("연월번호")
)
period_options = [
    {"label": r["연월라벨"], "value": int(r["연월번호"])}
    for _, r in periods_sorted.iterrows()
]

# 연월번호 → 연월라벨 매핑 (엑셀 파일명용)
period_to_label = {
    int(r["연월번호"]): r["연월라벨"]
    for _, r in periods_sorted.iterrows()
}

# ---------------- Streamlit 페이지 설정 ----------------
st.set_page_config(
    page_title="자동차 이전등록 대시보드",
    layout="wide",
)

# 전체 배경을 Dash와 최대한 비슷하게 중앙 정렬
st.markdown(
    """
    <style>
    .main {
        background-color: #FFFFFF;
    }
    .stApp {
        background-color: #FFFFFF;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 중앙 정렬된 컨테이너 느낌 주기 위해 max-width 설정
st.markdown(
    """
    <style>
    .block-container {
        max-width: 1400px;
        padding-top: 30px;
        padding-bottom: 30px;
        font-size: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 제목
st.markdown("## 자동차 이전등록 대시보드")

# ================= KPI + 필터 영역 =================

# KPI 박스 스타일을 비슷하게 보여주기 위한 HTML 카드 템플릿
def kpi_box(title, value, extra_html=""):
    return f"""
    <div style="
        flex: 1;
        background: #F8F8F8;
        padding: 22px;
        border-radius: 10px;
        text-align: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        height: 150px;
    ">
        <div style="font-size:20px; margin-bottom:4px;">{title}</div>
        <div style="font-size:34px; font-weight:700; color:#000;">{value}</div>
        {extra_html}
    </div>
    """

def colorize_html(txt, val):
    if val is None:
        return txt
    if val > 0:
        return f'<span style="color:red">{txt}</span>'
    if val < 0:
        return f'<span style="color:blue">{txt}</span>'
    return f'<span style="color:#555">{txt}</span>'

# ---- KPI 계산 (Dash 콜백 로직 그대로) ----
df_kpi = df.copy()
cur_period = int(df_kpi["연월번호"].max())
cur_year = cur_period // 100
cur_month = cur_period % 100

# KPI1: 연도 누적
ytd = df_kpi[(df_kpi["년도"] == cur_year) & (df_kpi["연월번호"] <= cur_period)]
kpi1_title = f"{cur_year}년 누적 이전등록 거래량"
kpi1_value = f"{len(ytd):,}"

# KPI2: 해당 월 거래량 + MoM/YoY
cur_cnt = len(df_kpi[df_kpi["연월번호"] == cur_period])

prev_year, prev_month = cur_year, cur_month - 1
if prev_month == 0:
    prev_month = 12
    prev_year -= 1
prev_period = prev_year * 100 + prev_month
prev_cnt = len(df_kpi[df_kpi["연월번호"] == prev_period])

mom_str = "-"
mom_val = None
if prev_cnt > 0:
    mom_val = (cur_cnt - prev_cnt) / prev_cnt * 100
    mom_str = f"{mom_val:+.1f}% (MoM)"

yoy_period = (cur_year - 1) * 100 + cur_month
yoy_cnt = len(df_kpi[df_kpi["연월번호"] == yoy_period])
yoy_str = "-"
yoy_val = None
if yoy_cnt > 0:
    yoy_val = (cur_cnt - yoy_cnt) / yoy_cnt * 100
    yoy_str = f"{yoy_val:+.1f}% (YoY)"

kpi2_title = f"{cur_month}월 이전등록 거래량"
kpi2_value = f"{cur_cnt:,}"

# KPI3: 중고차 비중
cur_all = cur_cnt
cur_used = len(
    df_kpi[(df_kpi["연월번호"] == cur_period) & (df_kpi["중고차시장"] == 1)]
)
cur_ratio = cur_used / cur_all * 100 if cur_all > 0 else 0

prev_used = len(
    df_kpi[(df_kpi["연월번호"] == prev_period) & (df_kpi["중고차시장"] == 1)]
)
prev_ratio = prev_used / prev_cnt * 100 if prev_cnt > 0 else None

mom_ratio_str = "-"
mom_ratio_val = None
if prev_ratio is not None:
    mom_ratio_val = cur_ratio - prev_ratio
    mom_ratio_str = f"{mom_ratio_val:+.1f}p (MoM)"

kpi3_title = f"{cur_month}월 중고차 비중"
kpi3_value = f"{cur_ratio:.1f}%"

mom_html = colorize_html(mom_str, mom_val)
yoy_html = colorize_html(yoy_str, yoy_val)
mom_ratio_html = colorize_html(mom_ratio_str, mom_ratio_val)

# KPI 3개를 한 줄에 Dash처럼 배치
kpi_html = f"""
<div style="display:flex; gap:20px; margin-bottom:20px;">
    {kpi_box(kpi1_title, kpi1_value)}
    {kpi_box(kpi2_title, kpi2_value, extra_html=f'''
        <div style="
            font-size:16px;
            margin-top:6px;
            display:flex;
            justify-content:center;
            gap:12px;
        ">
            <span>{mom_html}</span>
            <span>|</span>
            <span>{yoy_html}</span>
        </div>
    ''')}
    {kpi_box(kpi3_title, kpi3_value, extra_html=f'''
        <div style="font-size:16px; margin-top:6px;">
            {mom_ratio_html}
        </div>
    ''')}
</div>
"""
st.markdown(kpi_html, unsafe_allow_html=True)

# ================= 필터 + 탭 + 다운로드 박스 =================
st.markdown(
    """
    <div style="
        background:#EDF4FF;
        padding:18px 20px 10px 20px;
        border-radius:12px;
        margin-bottom:25px;
        box-shadow:0 2px 6px rgba(0,0,0,0.05);
    ">
    """,
    unsafe_allow_html=True,
)

# 1) 연월 + 다운로드 한 줄
col_sp1, col_sp2, col_btn = st.columns([1, 1, 0.5])

with col_sp1:
    st.markdown('<div style="font-size:14px;">시작 연월</div>', unsafe_allow_html=True)
    start_period = st.selectbox(
        "",
        options=[p["value"] for p in period_options],
        index=0,
        format_func=lambda v: period_to_label.get(int(v), str(v)),
        label_visibility="collapsed",
    )

with col_sp2:
    st.markdown('<div style="font-size:14px;">종료 연월</div>', unsafe_allow_html=True)
    end_period = st.selectbox(
        "",
        options=[p["value"] for p in period_options],
        index=len(period_options) - 1,
        format_func=lambda v: period_to_label.get(int(v), str(v)),
        label_visibility="collapsed",
    )

with col_btn:
    st.markdown("&nbsp;", unsafe_allow_html=True)
    download_clicked = st.button(
        ".XLSX",
        key="btn-download-excel",
        help="필터 조건에 맞는 피벗 엑셀 다운로드",
    )

# 2) 시장 구분 탭 느낌 (Tabs 대신 라디오 + 상단 border)
st.markdown(
    """
    <div style="border-bottom:2px solid #1E88E5; margin-top:5px; padding-bottom:4px;">
    """,
    unsafe_allow_html=True,
)
tab_cols = st.columns(3)

# Dash tab 스타일과 비슷하게 CSS 흉내
tab_styles = {
    "base": """
        padding:8px 20px;
        border:1px solid #1E88E5;
        border-bottom:none;
        background-color:#FFFFFF;
        color:#1E88E5;
        font-size:14px;
        font-weight:500;
        border-top-left-radius:8px;
        border-top-right-radius:8px;
        margin-right:4px;
        text-align:center;
        cursor:default;
    """,
    "selected": """
        padding:8px 20px;
        border:2px solid #1E88E5;
        border-bottom:none;
        background-color:#1E88E5;
        color:#FFFFFF;
        font-size:14px;
        font-weight:600;
        border-top-left-radius:8px;
        border-top-right-radius:8px;
        margin-right:4px;
        text-align:center;
        cursor:default;
    """,
}

# Streamlit에서 탭 버튼을 그대로 구현하기는 어려워서,
# 선택값은 라디오로 받고, 위에는 선택 상태만 보여주는 형식으로 구현
market = st.radio(
    "시장 구분",
    options=["전체", "중고", "유효"],
    index=0,
    horizontal=True,
    label_visibility="collapsed",
)

with tab_cols[0]:
    st.markdown(
        f'<div style="{tab_styles["selected" if market=="전체" else "base"]}">전체</div>',
        unsafe_allow_html=True,
    )
with tab_cols[1]:
    st.markdown(
        f'<div style="{tab_styles["selected" if market=="중고" else "base"]}">중고차시장</div>',
        unsafe_allow_html=True,
    )
with tab_cols[2]:
    st.markdown(
        f'<div style="{tab_styles["selected" if market=="유효" else "base"]}">유효시장</div>',
        unsafe_allow_html=True,
    )

st.markdown("</div>", unsafe_allow_html=True)  # 필터 박스 닫기

# ================= 데이터 필터링 (그래프/다운로드 공통) =================
if start_period > end_period:
    start_period, end_period = end_period, start_period

df_all = df[(df["연월번호"] >= start_period) & (df["연월번호"] <= end_period)].copy()
if market == "중고":
    df_all = df_all[df_all["중고차시장"] == 1]
elif market == "유효":
    df_all = df_all[df_all["유효시장"] == 1]

# =========================================
# 그래프 1: 월별 이전등록유형 추이
# =========================================
g1 = (
    df_all.groupby(["연월라벨", "이전등록유형"])
    .size()
    .reset_index(name="건수")
)
g_total = (
    df_all.groupby("연월라벨")
    .size()
    .reset_index(name="전체건수")
    .sort_values("연월라벨")
)

fig1 = go.Figure()

# 배경 막대
fig1.add_trace(
    go.Bar(
        x=g_total["연월라벨"],
        y=g_total["전체건수"],
        name="전체 건수",
        marker_color="#86969E",
        opacity=0.65,
        text=g_total["전체건수"],
        textposition="outside",
        texttemplate="%{text:,}",
        cliponaxis=False,
        hovertemplate="전체: %{y:,}건",
    )
)

# 유형별 라인
for t in g1["이전등록유형"].unique():
    d_ = g1[g1["이전등록유형"] == t].sort_values("연월라벨")
    fig1.add_trace(
        go.Scatter(
            x=d_["연월라벨"],
            y=d_["건수"],
            mode="lines+markers",
            name=str(t),
            hovertemplate=f"{t}: " + "%{y:,}건",
            line=dict(width=2),
        )
    )

fig1.update_layout(
    height=450,
    barmode="overlay",
    yaxis=dict(title="AP", tickformat=",d"),
    xaxis=dict(title="연월"),
    margin=dict(l=40, r=20, t=20, b=40),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    font=dict(size=14),
)

# =========================================
# 연령·성별 데이터
# =========================================
df_person = df_all[df_all["나이"] != "법인및사업자"].copy()

age = df_person["나이"].value_counts().reset_index()
age.columns = ["나이", "건수"]
age = age.sort_values("나이", ascending=False)

fig_age = px.bar(
    age,
    x="건수",
    y="나이",
    orientation="h",
)
fig_age.update_xaxes(tickformat=",d", title="건수")
fig_age.update_yaxes(title="나이")
fig_age.update_layout(
    height=320,
    margin=dict(l=60, r=20, t=20, b=40),
    showlegend=False,
    font=dict(size=14),
)

gender = df_person["성별"].value_counts().reset_index()
gender.columns = ["성별", "건수"]

fig_gender = px.pie(
    gender,
    values="건수",
    names="성별",
    hole=0.5,
)
fig_gender.update_layout(
    height=320,
    margin=dict(l=20, r=20, t=20, b=40),
    showlegend=True,
    font=dict(size=14),
)

# =========================================
# 월별 연령대별 추이
# =========================================
age_line = (
    df_person.groupby(["연월라벨", "나이"])
    .size()
    .reset_index(name="건수")
    .sort_values("연월라벨")
)

fig_age_line = px.line(
    age_line,
    x="연월라벨",
    y="건수",
    color="나이",
    markers=True,
)
fig_age_line.update_yaxes(tickformat=",d", title="건수")
fig_age_line.update_xaxes(title="연월")
fig_age_line.update_layout(
    height=380,
    margin=dict(l=40, r=20, t=24, b=40),
    font=dict(size=14),
)

# =========================================
# AP 월별 그래프 (시장 필터 영향 없음)
# =========================================
df_ap_f = df_ap[
    (df_ap["연월번호"] >= start_period)
    & (df_ap["연월번호"] <= end_period)
].sort_values("연월번호")

fig_ap = go.Figure()
fig_ap.add_trace(
    go.Bar(
        x=df_ap_f["연월라벨"],
        y=df_ap_f["AP"],
        name="AP 판매대수",
        text=df_ap_f["AP"],
        texttemplate="%{text:,}",
        textposition="outside",
        marker_color="#1976D2",
        hovertemplate="AP: %{y:,}",
    )
)

# --- AP 비중 계산 (분모: 월별 유효시장 건수) ---
valid_m = (
    df[df["유효시장"] == 1]
    .groupby(["연월번호", "연월라벨"])
    .size()
    .reset_index(name="유효시장건수")
)

df_ap_m = pd.merge(
    df_ap_f,
    valid_m,
    on=["연월번호", "연월라벨"],
    how="left",
)

df_ap_m["AP비중"] = df_ap_m["AP"] / df_ap_m["유효시장건수"] * 100

ap_max = df_ap_m["AP"].max()
ratio_max = df_ap_m["AP비중"].max()
df_ap_m["AP비중_시각화"] = (
    df_ap_m["AP비중"] / ratio_max
) * ap_max * 1.5

fig_ap.add_trace(
    go.Scatter(
        x=df_ap_m["연월라벨"],
        y=df_ap_m["AP비중_시각화"],
        name="AP 비중",
        legendgroup="ap",
        mode="lines+markers+text",
        cliponaxis=False,
        text=df_ap_m["AP비중"].round(2).astype(str) + "%",
        textposition="top center",
        textfont=dict(size=11),
        line=dict(width=3),
        marker=dict(size=8),
        hovertemplate="AP 비중: %{text}",
    )
)

fig_ap.update_layout(
    height=360,
    yaxis=dict(title="AP", tickformat=",d", range=[0, df_ap_m["AP"].max() * 1.8]),
    xaxis=dict(title="연월"),
    margin=dict(l=40, r=20, t=20, b=40),
    font=dict(size=14),
)

# =========================================
# 화면 출력 레이아웃 (Dash와 순서 동일)
# =========================================
# 그래프 박스도 Dash와 비슷하게 배경 박스 적용
st.markdown(
    """
    <div style="background:#EDF4FF; padding:16px; border-radius:10px; margin-bottom:20px;">
      <div style="background:#F8F8F8; padding:16px; border-radius:10px;">
        <h3 style="font-size:20px; margin:0 0 8px 0;">월별 이전등록유형 추이</h3>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.plotly_chart(fig1, use_container_width=True)

st.markdown(
    """
    <div style="background:#EDF4FF; padding:16px; border-radius:10px; margin-bottom:20px;">
      <div style="background:#F8F8F8; padding:16px 30px; border-radius:10px;">
        <h3 style="font-size:20px; margin:0 0 8px 0;">연령·성별 현황</h3>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
c_age, c_gender = st.columns([4, 1.5])
with c_age:
    st.plotly_chart(fig_age, use_container_width=True)
with c_gender:
    st.plotly_chart(fig_gender, use_container_width=True)

st.markdown(
    """
    <div style="background:#EDF4FF; padding:16px; border-radius:10px; margin-bottom:20px;">
      <div style="background:#F8F8F8; padding:16px; border-radius:10px;">
        <h3 style="font-size:20px; margin:0 0 8px 0;">월별 연령대별 추이</h3>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.plotly_chart(fig_age_line, use_container_width=True)

st.markdown(
    """
    <div style="background:#EDF4FF; padding:16px; border-radius:10px; margin-bottom:20px;">
      <div style="background:#F8F8F8; padding:16px; border-radius:10px;">
        <h3 style="font-size:20px; margin:0 0 8px 0;">AP 월별 추이</h3>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.plotly_chart(fig_ap, use_container_width=True)

# =========================================
# 엑셀 다운로드 (피벗) - Dash 콜백 변환
# =========================================
st.markdown("---")
st.markdown("### 피벗 엑셀 다운로드")

if download_clicked:
    df_all_dl = df[(df["연월번호"] >= start_period) & (df["연월번호"] <= end_period)].copy()
    if market == "중고":
        df_all_dl = df_all_dl[df_all_dl["중고차시장"] == 1]
    elif market == "유효":
        df_all_dl = df_all_dl[df_all_dl["유효시장"] == 1]

    if df_all_dl.empty:
        st.warning("선택한 기간/시장에 데이터가 없습니다.")
    else:
        df_person_dl = df_all_dl[df_all_dl["나이"] != "법인및사업자"].copy()
        df_all_dl.loc[df_all_dl["나이"] == "법인및사업자", "성별"] = "법인및사업자"

        # === 1) 월별 x 이전등록유형 (합계 포함) ===
        pvt_month_type = df_all_dl.pivot_table(
            index="연월라벨",
            columns="이전등록유형",
            aggfunc="size",
            fill_value=0,
            margins=False,
        )
        # 열 합계
        pvt_month_type["합계"] = pvt_month_type.sum(axis=1)
        # 행 합계
        total_row = pvt_month_type.sum(axis=0).to_frame().T
        total_row.index = ["합계"]
        pvt_month_type = pd.concat([pvt_month_type, total_row])

        # === 2) 월별 x 연령대 분포 ===
        pvt_age = df_all_dl.pivot_table(
            index="연월라벨",
            columns="나이",
            aggfunc="size",
            fill_value=0,
            margins=False,
        )

        # === 3) 월별 x 성별 비중 ===
        pvt_gender = df_all_dl.pivot_table(
            index="연월라벨",
            columns="성별",
            aggfunc="size",
            fill_value=0,
            margins=False,
        )

        # === 4) 월별 x 연령대 (개인만) ===
        pvt_age_month = df_person_dl.pivot_table(
            index="연월라벨",
            columns="나이",
            aggfunc="size",
            fill_value=0,
            margins=False,
        )

        # === 5) 월별 x 주행거리 구간 ===
        pvt_km = df_all_dl.pivot_table(
            index="연월라벨",
            columns="주행거리_범위",
            aggfunc="size",
            fill_value=0,
            margins=False,
        )

        # === 6) 월별 x 취득금액 구간 ===
        pvt_price = df_all_dl.pivot_table(
            index="연월라벨",
            columns="취득금액_범위",
            aggfunc="size",
            fill_value=0,
            margins=False,
        )

        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            pvt_month_type.to_excel(writer, sheet_name="월별_유형")
            pvt_age.to_excel(writer, sheet_name="연령대_분포")
            pvt_gender.to_excel(writer, sheet_name="성별_비중")
            pvt_age_month.to_excel(writer, sheet_name="월별_연령대")
            pvt_km.to_excel(writer, sheet_name="주행거리별_분포")
            pvt_price.to_excel(writer, sheet_name="취득금액별_분포")

        output.seek(0)

        start_label = period_to_label.get(start_period, str(start_period))
        end_label = period_to_label.get(end_period, str(end_period))
        market_map = {"전체": "ALL", "중고": "중고차", "유효": "유효시장"}
        market_label = market_map.get(market, "ALL")
        filename = f"이전등록_피벗_{start_label}_{end_label}_{market_label}.xlsx"

        st.download_button(
            label="다운로드 시작",
            data=output,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

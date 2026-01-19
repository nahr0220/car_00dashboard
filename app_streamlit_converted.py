import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from io import BytesIO
from pathlib import Path

# ========================================
# 1. 페이지 설정 (최초 Streamlit 명령)
# ========================================
st.set_page_config(page_title="자동차 이전등록 대시보드", layout="wide")

# ========================================
# 2. CSS (가운데 정렬 + 여백)
# ========================================
st.markdown(
    """
<style>
.stApp {
    max-width: 1200px !important;
    margin: 0 auto !important;
    padding: 20px 40px !important;
    background: #FFFFFF !important;
}
.block-container {
    max-width: 1200px !important;
    padding: 1rem 2rem !important;
    margin: 0 auto !important;
}
#MainMenu, footer, header { visibility: hidden !important; }
.kpi-box {
    flex: 1 !important;
    background: #F8F8F8 !important;
    padding: 22px !important;
    border-radius: 10px !important;
    text-align: center !important;
    display: flex !important;
    flex-direction: column !important;
    justify-content: center !important;
    height: 150px !important;
    margin: 0 8px !important;
}
.filter-box, .graph-box {
    background: #EDF4FF !important;
    border-radius: 12px !important;
    margin-bottom: 20px !important;
}
.graph-header {
    background: #E3F2FD !important;
    padding: 16px !important;
    border-radius: 10px !important;
    margin: 0 0 16px 0 !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# ========================================
# 3. 데이터 로드 & 공통 전처리
# ========================================

@st.cache_data
def load_data_v2():
    data_path = Path("data")
    
    # Excel 파일들 찾기 (실제 파일명 패턴)
    files = sorted(data_path.glob("output_*분기.xlsx")) + \
            sorted(data_path.glob("output_*분기.csv"))
    
    if not files:
        st.error("❌ data/output_*분기.xlsx 파일을 찾을 수 없습니다!")
        st.stop()  # 여기서 멈춰서 "Oh no" 안 뜨게
        
    df_list = []
    for f in files:
        try:
            if f.suffix.lower() == '.csv':
                df_q = pd.read_csv(f, encoding="utf-8-sig")
            else:  # xlsx
                df_q = pd.read_excel(f, engine='openpyxl')
            df_list.append(df_q)
            st.sidebar.success(f"✅ 로드: {f.name}")
        except Exception as e:
            st.error(f"❌ {f.name} 읽기 실패: {e}")
            continue
    
    if not df_list:
        st.error("모든 파일 읽기 실패!")
        st.stop()
        
    df = pd.concat(df_list, ignore_index=True)
    df.columns = df.columns.str.strip()
    
    # AP 데이터
    ap_file = data_path / "AP Sales Summary.xlsx"
    if ap_file.exists():
        df_ap = pd.read_excel(ap_file, skiprows=1, engine='openpyxl')
        df_ap.columns = ["년도", "월", "AP"]
        df_ap = df_ap[df_ap["년도"] >= 2024].copy()
        st.sidebar.success("✅ AP 데이터 로드")
    else:
        st.warning("⚠️ AP Sales Summary.xlsx 없음 (더미 사용)")
        df_ap = pd.DataFrame({'년도': [2024, 2025], '월': [1, 1], 'AP': [100, 120]})
    
    # 공통 전처리
    for d in (df, df_ap):
        if '년도' in d.columns and '월' in d.columns:
            d["연월번호"] = d["년도"] * 100 + d["월"]
            d["연월라벨"] = (d["년도"].astype(str) + "-" + 
                           d["월"].astype(str).str.zfill(2))
    
    periods = (df[["연월번호", "연월라벨"]].drop_duplicates()
               .sort_values("연월번호"))
    period_options = [{"label": r["연월라벨"], "value": int(r["연월번호"])} 
                      for _, r in periods.iterrows()]
    period_to_label = (periods.set_index("연월번호")["연월라벨"]
                       .astype(str).to_dict())
    
    st.sidebar.success(f"✅ 총 {len(df)}건 데이터 로드 완료!")
    return df, df_ap, period_options, period_to_label


df, df_ap, period_options, period_to_label = load_data_v2()


# ========================================
# 4. 제목
# ========================================
st.markdown("## 자동차 이전등록 대시보드")

# ========================================
# 5. KPI 계산
# ========================================
col1, col2, col3 = st.columns(3)

df_kpi = df.copy()
cur_period = int(df_kpi["연월번호"].max())
cur_year, cur_month = divmod(cur_period, 100)

# KPI1: 연도 누적
kpi1_ytd = df_kpi[
    (df_kpi["년도"] == cur_year) & (df_kpi["연월번호"] <= cur_period)
]
kpi1_value = len(kpi1_ytd)

# KPI2: 해당 월 거래량 + MoM/YoY
cur_cnt = len(df_kpi[df_kpi["연월번호"] == cur_period])

prev_year, prev_month = cur_year, cur_month - 1
if prev_month == 0:
    prev_month = 12
    prev_year -= 1
prev_period = prev_year * 100 + prev_month
prev_cnt = len(df_kpi[df_kpi["연월번호"] == prev_period])

if prev_cnt > 0:
    mom_val = (cur_cnt - prev_cnt) / prev_cnt * 100
    mom_str = f"{mom_val:+.1f}%"
else:
    mom_val = None
    mom_str = "-"

yoy_period = (cur_year - 1) * 100 + cur_month
yoy_cnt = len(df_kpi[df_kpi["연월번호"] == yoy_period])
if yoy_cnt > 0:
    yoy_val = (cur_cnt - yoy_cnt) / yoy_cnt * 100
    yoy_str = f"{yoy_val:+.1f}%"
else:
    yoy_val = None
    yoy_str = "-"

# KPI3: 중고차 비중
used_cnt = len(
    df_kpi[
        (df_kpi["연월번호"] == cur_period)
        & (df_kpi["중고차시장"] == 1)
    ]
)
ratio = used_cnt / cur_cnt * 100 if cur_cnt > 0 else 0

# ===== MODIFIED: 중고차 비중 MoM =====
prev_used_cnt = len(
    df_kpi[
        (df_kpi["연월번호"] == prev_period)
        & (df_kpi["중고차시장"] == 1)
    ]
)
prev_ratio = prev_used_cnt / prev_cnt * 100 if prev_cnt > 0 else None

if prev_ratio is not None:
    ratio_mom = ratio - prev_ratio
    ratio_mom_str = f"{ratio_mom:+.1f}%p"
else:
    ratio_mom = None
    ratio_mom_str = "-"

with col1:
    st.markdown(
        f"""
    <div class="kpi-box">
      <div style="font-size:18px;color:#666;">{cur_year}년 누적 거래량</div>
      <div style="font-size:34px;font-weight:700;">{kpi1_value:,}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )

with col2:
    mom_color = "red" if (mom_val is not None and mom_val > 0) else "blue"
    yoy_color = "red" if (yoy_val is not None and yoy_val > 0) else "blue"
    st.markdown(
        f"""
    <div class="kpi-box">
      <div style="font-size:18px;color:#666;">{cur_month}월 거래량</div>
      <div style="font-size:34px;font-weight:700;">{cur_cnt:,}</div>
      <div style="font-size:14px;margin-top:8px;">
        <span style="color:{mom_color};">{mom_str} (MoM)</span>
        <span style="color:#999;"> | </span>
        <span style="color:{yoy_color};">{yoy_str} (YoY)</span>
      </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

with col3:
    mom_color = "red" if (ratio_mom is not None and ratio_mom > 0) else "blue"
    st.markdown(
        f"""
    <div class="kpi-box">
      <div style="font-size:18px;color:#666;">{cur_month}월 중고차 비중</div>
      <div style="font-size:34px;font-weight:700;">{ratio:.1f}%</div>
      <div style="font-size:14px;margin-top:8px;">
        <span style="color:{mom_color};">{ratio_mom_str} (MoM)</span>
      </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

# ========================================
# 6. 필터 + 탭 + 다운로드 버튼 (수정)
# ========================================
st.markdown('<div class="filter-box">', unsafe_allow_html=True)

c_sp1, c_sp2, c_btn = st.columns([1, 1, 0.5])

with c_sp1:
    st.markdown(
        '<div style="font-size:14px;margin-bottom:4px;">시작 연월</div>',
        unsafe_allow_html=True,
    )
    start_period = st.selectbox(
        "",
        options=[p["value"] for p in period_options],
        index=0,
        format_func=lambda v: period_to_label.get(int(v), str(v)),
        label_visibility="collapsed",
    )

with c_sp2:
    st.markdown(
        '<div style="font-size:14px;margin-bottom:4px;">종료 연월</div>',
        unsafe_allow_html=True,
    )
    end_period = st.selectbox(
        "",
        options=[p["value"] for p in period_options],
        index=len(period_options) - 1,
        format_func=lambda v: period_to_label.get(int(v), str(v)),
        label_visibility="collapsed",
    )

# 시장 구분
st.markdown(
    """
<div style="display:flex; align-items:center; gap:6px;">
  <span style="font-size:14px;">시장 구분</span>
  <span
    style="
      display:inline-block;
      width:16px;
      height:16px;
      border-radius:50%;
      background:#1976D2;
      color:white;
      font-size:12px;
      text-align:center;
      line-height:16px;
      cursor:default;
    "
    title="
※ 출처: 당사 내부 자료, 국토교통부
전체: 국토교통부의 자동차 이전 데이터 전체
중고차시장: 중고차 전체 등록대수 중 개인 간 거래대수를 포함한 사업자 거래대수를 의미 (개인거래 + 매도 + 상사이전 + 알선)
유효시장: 중고차 전체 등록대수 중 개인 간 거래대수를 제외한 사업자 거래대수를 의미 (매도 + 상사이전 + 알선)
마케팅: 마케팅팀이 사전에 정의한 필터링 기준에 따라, 이전등록구분명이 ‘매매업자거래이전’이며 등록상세명이 ‘일반소유용’인 이전 등록 건을 의미
    "
  >i</span>
</div>
""",
    unsafe_allow_html=True,
)

market = st.radio(
    "",
    ["전체", "중고차시장", "유효시장", "마케팅"],
    index=0,
    horizontal=True,
    label_visibility="collapsed",
)


# ========================================
# **엑셀 데이터 생성 함수** (수정됨)
# ========================================
def create_excel_file(df_input, start_period, end_period, market, period_to_label):
    """시장 구분 필터가 적용된 엑셀 파일 생성"""
    
    # 1단계: 기간 필터링
    df_all_dl = df_input[
        (df_input["연월번호"] >= start_period)
        & (df_input["연월번호"] <= end_period)
    ].copy()
    
    # 2단계: 시장 구분 필터링 (중요!)
    if market == "중고차시장":
        df_all_dl = df_all_dl[df_all_dl["중고차시장"] == 1]
    elif market == "유효시장":
        df_all_dl = df_all_dl[df_all_dl["유효시장"] == 1]
    elif market == "마케팅":
        df_all_dl = df_all_dl[df_all_dl["마케팅"] == 1]
    # 전체는 필터 없음

    if df_all_dl.empty:
        return None, "데이터 없음"

    # 나머지 데이터 처리...
    df_person_dl = df_all_dl[df_all_dl["나이"] != "법인및사업자"].copy()
    df_all_dl.loc[df_all_dl["나이"] == "법인및사업자", "성별"] = "법인및사업자"

    # 피벗 테이블들 (필터된 df_all_dl 사용)
    pvt_month_type = df_all_dl.pivot_table(
        index="연월라벨",
        columns="이전등록유형",
        aggfunc="size",
        fill_value=0,
    )
    pvt_month_type["합계"] = pvt_month_type.sum(axis=1)
    total_row = pvt_month_type.sum(axis=0).to_frame().T
    total_row.index = ["합계"]
    pvt_month_type = pd.concat([pvt_month_type, total_row])

    pvt_age = df_all_dl.pivot_table(
        index=["나이","성별"], columns="연월라벨", aggfunc="size", fill_value=0
    )
    pvt_km = df_all_dl.pivot_table(
        index="주행거리_범위", columns="연월라벨", aggfunc="size", fill_value=0
    )
    pvt_price = df_all_dl.pivot_table(
        index="취득금액_범위", columns="연월라벨", aggfunc="size", fill_value=0
    )
    pvt_map = df_all_dl.pivot_table(
        index="시/도", columns="연월라벨", aggfunc="size", fill_value=0
    )
    pvt_map2 = df_all_dl.pivot_table(
        index=["시/도","구/군"], columns="연월라벨", aggfunc="size", fill_value=0
    )


    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        pvt_month_type.to_excel(writer, sheet_name="월별_분포")
        pvt_age.to_excel(writer, sheet_name="연령성별대_분포")
        pvt_km.to_excel(writer, sheet_name="주행거리별_분포")
        pvt_price.to_excel(writer, sheet_name="취득금액별_분포")
        pvt_map.to_excel(writer, sheet_name="지역별_분포")
        pvt_map2.to_excel(writer, sheet_name="상세지역별_분포")

    output.seek(0)
    return output, len(df_all_dl)


# **다운로드 버튼 (수정됨 - 캐시 제거)**
with c_btn:
    st.markdown("&nbsp;", unsafe_allow_html=True)
    
    # 💡 핵심: @st.cache_data 제거 → 매번 필터 적용됨!
    excel_file, record_count = create_excel_file(
        df, start_period, end_period, market, period_to_label
    )
    
    if excel_file:
        start_label = period_to_label.get(start_period, str(start_period))
        end_label = period_to_label.get(end_period, str(end_period))
        
        # 파일명에 시장 구분 표시
        market_map = {
            "전체": "전체",
            "중고차시장": "중고차",
            "유효시장": "유효시장",
            "마케팅": "마케팅"
        }
        
        filename = (
            f"이전등록_피벗_{start_label}_{end_label}_"
            f"{market_map.get(market, '전체')}.xlsx"
        )
        
        st.download_button(
            label=f"⬇️ XLSX ({record_count:,}건)",
            data=excel_file,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="instant_excel_download"
        )
    else:
        st.button("⬇️ XLSX", disabled=True, help="데이터 없음")

st.markdown('</div>', unsafe_allow_html=True)

# ========================================
# 7. 필터링된 데이터
# ========================================
if start_period > end_period:
    start_period, end_period = end_period, start_period

df_all = df[
    (df["연월번호"] >= start_period) & (df["연월번호"] <= end_period)
].copy()

if market == "중고차시장":
    df_all = df_all[df_all["중고차시장"] == 1]
elif market == "유효시장":
    df_all = df_all[df_all["유효시장"] == 1]
elif market == "마케팅":
    df_all = df_all[df_all["마케팅"] == 1]
# 전체는 필터 없음

# ========================================
# 8. 그래프 1: 월별 이전등록유형 추이
# ========================================
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
    yaxis=dict(title="건수", tickformat=",d"),
    xaxis=dict(title="연월"),
    margin=dict(l=40, r=20, t=20, b=40),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="right",
        x=1,
    ),
    font=dict(size=14),
)

st.markdown(
    """
<div class="graph-box">
  <div class="graph-header">
    <h3 style="margin:0;">월별 이전등록유형 추이</h3>
  </div>
</div>
""",
    unsafe_allow_html=True,
)
st.plotly_chart(fig1, use_container_width=True)

# ========================================
# 11. AP 월별 추이
# ========================================
df_ap_f = df_ap[
    (df_ap["연월번호"] >= start_period)
    & (df_ap["연월번호"] <= end_period)
].sort_values("연월번호")

# AP 월별 추이: 항상 전체(유효시장 기준)
df_ap_base = df[df["유효시장"] == 1]

valid_m = (
    df_ap_base
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

fig_ap = go.Figure()
fig_ap.add_trace(
    go.Bar(
        x=df_ap_m["연월라벨"],
        y=df_ap_m["AP"],
        name="AP 판매대수",
        text=df_ap_m["AP"],
        texttemplate="%{text:,}",
        textposition="outside",
        marker_color="#1976D2",
        hovertemplate="AP: %{y:,}",
    )
)
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
    yaxis=dict(
        title="AP",
        tickformat=",d",
        range=[0, df_ap_m["AP"].max() * 1.8],
    ),
    xaxis=dict(title="연월"),
    margin=dict(l=40, r=20, t=20, b=40),
    font=dict(size=14),
)

st.markdown(
    """
<div class="graph-box">
  <div class="graph-header">
    <h3 style="margin:0;">AP 월별 추이</h3>
  </div>
</div>
""",
    unsafe_allow_html=True,
)
st.plotly_chart(fig_ap, use_container_width=True)

# ========================================
# 9. 연령·성별 그래프
# ========================================
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

st.markdown(
    """
<div class="graph-box">
  <div class="graph-header">
    <h3 style="margin:0;">연령·성별 현황</h3>
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

# ========================================
# 10. 월별 연령대별 추이
# ========================================
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

st.markdown(
    """
<div class="graph-box">
  <div class="graph-header">
    <h3 style="margin:0;">월별 연령대별 추이</h3>
  </div>
</div>
""",
    unsafe_allow_html=True,
)
st.plotly_chart(fig_age_line, use_container_width=True)
# ===============================================================
# 자동차 이전등록 대시보드 (최종 통합본 - 오류 방지 및 기능 전체 포함)
# ===============================================================

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path
import tempfile
import os

# ---------------------------------------------------------------
# 1. Page Config 및 스타일 설정
# ---------------------------------------------------------------
st.set_page_config(page_title="자동차 이전등록 대시보드", layout="wide")

st.markdown("""
<style>
.stApp { max-width:1200px; margin:0 auto; padding:20px 40px; background:#fff; }
#MainMenu, footer, header { visibility:hidden; }
.kpi-box {
    background:#F8F8F8; padding:22px; border-radius:10px;
    text-align:center; height:150px;
    display:flex; flex-direction:column; justify-content:center;
}
.filter-box,.graph-box {
    background:#EDF4FF; border-radius:12px; margin-bottom:20px;
}
.graph-header {
    background:#E3F2FD; padding:16px; border-radius:10px;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------
# 2. DuckDB 연결 및 데이터 로드
# ---------------------------------------------------------------
@st.cache_resource
def get_con():
    con = duckdb.connect(database=":memory:")
    files = sorted(Path("data").glob("output_*분기.csv"))
    if not files:
        st.error("data 폴더에 CSV 파일이 없습니다.")
        st.stop()
    file_list_sql = "[" + ",".join(f"'{str(f)}'" for f in files) + "]"
    con.execute(f"""
        CREATE VIEW df AS
        SELECT *,
               년도*100 + 월 AS 연월번호,
               CAST(년도 AS VARCHAR)||'-'||LPAD(CAST(월 AS VARCHAR),2,'0') AS 연월라벨
        FROM read_csv_auto({file_list_sql})
    """)
    return con

con = get_con()

# ---------------------------------------------------------------
# 3. 데이터 유무 확인 및 기간 설정 (ValueError 방지)
# ---------------------------------------------------------------
periods = con.execute('SELECT DISTINCT "연월번호", "연월라벨" FROM df ORDER BY "연월번호"').df()

if periods.empty:
    st.warning("분석할 수 있는 데이터가 없습니다.")
    st.stop()

period_to_label = dict(zip(periods["연월번호"], periods["연월라벨"]))

# 데이터가 있을 때만 계산
cur_p = int(periods["연월번호"].max())
cur_year, cur_month = divmod(cur_p, 100)
prev_p = (cur_year*100+cur_month-1) if cur_month>1 else ((cur_year-1)*100+12)

# KPI 계산용 쿼리 (Error 방지 포함)
def query_cnt(sql, params):
    res = con.execute(sql, params).fetchone()[0]
    return res if res else 0

cur_cnt = query_cnt("SELECT COUNT(*) FROM df WHERE 연월번호=?", [cur_p])
prev_cnt = query_cnt("SELECT COUNT(*) FROM df WHERE 연월번호=?", [prev_p]) or 1
used_cur = query_cnt("SELECT COUNT(*) FROM df WHERE 연월번호=? AND 중고차시장=1", [cur_p])
used_prev = query_cnt("SELECT COUNT(*) FROM df WHERE 연월번호=? AND 중고차시장=1", [prev_p])

mom = (cur_cnt-prev_cnt)/prev_cnt*100
ratio_cur = used_cur/cur_cnt*100 if cur_cnt else 0
ratio_prev = used_prev/prev_cnt*100 if prev_cnt else 0
ratio_mom = ratio_cur - ratio_prev

# ---------------------------------------------------------------
# 4. 상단 KPI UI
# ---------------------------------------------------------------
st.markdown("## 자동차 이전등록 대시보드")
c1, c2, c3 = st.columns(3)
with c1: st.markdown(f"<div class='kpi-box'><h4>{cur_year}년 누적 거래량</h4><h2>{cur_cnt:,}</h2></div>", unsafe_allow_html=True)
with c2:
    m_color = "red" if mom>0 else "blue"
    st.markdown(f"<div class='kpi-box'><h4>{cur_month}월 거래량</h4><h2>{cur_cnt:,}</h2><div style='color:{m_color}'>{mom:+.1f}% MoM</div></div>", unsafe_allow_html=True)
with c3:
    r_color = "red" if ratio_mom>0 else "blue"
    st.markdown(f"<div class='kpi-box'><h4>중고차 비중</h4><h2>{ratio_cur:.1f}%</h2><div style='color:{r_color}'>{ratio_mom:+.1f}%p MoM</div></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------
# 5. 필터 및 도움말(?)
# ---------------------------------------------------------------
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
f1, f2, f3 = st.columns([1, 1, 0.6])
with f1: start_p = st.selectbox("시작 연월", periods["연월번호"], format_func=lambda x: period_to_label[x])
with f2: end_p = st.selectbox("종료 연월", periods["연월번호"], index=len(periods)-1, format_func=lambda x: period_to_label[x])

# 도움말 메시지
m_help = "전체: 모든 데이터 / 중고차: 매매거래 / 유효: 마케팅 타겟 / 마케팅: 특정 캠페인"
market = st.radio("시장 구분", ["전체", "중고차시장", "유효시장", "마케팅"], horizontal=True, help=m_help)

with f3:
    excel_clicked = st.button("📥 엑셀 파일 생성")
st.markdown("</div>", unsafe_allow_html=True)

where = f"연월번호 BETWEEN {start_p} AND {end_p}"
if market != "전체": where += f" AND {market}=1"

# ---------------------------------------------------------------
# 6. 엑셀 다중 시트 생성 함수
# ---------------------------------------------------------------
def create_multi_sheet_excel(where_clause):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    path = tmp.name
    tmp.close()

    df_filtered = con.execute(f"SELECT * FROM df WHERE {where_clause}").df()
    if df_filtered.empty: return None

    # 데이터 보정
    df_filtered.loc[df_filtered["나이"] == "법인및사업자", "성별"] = "법인및사업자"

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        # 1~2. 기본 분포
        df_filtered.pivot_table(index="연월라벨", columns="이전등록유형", aggfunc="size", fill_value=0).to_excel(writer, sheet_name="월별_분포")
        df_filtered.pivot_table(index=["나이","성별"], columns="연월라벨", aggfunc="size", fill_value=0).to_excel(writer, sheet_name="연령성별대_분포")
        
        # 3~5. 추가 범위 분포
        for col, s_name in zip(["주행거리_범위", "취득금액_범위", "시/도"], ["주행거리별_분포", "취득금액별_분포", "지역별_분포"]):
            if col in df_filtered.columns:
                df_filtered.pivot_table(index=col, columns="연월라벨", aggfunc="size", fill_value=0).to_excel(writer, sheet_name=s_name)
        
        # 6. 상세 지역
        if "시/도" in df_filtered.columns and "구/군" in df_filtered.columns:
            df_filtered.pivot_table(index=["시/도","구/군"], columns="연월라벨", aggfunc="size", fill_value=0).to_excel(writer, sheet_name="상세지역별_분포")

    return path

# 엑셀 다운로드 버튼 처리
if excel_clicked:
    with st.spinner("다중 시트 엑셀 준비 중..."):
        e_path = create_multi_sheet_excel(where)
        if e_path:
            with open(e_path, "rb") as f:
                st.download_button("⬇️ 상세 리포트 다운로드 (.xlsx)", f, file_name=f"report_{market}.xlsx")
        else:
            st.error("선택한 조건에 해당하는 데이터가 없습니다.")

# ---------------------------------------------------------------
# 7. 메인 그래프 (숫자 크게, 컴마 표시, 대시 제거)
# ---------------------------------------------------------------
g_total = con.execute(f"SELECT 연월라벨, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨 ORDER BY 연월번호").df()

if not g_total.empty:
    fig1 = go.Figure()
    fig1.add_bar(
        x=g_total["연월라벨"], y=g_total["건수"], name="전체", 
        text=g_total["건수"], textposition='outside'
    )
    # 글자 크기 20, 굵게, 컴마 표시
    fig1.update_traces(texttemplate='<b>%{text:,}</b>', textfont=dict(size=20, color="black"))
    # Y축 120k 방지 (tickformat=",d") 및 대시 제거
    fig1.update_layout(
        xaxis=dict(ticks=""),
        yaxis=dict(ticks="", tickformat=",d"),
        margin=dict(t=50)
    )

    st.markdown("<div class='graph-box'><div class='graph-header'><h3>월별 이전등록유형 추이</h3></div></div>", unsafe_allow_html=True)
    st.plotly_chart(fig1, use_container_width=True)

# ---------------------------------------------------------------
# Graph 2: AP 월별 추이
# ---------------------------------------------------------------
valid_m = con.execute(f"SELECT 연월번호, 연월라벨, COUNT(*) AS 유효시장건수 FROM df WHERE 유효시장=1 GROUP BY 연월번호, 연월라벨").df()
df_ap_m = pd.merge(df_ap, valid_m, on=["연월번호","연월라벨"], how="inner")

if not df_ap_m.empty:
    df_ap_m["AP비중"] = df_ap_m["AP"]/df_ap_m["유효시장건수"]*100
    ap_max = df_ap_m["AP"].max() if not df_ap_m["AP"].empty else 1
    ratio_max = df_ap_m["AP비중"].max() if not df_ap_m["AP비중"].empty else 1
    df_ap_m["AP비중_시각화"] = (df_ap_m["AP비중"]/ratio_max) * ap_max * 1.6

    fig_ap = go.Figure()
    fig_ap.add_bar(
        x=df_ap_m["연월라벨"], y=df_ap_m["AP"], name="AP 판매량", 
        text=df_ap_m["AP"], textposition='outside',
        texttemplate='<b>%{text:,}</b>', textfont=dict(size=15, color="black")
    )
    fig_ap.add_scatter(
        x=df_ap_m["연월라벨"], y=df_ap_m["AP비중_시각화"], 
        mode="lines+markers+text", text=df_ap_m["AP비중"].round(2).astype(str) + "%",
        textposition="top center", textfont=dict(size=10, color="red", family="Arial Black"), 
        name="AP 비중 (%)", line=dict(color='red', width=1.5)
    )
    fig_ap.update_layout(xaxis=dict(ticks=""), yaxis=dict(ticks=""))
    fig_ap.update_yaxes(range=[0, ap_max * 2.0])
    st.markdown("<div class='graph-box'><div class='graph-header'><h3>AP 월별 추이 (유효시장 대비)</h3></div></div>", unsafe_allow_html=True)
    st.plotly_chart(fig_ap, use_container_width=True)

# ---------------------------------------------------------------
# Graph 3 & 4
# ---------------------------------------------------------------
age_data = con.execute(f"SELECT 나이, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 나이 ORDER BY 나이").df()
gender_data = con.execute(f"SELECT 성별, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 성별").df()

st.markdown("<div class='graph-box'><div class='graph-header'><h3>연령·성별 현황</h3></div></div>", unsafe_allow_html=True)
c_age, c_gender = st.columns([4, 2])
with c_age:
    fig_age = px.bar(age_data, x="건수", y="나이", orientation="h", text_auto=',.0f')
    fig_age.update_traces(texttemplate='<b>%{text}</b>', textposition='outside', textfont=dict(size=18, color="black"))
    fig_age.update_layout(xaxis=dict(ticks=""), yaxis=dict(ticks=""))
    st.plotly_chart(fig_age, use_container_width=True)

with c_gender:
    fig_gender = px.pie(gender_data, values="건수", names="성별", hole=0.5)
    fig_gender.update_traces(textfont_size=16)
    st.plotly_chart(fig_gender, use_container_width=True)

age_line = con.execute(f"SELECT 연월라벨, 나이, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 연월번호, 연월라벨, 나이 ORDER BY 연월번호").df()
fig_age_line = px.line(age_line, x="연월라벨", y="건수", color="나이", markers=True)
fig_age_line.update_layout(xaxis=dict(ticks=""), yaxis=dict(ticks=""))
st.markdown("<div class='graph-box'><div class='graph-header'><h3>월별 연령대별 추이</h3></div></div>", unsafe_allow_html=True)
st.plotly_chart(fig_age_line, use_container_width=True)
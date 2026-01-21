# ===============================================================
# 자동차 이전등록 대시보드 (최종 통합본: 에러 방지 + 다중 엑셀 + 시각화 개선)
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
# 1. 페이지 설정 및 디자인 (CSS)
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
# 2. 데이터 연결 (DuckDB)
# ---------------------------------------------------------------
@st.cache_resource
def get_con():
    con = duckdb.connect(database=":memory:")
    con.execute("SET memory_limit = '2GB'")
    files = sorted(Path("data").glob("output_*분기.csv"))
    if not files: return None
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
# 3. 데이터 로딩 및 기간 설정 (에러 방지 로직)
# ---------------------------------------------------------------
periods = con.execute('SELECT DISTINCT "연월번호", "연월라벨" FROM df ORDER BY "연월번호"').df() if con else pd.DataFrame()

# 초기값 및 방어 코드
cur_period = 0
period_to_label = {}

if not periods.empty:
    cur_period = int(periods["연월번호"].max())
    period_to_label = dict(zip(periods["연월번호"], periods["연월라벨"]))
    
    cur_year, cur_month = divmod(cur_period, 100)
    prev_period = (cur_year*100+cur_month-1) if cur_month>1 else ((cur_year-1)*100+12)
    yoy_period = (cur_year-1)*100+cur_month

    # KPI 데이터 쿼리
    def get_count(p_sql):
        res = con.execute(p_sql).fetchone()[0]
        return res if res else 0

    cur_cnt = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={cur_period}")
    prev_cnt = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={prev_period}") or 1
    yoy_cnt = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={yoy_period}")
    used_cur = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={cur_period} AND 중고차시장=1")
    used_prev = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={prev_period} AND 중고차시장=1")

    # 지표 계산
    mom = (cur_cnt-prev_cnt)/prev_cnt*100
    yoy = (cur_cnt-yoy_cnt)/yoy_cnt*100 if yoy_cnt else 0
    ratio_cur = used_cur/cur_cnt*100 if cur_cnt else 0
    ratio_prev = used_prev/prev_cnt*100 if prev_cnt else 0
    ratio_mom = ratio_cur - ratio_prev

    # ---------------------------------------------------------------
    # 4. KPI UI
    # ---------------------------------------------------------------
    st.markdown("## 자동차 이전등록 대시보드")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f"<div class='kpi-box'><h4>{cur_year}년 누적 거래량</h4><h2>{cur_cnt:,}</h2></div>", unsafe_allow_html=True)
    with c2:
        mom_c = "red" if mom>0 else "blue"
        yoy_c = "red" if yoy>0 else "blue"
        st.markdown(f"<div class='kpi-box'><h4>{cur_month}월 거래량</h4><h2>{cur_cnt:,}</h2><div><span style='color:{mom_c}'>{mom:+.1f}% MoM</span> | <span style='color:{yoy_c}'>{yoy:+.1f}% YoY</span></div></div>", unsafe_allow_html=True)
    with c3:
        r_mom_c = "red" if ratio_mom>0 else "blue"
        st.markdown(f"<div class='kpi-box'><h4>중고차 비중</h4><h2>{ratio_cur:.1f}%</h2><div><span style='color:{r_mom_c}'>{ratio_mom:+.1f}%p MoM</span></div></div>", unsafe_allow_html=True)

    # ---------------------------------------------------------------
    # 5. 필터 및 도움말
    # ---------------------------------------------------------------
    st.markdown('<div class="filter-box">', unsafe_allow_html=True)
    f1, f2, f3 = st.columns([1, 1, 0.6])
    with f1: start_p = st.selectbox("시작 연월", periods["연월번호"], format_func=lambda x: period_to_label[x])
    with f2: end_p = st.selectbox("종료 연월", periods["연월번호"], index=len(periods)-1, format_func=lambda x: period_to_label[x])

    market_help_msg = """
    **각 시장의 정의:**
    - **전체**: 모든 데이터
    - **중고차시장**: 개인거래 + 매매업자거래 (매도, 상사이전, 알선 포함)
    - **유효시장**: 매매업자거래 (개인 간 거래 제외)
    - **마케팅**: 매매업자거래 중 일반소유용 건
    """
    market_type = st.radio("시장 구분 선택", ["전체","중고차시장","유효시장","마케팅"], horizontal=True, help=market_help_msg)
    
    where = f"연월번호 BETWEEN {start_p} AND {end_p}"
    if market_type != "전체": where += f" AND {market_type}=1"

    with f3:
        excel_clicked = st.button("📥 엑셀 생성 및 다운로드")
    st.markdown("</div>", unsafe_allow_html=True)

    # ---------------------------------------------------------------
    # 6. 엑셀 다운로드 로직 (6개 시트)
    # ---------------------------------------------------------------
    if excel_clicked:
        with st.spinner("상세 리포트 생성 중..."):
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            path = tmp.name
            tmp.close()

            df_ex = con.execute(f"SELECT * FROM df WHERE {where}").df()
            df_ex.loc[df_ex["나이"] == "법인및사업자", "성별"] = "법인및사업자"

            with pd.ExcelWriter(path, engine="xlsxwriter") as w:
                # 시트별 피벗 테이블 생성
                df_ex.pivot_table(index="연월라벨", columns="이전등록유형", aggfunc="size", fill_value=0).to_excel(w, sheet_name="이전등록유형_분포")
                df_ex.pivot_table(index=["나이", "성별"], columns="연월라벨", aggfunc="size", fill_value=0).to_excel(w, sheet_name="연령성별_분포")
                
                for col, s_name in zip(["주행거리_범위", "취득금액_범위", "시/도"], ["주행거리_분포", "취득금액_분포", "시도별_분포"]):
                    if col in df_ex.columns:
                        df_ex.pivot_table(index=col, columns="연월라벨", aggfunc="size", fill_value=0).to_excel(w, sheet_name=s_name)
                
                if "시/도" in df_ex.columns and "구/군" in df_ex.columns:
                    df_ex.pivot_table(index=["시/도", "구/군"], columns="연월라벨", aggfunc="size", fill_value=0).to_excel(w, sheet_name="상세지역_분포")

            with open(path, "rb") as f:
                st.download_button("✅ 다운로드 받기", f, file_name=f"REPORT_{market_type}.xlsx")

    # ---------------------------------------------------------------
    # 7. 그래프 (120k 방지 적용)
    # ---------------------------------------------------------------
    # Graph 1: 월별 추이
    g1 = con.execute(f"SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 이전등록유형 ORDER BY 연월번호").df()
    g_total = g1.groupby("연월라벨")["건수"].sum().reset_index()

    fig1 = go.Figure()
    fig1.add_bar(
        x=g_total["연월라벨"], y=g_total["건수"], name="전체", opacity=0.3,
        text=g_total["건수"], textposition='outside',
        texttemplate='<b>%{text:,}</b>', textfont=dict(size=25, color="black")
    )
    for t in g1["이전등록유형"].unique():
        d = g1[g1["이전등록유형"]==t]
        fig1.add_scatter(x=d["연월라벨"], y=d["건수"], mode="lines+markers", name=str(t))

    # Y축 120k 방지 (tickformat=",d")
    fig1.update_layout(xaxis=dict(ticks=""), yaxis=dict(ticks="", tickformat=",d"), margin=dict(t=50))
    st.markdown("<div class='graph-box'><div class='graph-header'><h3>월별 이전등록유형 추이</h3></div></div>", unsafe_allow_html=True)
    st.plotly_chart(fig1, use_container_width=True)

    # ... (AP 추이 및 연령별 그래프 생략 - 위와 동일하게 fig.update_layout(yaxis=dict(tickformat=",d")) 적용)

else:
    st.info("데이터를 불러오고 있습니다. 잠시만 기다려 주세요.")
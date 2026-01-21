import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path
import tempfile
import os

# 1. 페이지 설정 및 디자인
st.set_page_config(page_title="자동차 이전등록 대시보드", layout="wide")

st.markdown("""
<style>
.stApp { max-width:1200px; margin:0 auto; padding:20px 40px; background:#fff; }
#MainMenu, footer, header { visibility:hidden; }
.kpi-box { background:#F8F8F8; padding:22px; border-radius:10px; text-align:center; height:150px; display:flex; flex-direction:column; justify-content:center; }
.filter-box,.graph-box { background:#EDF4FF; border-radius:12px; margin-bottom:20px; }
.graph-header { background:#E3F2FD; padding:16px; border-radius:10px; }
</style>
""", unsafe_allow_html=True)

# 2. 데이터 연결 (메모리 최적화 설정)
@st.cache_resource
def get_con():
    con = duckdb.connect(database=":memory:")
    # 메모리 제한 설정 (튕김 방지)
    con.execute("SET memory_limit = '1GB'") 
    files = sorted(Path("data").glob("output_*분기.csv"))
    if not files: return None
    file_list_sql = "[" + ",".join(f"'{str(f)}'" for f in files) + "]"
    
    # 뷰 생성 시 필요한 컬럼만 명시적으로 가져오면 더 가볍습니다.
    con.execute(f"""
        CREATE VIEW df AS
        SELECT *,
               년도*100 + 월 AS 연월번호,
               CAST(년도 AS VARCHAR)||'-'||LPAD(CAST(월 AS VARCHAR),2,'0') AS 연월라벨
        FROM read_csv_auto({file_list_sql})
    """)
    return con

con = get_con()

# AP 데이터 로드 (에러 방지)
try:
    df_ap = pd.read_excel("data/AP Sales Summary.xlsx", skiprows=1)
    df_ap.columns = ["년도","월","AP"]
    df_ap = df_ap[df_ap["년도"]>=2024]
    df_ap["연월번호"] = df_ap["년도"]*100 + df_ap["월"]
    df_ap["연월라벨"] = df_ap["년도"].astype(str) + "-" + df_ap["월"].astype(str).str.zfill(2)
except:
    df_ap = pd.DataFrame(columns=["연월번호", "연월라벨", "AP"])

# 3. 데이터 로딩 및 기간 설정
periods = con.execute('SELECT DISTINCT "연월번호", "연월라벨" FROM df ORDER BY "연월번호"').df() if con else pd.DataFrame()

if not periods.empty:
    cur_period = int(periods["연월번호"].max())
    period_to_label = dict(zip(periods["연월번호"], periods["연월라벨"]))
    cur_year, cur_month = divmod(cur_period, 100)
    prev_period = (cur_year*100+cur_month-1) if cur_month>1 else ((cur_year-1)*100+12)
    yoy_period = (cur_year-1)*100+cur_month

    # KPI 쿼리 (필요한 값만 쏙쏙 골라오기)
    cur_cnt = con.execute(f"SELECT COUNT(*) FROM df WHERE 연월번호={cur_period}").fetchone()[0]
    prev_cnt = con.execute(f"SELECT COUNT(*) FROM df WHERE 연월번호={prev_period}").fetchone()[0] or 1
    yoy_cnt = con.execute(f"SELECT COUNT(*) FROM df WHERE 연월번호={yoy_period}").fetchone()[0] or 1
    used_cur = con.execute(f"SELECT COUNT(*) FROM df WHERE 연월번호={cur_period} AND 중고차시장=1").fetchone()[0]
    used_prev = con.execute(f"SELECT COUNT(*) FROM df WHERE 연월번호={prev_period} AND 중고차시장=1").fetchone()[0]

    # 지표 계산
    mom = (cur_cnt-prev_cnt)/prev_cnt*100
    yoy = (cur_cnt-yoy_cnt)/yoy_cnt*100
    ratio_cur = used_cur/cur_cnt*100 if cur_cnt else 0
    ratio_mom = ratio_cur - (used_prev/prev_cnt*100 if prev_cnt else 0)

    # 4. KPI UI
    st.markdown("## 자동차 이전등록 대시보드")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f"<div class='kpi-box'><h4>{cur_year}년 누적 거래량</h4><h2>{cur_cnt:,}</h2></div>", unsafe_allow_html=True)
    with c2:
        mom_c, yoy_c = ("red" if mom>0 else "blue"), ("red" if yoy>0 else "blue")
        st.markdown(f"<div class='kpi-box'><h4>{cur_month}월 거래량</h4><h2>{cur_cnt:,}</h2><div><span style='color:{mom_c}'>{mom:+.1f}% MoM</span> | <span style='color:{yoy_c}'>{yoy:+.1f}% YoY</span></div></div>", unsafe_allow_html=True)
    with c3:
        r_mom_c = "red" if ratio_mom>0 else "blue"
        st.markdown(f"<div class='kpi-box'><h4>중고차 비중</h4><h2>{ratio_cur:.1f}%</h2><div><span style='color:{r_mom_c}'>{ratio_mom:+.1f}%p MoM</span></div></div>", unsafe_allow_html=True)

    # 5. 필터 영역
    st.markdown('<div class="filter-box">', unsafe_allow_html=True)
    f1, f2, f3 = st.columns([1, 1, 0.6])
    with f1: start_p = st.selectbox("시작 연월", periods["연월번호"], format_func=lambda x: period_to_label[x])
    with f2: end_p = st.selectbox("종료 연월", periods["연월번호"], index=len(periods)-1, format_func=lambda x: period_to_label[x])
    
    market_type = st.radio("시장 구분 선택", ["전체","중고차시장","유효시장","마케팅"], horizontal=True, help="각 시장별 정의에 따라 데이터를 필터링합니다.")
    
    where = f"연월번호 BETWEEN {start_p} AND {end_p}"
    if market_type != "전체": where += f" AND {market_type}=1"

    with f3:
        excel_clicked = st.button("📥 엑셀 리포트 생성")
    st.markdown("</div>", unsafe_allow_html=True)

    # 6. 엑셀 생성 (메모리 절약형 로직)
    if excel_clicked:
        with st.spinner("메모리 최적화하며 엑셀 생성 중..."):
            # 필요한 컬럼만 최소한으로 가져와서 메모리 확보
            df_ex = con.execute(f"SELECT 연월라벨, 이전등록유형, 나이, 성별, 주행거리_범위, 취득금액_범위, \"시/도\", \"구/군\" FROM df WHERE {where}").df()
            df_ex.loc[df_ex["나이"] == "법인및사업자", "성별"] = "법인및사업자"
            
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            with pd.ExcelWriter(tmp.name, engine="xlsxwriter") as w:
                df_ex.pivot_table(index="연월라벨", columns="이전등록유형", aggfunc="size", fill_value=0).to_excel(w, sheet_name="이전등록유형_분포")
                df_ex.pivot_table(index=["나이", "성별"], columns="연월라벨", aggfunc="size", fill_value=0).to_excel(w, sheet_name="연령성별_분포")
                for col, s_name in zip(["주행거리_범위", "취득금액_범위", "시/도"], ["주행거리_분포", "취득금액_분포", "시도별_분포"]):
                    df_ex.pivot_table(index=col, columns="연월라벨", aggfunc="size", fill_value=0).to_excel(w, sheet_name=s_name)
            
            with open(tmp.name, "rb") as f:
                st.download_button("✅ 엑셀 다운로드", f, file_name=f"REPORT_{market_type}.xlsx")

    # 7. 그래프 영역 (120k 방지)
    g1 = con.execute(f"SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 이전등록유형 ORDER BY 연월번호").df()
    g_total = g1.groupby("연월라벨")["건수"].sum().reset_index()
    fig1 = go.Figure()
    fig1.add_bar(x=g_total["연월라벨"], y=g_total["건수"], name="전체", opacity=0.3, text=g_total["건수"], textposition='outside', texttemplate='<b>%{text:,}</b>', textfont_size=25)
    for t in g1["이전등록유형"].unique():
        d = g1[g1["이전등록유형"]==t]
        fig1.add_scatter(x=d["연월라벨"], y=d["건수"], mode="lines+markers", name=str(t))
    fig1.update_layout(yaxis=dict(tickformat=",d"), margin=dict(t=50))
    st.markdown("<div class='graph-box'><div class='graph-header'><h3>월별 이전등록유형 추이</h3></div></div>", unsafe_allow_html=True)
    st.plotly_chart(fig1, use_container_width=True)

    # AP 추이 (유효시장 대비)
    valid_m = con.execute(f"SELECT 연월번호, 연월라벨, COUNT(*) AS 유효시장건수 FROM df WHERE 유효시장=1 GROUP BY 연월번호, 연월라벨").df()
    df_ap_m = pd.merge(df_ap, valid_m, on=["연월번호","연월라벨"], how="inner")
    if not df_ap_m.empty:
        df_ap_m["AP비중"] = df_ap_m["AP"]/df_ap_m["유효시장건수"]*100
        ap_max = df_ap_m["AP"].max() or 1
        ratio_max = df_ap_m["AP비중"].max() or 1
        df_ap_m["AP비중_시각화"] = (df_ap_m["AP비중"]/ratio_max) * ap_max * 1.6
        fig_ap = go.Figure()
        fig_ap.add_bar(x=df_ap_m["연월라벨"], y=df_ap_m["AP"], name="AP 판매량", text=df_ap_m["AP"], textposition='outside', texttemplate='<b>%{text:,}</b>', textfont_size=15)
        fig_ap.add_scatter(x=df_ap_m["연월라벨"], y=df_ap_m["AP비중_시각화"], mode="lines+markers+text", text=df_ap_m["AP비중"].round(2).astype(str) + "%", textposition="top center", textfont=dict(size=12, color="red"), name="AP 비중 (%)")
        fig_ap.update_layout(yaxis=dict(tickformat=",d"))
        st.markdown("<div class='graph-box'><div class='graph-header'><h3>AP 월별 추이 (유효시장 대비)</h3></div></div>", unsafe_allow_html=True)
        st.plotly_chart(fig_ap, use_container_width=True)

    # 연령/성별
    age_data = con.execute(f"SELECT 나이, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 나이 ORDER BY 나이").df()
    gender_data = con.execute(f"SELECT 성별, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 성별").df()
    st.markdown("<div class='graph-box'><div class='graph-header'><h3>연령·성별 현황</h3></div></div>", unsafe_allow_html=True)
    c_age, c_gender = st.columns([4, 2])
    with c_age:
        fig_age = px.bar(age_data, x="건수", y="나이", orientation="h", text_auto=',.0f')
        fig_age.update_traces(texttemplate='<b>%{text}</b>', textposition='outside', textfont_size=18)
        fig_age.update_layout(xaxis=dict(tickformat=",d"))
        st.plotly_chart(fig_age, use_container_width=True)
    with c_gender:
        fig_gender = px.pie(gender_data, values="건수", names="성별", hole=0.5)
        st.plotly_chart(fig_gender, use_container_width=True)

else:
    st.info("데이터 로딩 중...")
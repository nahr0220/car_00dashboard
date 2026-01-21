# ===============================================================
# 자동차 이전등록 대시보드 (최종 최적화: 연산 분산형)
# ===============================================================

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path
import tempfile
import os

# 1. 페이지 설정
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

# 2. 데이터 연결 및 뷰 생성 (메모리 제한 512MB로 더 보수적 설정)
@st.cache_resource
def get_con():
    con = duckdb.connect(database=":memory:")
    con.execute("SET memory_limit = '512MB'") 
    files = sorted(Path("data").glob("output_*분기.csv"))
    if not files: return None
    file_list_sql = "[" + ",".join(f"'{str(f)}'" for f in files) + "]"
    con.execute(f"CREATE VIEW df AS SELECT *, 년도*100 + 월 AS 연월번호, CAST(년도 AS VARCHAR)||'-'||LPAD(CAST(월 AS VARCHAR),2,'0') AS 연월라벨 FROM read_csv_auto({file_list_sql})")
    return con

con = get_con()

# AP 데이터 로드
try:
    df_ap = pd.read_excel("data/AP Sales Summary.xlsx", skiprows=1)
    df_ap.columns = ["년도","월","AP"]
    df_ap = df_ap[df_ap["년도"]>=2024]
    df_ap["연월번호"] = df_ap["년도"]*100 + df_ap["월"]
    df_ap["연월라벨"] = df_ap["년도"].astype(str) + "-" + df_ap["월"].astype(str).str.zfill(2)
except:
    df_ap = pd.DataFrame(columns=["연월번호", "연월라벨", "AP"])

# 3. 기간 설정
periods = con.execute('SELECT DISTINCT "연월번호", "연월라벨" FROM df ORDER BY "연월번호"').df() if con else pd.DataFrame()

if not periods.empty:
    cur_p = int(periods["연월번호"].max())
    p_to_l = dict(zip(periods["연월번호"], periods["연월라벨"]))
    cur_y, cur_m = divmod(cur_p, 100)
    prev_p = (cur_y*100+cur_m-1) if cur_m>1 else ((cur_y-1)*100+12)
    yoy_p = (cur_y-1)*100+cur_m

    # KPI 쿼리
    c_cnt = con.execute(f"SELECT COUNT(*) FROM df WHERE 연월번호={cur_p}").fetchone()[0]
    p_cnt = con.execute(f"SELECT COUNT(*) FROM df WHERE 연월번호={prev_p}").fetchone()[0] or 1
    y_cnt = con.execute(f"SELECT COUNT(*) FROM df WHERE 연월번호={yoy_p}").fetchone()[0] or 1
    u_cur = con.execute(f"SELECT COUNT(*) FROM df WHERE 연월번호={cur_p} AND 중고차시장=1").fetchone()[0]
    u_prev = con.execute(f"SELECT COUNT(*) FROM df WHERE 연월번호={prev_p} AND 중고차시장=1").fetchone()[0]

    mom, yoy = (c_cnt-p_cnt)/p_cnt*100, (c_cnt-y_cnt)/y_cnt*100
    r_cur = u_cur/c_cnt*100 if c_cnt else 0
    r_mom = r_cur - (u_prev/p_cnt*100 if p_cnt else 0)

    # 4. KPI UI
    st.markdown("## 자동차 이전등록 대시보드")
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(f"<div class='kpi-box'><h4>{cur_y}년 누적 거래량</h4><h2>{c_cnt:,}</h2></div>", unsafe_allow_html=True)
    with c2:
        m_c, y_c = ("red" if mom>0 else "blue"), ("red" if yoy>0 else "blue")
        st.markdown(f"<div class='kpi-box'><h4>{cur_m}월 거래량</h4><h2>{c_cnt:,}</h2><div><span style='color:{m_c}'>{mom:+.1f}% MoM</span> | <span style='color:{y_c}'>{yoy:+.1f}% YoY</span></div></div>", unsafe_allow_html=True)
    with c3:
        rm_c = "red" if r_mom>0 else "blue"
        st.markdown(f"<div class='kpi-box'><h4>중고차 비중</h4><h2>{r_cur:.1f}%</h2><div><span style='color:{rm_c}'>{r_mom:+.1f}%p MoM</span></div></div>", unsafe_allow_html=True)

    # 5. 필터 영역
    st.markdown('<div class="filter-box">', unsafe_allow_html=True)
    f1, f2, f3 = st.columns([1, 1, 0.6])
    with f1: s_p = st.selectbox("시작 연월", periods["연월번호"], format_func=lambda x: p_to_l[x])
    with f2: e_p = st.selectbox("종료 연월", periods["연월번호"], index=len(periods)-1, format_func=lambda x: p_to_l[x])
    m_type = st.radio("시장 구분", ["전체","중고차시장","유효시장","마케팅"], horizontal=True)
    
    where = f"연월번호 BETWEEN {s_p} AND {e_p}"
    if m_type != "전체": where += f" AND {m_type}=1"

    with f3:
        excel_btn = st.button("📥 엑셀 리포트 생성")
    st.markdown("</div>", unsafe_allow_html=True)

    # 6. 엑셀 생성 (속도와 안전의 절충안)
    if excel_btn:
        with st.spinner("엑셀 생성 중..."):
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
            
            # [수정] 모든 시트에 필요한 컬럼만 딱 한 번만 쿼리 (속도 업!)
            needed_cols = ["연월라벨", "이전등록유형", "나이", "성별", "주행거리_범위", "취득금액_범위", "\"시/도\"", "\"구/군\""]
            df_ex = con.execute(f"SELECT {', '.join(needed_cols)} FROM df WHERE {where}").df()
            
            # 법인 데이터 전처리 (한 번만 수행)
            if "나이" in df_ex.columns:
                df_ex.loc[df_ex["나이"] == "법인및사업자", "성별"] = "법인및사업자"

            with pd.ExcelWriter(tmp.name, engine="xlsxwriter") as w:
                # 메모리에 올라온 df_ex를 활용해 6개 시트 순식간에 작성
                df_ex.pivot_table(index="연월라벨", columns="이전등록유형", aggfunc="size", fill_value=0).to_excel(w, sheet_name="이전등록유형_분포")
                df_ex.pivot_table(index=["나이", "성별"], columns="연월라벨", aggfunc="size", fill_value=0).to_excel(w, sheet_name="연령성별_분포")
                
                for col, s_name in zip(["주행거리_범위", "취득금액_범위", "\"시/도\""], ["주행거리", "취득금액", "지역"]):
                    clean_col = col.replace('"', '') # 쿼리용 따옴표 제거
                    if clean_col in df_ex.columns:
                        df_ex.pivot_table(index=clean_col, columns="연월라벨", aggfunc="size", fill_value=0).to_excel(w, sheet_name=s_name)
                
                if "시/도" in df_ex.columns and "구/군" in df_ex.columns:
                    df_ex.pivot_table(index=["시/도", "구/군"], columns="연월라벨", aggfunc="size", fill_value=0).to_excel(w, sheet_name="상세지역")

            with open(tmp.name, "rb") as f:
                st.download_button("✅ 다운로드 받기", f, file_name=f"REPORT_{m_type}.xlsx")

    # 7. 그래프 영역 (생략 없이 모두 포함)
    # 월별 추이
    g1 = con.execute(f"SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 이전등록유형 ORDER BY 연월번호").df()
    g_tot = g1.groupby("연월라벨")["건수"].sum().reset_index()
    fig1 = go.Figure()
    fig1.add_bar(x=g_tot["연월라벨"], y=g_tot["건수"], name="전체", opacity=0.3, text=g_tot["건수"], textposition='outside', texttemplate='<b>%{text:,}</b>', textfont_size=25)
    for t in g1["이전등록유형"].unique():
        d = g1[g1["이전등록유형"]==t]
        fig1.add_scatter(x=d["연월라벨"], y=d["건수"], mode="lines+markers", name=str(t))
    fig1.update_layout(yaxis=dict(tickformat=",d"), margin=dict(t=50))
    st.markdown("<div class='graph-box'><div class='graph-header'><h3>월별 이전등록유형 추이</h3></div></div>", unsafe_allow_html=True)
    st.plotly_chart(fig1, use_container_width=True)

    # AP 추이
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
    age_d = con.execute(f"SELECT 나이, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 나이 ORDER BY 나이").df()
    gen_d = con.execute(f"SELECT 성별, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 성별").df()
    st.markdown("<div class='graph-box'><div class='graph-header'><h3>연령·성별 현황</h3></div></div>", unsafe_allow_html=True)
    ca, cg = st.columns([4, 2])
    with ca:
        f_age = px.bar(age_d, x="건수", y="나이", orientation="h", text_auto=',.0f')
        f_age.update_traces(texttemplate='<b>%{text}</b>', textposition='outside', textfont_size=18)
        f_age.update_layout(xaxis=dict(tickformat=",d"))
        st.plotly_chart(f_age, use_container_width=True)
    with cg:
        f_gen = px.pie(gen_d, values="건수", names="성별", hole=0.5)
        st.plotly_chart(f_gen, use_container_width=True)

    # 연령대 추이
    age_l = con.execute(f"SELECT 연월라벨, 나이, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 연월번호, 연월라벨, 나이 ORDER BY 연월번호").df()
    f_age_l = px.line(age_l, x="연월라벨", y="건수", color="나이", markers=True)
    f_age_l.update_layout(yaxis=dict(tickformat=",d"))
    st.markdown("<div class='graph-box'><div class='graph-header'><h3>월별 연령대별 추이</h3></div></div>", unsafe_allow_html=True)
    st.plotly_chart(f_age_l, use_container_width=True)
else:
    st.info("데이터 로딩 중...")
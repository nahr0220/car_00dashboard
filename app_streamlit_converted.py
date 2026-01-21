# =============================================================== 
# 자동차 이전등록 대시보드 (KPI + 엑셀 다운로드 완벽 복구 버전) 
# =============================================================== 
import duckdb 
import pandas as pd 
import plotly.express as px 
import plotly.graph_objects as go 
import streamlit as st 
from pathlib import Path 
import tempfile 
import os 

# --------------------------------------------------------------- # Page config # --------------------------------------------------------------- 
st.set_page_config(page_title="자동차 이전등록 대시보드", layout="wide") 
st.markdown(""" <style> .stApp { max-width:1200px; margin:0 auto; padding:20px 40px; background:#fff; } #MainMenu, footer, header { visibility:hidden; } .kpi-box { background:#F8F8F8; padding:22px; border-radius:10px; text-align:center; height:150px; display:flex; flex-direction:column; justify-content:center; } .filter-box,.graph-box { background:#EDF4FF; border-radius:12px; margin-bottom:20px; } .graph-header { background:#E3F2FD; padding:16px; border-radius:10px; } </style> """, unsafe_allow_html=True) 

@st.cache_resource 
def get_con(): 
    try: 
        con = duckdb.connect(database=":memory:") 
        con.execute("SET memory_limit = '2GB'") 
        files = sorted(Path("data").glob("output_*분기.csv")) 
        if not files: 
            st.error("❌ data 폴더에 output_*.csv 파일이 없습니다!") 
            return None 
        file_list_sql = "[" + ",".join(f"'{str(f)}'" for f in files) + "]" 
        con.execute(f""" CREATE VIEW df AS SELECT *, 년도*100 + 월 AS 연월번호, CAST(년도 AS VARCHAR)||'-'||LPAD(CAST(월 AS VARCHAR),2,'0') AS 연월라벨 FROM read_csv_auto({file_list_sql}) """) 
        return con 
    except Exception as e: 
        st.error(f"데이터베이스 연결 실패: {e}") 
        return None 

con = get_con() 
if con is None: st.stop() 

# --------------------------------------------------------------- # AP data # --------------------------------------------------------------- 
try: 
    df_ap = pd.read_excel("data/AP Sales Summary.xlsx", skiprows=1) 
    df_ap.columns = ["년도","월","AP"] 
    df_ap = df_ap[df_ap["년도"]>=2024] 
    df_ap["연월번호"] = df_ap["년도"]*100+df_ap["월"] 
    df_ap["연월라벨"] = df_ap["년도"].astype(str)+"-"+df_ap["월"].astype(str).str.zfill(2) 
except: 
    df_ap = pd.DataFrame(columns=["연월번호", "연월라벨", "AP"]) 

periods = con.execute('SELECT DISTINCT "연월번호", "연월라벨" FROM df ORDER BY "연월번호"').df() 
if periods.empty: st.stop()
period_to_label = dict(zip(periods["연월번호"], periods["연월라벨"])) 

# --------------------------------------------------------------- # Filters # --------------------------------------------------------------- 
st.markdown("<h1 style='font-size:36px;'>자동차 이전등록 대시보드</h1>", unsafe_allow_html=True) 
st.markdown('<div class="filter-box">', unsafe_allow_html=True) 
f1, f2, f3 = st.columns([1, 1, 0.6]) 

with f1: start_p = st.selectbox("시작 연월", periods["연월번호"], format_func=lambda x: period_to_label.get(x, str(x))) 
with f2: end_p = st.selectbox("종료 연월", periods["연월번호"], index=len(periods)-1, format_func=lambda x: period_to_label.get(x, str(x))) 

if start_p is None or end_p is None: st.stop()
if start_p > end_p:
    st.error("⚠️ 시작 연월이 종료 연월보다 큽니다. 기간을 다시 선택하세요.")
    st.stop()

where = f"연월번호 BETWEEN {start_p} AND {end_p}" 
market_help_msg = """**출처: 국토교통부 자료**
- **전체**: 국토교통부의 자동차 이전 데이터 전체 
- **중고차시장**: 개인거래 + 매도 + 상사이전 + 알선
- **유효시장**: 매도 + 상사이전 + 알선
- **마케팅**: 매매업자거래이전 중 일반소유용 건""" 
market_type = st.radio("시장 구분 선택", ["전체","중고차시장","유효시장","마케팅"], horizontal=True, help=market_help_msg) 
if market_type != "전체": where += f" AND {market_type}=1" 

# --------------------------------------------------------------- # KPI & Excel Download # --------------------------------------------------------------- 
def safe_query(q):
    res = con.execute(q).fetchone()
    return res[0] if res and res[0] is not None else 0

total_range_cnt = safe_query(f"SELECT COUNT(*) FROM df WHERE {where}")
end_month_where = f"연월번호 = {end_p}"
if market_type != "전체": end_month_where += f" AND {market_type}=1"
end_month_cnt = safe_query(f"SELECT COUNT(*) FROM df WHERE {end_month_where}")
used_cnt = safe_query(f"SELECT COUNT(*) FROM df WHERE {where} AND 중고차시장=1")
ratio_avg = (used_cnt / total_range_cnt * 100) if total_range_cnt > 0 else 0

c1, c2, c3 = st.columns(3) 
with c1: st.markdown(f"<div class='kpi-box'><h4>선택 기간 누적 거래량</h4><h2>{total_range_cnt:,}건</h2></div>", unsafe_allow_html=True) 
with c2: st.markdown(f"<div class='kpi-box'><h4>{period_to_label.get(end_p)} 거래량</h4><h2>{end_month_cnt:,}건</h2></div>", unsafe_allow_html=True) 
with c3: st.markdown(f"<div class='kpi-box'><h4>중고차 시장 비중 (평균)</h4><h2>{ratio_avg:.1f}%</h2></div>", unsafe_allow_html=True) 

# 엑셀 다운로드 (로직 복구 완료)
if st.button("📥 엑셀 생성 및 다운로드", key="excel_download"): 
    try: 
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp: 
            path = tmp.name 
            with pd.ExcelWriter(path, engine="xlsxwriter") as w: 
                con.execute(f"SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 이전등록유형 ORDER BY 연월번호").df().pivot(index="연월라벨", columns="이전등록유형", values="건수").fillna(0).to_excel(w, sheet_name="월별_이전등록유형_건수") 
                age_gender = con.execute(f"SELECT 연월라벨, 나이, 성별, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 나이, 성별 ORDER BY 연월번호").df() 
                age_gender.pivot_table(index="연월라벨", columns=["나이", "성별"], values="건수", fill_value=0).to_excel(w, sheet_name="연령성별_분포") 
                con.execute(f"SELECT 연월라벨, 주행거리_범위, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 주행거리_범위 ORDER BY 연월번호").df().pivot(index="연월라벨", columns="주행거리_범위", values="건수").fillna(0).to_excel(w, sheet_name="주행거리_분포") 
                con.execute(f"SELECT 연월라벨, \"시/도\" AS 시도, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, \"시/도\" ORDER BY 연월번호").df().pivot(index="연월라벨", columns="시도", values="건수").fillna(0).to_excel(w, sheet_name="지역별_분포") 
            with open(path, "rb") as f: 
                st.download_button("✅ 다운로드 클릭", f, file_name=f"이전등록_{period_to_label.get(start_p)}_{period_to_label.get(end_p)}_{market_type}.xlsx") 
    except Exception as e: st.error(f"❌ 엑셀 생성 실패: {e}") 
st.markdown("</div>", unsafe_allow_html=True) 

# --------------------------------------------------------------- # Graph 1: 월별 이전등록유형 추이 # --------------------------------------------------------------- 
st.markdown(f"""
    <div class="graph-box" style="margin-bottom: 0px;">
        <div class="graph-header" style="display: flex; justify-content: space-between; align-items: center; padding: 16px 20px;">
            <h3 style="margin: 0; padding: 0; border: none; font-weight: 800; color: #1E1E1E;">월별 이전등록유형 추이</h3>
            <div title="마우스 오버 시 상세 도움말이 표시됩니다" style="cursor: help; width: 22px; height: 22px; background-color: #5B9BD5; color: white; border-radius: 50%; text-align: center; line-height: 22px; font-size: 14px; font-weight: bold; display: flex; justify-content: center; align-items: center;">?</div>
        </div>
    </div>
""", unsafe_allow_html=True)

g1 = con.execute(f"SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 이전등록유형 ORDER BY 연월번호").df() 
if not g1.empty:
    g_total = g1.groupby("연월라벨")["건수"].sum().reset_index() 
    fig1 = go.Figure() 
    fig1.add_bar( x=g_total["연월라벨"], y=g_total["건수"], name="전체", opacity=0.25, marker_color="#5B9BD5" ) 
    fig1.add_scatter( x=g_total["연월라벨"], y=g_total["건수"] * 1.05, mode="text", text=g_total["건수"], texttemplate="<b>%{text:,}</b>", textfont=dict(size=10, color="#888888"), showlegend=False ) 
    for t in g1["이전등록유형"].unique(): 
        d = g1[g1["이전등록유형"]==t] 
        fig1.add_scatter(x=d["연월라벨"], y=d["건수"], mode="lines+markers", name=str(t)) 
    fig1.update_layout(xaxis=dict(ticks=""), yaxis=dict(ticks="", tickformat=","), margin=dict(t=20)) 
    st.plotly_chart(fig1, width='stretch')

# --------------------------------------------------------------- # Graph 2: AP 월별 추이 # --------------------------------------------------------------- 
st.markdown("<div class='graph-box'><div class='graph-header'><h3 style='font-weight: 800;'>AP 판매 추이 및 유효시장 점유율</h3></div></div>", unsafe_allow_html=True) 
valid_m = con.execute(f"SELECT 연월번호, 연월라벨, COUNT(*) AS 유효시장건수 FROM df WHERE {where} AND 유효시장=1 GROUP BY 연월번호, 연월라벨").df() 
df_ap_filtered = df_ap[(df_ap["연월번호"] >= start_p) & (df_ap["연월번호"] <= end_p)] 
df_ap_m = pd.merge(df_ap_filtered, valid_m, on=["연월번호","연월라벨"], how="inner") 
if not df_ap_m.empty: 
    df_ap_m["AP비중"] = df_ap_m["AP"]/df_ap_m["유효시장건수"]*100 
    ap_max = df_ap_m["AP"].max() if not df_ap_m["AP"].empty else 1 
    ratio_max = df_ap_m["AP비중"].max() if not df_ap_m["AP비중"].empty else 1 
    df_ap_m["AP비중_시각화"] = (df_ap_m["AP비중"]/ratio_max) * ap_max * 1.6 
    fig_ap = go.Figure() 
    fig_ap.add_bar(x=df_ap_m["연월라벨"], y=df_ap_m["AP"], name="AP 판매량", text=df_ap_m["AP"], textposition='outside', texttemplate='<b>%{text:,}</b>') 
    fig_ap.add_scatter(x=df_ap_m["연월라벨"], y=df_ap_m["AP비중_시각화"], mode="lines+markers+text", text=df_ap_m["AP비중"].round(2).astype(str) + "%", textposition="top center", name="AP 비중 (%)", line=dict(color='red', width=1.3)) 
    fig_ap.update_layout(xaxis=dict(ticks=""), yaxis=dict(ticks="", tickformat=","), margin=dict(t=50)) 
    fig_ap.update_yaxes(range=[0, ap_max * 2.0]) 
    st.plotly_chart(fig_ap, width='stretch') 

# --------------------------------------------------------------- # Graph 3 & 4: 연령·성별 # --------------------------------------------------------------- 
st.markdown("<div class='graph-box'><div class='graph-header'><h3 style='font-weight: 800;'>연령·성별 현황</h3></div></div>", unsafe_allow_html=True) 
age_data = con.execute(f"SELECT 나이, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 나이 ORDER BY 나이").df() 
gender_data = con.execute(f"SELECT 성별, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 성별").df() 
if not age_data.empty: 
    c_age, c_gender = st.columns([4, 2]) 
    with c_age: 
        fig_age = px.bar(age_data, x="건수", y="나이", orientation="h") 
        st.plotly_chart(fig_age, width='stretch') 
    with c_gender: 
        fig_gender = px.pie(gender_data, values="건수", names="성별", hole=0.5) 
        st.plotly_chart(fig_gender, width='stretch') 

# --------------------------------------------------------------- # Graph 5: 월별 연령대별 추이 # --------------------------------------------------------------- 
age_line = con.execute(f"SELECT 연월라벨, 나이, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 연월번호, 연월라벨, 나이 ORDER BY 연월번호").df() 
if not age_line.empty: 
    st.markdown("<div class='graph-box'><div class='graph-header'><h3 style='font-weight: 800;'>월별 연령대별 추이</h3></div></div>", unsafe_allow_html=True) 
    fig_age_line = px.line(age_line, x="연월라벨", y="건수", color="나이", markers=True) 
    st.plotly_chart(fig_age_line, width='stretch')
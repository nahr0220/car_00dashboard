# ===============================================================
# 자동차 이전등록 대시보드 (FINAL VISUAL POLISHED)
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
# Page config
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

@st.cache_resource
def get_con():
    con = duckdb.connect(database=":memory:")
    con.execute("SET memory_limit = '2GB'")
    files = sorted(Path("data").glob("output_*분기.csv"))
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
# AP data
# ---------------------------------------------------------------
try:
    df_ap = pd.read_excel("data/AP Sales Summary.xlsx", skiprows=1)
    df_ap.columns = ["년도","월","AP"]
    df_ap = df_ap[df_ap["년도"]>=2024]
    df_ap["연월번호"] = df_ap["년도"]*100+df_ap["월"]
    df_ap["연월라벨"] = df_ap["년도"].astype(str)+"-"+df_ap["월"].astype(str).str.zfill(2)
except:
    df_ap = pd.DataFrame(columns=["연월번호", "연월라벨", "AP"])

periods = con.execute('SELECT DISTINCT "연월번호", "연월라벨" FROM df ORDER BY "연월번호"').df()
period_to_label = dict(zip(periods["연월번호"], periods["연월라벨"]))

# ---------------------------------------------------------------
# KPI
# ---------------------------------------------------------------
cur_period = int(periods["연월번호"].max())
cur_year, cur_month = divmod(cur_period,100)

def get_count(p_sql):
    return con.execute(p_sql).fetchone()[0]

cur_cnt = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={cur_period}")
prev_period = (cur_year*100+cur_month-1) if cur_month>1 else ((cur_year-1)*100+12)
prev_cnt = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={prev_period}")
yoy_period = (cur_year-1)*100+cur_month
yoy_cnt = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={yoy_period}")

mom = (cur_cnt-prev_cnt)/prev_cnt*100 if prev_cnt else 0
yoy = (cur_cnt-yoy_cnt)/yoy_cnt*100 if yoy_cnt else 0
used_cnt = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={cur_period} AND 중고차시장=1")
ratio = used_cnt/cur_cnt*100 if cur_cnt else 0

st.markdown("## 자동차 이전등록 대시보드")
c1,c2,c3 = st.columns(3)
with c1: st.markdown(f"<div class='kpi-box'><h4>{cur_year}년 누적 거래량</h4><h2>{cur_cnt:,}</h2></div>", unsafe_allow_html=True)
with c2:
    mom_c = "red" if mom>0 else "blue"
    yoy_c = "red" if yoy>0 else "blue"
    st.markdown(f"<div class='kpi-box'><h4>{cur_month}월 거래량</h4><h2>{cur_cnt:,}</h2><div><span style='color:{mom_c}'>{mom:+.1f}% MoM</span> | <span style='color:{yoy_c}'>{yoy:+.1f}% YoY</span></div></div>", unsafe_allow_html=True)
with c3: st.markdown(f"<div class='kpi-box'><h4>중고차 비중</h4><h2>{ratio:.1f}%</h2></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------
# Filters & Excel Logic
# ---------------------------------------------------------------
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
f1,f2,f3 = st.columns([1,1,0.6])
with f1: start_p = st.selectbox("시작 연월", periods["연월번호"], format_func=lambda x: period_to_label[x])
with f2: end_p = st.selectbox("종료 연월", periods["연월번호"], index=len(periods)-1, format_func=lambda x: period_to_label[x])

if start_p > end_p: start_p, end_p = end_p, start_p
where = f"연월번호 BETWEEN {start_p} AND {end_p}"
market_type = st.radio("시장 구분", ["전체","중고차시장","유효시장","마케팅"], horizontal=True)
if market_type != "전체": where += f" AND {market_type}=1"

def create_excel_to_disk(g1_data, current_where):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    path = tmp.name
    tmp.close()
    with pd.ExcelWriter(path, engine="xlsxwriter") as w:
        g1_data.pivot(index="연월라벨", columns="이전등록유형", values="건수").fillna(0).to_excel(w, "월별_분포")
        con.execute(f"SELECT 나이, 성별, COUNT(*) AS 건수 FROM df WHERE {current_where} GROUP BY 나이, 성별").df().to_excel(w, "연령성별_분포")
    return path

with f3:
    if st.button("📥 엑셀 생성 및 다운로드"):
        g_excel = con.execute(f"SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 이전등록유형 ORDER BY 연월번호").df()
        path = create_excel_to_disk(g_excel, where)
        with open(path, "rb") as f:
            st.download_button("✅ 준비완료! 파일 다운로드", f, file_name=f"이전등록_{period_to_label[start_p]}_{period_to_label[end_p]}.xlsx")
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------
# Graph 1: 월별 이전등록유형 추이 (글씨 진하게 수정)
# ---------------------------------------------------------------
g1 = con.execute(f"SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 이전등록유형 ORDER BY 연월번호").df()
g_total = g1.groupby("연월라벨")["건수"].sum().reset_index()

fig1 = go.Figure()
fig1.add_bar(
    x=g_total["연월라벨"], 
    y=g_total["건수"], 
    name="전체", 
    opacity=0.3,
    text=g_total["건수"],
    textposition='outside',
    texttemplate='<b>%{text:,}</b>', # <b> 태그로 진하게 설정
    textfont=dict(size=14, color="black",family="Arial")
)
for t in g1["이전등록유형"].unique():
    d = g1[g1["이전등록유형"]==t]
    fig1.add_scatter(x=d["연월라벨"], y=d["건수"], mode="lines+markers", name=str(t))

st.markdown("<div class='graph-box'><div class='graph-header'><h3>월별 이전등록유형 추이</h3></div></div>", unsafe_allow_html=True)
st.plotly_chart(fig1, use_container_width=True)

# ---------------------------------------------------------------
# Graph 2: AP 월별 추이 (비중 위치 한참 위로 수정)
# ---------------------------------------------------------------
valid_m = con.execute(f"SELECT 연월번호, 연월라벨, COUNT(*) AS 유효시장건수 FROM df WHERE 유효시장=1 GROUP BY 연월번호, 연월라벨").df()
df_ap_m = pd.merge(df_ap, valid_m, on=["연월번호","연월라벨"], how="inner")

if not df_ap_m.empty:
    df_ap_m["AP비중"] = df_ap_m["AP"]/df_ap_m["유효시장건수"]*100
    ap_max = df_ap_m["AP"].max() if not df_ap_m["AP"].empty else 1
    ratio_max = df_ap_m["AP비중"].max() if not df_ap_m["AP비중"].empty else 1
    
    # 비중 위치를 막대 최대값보다 더 위쪽(1.2배 지점)으로 보정하여 '한참 위로' 배치
    df_ap_m["AP비중_시각화"] = (df_ap_m["AP비중"]/ratio_max) * ap_max * 1.5

    fig_ap = go.Figure()
    fig_ap.add_bar(
        x=df_ap_m["연월라벨"], 
        y=df_ap_m["AP"], 
        name="AP 판매량", 
        text=df_ap_m["AP"], 
        textposition='outside',
        texttemplate='<b>%{text:,}</b>'
    )
    fig_ap.add_scatter(
        x=df_ap_m["연월라벨"], 
        y=df_ap_m["AP비중_시각화"], 
        mode="lines+markers+text",
        text=df_ap_m["AP비중"].round(2).astype(str) + "%",
        textposition="top center",
        textfont=dict(size=11, color="red"), # 비중 글씨도 진하게
        name="AP 비중 (%)",
        line=dict(color='red', width=1)
    )
    # 상단 여백 확보를 위해 y축 범위 자동 조절
    fig_ap.update_yaxes(range=[0, ap_max * 2]) 
    
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
    fig_age.update_traces(texttemplate='<b>%{text}</b>', textposition='outside')
    st.plotly_chart(fig_age, use_container_width=True)
with c_gender:
    st.plotly_chart(px.pie(gender_data, values="건수", names="성별", hole=0.5), use_container_width=True)

age_line = con.execute(f"SELECT 연월라벨, 나이, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 연월번호, 연월라벨, 나이 ORDER BY 연월번호").df()
st.markdown("<div class='graph-box'><div class='graph-header'><h3>월별 연령대별 추이</h3></div></div>", unsafe_allow_html=True)
st.plotly_chart(px.line(age_line, x="연월라벨", y="건수", color="나이", markers=True), use_container_width=True)
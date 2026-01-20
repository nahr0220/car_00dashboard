
# ===============================================================
# 자동차 이전등록 대시보드
# FULL FINAL ABSOLUTE VERSION
# DuckDB + Disk Excel Download (NO OOM)
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

# ---------------------------------------------------------------
# CSS
# ---------------------------------------------------------------
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
# DuckDB connection
# ---------------------------------------------------------------
@st.cache_resource
def get_con():
    con = duckdb.connect(database=":memory:")
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
df_ap = pd.read_excel("data/AP Sales Summary.xlsx", skiprows=1)
df_ap.columns = ["년도","월","AP"]
df_ap = df_ap[df_ap["년도"]>=2024]
df_ap["연월번호"] = df_ap["년도"]*100+df_ap["월"]
df_ap["연월라벨"] = df_ap["년도"].astype(str)+"-"+df_ap["월"].astype(str).str.zfill(2)

# ---------------------------------------------------------------
# Periods
# ---------------------------------------------------------------
periods = con.execute(
    'SELECT DISTINCT "연월번호", "연월라벨" FROM df ORDER BY "연월번호"'
).df()
period_to_label = dict(zip(periods["연월번호"], periods["연월라벨"]))

# ---------------------------------------------------------------
# KPI
# ---------------------------------------------------------------
cur_period = int(periods["연월번호"].max())
cur_year, cur_month = divmod(cur_period,100)

cur_cnt = con.execute(
    "SELECT COUNT(*) FROM df WHERE 연월번호=?", [cur_period]
).fetchone()[0]

prev_period = (cur_year*100+cur_month-1) if cur_month>1 else ((cur_year-1)*100+12)
prev_cnt = con.execute(
    "SELECT COUNT(*) FROM df WHERE 연월번호=?", [prev_period]
).fetchone()[0]

yoy_period = (cur_year-1)*100+cur_month
yoy_cnt = con.execute(
    "SELECT COUNT(*) FROM df WHERE 연월번호=?", [yoy_period]
).fetchone()[0]

mom = (cur_cnt-prev_cnt)/prev_cnt*100 if prev_cnt else None
yoy = (cur_cnt-yoy_cnt)/yoy_cnt*100 if yoy_cnt else None

used_cnt = con.execute(
    "SELECT COUNT(*) FROM df WHERE 연월번호=? AND 중고차시장=1", [cur_period]
).fetchone()[0]
ratio = used_cnt/cur_cnt*100 if cur_cnt else 0

# ---------------------------------------------------------------
# KPI UI
# ---------------------------------------------------------------
st.markdown("## 자동차 이전등록 대시보드")
c1,c2,c3 = st.columns(3)

with c1:
    st.markdown(f"<div class='kpi-box'><h4>{cur_year}년 누적 거래량</h4><h2>{cur_cnt:,}</h2></div>", unsafe_allow_html=True)

with c2:
    mom_color = "red" if mom and mom>0 else "blue"
    yoy_color = "red" if yoy and yoy>0 else "blue"
    st.markdown(
        f"<div class='kpi-box'><h4>{cur_month}월 거래량</h4><h2>{cur_cnt:,}</h2>"
        f"<div><span style='color:{mom_color}'>{mom:+.1f}% MoM</span> | "
        f"<span style='color:{yoy_color}'>{yoy:+.1f}% YoY</span></div></div>",
        unsafe_allow_html=True
    )

with c3:
    st.markdown(f"<div class='kpi-box'><h4>중고차 비중</h4><h2>{ratio:.1f}%</h2></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------
# Filters + Excel button
# ---------------------------------------------------------------
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
f1,f2,f3 = st.columns([1,1,0.6])

with f1:
    start_p = st.selectbox("시작 연월", periods["연월번호"], format_func=lambda x: period_to_label[x])
with f2:
    end_p = st.selectbox("종료 연월", periods["연월번호"], index=len(periods)-1,
                         format_func=lambda x: period_to_label[x])
with f3:
    excel_clicked = st.button("📥 엑셀 생성")

market = st.radio("시장 구분", ["전체","중고차시장","유효시장","마케팅"], horizontal=True)
st.markdown("</div>", unsafe_allow_html=True)

if start_p>end_p:
    start_p,end_p = end_p,start_p

where = f"연월번호 BETWEEN {start_p} AND {end_p}"
if market!="전체":
    where += f" AND {market}=1"

# ---------------------------------------------------------------
# Graph 1: 월별 이전등록유형 추이
# ---------------------------------------------------------------
g1 = con.execute(f"""
    SELECT 연월번호, 연월라벨, 이전등록유형, COUNT(*) AS 건수
    FROM df WHERE {where}
    GROUP BY 연월번호, 연월라벨, 이전등록유형
    ORDER BY 연월번호
""").df()

g_total = con.execute(f"""
    SELECT 연월번호, 연월라벨, COUNT(*) AS 전체건수
    FROM df WHERE {where}
    GROUP BY 연월번호, 연월라벨
    ORDER BY 연월번호
""").df()

fig1 = go.Figure()
fig1.add_bar(x=g_total["연월라벨"], y=g_total["전체건수"], name="전체", opacity=0.6)
for t in g1["이전등록유형"].unique():
    d = g1[g1["이전등록유형"]==t]
    fig1.add_scatter(x=d["연월라벨"], y=d["건수"], mode="lines+markers", name=str(t))

st.markdown("<div class='graph-box'><div class='graph-header'><h3>월별 이전등록유형 추이</h3></div></div>", unsafe_allow_html=True)
st.plotly_chart(fig1, use_container_width=True)

# ---------------------------------------------------------------
# Graph 2: AP 월별 추이
# ---------------------------------------------------------------
valid_m = con.execute("""
    SELECT 연월번호, 연월라벨, COUNT(*) AS 유효시장건수
    FROM df WHERE 유효시장=1
    GROUP BY 연월번호, 연월라벨
""").df()

df_ap_m = pd.merge(df_ap, valid_m, on=["연월번호","연월라벨"], how="left")
df_ap_m["AP비중"] = df_ap_m["AP"]/df_ap_m["유효시장건수"]*100

ap_max = df_ap_m["AP"].max()
ratio_max = df_ap_m["AP비중"].max()
df_ap_m["AP비중_시각화"] = (df_ap_m["AP비중"]/ratio_max)*ap_max*1.5

fig_ap = go.Figure()
fig_ap.add_bar(x=df_ap_m["연월라벨"], y=df_ap_m["AP"], name="AP")
fig_ap.add_scatter(
    x=df_ap_m["연월라벨"],
    y=df_ap_m["AP비중_시각화"],
    mode="lines+markers+text",
    text=df_ap_m["AP비중"].round(2).astype(str)+"%",
    name="AP 비중"
)

st.markdown("<div class='graph-box'><div class='graph-header'><h3>AP 월별 추이</h3></div></div>", unsafe_allow_html=True)
st.plotly_chart(fig_ap, use_container_width=True)

# ---------------------------------------------------------------
# Graph 3: 연령·성별
# ---------------------------------------------------------------
df_person = con.execute(f"""
    SELECT 나이, 성별 FROM df WHERE {where} AND 나이!='법인및사업자'
""").df()

age = df_person["나이"].value_counts().reset_index()
age.columns = ["나이","건수"]
fig_age = px.bar(age, x="건수", y="나이", orientation="h")

gender = df_person["성별"].value_counts().reset_index()
gender.columns = ["성별","건수"]
fig_gender = px.pie(gender, values="건수", names="성별", hole=0.5)

st.markdown("<div class='graph-box'><div class='graph-header'><h3>연령·성별 현황</h3></div></div>", unsafe_allow_html=True)
c_age,c_gender = st.columns([4,1.5])
c_age.plotly_chart(fig_age, use_container_width=True)
c_gender.plotly_chart(fig_gender, use_container_width=True)

# ---------------------------------------------------------------
# Graph 4: 월별 연령대별 추이
# ---------------------------------------------------------------
age_line = con.execute(f"""
    SELECT 연월번호, 연월라벨, 나이, COUNT(*) AS 건수
    FROM df WHERE {where} AND 나이!='법인및사업자'
    GROUP BY 연월번호, 연월라벨, 나이
    ORDER BY 연월번호
""").df()

fig_age_line = px.line(age_line, x="연월라벨", y="건수", color="나이", markers=True)

st.markdown("<div class='graph-box'><div class='graph-header'><h3>월별 연령대별 추이</h3></div></div>", unsafe_allow_html=True)
st.plotly_chart(fig_age_line, use_container_width=True)

# ---------------------------------------------------------------
# Excel generation (DISK based)
# ---------------------------------------------------------------
def create_excel_to_disk():
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
    path = tmp.name
    tmp.close()

    with pd.ExcelWriter(path, engine="xlsxwriter") as w:
        con.execute(f"""
            SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수
            FROM df WHERE {where}
            GROUP BY 연월라벨, 이전등록유형
        """).df().pivot(
            index="연월라벨",
            columns="이전등록유형",
            values="건수"
        ).fillna(0).to_excel(w, "월별_분포")

        con.execute(f"""
            SELECT 나이, 성별, COUNT(*) AS 건수
            FROM df WHERE {where}
            GROUP BY 나이, 성별
        """).df().pivot(
            index=["나이","성별"],
            values="건수"
        ).fillna(0).to_excel(w, "연령성별대_분포")

    return path

if "excel_path" not in st.session_state:
    st.session_state.excel_path = None
    st.session_state.excel_name = None

if excel_clicked:
    with st.spinner("엑셀 생성 중..."):
        st.session_state.excel_path = create_excel_to_disk()
        st.session_state.excel_name = f"이전등록_{period_to_label[start_p]}_{period_to_label[end_p]}_{market}.xlsx"

if st.session_state.excel_path and os.path.exists(st.session_state.excel_path):
    with open(st.session_state.excel_path, "rb") as f:
        st.download_button(
            "⬇️ XLSX 다운로드",
            f,
            file_name=st.session_state.excel_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

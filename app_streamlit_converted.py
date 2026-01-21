# ===============================================================
# 자동차 이전등록 대시보드 (KPI MoM + HELP TOOLTIP) - FINAL
# ===============================================================

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path
import tempfile

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

# ---------------------------------------------------------------
# DB
# ---------------------------------------------------------------
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
    df_ap["연월번호"] = df_ap["년도"]*100 + df_ap["월"]
    df_ap["연월라벨"] = df_ap["년도"].astype(str)+"-"+df_ap["월"].astype(str).str.zfill(2)
except:
    df_ap = pd.DataFrame(columns=["연월번호","연월라벨","AP"])

# ---------------------------------------------------------------
# Periods
# ---------------------------------------------------------------
periods = con.execute(
    'SELECT DISTINCT 연월번호, 연월라벨 FROM df ORDER BY 연월번호'
).df()
period_to_label = dict(zip(periods["연월번호"], periods["연월라벨"]))

# ---------------------------------------------------------------
# KPI (단일 블록)
# ---------------------------------------------------------------
def get_count(sql):
    return con.execute(sql).fetchone()[0]

if periods.empty:
    cur_year = cur_month = None
    cur_cnt = prev_cnt = yoy_cnt = 0
    ratio_cur = ratio_mom = mom = yoy = 0
else:
    cur_period = int(periods["연월번호"].max())
    cur_year, cur_month = divmod(cur_period, 100)

    cur_cnt = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={cur_period}")

    prev_period = (
        cur_year*100 + cur_month - 1
        if cur_month > 1 else (cur_year-1)*100 + 12
    )
    prev_cnt = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={prev_period}")

    yoy_period = (cur_year-1)*100 + cur_month
    yoy_cnt = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={yoy_period}")

    used_cur = get_count(
        f"SELECT COUNT(*) FROM df WHERE 연월번호={cur_period} AND 중고차시장=1"
    )
    used_prev = get_count(
        f"SELECT COUNT(*) FROM df WHERE 연월번호={prev_period} AND 중고차시장=1"
    )

    ratio_cur = used_cur / cur_cnt * 100 if cur_cnt else 0
    ratio_prev = used_prev / prev_cnt * 100 if prev_cnt else 0

    mom = (cur_cnt - prev_cnt) / prev_cnt * 100 if prev_cnt else 0
    yoy = (cur_cnt - yoy_cnt) / yoy_cnt * 100 if yoy_cnt else 0
    ratio_mom = ratio_cur - ratio_prev

# ---------------------------------------------------------------
# KPI UI
# ---------------------------------------------------------------
st.markdown("## 자동차 이전등록 대시보드")
c1,c2,c3 = st.columns(3)

with c1:
    st.markdown(
        f"<div class='kpi-box'><h4>{cur_year if cur_year else '-'}년 누적 거래량</h4>"
        f"<h2>{cur_cnt:,}</h2></div>",
        unsafe_allow_html=True
    )

with c2:
    st.markdown(
        f"<div class='kpi-box'><h4>{cur_month if cur_month else '-'}월 거래량</h4>"
        f"<h2>{cur_cnt:,}</h2>"
        f"<div>{mom:+.1f}% MoM | {yoy:+.1f}% YoY</div></div>",
        unsafe_allow_html=True
    )

with c3:
    st.markdown(
        f"<div class='kpi-box'><h4>중고차 비중</h4>"
        f"<h2>{ratio_cur:.1f}%</h2>"
        f"<div>{ratio_mom:+.1f}%p MoM</div></div>",
        unsafe_allow_html=True
    )

# ---------------------------------------------------------------
# Filters
# ---------------------------------------------------------------
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
f1,f2,f3 = st.columns([1,1,0.6])

with f1:
    start_p = st.selectbox("시작 연월", periods["연월번호"], format_func=lambda x: period_to_label[x])
with f2:
    end_p = st.selectbox("종료 연월", periods["연월번호"], index=len(periods)-1,
                         format_func=lambda x: period_to_label[x])

if start_p > end_p:
    start_p, end_p = end_p, start_p

where = f"연월번호 BETWEEN {start_p} AND {end_p}"

market_help = """
- 전체
- 중고차시장
- 유효시장
- 마케팅
"""
market_type = st.radio(
    "시장 구분 선택",
    ["전체","중고차시장","유효시장","마케팅"],
    horizontal=True,
    help=market_help
)

if market_type != "전체":
    where += f" AND {market_type}=1"

# ---------------------------------------------------------------
# Excel download (5 sheets 유지)
# ---------------------------------------------------------------
with f3:
    if st.button("📥 엑셀 생성 및 다운로드"):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        path = tmp.name
        tmp.close()

        with pd.ExcelWriter(path, engine="xlsxwriter") as w:

            # 1. 이전등록유형
            con.execute(f"""
                SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수
                FROM df WHERE {where}
                GROUP BY 연월번호, 연월라벨, 이전등록유형
                ORDER BY 연월번호
            """).df().pivot(
                index="연월라벨", columns="이전등록유형", values="건수"
            ).fillna(0).to_excel(w, sheet_name="월별_이전등록유형")

            # 2. 연령/성별
            con.execute(f"""
                SELECT 연월라벨, 나이, 성별, COUNT(*) AS 건수
                FROM df WHERE {where}
                GROUP BY 연월번호, 연월라벨, 나이, 성별
            """).df().pivot_table(
                index="연월라벨", columns=["나이","성별"],
                values="건수", fill_value=0
            ).to_excel(w, sheet_name="연령성별")

            # 3. 주행거리
            con.execute(f"""
                SELECT 연월라벨, 주행거리_범위, COUNT(*) AS 건수
                FROM df WHERE {where}
                GROUP BY 연월번호, 연월라벨, 주행거리_범위
            """).df().pivot(
                index="연월라벨", columns="주행거리_범위", values="건수"
            ).fillna(0).to_excel(w, sheet_name="주행거리")

            # 4. 취득금액
            con.execute(f"""
                SELECT 연월라벨, 취득금액_범위, COUNT(*) AS 건수
                FROM df WHERE {where}
                GROUP BY 연월번호, 연월라벨, 취득금액_범위
            """).df().pivot(
                index="연월라벨", columns="취득금액_범위", values="건수"
            ).fillna(0).to_excel(w, sheet_name="취득금액")

            # 5. 지역
            con.execute(f"""
                SELECT 연월라벨, "시/도" AS 시도, COUNT(*) AS 건수
                FROM df WHERE {where}
                GROUP BY 연월번호, 연월라벨, "시/도"
            """).df().pivot(
                index="연월라벨", columns="시도", values="건수"
            ).fillna(0).to_excel(w, sheet_name="지역")

        with open(path, "rb") as f:
            st.download_button(
                "✅ 파일 다운로드",
                f,
                file_name=f"이전등록_{period_to_label[start_p]}_{period_to_label[end_p]}.xlsx"
            )

st.markdown("</div>", unsafe_allow_html=True)
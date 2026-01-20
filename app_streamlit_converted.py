
# 자동차 이전등록 대시보드 (Cloud Safe Full Version - DuckDB)
# ------------------------------------------------------------
# 기능 / UI / 그래프 / AP 비중 / 엑셀 다운로드 100% 유지
# 메모리 안정화를 위해 DuckDB 사용

import duckdb
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from io import BytesIO
from pathlib import Path

# ========================================
# 1. 페이지 설정
# ========================================
st.set_page_config(page_title="자동차 이전등록 대시보드", layout="wide")

# ========================================
# 2. CSS (원본 유지)
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
# 3. DuckDB 연결 및 CSV 로딩
# ========================================
@st.cache_resource
def get_con():
    con = duckdb.connect(database=":memory:")
    files = sorted(Path("data").glob("output_*분기.csv"))
    if not files:
        raise FileNotFoundError("CSV 파일이 없습니다.")
    con.execute(
        """
        CREATE VIEW df AS
        SELECT *,
               년도*100 + 월 AS 연월번호,
               CAST(년도 AS VARCHAR) || '-' || LPAD(CAST(월 AS VARCHAR),2,'0') AS 연월라벨
        FROM read_csv_auto(?)
        """, [files]
    )
    return con

con = get_con()

# ========================================
# 4. AP 데이터 (pandas)
# ========================================
df_ap = pd.read_excel("data/AP Sales Summary.xlsx", skiprows=1)
df_ap.columns = ["년도", "월", "AP"]
df_ap = df_ap[df_ap["년도"] >= 2024]
df_ap["연월번호"] = df_ap["년도"] * 100 + df_ap["월"]
df_ap["연월라벨"] = df_ap["년도"].astype(str) + "-" + df_ap["월"].astype(str).str.zfill(2)

# ========================================
# 5. 기간 옵션
# ========================================
periods = con.execute(
    """
    SELECT DISTINCT 연월번호, 연월라벨
    FROM df
    ORDER BY 연월번호
    """
).df()

period_to_label = dict(zip(periods["연월번호"], periods["연월라벨"]))

# ========================================
# 6. KPI
# ========================================
cur_period = int(periods["연월번호"].max())
cur_year, cur_month = divmod(cur_period, 100)

cur_cnt = con.execute(
    "SELECT COUNT(*) FROM df WHERE 연월번호=?", [cur_period]
).fetchone()[0]

ytd_cnt = con.execute(
    "SELECT COUNT(*) FROM df WHERE 년도=? AND 연월번호<=?",
    [cur_year, cur_period]
).fetchone()[0]

used_cnt = con.execute(
    "SELECT COUNT(*) FROM df WHERE 연월번호=? AND 중고차시장=1",
    [cur_period]
).fetchone()[0]

ratio = used_cnt / cur_cnt * 100 if cur_cnt else 0

# KPI UI
st.markdown("## 자동차 이전등록 대시보드")
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown(
        f"""
        <div class="kpi-box">
            <div style="font-size:18px;color:#666;">{cur_year}년 누적 거래량</div>
            <div style="font-size:34px;font-weight:700;">{ytd_cnt:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c2:
    st.markdown(
        f"""
        <div class="kpi-box">
            <div style="font-size:18px;color:#666;">{cur_month}월 거래량</div>
            <div style="font-size:34px;font-weight:700;">{cur_cnt:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c3:
    st.markdown(
        f"""
        <div class="kpi-box">
            <div style="font-size:18px;color:#666;">{cur_month}월 중고차 비중</div>
            <div style="font-size:34px;font-weight:700;">{ratio:.1f}%</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ========================================
# 7. 필터
# ========================================
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
c_sp1, c_sp2 = st.columns(2)

with c_sp1:
    start_period = st.selectbox(
        "시작 연월",
        periods["연월번호"],
        format_func=lambda x: period_to_label[x],
    )

with c_sp2:
    end_period = st.selectbox(
        "종료 연월",
        periods["연월번호"],
        index=len(periods) - 1,
        format_func=lambda x: period_to_label[x],
    )

market = st.radio(
    "시장 구분",
    ["전체", "중고차시장", "유효시장", "마케팅"],
    horizontal=True,
)

# 공통 WHERE 절
where = f"연월번호 BETWEEN {min(start_period, end_period)} AND {max(start_period, end_period)}"
if market != "전체":
    where += f" AND {market}=1"

st.markdown("</div>", unsafe_allow_html=True)

# ========================================
# 8. 월별 이전등록유형 추이
# ========================================
g1 = con.execute(
    f"""
    SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수
    FROM df
    WHERE {where}
    GROUP BY 연월라벨, 이전등록유형
    """
).df()

g_total = con.execute(
    f"""
    SELECT 연월라벨, COUNT(*) AS 전체건수
    FROM df
    WHERE {where}
    GROUP BY 연월라벨
    ORDER BY 연월라벨
    """
).df()

fig1 = go.Figure()
fig1.add_bar(
    x=g_total["연월라벨"],
    y=g_total["전체건수"],
    name="전체 건수",
    opacity=0.65,
    text=g_total["전체건수"],
    texttemplate="%{text:,}",
)

for t in g1["이전등록유형"].unique():
    d = g1[g1["이전등록유형"] == t]
    fig1.add_scatter(
        x=d["연월라벨"],
        y=d["건수"],
        mode="lines+markers",
        name=str(t),
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
# 9. AP 월별 추이 (비중 포함)
# ========================================
valid_m = con.execute(
    """
    SELECT 연월번호, 연월라벨, COUNT(*) AS 유효시장건수
    FROM df
    WHERE 유효시장=1
    GROUP BY 연월번호, 연월라벨
    """
).df()

df_ap_m = pd.merge(df_ap, valid_m, on=["연월번호", "연월라벨"], how="left")
df_ap_m["AP비중"] = df_ap_m["AP"] / df_ap_m["유효시장건수"] * 100

ap_max = df_ap_m["AP"].max()
ratio_max = df_ap_m["AP비중"].max()
df_ap_m["AP비중_시각화"] = (df_ap_m["AP비중"] / ratio_max) * ap_max * 1.5

fig_ap = go.Figure()
fig_ap.add_bar(
    x=df_ap_m["연월라벨"],
    y=df_ap_m["AP"],
    name="AP 판매대수",
    text=df_ap_m["AP"],
    texttemplate="%{text:,}",
    textposition="outside",
)

fig_ap.add_scatter(
    x=df_ap_m["연월라벨"],
    y=df_ap_m["AP비중_시각화"],
    name="AP 비중",
    mode="lines+markers+text",
    text=df_ap_m["AP비중"].round(2).astype(str) + "%",
    textposition="top center",
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
# 10. 엑셀 다운로드
# ========================================
def make_excel():
    df_dl = con.execute(
        f"""
        SELECT 연월라벨, 이전등록유형, 나이, 성별,
               주행거리_범위, 취득금액_범위, 시/도, 구/군
        FROM df
        WHERE {where}
        """
    ).df()

    out = BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as w:
        df_dl.pivot_table(index="연월라벨", columns="이전등록유형", aggfunc="size", fill_value=0).to_excel(w,"월별")
        df_dl.pivot_table(index=["나이","성별"], aggfunc="size", fill_value=0).to_excel(w,"연령성별")
        df_dl.pivot_table(index="주행거리_범위", aggfunc="size", fill_value=0).to_excel(w,"주행거리")
        df_dl.pivot_table(index="취득금액_범위", aggfunc="size", fill_value=0).to_excel(w,"취득금액")
        df_dl.pivot_table(index="시/도", aggfunc="size", fill_value=0).to_excel(w,"지역")
        df_dl.pivot_table(index=["시/도","구/군"], aggfunc="size", fill_value=0).to_excel(w,"상세지역")
    out.seek(0)
    return out

if st.button("엑셀 생성"):
    excel = make_excel()
    st.download_button("⬇️ XLSX", excel, file_name="이전등록_전체.xlsx")

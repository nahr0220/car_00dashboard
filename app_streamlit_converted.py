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
# 2. CSS
# ========================================
st.markdown(
    """
<style>
.stApp { max-width:1200px; margin:auto; padding:20px 40px; }
#MainMenu, footer, header { visibility: hidden; }
.kpi-box {
    background:#F8F8F8; padding:22px; border-radius:10px;
    text-align:center; height:150px;
}
.filter-box, .graph-box {
    background:#EDF4FF; border-radius:12px; margin-bottom:20px;
}
.graph-header {
    background:#E3F2FD; padding:16px; border-radius:10px;
}
</style>
""",
    unsafe_allow_html=True,
)

# ========================================
# 3. 데이터 로드 (메모리 최적화)
# ========================================
@st.cache_data
def load_data():
    dtype_map = {
        "년도": "int16",
        "월": "int8",
        "중고차시장": "int8",
        "유효시장": "int8",
        "마케팅": "int8",
        "성별": "category",
        "나이": "category",
        "이전등록유형": "category",
        "시/도": "category",
        "구/군": "category",
        "주행거리_범위": "category",
        "취득금액_범위": "category",
    }

    data_path = Path("data")
    files = sorted(data_path.glob("output_*분기.csv"))
    if not files:
        raise FileNotFoundError("CSV 없음")

    df = pd.concat(
        [
            pd.read_csv(f, encoding="utf-8-sig", dtype=dtype_map, low_memory=False)
            for f in files
        ],
        ignore_index=True,
    )

    df.columns = df.columns.str.strip()
    df["연월번호"] = df["년도"] * 100 + df["월"]
    df["연월라벨"] = df["년도"].astype(str) + "-" + df["월"].astype(str).str.zfill(2)

    # AP 데이터
    df_ap = pd.read_excel("data/AP Sales Summary.xlsx", skiprows=1)
    df_ap.columns = ["년도", "월", "AP"]
    df_ap = df_ap[df_ap["년도"] >= 2024]
    df_ap["연월번호"] = df_ap["년도"] * 100 + df_ap["월"]
    df_ap["연월라벨"] = (
        df_ap["년도"].astype(str) + "-" + df_ap["월"].astype(str).str.zfill(2)
    )

    # 월별 집계 (그래프용)
    monthly_type = (
        df.groupby(["연월라벨", "이전등록유형"])
        .size()
        .reset_index(name="건수")
    )
    monthly_total = (
        df.groupby("연월라벨")
        .size()
        .reset_index(name="전체건수")
    )

    periods = (
        df[["연월번호", "연월라벨"]]
        .drop_duplicates()
        .sort_values("연월번호")
    )

    return df, df_ap, monthly_type, monthly_total, periods


df, df_ap, g_type, g_total, periods = load_data()
period_to_label = dict(zip(periods["연월번호"], periods["연월라벨"]))

# ========================================
# 4. KPI
# ========================================
cur_period = int(df["연월번호"].max())
cur_year, cur_month = divmod(cur_period, 100)

cur_cnt = (df["연월번호"] == cur_period).sum()
ytd_cnt = ((df["년도"] == cur_year) & (df["연월번호"] <= cur_period)).sum()

# ========================================
# 5. 필터
# ========================================
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
c1, c2, c3 = st.columns([1, 1, 0.6])

with c1:
    start_period = st.selectbox(
        "시작 연월", periods["연월번호"], format_func=lambda x: period_to_label[x]
    )

with c2:
    end_period = st.selectbox(
        "종료 연월",
        periods["연월번호"],
        index=len(periods) - 1,
        format_func=lambda x: period_to_label[x],
    )

market = st.radio(
    "시장",
    ["전체", "중고차시장", "유효시장", "마케팅"],
    horizontal=True,
)

# ========================================
# 6. 필터링 (copy ❌)
# ========================================
df_f = df.loc[
    (df["연월번호"] >= min(start_period, end_period))
    & (df["연월번호"] <= max(start_period, end_period))
]

if market != "전체":
    df_f = df_f[df_f[market] == 1]

# ========================================
# 7. 월별 추이 그래프
# ========================================
fig = go.Figure()
fig.add_bar(
    x=g_total["연월라벨"],
    y=g_total["전체건수"],
    name="전체",
    opacity=0.5,
)

for t in g_type["이전등록유형"].unique():
    d = g_type[g_type["이전등록유형"] == t]
    fig.add_scatter(x=d["연월라벨"], y=d["건수"], mode="lines+markers", name=t)

fig.update_layout(height=420)
st.plotly_chart(fig, use_container_width=True)

# ========================================
# 8. 다운로드 (클릭 시 생성)
# ========================================
def make_excel(df_dl):
    cols = [
        "연월라벨", "이전등록유형", "나이", "성별",
        "주행거리_범위", "취득금액_범위", "시/도", "구/군"
    ]
    df_dl = df_dl[cols]

    out = BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as w:
        df_dl.pivot_table(
            index="연월라벨", columns="이전등록유형", aggfunc="size", fill_value=0
        ).to_excel(w, "월별")
        df_dl.pivot_table(
            index=["나이", "성별"], aggfunc="size", fill_value=0
        ).to_excel(w, "연령성별")
    out.seek(0)
    return out


with c3:
    if st.button("엑셀 생성"):
        excel = make_excel(df_f)
        st.download_button(
            "⬇ XLSX",
            excel,
            file_name="이전등록_다운로드.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

st.markdown("</div>", unsafe_allow_html=True)

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from io import BytesIO
from pathlib import Path

# ========================================
# 1. Page Config
# ========================================
st.set_page_config(page_title="자동차 이전등록 대시보드", layout="wide")

# ========================================
# 2. CSS
# ========================================
st.markdown(
"""
<style>
.stApp { max-width:1200px; margin:auto; padding:20px 40px; }
#MainMenu, footer, header { visibility:hidden; }
.kpi-box {
    background:#F8F8F8; padding:22px; border-radius:10px;
    text-align:center; height:150px;
}
.filter-box,.graph-box {
    background:#EDF4FF; border-radius:12px; margin-bottom:20px;
}
.graph-header {
    background:#E3F2FD; padding:16px; border-radius:10px;
}
</style>
""",
unsafe_allow_html=True
)

# ========================================
# 3. Load Data (MEMORY SAFE)
# ========================================
@st.cache_data
def load_data():
    dtype = {
        "년도": "int16", "월": "int8",
        "중고차시장": "int8", "유효시장": "int8", "마케팅": "int8",
        "성별": "category", "나이": "category",
        "이전등록유형": "category",
        "시/도": "category", "구/군": "category",
        "주행거리_범위": "category",
        "취득금액_범위": "category"
    }

    files = sorted(Path("data").glob("output_*분기.csv"))
    df = pd.concat(
        [pd.read_csv(f, encoding="utf-8-sig", dtype=dtype, low_memory=False)
         for f in files],
        ignore_index=True
    )

    df.columns = df.columns.str.strip()
    df["연월번호"] = df["년도"] * 100 + df["월"]
    df["연월라벨"] = df["년도"].astype(str) + "-" + df["월"].astype(str).str.zfill(2)

    # AP
    ap = pd.read_excel("data/AP Sales Summary.xlsx", skiprows=1)
    ap.columns = ["년도", "월", "AP"]
    ap = ap[ap["년도"] >= 2024]
    ap["연월번호"] = ap["년도"] * 100 + ap["월"]
    ap["연월라벨"] = ap["년도"].astype(str) + "-" + ap["월"].astype(str).str.zfill(2)

    periods = (
        df[["연월번호", "연월라벨"]]
        .drop_duplicates()
        .sort_values("연월번호")
    )

    return df, ap, periods


df, df_ap, periods = load_data()
period_to_label = dict(zip(periods["연월번호"], periods["연월라벨"]))

# ========================================
# 4. KPI
# ========================================
cur_period = int(df["연월번호"].max())
cur_year, cur_month = divmod(cur_period, 100)

cur_cnt = (df["연월번호"] == cur_period).sum()
ytd_cnt = ((df["년도"] == cur_year) & (df["연월번호"] <= cur_period)).sum()

prev_period = (cur_year * 100 + cur_month - 1) if cur_month > 1 else ((cur_year - 1) * 100 + 12)
prev_cnt = (df["연월번호"] == prev_period).sum()
mom = (cur_cnt - prev_cnt) / prev_cnt * 100 if prev_cnt else None

yoy_period = (cur_year - 1) * 100 + cur_month
yoy_cnt = (df["연월번호"] == yoy_period).sum()
yoy = (cur_cnt - yoy_cnt) / yoy_cnt * 100 if yoy_cnt else None

used_cnt = ((df["연월번호"] == cur_period) & (df["중고차시장"] == 1)).sum()
used_ratio = used_cnt / cur_cnt * 100 if cur_cnt else 0

# ========================================
# 5. KPI UI
# ========================================
c1, c2, c3 = st.columns(3)

with c1:
    st.markdown(f"<div class='kpi-box'><h4>{cur_year}년 누적</h4><h2>{ytd_cnt:,}</h2></div>", unsafe_allow_html=True)
with c2:
    st.markdown(
        f"<div class='kpi-box'><h4>{cur_month}월 거래</h4><h2>{cur_cnt:,}</h2>"
        f"<div>{mom:+.1f}% MoM | {yoy:+.1f}% YoY</div></div>",
        unsafe_allow_html=True
    )
with c3:
    st.markdown(
        f"<div class='kpi-box'><h4>중고차 비중</h4><h2>{used_ratio:.1f}%</h2></div>",
        unsafe_allow_html=True
    )

# ========================================
# 6. Filters
# ========================================
st.markdown("<div class='filter-box'>", unsafe_allow_html=True)
f1, f2 = st.columns(2)
with f1:
    start_p = st.selectbox("시작", periods["연월번호"], format_func=lambda x: period_to_label[x])
with f2:
    end_p = st.selectbox("종료", periods["연월번호"], index=len(periods)-1,
                          format_func=lambda x: period_to_label[x])

market = st.radio("시장", ["전체","중고차시장","유효시장","마케팅"], horizontal=True)

df_f = df.loc[
    (df["연월번호"] >= min(start_p, end_p)) &
    (df["연월번호"] <= max(start_p, end_p))
]
if market != "전체":
    df_f = df_f[df_f[market] == 1]

# ========================================
# 7. 월별 이전등록 추이
# ========================================
g_total = df_f.groupby("연월라벨").size().reset_index(name="전체")
g_type = df_f.groupby(["연월라벨","이전등록유형"]).size().reset_index(name="건수")

fig1 = go.Figure()
fig1.add_bar(x=g_total["연월라벨"], y=g_total["전체"], name="전체", opacity=0.6)
for t in g_type["이전등록유형"].unique():
    d = g_type[g_type["이전등록유형"] == t]
    fig1.add_scatter(x=d["연월라벨"], y=d["건수"], mode="lines+markers", name=t)

st.plotly_chart(fig1, use_container_width=True)

# ========================================
# 8. AP 월별 추이
# ========================================
valid = df[df["유효시장"] == 1].groupby(["연월번호","연월라벨"]).size().reset_index(name="유효")
ap_m = pd.merge(df_ap, valid, on=["연월번호","연월라벨"], how="left")
ap_m["AP비중"] = ap_m["AP"] / ap_m["유효"] * 100

fig_ap = go.Figure()
fig_ap.add_bar(x=ap_m["연월라벨"], y=ap_m["AP"], name="AP")
fig_ap.add_scatter(x=ap_m["연월라벨"], y=ap_m["AP비중"], mode="lines+markers", name="AP비중")

st.plotly_chart(fig_ap, use_container_width=True)

# ========================================
# 9. 연령/성별
# ========================================
person = df_f[df_f["나이"] != "법인및사업자"]

age = person["나이"].value_counts().reset_index()
fig_age = px.bar(age, x="count", y="나이", orientation="h")
gender = person["성별"].value_counts().reset_index()
fig_gender = px.pie(gender, values="count", names="성별", hole=0.5)

c1, c2 = st.columns([3,1])
c1.plotly_chart(fig_age, use_container_width=True)
c2.plotly_chart(fig_gender, use_container_width=True)

# ========================================
# 10. 연령대 추이
# ========================================
age_line = person.groupby(["연월라벨","나이"]).size().reset_index(name="건수")
fig_age_line = px.line(age_line, x="연월라벨", y="건수", color="나이", markers=True)
st.plotly_chart(fig_age_line, use_container_width=True)

# ========================================
# 11. Excel Download (ON CLICK)
# ========================================
def make_excel(df_dl):
    cols = [
        "연월라벨","이전등록유형","나이","성별",
        "주행거리_범위","취득금액_범위","시/도","구/군"
    ]
    df_dl = df_dl[cols]
    out = BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as w:
        df_dl.pivot_table(index="연월라벨", columns="이전등록유형", aggfunc="size", fill_value=0).to_excel(w, "월별")
        df_dl.pivot_table(index=["나이","성별"], aggfunc="size", fill_value=0).to_excel(w, "연령성별")
        df_dl.pivot_table(index="주행거리_범위", aggfunc="size", fill_value=0).to_excel(w, "주행거리")
        df_dl.pivot_table(index="취득금액_범위", aggfunc="size", fill_value=0).to_excel(w, "취득금액")
        df_dl.pivot_table(index="시/도", aggfunc="size", fill_value=0).to_excel(w, "지역")
        df_dl.pivot_table(index=["시/도","구/군"], aggfunc="size", fill_value=0).to_excel(w, "상세지역")
    out.seek(0)
    return out

if st.button("엑셀 생성"):
    excel = make_excel(df_f)
    st.download_button("⬇ XLSX", excel, file_name="이전등록_전체.xlsx")
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
st.markdown(""" <style> .stApp { max-width:1200px; margin:0 auto; padding:20px 40px; background:#fff; } .kpi-box { background:#F8F8F8; padding:22px; border-radius:10px; text-align:center; height:150px; display:flex; flex-direction:column; justify-content:center; } .filter-box,.graph-box { background:#EDF4FF; border-radius:12px; margin-bottom:20px; } .graph-header { background:#E3F2FD; padding:16px; border-radius:10px; } h3 { margin:0; font-weight:800; color:#1E1E1E; border:none; } </style> """, unsafe_allow_html=True) 

# 2. 데이터 연결
@st.cache_resource 
def get_con(): 
    try: 
        con = duckdb.connect(database=":memory:") 
        base_path = Path(__file__).parent.absolute() / "data" 
        files = sorted(base_path.glob("output_*분기.csv")) 
        if not files: return None 
        file_list_sql = "[" + ",".join(f"'{str(f.as_posix())}'" for f in files) + "]" 
        con.execute(f"CREATE VIEW df AS SELECT *, 년도*100+월 AS 연월번호, CAST(년도 AS VARCHAR)||'-'||LPAD(CAST(월 AS VARCHAR),2,'0') AS 연월라벨 FROM read_csv_auto({file_list_sql})") 
        return con 
    except: return None 

con = get_con() 
if con is None: 
    st.error("❌ 'data' 폴더에 데이터 파일이 없습니다.")
    st.stop()

# 3. 필터 데이터 준비
periods_df = con.execute('SELECT DISTINCT 연월번호, 연월라벨 FROM df ORDER BY 연월번호').df() 
if periods_df.empty: st.stop()
period_list = periods_df["연월번호"].tolist()
period_labels = dict(zip(periods_df["연월번호"], periods_df["연월라벨"])) 

# --------------------------------------------------------------- # 4. Filters
st.markdown("<h1 style='font-size:36px;'>자동차 이전등록 대시보드</h1>", unsafe_allow_html=True) 
st.markdown('<div class="filter-box">', unsafe_allow_html=True) 
f1, f2, f3 = st.columns([1, 1, 0.6]) 

with f1: start_p = st.selectbox("시작 연월", period_list, format_func=lambda x: period_labels.get(x)) 
with f2: end_p = st.selectbox("종료 연월", period_list, index=len(period_list)-1, format_func=lambda x: period_labels.get(x)) 

if start_p is None or end_p is None: st.stop()
if start_p > end_p:
    st.error("⚠️ 시작 연월이 종료 연월보다 큽니다.")
    st.stop()

# 시장 구분 도움말
market_help_msg = """**출처: 국토교통부 자료**
- **전체**: 국토교통부의 자동차 이전 데이터 전체 
- **중고차시장**: 이전 데이터 전체 중 개인 간 거래대수를 포함한 사업자 거래대수 (개인거래 + 매도 + 상사이전 + 알선) 
- **유효시장**: 이전 데이터 전체 중 개인 간 거래대수를 제외한 사업자 거래대수 (매도 + 상사이전 + 알선) 
- **마케팅**: 마케팅팀이 사전에 정의한 필터링 기준에 따라, 이전등록구분명이 '매매업자거래이전'이며 등록상세명이 '일반소유용'인 이전 등록 건""" 

market_type = st.radio("시장 구분 선택", ["전체","중고차시장","유효시장","마케팅"], horizontal=True, help=market_help_msg) 

where = f"연월번호 BETWEEN {start_p} AND {end_p}" 
if market_type != "전체": where += f" AND {market_type}=1" 
st.markdown("</div>", unsafe_allow_html=True) 

# --------------------------------------------------------------- # 5. KPI 섹션
def get_val(q):
    res = con.execute(q).fetchone()
    return res[0] if res and res[0] is not None else 0

total_cnt = get_val(f"SELECT COUNT(*) FROM df WHERE {where}")

# [수정] 종료 연월(최신달) 데이터만 추출 (최대 거래월 로직 제거)
cur_month_label = period_labels.get(end_p)
cur_month_where = f"연월번호 = {end_p}"
if market_type != "전체": cur_month_where += f" AND {market_type}=1"
cur_month_val = get_val(f"SELECT COUNT(*) FROM df WHERE {cur_month_where}")

ratio_avg = (get_val(f"SELECT COUNT(*) FROM df WHERE {where} AND 중고차시장=1") / total_cnt * 100) if total_cnt > 0 else 0

c1, c2, c3 = st.columns(3) 
with c1: st.markdown(f"<div class='kpi-box'><h4>선택 기간 누적 거래량</h4><h2>{total_cnt:,}건</h2></div>", unsafe_allow_html=True) 

# [반영] 선택한 종료 연월의 거래건수를 표시
with c2: 
    display_date = cur_month_label.replace('-', '년 ') + '월'
    st.markdown(f"<div class='kpi-box'><h4>{display_date} 거래건수</h4><h2>{cur_month_val:,}건</h2></div>", unsafe_allow_html=True) 

with c3: st.markdown(f"<div class='kpi-box'><h4>중고차 시장 비중 (평균)</h4><h2>{ratio_avg:.1f}%</h2></div>", unsafe_allow_html=True) 

# --------------------------------------------------------------- # 6. 엑셀 다운로드
if st.button("📥 엑셀 생성 및 다운로드"): 
    try: 
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp: 
            path = tmp.name 
            with pd.ExcelWriter(path, engine="xlsxwriter") as w: 
                con.execute(f"SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 이전등록유형 ORDER BY 연월번호").df().pivot(index="연월라벨", columns="이전등록유형", values="건수").fillna(0).to_excel(w, sheet_name="월별_이전등록유형_건수") 
                age_gender_m = con.execute(f"SELECT 연월라벨, 나이, 성별, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 나이, 성별 ORDER BY 연월번호").df() 
                age_gender_m.loc[age_gender_m['나이'] == '법인및사업자', '성별'] = '법인및사업자' 
                age_gender_m.pivot_table(index="연월라벨", columns=["나이", "성별"], values="건수", fill_value=0).to_excel(w, sheet_name="연령성별_분포") 
                con.execute(f"SELECT 연월라벨, 주행거리_범위, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 주행거리_범위 ORDER BY 연월번호").df().pivot(index="연월라벨", columns="주행거리_범위", values="건수").fillna(0).to_excel(w, sheet_name="주행거리_분포") 
                con.execute(f"SELECT 연월라벨, 취득금액_범위, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 취득금액_범위 ORDER BY 연월번호").df().pivot(index="연월라벨", columns="취득금액_범위", values="건수").fillna(0).to_excel(w, sheet_name="취득금액_분포") 
                con.execute(f"SELECT 연월라벨, \"시/도\" AS 시도, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, \"시/도\" ORDER BY 연월번호").df().pivot(index="연월라벨", columns="시도", values="건수").fillna(0).to_excel(w, sheet_name="지역별_분포") 
            with open(path, "rb") as f: 
                f_name = f"이전등록_{period_labels.get(start_p)}_{period_labels.get(end_p)}.xlsx"
                st.download_button("✅ 다운로드 클릭", f, file_name=f_name) 
    except Exception as e: st.error(f"엑셀 생성 실패: {e}") 

# --------------------------------------------------------------- # 7. 시각화 (그래프 4개)
graph_help_msg = """**중고차 거래(이전등록) 유형**
- 1. 매입 : 자동차매매업자가 상품용으로 구매하여 중고차 거래로 등록한 차량
- 2. 매도 : 자동차매매업자가 자동차 매매업자를 제외한 타인에게 판매하여 중고차 거래로 등록한 차량
- 3. 상사이전 : 자동차매매업자가 다른 자동차매매업자에게 상품용으로 판매하여 중고차 거래로 등록한 차량
- 4. 알선 : 자동차매매업자가 중개 판매하여 중고차 거래로 등록한 차량
- 5. 개인거래 : 자동차매매업자와 무관하게 당사자간 거래로 등록한 차량
- 6. 기타 : 위 유형 외에 상속, 증여, 촉탁 등으로 중고차 거래로 등록한 차량"""

st.markdown(f""" <div class='graph-box'><div class='graph-header' style='display:flex; justify-content:space-between; align-items:center;'><h3>월별 이전등록유형 추이</h3><div title="{graph_help_msg}" style='cursor:help; width:22px; height:22px; background:#5B9BD5; color:white; border-radius:50%; text-align:center; line-height:22px; font-weight:bold;'>?</div></div></div> """, unsafe_allow_html=True)

g1 = con.execute(f"SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 이전등록유형 ORDER BY 연월번호").df() 
if not g1.empty:
    g_total = g1.groupby("연월라벨")["건수"].sum().reset_index() 
    fig1 = go.Figure() 
    fig1.add_bar(x=g_total["연월라벨"], y=g_total["건수"], name="전체", opacity=0.25, marker_color="#5B9BD5") 
    for t in g1["이전등록유형"].unique(): 
        d = g1[g1["이전등록유형"]==t] 
        fig1.add_scatter(x=d["연월라벨"], y=d["건수"], mode="lines+markers", name=str(t)) 
    fig1.update_layout(yaxis=dict(tickformat=","), margin=dict(t=20)) 
    st.plotly_chart(fig1, use_container_width=True)

st.markdown("<div class='graph-box'><div class='graph-header'><h3>연령·성별 현황</h3></div></div>", unsafe_allow_html=True) 
age_data = con.execute(f"SELECT 나이, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 나이 ORDER BY 나이").df() 
gender_data = con.execute(f"SELECT 성별, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 성별").df() 
if not age_data.empty: 
    c1, c2 = st.columns([4, 2]) 
    with c1: st.plotly_chart(px.bar(age_data, x="건수", y="나이", orientation="h", text_auto=","), use_container_width=True) 
    with c2: st.plotly_chart(px.pie(gender_data, values="건수", names="성별", hole=0.5), use_container_width=True) 

st.markdown("<div class='graph-box'><div class='graph-header'><h3>월별 연령대별 추이</h3></div></div>", unsafe_allow_html=True) 
age_line = con.execute(f"SELECT 연월라벨, 나이, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 연월번호, 연월라벨, 나이 ORDER BY 연월번호").df() 
if not age_line.empty: 
    st.plotly_chart(px.line(age_line, x="연월라벨", y="건수", color="나이", markers=True), use_container_width=True)
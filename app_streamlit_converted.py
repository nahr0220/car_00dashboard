# =============================================================== 
# 자동차 이전등록 대시보드 [수정본: KPI 종료월 변경 & 도움말 추가]
# =============================================================== 
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

# 2. 데이터 로드
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

# AP 데이터 로드
try: 
    df_ap = pd.read_excel("data/AP Sales Summary.xlsx", skiprows=1) 
    df_ap.columns = ["년도","월","AP"] 
    df_ap = df_ap[df_ap["년도"]>=2024] 
    df_ap["연월번호"] = df_ap["년도"]*100+df_ap["월"] 
    df_ap["연월라벨"] = df_ap["년도"].astype(str)+"-"+df_ap["월"].astype(str).str.zfill(2) 
except: 
    df_ap = pd.DataFrame(columns=["연월번호", "연월라벨", "AP"]) 

if con is None: 
    st.error("❌ 'data' 폴더에 CSV 파일이 없습니다.")
    st.stop()

# 3. 필터 및 기간 선택
periods_df = con.execute('SELECT DISTINCT 연월번호, 연월라벨 FROM df ORDER BY 연월번호').df() 
if periods_df.empty: st.stop()
period_list = periods_df["연월번호"].tolist()
period_labels = dict(zip(periods_df["연월번호"], periods_df["연월라벨"])) 

st.markdown("<h1 style='font-size:36px;'>자동차 이전등록 대시보드</h1>", unsafe_allow_html=True) 
st.markdown('<div class="filter-box">', unsafe_allow_html=True) 
f1, f2, f3 = st.columns([1, 1, 0.6]) 

with f1: start_p = st.selectbox("시작 연월", period_list, format_func=lambda x: period_labels.get(x)) 
with f2: end_p = st.selectbox("종료 연월", period_list, index=len(period_list)-1, format_func=lambda x: period_labels.get(x)) 

# 날짜 예외 처리
if start_p > end_p:
    st.error("⚠️ 시작 연월이 종료 연월보다 큽니다. 기간을 다시 선택하세요.")
    st.stop()

# [수정] 시장 구분 및 도움말 메시지
market_help_msg = """**출처: 국토교통부 자료** 
- **전체**: 국토교통부의 자동차 이전 데이터 전체 
- **중고차시장**: 이전 데이터 전체 중 개인 간 거래대수를 포함한 사업자 거래대수 (개인거래 + 매도 + 상사이전 + 알선) 
- **유효시장**: 이전 데이터 전체 중 개인 간 거래대수를 제외한 사업자 거래대수 (매도 + 상사이전 + 알선) 
- **마케팅**: 마케팅팀이 사전에 정의한 필터링 기준에 따라, 이전등록구분명이 '매매업자거래이전'이며 등록상세명이 '일반소유용'인 이전 등록 건""" 

market_type = st.radio("시장 구분 선택", ["전체","중고차시장","유효시장","마케팅"], horizontal=True, help=market_help_msg) 
st.markdown("</div>", unsafe_allow_html=True) 

# 조건절 생성
where = f"연월번호 BETWEEN {start_p} AND {end_p}" 
if market_type != "전체": 
    where += f" AND {market_type}=1" 

# 4. KPI 계산
def get_val(q):
    res = con.execute(q).fetchone()
    return res[0] if res and res[0] is not None else 0

total_cnt = get_val(f"SELECT COUNT(*) FROM df WHERE {where}")

# [수정] KPI 2: 종료 연월 거래량 계산
end_label = period_labels.get(end_p)
end_where = f"연월번호 = {end_p}"
if market_type != "전체": end_where += f" AND {market_type}=1"
end_val = get_val(f"SELECT COUNT(*) FROM df WHERE {end_where}")

ratio_avg = (get_val(f"SELECT COUNT(*) FROM df WHERE {where} AND 중고차시장=1") / total_cnt * 100) if total_cnt > 0 else 0

c1, c2, c3 = st.columns(3) 
with c1: st.markdown(f"<div class='kpi-box'><h4>선택 기간 누적 거래량</h4><h2>{total_cnt:,}건</h2></div>", unsafe_allow_html=True) 
with c2: st.markdown(f"<div class='kpi-box'><h4>종료월 거래량 ({end_label})</h4><h2>{end_val:,}건</h2></div>", unsafe_allow_html=True) 
with c3: st.markdown(f"<div class='kpi-box'><h4>중고차 시장 비중 (평균)</h4><h2>{ratio_avg:.1f}%</h2></div>", unsafe_allow_html=True)

# 5. 엑셀 다운로드 (파일명 규칙 복구: 이전등록_시작_종료.xlsx)
if st.button("📥 엑셀 생성 및 다운로드"): 
    try: 
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp: 
            path = tmp.name 
            with pd.ExcelWriter(path, engine="xlsxwriter") as w: 
                # 시트 1~5 순차 생성
                con.execute(f"SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 이전등록유형 ORDER BY 연월번호").df().pivot(index="연월라벨", columns="이전등록유형", values="건수").fillna(0).to_excel(w, sheet_name="월별_이전등록유형_건수") 
                age_gender_m = con.execute(f"SELECT 연월라벨, 나이, 성별, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 나이, 성별 ORDER BY 연월번호").df() 
                age_gender_m.loc[age_gender_m['나이'] == '법인및사업자', '성별'] = '법인및사업자' 
                age_gender_m.pivot_table(index="연월라벨", columns=["나이", "성별"], values="건수", fill_value=0).to_excel(w, sheet_name="연령성별_분포") 
                con.execute(f"SELECT 연월라벨, 주행거리_범위, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 주행거리_범위 ORDER BY 연월번호").df().pivot(index="연월라벨", columns="주행거리_범위", values="건수").fillna(0).to_excel(w, sheet_name="주행거리_분포") 
                con.execute(f"SELECT 연월라벨, 취득금액_범위, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 취득금액_범위 ORDER BY 연월번호").df().pivot(index="연월라벨", columns="취득금액_범위", values="건수").fillna(0).to_excel(w, sheet_name="취득금액_분포") 
                con.execute(f"SELECT 연월라벨, \"시/도\" AS 시도, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, \"시/도\" ORDER BY 연월번호").df().pivot(index="연월라벨", columns="시도", values="건수").fillna(0).to_excel(w, sheet_name="지역별_분포") 
            
            with open(path, "rb") as f: 
                # [요청사항 반영] 선택한 연월 라벨을 파일명에 포함
                file_name = f"이전등록_{period_labels.get(start_p, 'N/A')}_{period_labels.get(end_p, 'N/A')}_{market_type}.xlsx"
                st.download_button("✅ 다운로드 클릭", f, file_name=file_name) 
    except Exception as e: st.error(f"엑셀 생성 실패: {e}") 

# 6. 시각화 (그래프 5종 및 디자인 디테일)
# [1] 이전등록유형 추이
tooltip_text = """[중고차 거래(이전등록) 유형]
1. 매입: 매매업자가 상품용으로 구매하여 등록
2. 매도: 매매업자가 일반인에게 판매하여 등록
3. 상사이전: 매매업자 간 상품용 판매 등록
4. 알선: 매매업자가 중개 판매하여 등록
5. 개인거래: 당사자 간 직접 거래 등록
6. 기타: 상속, 증여, 촉탁 등 기타 등록"""

st.markdown(f""" 
<div class='graph-box'>
    <div class='graph-header' style='display:flex; justify-content:space-between; align-items:center;'>
        <h3>월별 이전등록유형 추이</h3>
        <div title='{tooltip_text}' style='cursor:help; width:22px; height:22px; background:#5B9BD5; color:white; border-radius:50%; text-align:center; line-height:22px; font-weight:bold;'>?</div>
    </div>
</div> 
""", unsafe_allow_html=True)
g1 = con.execute(f"SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수 FROM df WHERE {where} GROUP BY 연월번호, 연월라벨, 이전등록유형 ORDER BY 연월번호").df() 
if not g1.empty:
    g_total = g1.groupby("연월라벨")["건수"].sum().reset_index() 
    fig1 = go.Figure() 
    fig1.add_bar(x=g_total["연월라벨"], y=g_total["건수"], name="전체", opacity=0.25, marker_color="#5B9BD5") 
    fig1.add_scatter(x=g_total["연월라벨"], y=g_total["건수"] * 1.05, mode="text", text=g_total["건수"], texttemplate="<b>%{text:,}</b>", textfont=dict(size=10, color="#888888"), showlegend=False) 
    for t in g1["이전등록유형"].unique(): 
        d = g1[g1["이전등록유형"]==t] 
        fig1.add_scatter(x=d["연월라벨"], y=d["건수"], mode="lines+markers", name=str(t)) 
    fig1.update_layout(yaxis=dict(tickformat=","), margin=dict(t=20)) 
    st.plotly_chart(fig1, use_container_width=True)

# [2] AP 추이 (dtick=1000 고정)
st.markdown("<div class='graph-box'><div class='graph-header'><h3>AP 판매 추이 및 유효시장 점유율</h3></div></div>", unsafe_allow_html=True) 
valid_m = con.execute(f"SELECT 연월번호, 연월라벨, COUNT(*) AS 유효시장건수 FROM df WHERE {where} AND 유효시장=1 GROUP BY 연월번호, 연월라벨").df() 
df_ap_m = pd.merge(df_ap[(df_ap["연월번호"]>=start_p)&(df_ap["연월번호"]<=end_p)], valid_m, on=["연월번호","연월라벨"], how="inner") 
if not df_ap_m.empty: 
    df_ap_m["AP비중"] = df_ap_m["AP"]/df_ap_m["유효시장건수"]*100 
    ap_max = df_ap_m["AP"].max() 
    ratio_max = df_ap_m["AP비중"].max() 
    df_ap_m["AP비중_시각화"] = (df_ap_m["AP비중"]/ratio_max) * ap_max * 1.6 
    fig_ap = go.Figure() 
    fig_ap.add_bar(x=df_ap_m["연월라벨"], y=df_ap_m["AP"], name="AP 판매량", text=df_ap_m["AP"], textposition='outside', texttemplate='<b>%{text:,}</b>') 
    fig_ap.add_scatter(x=df_ap_m["연월라벨"], y=df_ap_m["AP비중_시각화"], mode="lines+markers+text", text=df_ap_m["AP비중"].round(2).astype(str)+"%", textposition="top center", name="AP 비중(%)", line=dict(color='red')) 
    fig_ap.update_layout(yaxis=dict(tickformat=",", dtick=1000), margin=dict(t=50, b=50)) 
    st.plotly_chart(fig_ap, use_container_width=True) 

# [3] 연령성별 (가로바 + 파이차트)
st.markdown("<div class='graph-box'><div class='graph-header'><h3>연령·성별 현황</h3></div></div>", unsafe_allow_html=True) 
age_data = con.execute(f"SELECT 나이, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 나이 ORDER BY 나이").df() 
gender_data = con.execute(f"SELECT 성별, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 성별").df() 
if not age_data.empty: 
    c1, c2 = st.columns([4, 2]) 
    with c1: st.plotly_chart(px.bar(age_data, x="건수", y="나이", orientation="h", text_auto=","), use_container_width=True) 
    with c2: st.plotly_chart(px.pie(gender_data, values="건수", names="성별", hole=0.5), use_container_width=True) 

# [4] 연령대별 라인 추이
st.markdown("<div class='graph-box'><div class='graph-header'><h3>월별 연령대별 추이</h3></div></div>", unsafe_allow_html=True) 
age_line = con.execute(f"SELECT 연월라벨, 나이, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 연월번호, 연월라벨, 나이 ORDER BY 연월번호").df() 
if not age_line.empty: 
    st.plotly_chart(px.line(age_line, x="연월라벨", y="건수", color="나이", markers=True), use_container_width=True)
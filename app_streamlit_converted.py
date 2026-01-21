# =============================================================== 
# 자동차 이전등록 대시보드 (KPI MoM + HELP TOOLTIP) - 그래프 안정화 버전
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
.kpi-box { background:#F8F8F8; padding:22px; border-radius:10px; text-align:center; height:150px; display:flex; flex-direction:column; justify-content:center; }
.filter-box,.graph-box { background:#EDF4FF; border-radius:12px; margin-bottom:20px; }
.graph-header { background:#E3F2FD; padding:16px; border-radius:10px; }
</style>
""", unsafe_allow_html=True)

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
        con.execute(f"""
            CREATE VIEW df AS 
            SELECT *, 년도*100 + 월 AS 연월번호, 
            CAST(년도 AS VARCHAR)||'-'||LPAD(CAST(월 AS VARCHAR),2,'0') AS 연월라벨 
            FROM read_csv_auto({file_list_sql})
        """)
        return con
    except Exception as e:
        st.error(f"데이터베이스 연결 실패: {e}")
        return None

con = get_con()
if con is None:
    st.stop()

# ---------------------------------------------------------------
# AP data (안전하게 로드)
# ---------------------------------------------------------------
try:
    df_ap = pd.read_excel("data/AP Sales Summary.xlsx", skiprows=1)
    df_ap.columns = ["년도","월","AP"]
    df_ap = df_ap[df_ap["년도"]>=2024]
    df_ap["연월번호"] = df_ap["년도"]*100+df_ap["월"]
    df_ap["연월라벨"] = df_ap["년도"].astype(str)+"-"+df_ap["월"].astype(str).str.zfill(2)
except:
    df_ap = pd.DataFrame(columns=["연월번호", "연월라벨", "AP"])

# ---------------------------------------------------------------
# KPI 계산 (캐싱 + 에러 처리)
# ---------------------------------------------------------------
@st.cache_data
def calculate_kpi(_con):
    try:
        periods = _con.execute('SELECT DISTINCT "연월번호", "연월라벨" FROM df ORDER BY "연월번호"').df()
        if periods.empty:
            return None
        cur_period = int(periods["연월번호"].max())
        cur_year, cur_month = divmod(cur_period,100)
        
        def get_count(p_sql):
            return _con.execute(p_sql).fetchone()[0] or 0
        
        cur_cnt = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={cur_period}")
        prev_period = (cur_year*100+cur_month-1) if cur_month>1 else ((cur_year-1)*100+12)
        prev_cnt = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={prev_period}")
        yoy_period = (cur_year-1)*100+cur_month
        yoy_cnt = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={yoy_period}")
        used_cur = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={cur_period} AND 중고차시장=1")
        ratio_cur = used_cur/cur_cnt*100 if cur_cnt else 0
        used_prev = get_count(f"SELECT COUNT(*) FROM df WHERE 연월번호={prev_period} AND 중고차시장=1")
        ratio_prev = used_prev/prev_cnt*100 if prev_cnt else 0
        mom = (cur_cnt-prev_cnt)/prev_cnt*100 if prev_cnt else 0
        yoy = (cur_cnt-yoy_cnt)/yoy_cnt*100 if yoy_cnt else 0
        ratio_mom = ratio_cur - ratio_prev
        return {
            'periods': periods, 'cur_year': cur_year, 'cur_month': cur_month,
            'cur_cnt': cur_cnt, 'mom': mom, 'yoy': yoy, 
            'ratio_cur': ratio_cur, 'ratio_mom': ratio_mom
        }
    except:
        return None

kpi_data = calculate_kpi(con)
if kpi_data is None:
    st.error("❌ KPI 데이터 계산 실패. 데이터를 확인해주세요.")
    st.stop()

periods = kpi_data['periods']
period_to_label = dict(zip(periods["연월번호"], periods["연월라벨"]))
cur_year, cur_month, cur_cnt = kpi_data['cur_year'], kpi_data['cur_month'], kpi_data['cur_cnt']
mom, yoy, ratio_cur, ratio_mom = kpi_data['mom'], kpi_data['yoy'], kpi_data['ratio_cur'], kpi_data['ratio_mom']

# ---------------------------------------------------------------
# Session State 초기화 (그래프 안정화)
# ---------------------------------------------------------------
if 'market_type' not in st.session_state:
    st.session_state.market_type = "전체"

# ---------------------------------------------------------------
# KPI 대시보드
# ---------------------------------------------------------------
st.markdown("<h1 style='font-size:36px;'>자동차 이전등록 대시보드</h1>", unsafe_allow_html=True)
st.write("")
c1,c2,c3 = st.columns(3)
with c1:
    st.markdown(f"<div class='kpi-box'><h4>{cur_year}년 누적 거래량</h4><h2>{cur_cnt:,}건</h2></div>", unsafe_allow_html=True)
with c2:
    mom_c = "red" if mom>0 else "blue"
    yoy_c = "red" if yoy>0 else "blue"
    st.markdown(f"<div class='kpi-box'><h4>{cur_month}월 거래량</h4><h2>{cur_cnt:,}건</h2><div><span style='color:{mom_c}'>{mom:+.1f}% MoM</span> | <span style='color:{yoy_c}'>{yoy:+.1f}% YoY</span></div></div>", unsafe_allow_html=True)
with c3:
    r_mom_c = "red" if ratio_mom>0 else "blue"
    st.markdown(f"<div class='kpi-box'><h4>중고차 비중</h4><h2>{ratio_cur:.1f}%</h2><div><span style='color:{r_mom_c}'>{ratio_mom:+.1f}%p MoM</span></div></div>", unsafe_allow_html=True)

# ---------------------------------------------------------------
# Filters & Excel Download (Session State 적용)
# ---------------------------------------------------------------
st.markdown('<div class="filter-box">', unsafe_allow_html=True)
f1,f2,f3 = st.columns([1,1,0.6])

with f1:
    start_p = st.selectbox("시작 연월", periods["연월번호"], format_func=lambda x: period_to_label.get(x, str(x)))
with f2:
    end_p = st.selectbox("종료 연월", periods["연월번호"], index=len(periods)-1, format_func=lambda x: period_to_label.get(x, str(x)))
if start_p > end_p:
    start_p, end_p = end_p, start_p

where_base = f"연월번호 BETWEEN {start_p} AND {end_p}"
market_help_msg = """**출처: 국토교통부 자료**
- **전체**: 국토교통부의 자동차 이전 데이터 전체
- **중고차시장**: 이전 데이터 전체 중 개인 간 거래대수를 포함한 사업자 거래대수 (개인거래 + 매도 + 상사이전 + 알선)
- **유효시장**: 이전 데이터 전체 중 개인 간 거래대수를 제외한 사업자 거래대수 (매도 + 상사이전 + 알선)
- **마케팅**: 마케팅팀이 사전에 정의한 필터링 기준에 따라, 이전등록구분명이 '매매업자거래이전'이며 등록상세명이 '일반소유용'인 이전 등록 건"""

def update_market(market):
    st.session_state.market_type = market

market_type = st.radio("시장 구분 선택", ["전체","중고차시장","유효시장","마케팅"], 
                      horizontal=True, help=market_help_msg, 
                      index=["전체","중고차시장","유효시장","마케팅"].index(st.session_state.market_type),
                      key="market_radio", on_change=update_market)

where = where_base
if market_type != "전체":
    where += f" AND {market_type}=1"

# 엑셀 다운로드 (기존 코드 유지)
if st.button("📥 엑셀 생성 및 다운로드", key="excel_download"):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
            path = tmp.name
            with pd.ExcelWriter(path, engine="xlsxwriter") as w:
                # 월별 건수
                monthly_type_cnt = con.execute(f"""
                    SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수 
                    FROM df WHERE {where} 
                    GROUP BY 연월번호, 연월라벨, 이전등록유형 
                    ORDER BY 연월번호
                """).df()
                monthly_type_cnt.pivot(index="연월라벨", columns="이전등록유형", values="건수").fillna(0).to_excel(w, sheet_name="월별_이전등록유형_건수")
                
                # 연령·성별
                age_gender_m = con.execute(f"""
                    SELECT 연월라벨, 나이, 성별, COUNT(*) AS 건수 
                    FROM df WHERE {where} 
                    GROUP BY 연월번호, 연월라벨, 나이, 성별 
                    ORDER BY 연월번호
                """).df()
                age_gender_m.loc[age_gender_m['나이'] == '법인및사업자', '성별'] = '법인및사업자'
                age_gender_m.pivot_table(index="연월라벨", columns=["나이", "성별"], values="건수", fill_value=0).to_excel(w, sheet_name="연령성별_분포")
                
                # 주행거리
                mileage_m = con.execute(f"""
                    SELECT 연월라벨, 주행거리_범위, COUNT(*) AS 건수 
                    FROM df WHERE {where} 
                    GROUP BY 연월번호, 연월라벨, 주행거리_범위 
                    ORDER BY 연월번호
                """).df()
                mileage_m.pivot(index="연월라벨", columns="주행거리_범위", values="건수").fillna(0).to_excel(w, sheet_name="주행거리_분포")
                
                # 취득금액
                price_m = con.execute(f"""
                    SELECT 연월라벨, 취득금액_범위, COUNT(*) AS 건수 
                    FROM df WHERE {where} 
                    GROUP BY 연월번호, 연월라벨, 취득금액_범위 
                    ORDER BY 연월번호
                """).df()
                price_m.pivot(index="연월라벨", columns="취득금액_범위", values="건수").fillna(0).to_excel(w, sheet_name="취득금액_분포")
                
                # 시/도
                sido_m = con.execute(f"""
                    SELECT 연월라벨, "시/도" AS 시도, COUNT(*) AS 건수 
                    FROM df WHERE {where} 
                    GROUP BY 연월번호, 연월라벨, "시/도" 
                    ORDER BY 연월번호
                """).df()
                sido_m.pivot(index="연월라벨", columns="시도", values="건수").fillna(0).to_excel(w, sheet_name="지역별_분포")
            
            with open(path, "rb") as f:
                st.download_button(
                    "✅ 다운로드", f, 
                    file_name=f"이전등록_{period_to_label.get(start_p, 'N/A')}_{period_to_label.get(end_p, 'N/A')}.xlsx",
                    key="download_btn"
                )
            st.success("✅ 엑셀 파일 준비 완료!")
    except Exception as e:
        st.error(f"❌ 엑셀 생성 실패: {str(e)[:100]}")
    finally:
        if 'path' in locals():
            try: os.unlink(path)
            except: pass
st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------
# 그래프 데이터 캐싱 함수 (안정화)
# ---------------------------------------------------------------
@st.cache_data
def get_cached_data(_con, _where, query_type):
    try:
        return _con.execute(query_type.format(where=_where)).df()
    except:
        return pd.DataFrame()

# ---------------------------------------------------------------
# Graph 1: 월별 이전등록유형 추이 (안정화)
# ---------------------------------------------------------------
st.markdown("<div class='graph-box'><div class='graph-header'><h3>월별 이전등록유형 추이</h3></div></div>", unsafe_allow_html=True)
g1_query = """
    SELECT 연월라벨, 이전등록유형, COUNT(*) AS 건수 
    FROM df WHERE {where} 
    GROUP BY 연월번호, 연월라벨, 이전등록유형 
    ORDER BY 연월번호
""".format(where=where)
g1 = get_cached_data(con, where, g1_query)

if g1.empty:
    st.warning("📊 선택된 기간/시장에 이전등록 데이터가 없습니다.")
    fig1 = go.Figure()
    fig1.add_annotation(text="데이터 없음", xref="paper", yref="paper", x=0.5, y=0.5, 
                       font=dict(size=20), showarrow=False)
else:
    g_total = g1.groupby("연월라벨")["건수"].sum().reset_index()
    fig1 = go.Figure()
    fig1.add_bar(x=g_total["연월라벨"], y=g_total["건수"], name="전체", opacity=0.25, marker_color="#5B9BD5")
    fig1.add_scatter(x=g_total["연월라벨"], y=g_total["건수"] * 1.05, mode="text", 
                    text=g_total["건수"], texttemplate="<b>%{text:,}</b>", 
                    textfont=dict(size=10, color="#888888"), showlegend=False)
    for t in g1["이전등록유형"].unique():
        d = g1[g1["이전등록유형"]==t]
        fig1.add_scatter(x=d["연월라벨"], y=d["건수"], mode="lines+markers", name=str(t))
    fig1.update_layout(xaxis=dict(ticks=""), yaxis=dict(ticks="", tickformat=","), 
                      template="plotly_white")
st.plotly_chart(fig1, use_container_width=True)

# ---------------------------------------------------------------
# Graph 2: AP 월별 추이 (안정화)
# ---------------------------------------------------------------
st.markdown("<div class='graph-box'><div class='graph-header'><h3>AP 판매 추이 및 유효시장 점유율</h3></div></div>", unsafe_allow_html=True)
valid_m_query = """
    SELECT 연월번호, 연월라벨, COUNT(*) AS 유효시장건수 
    FROM df WHERE {where} AND 유효시장=1 
    GROUP BY 연월번호, 연월라벨
""".format(where=where_base)  # AP는 유효시장 기준
valid_m = get_cached_data(con, where_base, valid_m_query)

df_ap_filtered = df_ap[(df_ap["연월번호"] >= start_p) & (df_ap["연월번호"] <= end_p)]
df_ap_m = pd.merge(df_ap_filtered, valid_m, on=["연월번호","연월라벨"], how="inner")

if df_ap_m.empty:
    fig_ap = go.Figure()
    fig_ap.add_annotation(text="AP 데이터 없음", xref="paper", yref="paper", x=0.5, y=0.5, 
                         font=dict(size=20), showarrow=False)
else:
    df_ap_m["AP비중"] = df_ap_m["AP"]/df_ap_m["유효시장건수"]*100
    ap_max = df_ap_m["AP"].max() if not df_ap_m["AP"].empty else 1
    ratio_max = df_ap_m["AP비중"].max() if not df_ap_m["AP비중"].empty else 1
    df_ap_m["AP비중_시각화"] = (df_ap_m["AP비중"]/ratio_max) * ap_max * 1.6
    
    fig_ap = go.Figure()
    fig_ap.add_bar(x=df_ap_m["연월라벨"], y=df_ap_m["AP"], name="AP 판매량", 
                  text=df_ap_m["AP"], textposition='outside', 
                  texttemplate='<b>%{text:,}</b>', textfont=dict(size=13, color="black"))
    fig_ap.add_scatter(x=df_ap_m["연월라벨"], y=df_ap_m["AP비중_시각화"], 
                      mode="lines+markers+text", 
                      text=df_ap_m["AP비중"].round(2).astype(str) + "%", 
                      textposition="top center", 
                      textfont=dict(size=10, color="#9E2A2B", family="Arial Black"), 
                      name="AP 비중 (%)", line=dict(color='red', width=1.3))
    fig_ap.update_layout(xaxis=dict(ticks="", title="연월"), 
                        yaxis=dict(ticks="", tickformat=",", title="판매량", dtick=1000), 
                        margin=dict(t=50, b=50, l=50, r=50), template="plotly_white")
    fig_ap.update_yaxes(range=[0, ap_max * 2.0])
st.plotly_chart(fig_ap, use_container_width=True)

# ---------------------------------------------------------------
# Graph 3 & 4: 연령·성별 (안정화)
# ---------------------------------------------------------------
st.markdown("<div class='graph-box'><div class='graph-header'><h3>연령·성별 현황</h3></div></div>", unsafe_allow_html=True)
age_query = "SELECT 나이, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 나이 ORDER BY 나이".format(where=where)
gender_query = "SELECT 성별, COUNT(*) AS 건수 FROM df WHERE {where} AND 나이!='법인및사업자' GROUP BY 성별".format(where=where)
age_data = get_cached_data(con, where, age_query)
gender_data = get_cached_data(con, where, gender_query)

c_age, c_gender = st.columns([4, 2])
with c_age:
    if age_data.empty:
        st.warning("연령 데이터 없음")
    else:
        fig_age = px.bar(age_data, x="건수", y="나이", orientation="h")
        fig_age.update_layout(xaxis=dict(ticks="", tickformat=","), yaxis=dict(ticks=""), template="plotly_white")
        st.plotly_chart(fig_age, use_container_width=True)

with c_gender:
    if gender_data.empty:
        st.warning("성별 데이터 없음")
    else:
        fig_gender = px.pie(gender_data, values="건수", names="성별", hole=0.5)
        fig_gender.update_traces(textfont_size=16)
        st.plotly_chart(fig_gender, use_container_width=True)

# ---------------------------------------------------------------
# Graph 5: 월별 연령대별 추이 (안정화)
# ---------------------------------------------------------------
age_line_query = """
    SELECT 연월라벨, 나이, COUNT(*) AS 건수 
    FROM df WHERE {where} AND 나이!='법인및사업자' 
    GROUP BY 연월번호, 연월라벨, 나이 
    ORDER BY 연월번호
""".format(where=where)
age_line = get_cached_data(con, where, age_line_query)

st.markdown("<div class='graph-box'><div class='graph-header'><h3>월별 연령대별 추이</h3></div></div>", unsafe_allow_html=True)
if age_line.empty:
    st.warning("월별 연령 데이터 없음")
else:
    fig_age_line = px.line(age_line, x="연월라벨", y="건수", color="나이", markers=True)
    fig_age_line.update_layout(xaxis=dict(ticks=""), yaxis=dict(ticks="", tickformat=","), template="plotly_white")
    st.plotly_chart(fig_age_line, use_container_width=True)

st.info("🔄 대시보드 안정화 완료! 시장 구분 변경해도 그래프가 일관되게 표시됩니다.")

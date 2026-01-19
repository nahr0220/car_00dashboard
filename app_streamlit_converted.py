import streamlit as st
import pandas as pd
from pathlib import Path

# ========================================
# 페이지 설정
# ========================================
st.set_page_config(page_title="자동차 이전등록 대시보드", layout="wide")

# ========================================
# 데이터 로드
# ========================================
@st.cache_data
def load_data():
    # 1) 분기별 이전등록 데이터 (CSV)
    data_path = Path("data")
    files = sorted(data_path.glob("output_*분기.csv"))

    if not files:
        raise FileNotFoundError("분기별 데이터 파일이 없습니다. data 폴더를 확인하세요.")

    df_list = []

    for f in files:
        df_q = pd.read_csv(f, encoding="utf-8-sig")

        # 컬럼 정규화 (공백, BOM 제거)
        df_q.columns = (
            df_q.columns
            .astype(str)
            .str.strip()
            .str.replace("\ufeff", "", regex=False)
        )

        # '연도' → '년도' 통일
        if "연도" in df_q.columns and "년도" not in df_q.columns:
            df_q = df_q.rename(columns={"연도": "년도"})

        # 필수 컬럼 체크
        required = {"년도", "월"}
        missing = required - set(df_q.columns)
        if missing:
            st.error(f"❌ 컬럼 누락 파일: {f.name}")
            st.write("컬럼 목록:", df_q.columns.tolist())
            st.stop()

        df_list.append(df_q)

    df = pd.concat(df_list, ignore_index=True)

    # ====================================
    # 2) AP 데이터
    # ====================================
    df_ap = pd.read_excel(
        "data/AP Sales Summary.xlsx",
        skiprows=1
    )

    df_ap.columns = (
        df_ap.columns
        .astype(str)
        .str.strip()
        .str.replace("\ufeff", "", regex=False)
    )

    if "연도" in df_ap.columns and "년도" not in df_ap.columns:
        df_ap = df_ap.rename(columns={"연도": "년도"})

    # 앞의 3개 컬럼만 사용
    df_ap = df_ap.iloc[:, :3]
    df_ap.columns = ["년도", "월", "AP"]
    df_ap = df_ap[df_ap["년도"] >= 2024].copy()

    # ====================================
    # 연월 처리 (df)
    # ====================================
    df["연월번호"] = df["년도"].astype(int) * 100 + df["월"].astype(int)
    df["연월라벨"] = (
        df["년도"].astype(str)
        + "-"
        + df["월"].astype(str).str.zfill(2)
    )

    # ====================================
    # 연월 처리 (df_ap)
    # ====================================
    df_ap["연월번호"] = df_ap["년도"].astype(int) * 100 + df_ap["월"].astype(int)
    df_ap["연월라벨"] = (
        df_ap["년도"].astype(str)
        + "-"
        + df_ap["월"].astype(str).str.zfill(2)
    )

    # ====================================
    # 기간 옵션 생성
    # ====================================
    periods = (
        df[["연월번호", "연월라벨"]]
        .drop_duplicates()
        .sort_values("연월번호")
    )

    period_options = [
        {"label": r["연월라벨"], "value": int(r["연월번호"])}
        for _, r in periods.iterrows()
    ]

    period_to_label = (
        periods.set_index("연월번호")["연월라벨"]
        .astype(str)
        .to_dict()
    )

    return df, df_ap, period_options, period_to_label


# ========================================
# 앱 시작
# ========================================
st.title("자동차 이전등록 대시보드")

with st.spinner("데이터 로딩 중..."):
    df, df_ap, period_options, period_to_label = load_data()

st.success("데이터 로딩 완료")

# ========================================
# 확인용 출력 (문제 해결 후 삭제 가능)
# ========================================
st.subheader("이전등록 데이터 미리보기")
st.dataframe(df.head(20))

st.subheader("AP 데이터 미리보기")
st.dataframe(df_ap.head(20))

import streamlit as st
import pandas as pd
import numpy as np
from pathlib import Path

st.set_page_config(page_title="자동차 대시보드", layout="wide")

st.markdown("# 🔍 디버그 모드 - 어디서 문제인지 확인")

# 1. 파일 목록 먼저 보여주기
data_path = Path("data")
st.write("### 📁 data 폴더 파일:")
files = list(data_path.rglob("*"))
for f in files:
    st.write(f"- {f}")

# 2. 데이터 로드 시도
try:
    st.write("### 📊 데이터 로드 시도...")
    
    # Excel 파일들
    excel_files = list(data_path.glob("output_*분기.xlsx"))
    st.write(f"찾은 Excel: {len(excel_files)}개")
    
    if excel_files:
        df = pd.read_excel(excel_files[0])  # 첫 번째 파일만
        st.write("✅ 첫 파일 로드 성공!")
        st.write("컬럼:", list(df.columns))
        st.write(df.head())
    else:
        st.write("❌ Excel 파일 없음 - 더미 데이터 사용")
        df = pd.DataFrame({'A': range(10), 'B': np.random.rand(10)})
    
    # AP 파일
    ap_file = data_path / "AP Sales Summary.xlsx"
    if ap_file.exists():
        df_ap = pd.read_excel(ap_file)
        st.write("✅ AP 파일 로드:", df_ap.head())
    else:
        st.write("❌ AP 파일 없음")
    
except Exception as e:
    st.error(f"❌ 에러 발생: {e}")
    st.write("Traceback:", e)

st.success("🎉 코드 실행 완료 - 위에 뭐가 떴는지 확인해!")
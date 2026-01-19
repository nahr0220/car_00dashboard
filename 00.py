import pandas as pd
import glob

# 1. 모든 CSV 파일 불러와서 합치기
path = 'data/' # CSV 파일들이 있는 폴더
all_files = glob.glob(path + "output_*.csv")

li = []
for filename in all_files:
    df = pd.read_csv(filename, index_col=None, header=0, encoding='utf-8-sig')
    li.append(df)

full_df = pd.concat(li, axis=0, ignore_index=True)

# 2. 용량을 더 줄이기 위해 압축(snappy) 형식을 사용하여 저장
full_df.to_parquet('data/data.parquet', compression='snappy')

print("변환 완료! data/data.parquet 파일의 용량을 확인해보세요.")
import pandas as pd
from pathlib import Path

root = Path(__file__).resolve().parent
path = root / 'data' / 'hospital_enhanced_full_dataset.csv'
print('DATA PATH:', path)
df = pd.read_csv(path)
print('rows', len(df))
print('columns:', df.columns.tolist())
print('dtypes:')
print(df.dtypes)
print('\nhead:')
print(df.head(5).to_string(index=False))

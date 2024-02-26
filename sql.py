import pandas as pd
from sqlalchemy import create_engine

# Baca file CSV dengan delimiter '|'
df = pd.read_csv('komunitas_anggota_jawa_timur.csv', delimiter='|')

# Pra-pemrosesan nama kolom
# df.columns = df.columns.str.replace(' ', '_').str.replace('"', '')

# Buat koneksi ke database MariaDB
engine = create_engine('mysql+pymysql://root:@localhost/komunitas_anggota_jawa_timur')

# Konversi DataFrame ke SQL
df.to_sql('anggota', con=engine, if_exists='replace', index=False)

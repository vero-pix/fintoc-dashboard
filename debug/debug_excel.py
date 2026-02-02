import pandas as pd
import requests
from io import BytesIO

FORECAST_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSCnSKEn66rdSM8T1R-lWIi79kzK1I2kDnS2ms7viozTdOW9tV5Gt7FBXRB-aErK-nhMFMU4C00Wbg7/pub?output=xlsx"

print("Descargando Excel...")
response = requests.get(FORECAST_URL)
df = pd.read_excel(BytesIO(response.content))
print("\nColumnas encontradas:")
for col in df.columns:
    print(f"- {col}")

print("\nPrimeras filas del 2026:")
print(df[df['Año'] == 2026].head())

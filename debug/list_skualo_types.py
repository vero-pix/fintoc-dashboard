import requests
import os
from dotenv import load_dotenv

load_dotenv()

def list_types():
    token = os.getenv('SKUALO_TOKEN')
    headers = {
        'Authorization': f'Bearer {token}',
        'accept': 'application/json'
    }
    url = "https://api.skualo.cl/76243957-3/tablas/tiposdocumentos?PageSize=100"
    
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            items = resp.json().get('items', [])
            print(f"{'ID':<10} | {'Nombre':<40} | {'Es Fiscal':<10}")
            print("-" * 65)
            for item in items:
                id_val = str(item.get('id', ''))
                nombre_val = str(item.get('nombre', ''))
                fiscal_val = str(item.get('esFiscal', ''))
                print(f"{id_val:<10} | {nombre_val:<40} | {fiscal_val:<10}")
        else:
            print(f"Error: {resp.status_code} - {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_types()

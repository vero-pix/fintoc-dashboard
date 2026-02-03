import requests
import os
from dotenv import load_dotenv

load_dotenv()

def test_skualo_search():
    token = os.getenv('SKUALO_TOKEN')
    headers = {
        'Authorization': f'Bearer {token}',
        'accept': 'application/json'
    }
    
    url = "https://api.skualo.cl/76243957-3/documentos"
    
    print("\nPrueba 1: idTipoDocumento eq OC (SIN COMILLAS)")
    params = {
        "search": "idTipoDocumento eq OC",
        "pageSize": 5
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"Success! {len(resp.json().get('items', []))} docs")
        else:
            print(f"Error: {resp.text}")

        print("\nPrueba 2: idTipoDocumento eq OC and fecha gte 01-01-2026 (SIN COMILLAS)")
        params["search"] = "idTipoDocumento eq OC and fecha gte 01-01-2026"
        resp = requests.get(url, headers=headers, params=params)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"Success! {len(resp.json().get('items', []))} docs")
        else:
            print(f"Error: {resp.text}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_skualo_search()

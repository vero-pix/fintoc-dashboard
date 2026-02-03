import requests
import os
from dotenv import load_dotenv

load_dotenv()

def probe_syntax():
    token = os.getenv('SKUALO_TOKEN')
    headers = {
        'Authorization': f'Bearer {token}',
        'accept': 'application/json'
    }
    url = "https://api.skualo.cl/76243957-3/documentos"
    
    syntaxes = [
        "idTipoDocumento eq OC",
        "idTipoDocumento eq OC and fecha gte 2026-01-01",
        "idTipoDocumento eq OC and fecha gte 01-01-2026",
        "idTipoDocumento eq OC and fecha gte '2026-01-01'",
        "idTipoDocumento eq OC AND fecha >= 2026-01-01",
        "fecha gte 2026-01-01"
    ]
    
    for s in syntaxes:
        print(f"\nProbing: {s}")
        params = {"search": s, "pageSize": 5}
        try:
            resp = requests.get(url, headers=headers, params=params)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                items = resp.json()
                if not isinstance(items, list):
                    items = items.get('items', [])
                print(f"Items found: {len(items)}")
                if items:
                    print(f"Sample Keys: {list(items[0].keys())}")
                    print(f"Sample Item: {items[0]}")
            else:
                print(f"Error: {resp.text}")
        except Exception as e:
            print(f"Exception: {e}")

if __name__ == "__main__":
    probe_syntax()

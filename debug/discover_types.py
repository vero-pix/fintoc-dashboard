import requests
import os
from dotenv import load_dotenv

load_dotenv()

def discover_skualo():
    token = os.getenv('SKUALO_TOKEN')
    headers = {
        'Authorization': f'Bearer {token}',
        'accept': 'application/json'
    }
    
    url = "https://api.skualo.cl/76243957-3/documentos"
    # Intentamos obtener una muestra amplia para ver qué tipos existen
    params = {
        "pageSize": 500,
        "search": "fecha gte 01-01-2026"
    }
    
    try:
        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code == 200:
            items = resp.json().get('items', [])
            print(f"Total items: {len(items)}")
            tipos = {}
            for item in items:
                t = item.get('idTipoDocumento')
                if t not in tipos:
                    tipos[t] = item.get('tipoDocumento', 'N/A')
            
            print("\nTipos encontrados:")
            for tid, tnom in tipos.items():
                print(f"  {tid}: {tnom}")
        else:
            print(f"Error {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    discover_skualo()

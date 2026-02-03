import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

def probe_di():
    token = os.getenv('SKUALO_TOKEN')
    headers = {
        'Authorization': f'Bearer {token}',
        'accept': 'application/json'
    }
    
    # Probamos con DI 3036
    # Primero buscamos el idDocumento
    url_search = "https://api.skualo.cl/76243957-3/documentos?search=idTipoDocumento eq DI&pageSize=1"
    resp = requests.get(url_search, headers=headers)
    if resp.status_code == 200:
        data = resp.json()
        items = data if isinstance(data, list) else data.get('items', [])
        if items:
            id_doc = items[0]['idDocumento']
            url_det = f"https://api.skualo.cl/76243957-3/documentos/{id_doc}"
            resp_det = requests.get(url_det, headers=headers)
            print(json.dumps(resp_det.json(), indent=2))

if __name__ == "__main__":
    probe_di()

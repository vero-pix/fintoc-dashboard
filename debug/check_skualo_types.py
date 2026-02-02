import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

def get_types():
    token = os.getenv('SKUALO_TOKEN')
    if not token:
        print("No SKUALO_TOKEN found")
        return
    
    headers = {
        'Authorization': f'Bearer {token}',
        'accept': 'application/json'
    }
    
    url = "https://api.skualo.cl/76243957-3/tablas/tipos_documentos"
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            items = response.json().get('items', [])
            for item in items:
                print(f"{item.get('id')}: {item.get('nombre')}")
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == '__main__':
    get_types()

import requests
import os
from dotenv import load_dotenv
from datetime import date, datetime

load_dotenv()

def debug_facturas():
    token = os.getenv('SKUALO_TOKEN')
    headers = {
        'Authorization': f'Bearer {token}',
        'accept': 'application/json'
    }
    
    # Probamos con tipos detectados
    tipos = ["FACE", "FXCE", "INV", "DI"]
    
    print(f"\n{'TIPO':<6} | {'FOLIO':<10} | {'ESTADO':<12} | {'FECHA':<12} | {'MONTO':<12}")
    print("-" * 60)
    
    for tipo in tipos:
        url = f"https://api.skualo.cl/76243957-3/documentos?search=idTipoDocumento eq {tipo}&pageSize=50"
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                items = resp.json().get('items', [])
                for item in items:
                    print(f"{tipo:<6} | {item.get('folio'):<10} | {item.get('estado'):<12} | {item.get('fecha')[:10]:<12} | ${item.get('total', 0):,.0f}")
            else:
                print(f"Error {tipo}: {resp.status_code}")
        except Exception as e:
            print(f"Error {tipo}: {e}")

if __name__ == "__main__":
    debug_facturas()

"""
Test script para verificar si Skualo tiene endpoints de bancos para cuentas USD/EUR.
"""
import requests
from skualo_auth import SkualoAuth
from dotenv import load_dotenv

load_dotenv()

def test_bancos_endpoint():
    token = SkualoAuth().get_token()
    base_url = "https://api.skualo.cl/76243957-3"
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json"
    }
    
    # IDs de cuentas USD/EUR del Balance Tributario
    cuentas_usd_eur = {
        "1103001": "Bice USD",
        "1103002": "Santander USD", 
        "1103003": "Bice EUR"
    }
    
    print("=== Probando endpoint /bancos para cuentas USD/EUR ===\n")
    
    for cuenta_id, nombre in cuentas_usd_eur.items():
        print(f"Probando {nombre} (ID: {cuenta_id})...")
        url = f"{base_url}/bancos/{cuenta_id}"
        
        try:
            response = requests.get(url, headers=headers)
            print(f"  Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])
                print(f"  Movimientos encontrados: {len(items)}")
                if items:
                    # Mostrar primer movimiento para ver estructura
                    print(f"  Ejemplo: {items[0]}")
            else:
                print(f"  Error: {response.text[:200]}")
        except Exception as e:
            print(f"  Excepción: {e}")
        print()
    
    # Probar endpoint de saldos/cartola si existe
    print("=== Probando otros endpoints de tesorería ===\n")
    
    endpoints_a_probar = [
        "/tesoreria/saldos",
        "/tesoreria/cuentas",
        "/tesoreria/cartola",
        "/bancos",
    ]
    
    for endpoint in endpoints_a_probar:
        url = f"{base_url}{endpoint}"
        print(f"GET {endpoint}...")
        try:
            response = requests.get(url, headers=headers)
            print(f"  Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, dict):
                    print(f"  Keys: {list(data.keys())[:5]}")
                elif isinstance(data, list):
                    print(f"  Lista con {len(data)} items")
        except Exception as e:
            print(f"  Error: {e}")
        print()

if __name__ == "__main__":
    test_bancos_endpoint()

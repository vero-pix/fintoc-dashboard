import os
from dotenv import load_dotenv
import requests

load_dotenv()

secret_key = os.getenv("FINTOC_SECRET_KEY")
link_token = os.getenv("FINTOC_LINK_TOKEN")
base_url = os.getenv("FINTOC_BASE_URL")

print("=== Conectando a Fintoc ===\n")

url = f"{base_url}/v1/accounts/"
headers = {"Authorization": secret_key}
params = {"link_token": link_token}

print(f"URL: {url}")
print(f"Params: {params}\n")

try:
    response = requests.get(url, headers=headers, params=params)
    print(f"Status: {response.status_code}\n")
    
    if response.status_code == 200:
        accounts = response.json()
        print(f"✅ Cuentas obtenidas: {len(accounts)}\n")
        for account in accounts:
            print(f"  - {account['name']} ({account['currency']})")
            print(f"    ID: {account['id']}")
            print(f"    Saldo disponible: ${account['balance']['available']:,.0f}\n")
    else:
        print(f"❌ Error: {response.json()}")
except Exception as e:
    print(f"❌ Excepción: {e}")
import requests
import os
from dotenv import load_dotenv

load_dotenv()


class FintocClient:
    def __init__(self):
        self.secret_key = os.getenv("FINTOC_SECRET_KEY")
        self.base_url = os.getenv("FINTOC_BASE_URL")
        self.headers = {"Authorization": f"Bearer {self.secret_key}"}
        
        self.links = {
            "Scotia": os.getenv("FINTOC_LINK_SCOTIA"),
            "BCI": os.getenv("FINTOC_LINK_BCI"),
            "Banco de Chile": os.getenv("FINTOC_LINK_CHILE"),
            "Santander": os.getenv("FINTOC_LINK_SANTANDER"),
            "Bice": os.getenv("FINTOC_LINK_BICE"),
        }

    def get_accounts(self, link_token):
        try:
            url = f"{self.base_url}/v1/accounts/"
            params = {"link_token": link_token}
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"ERROR obteniendo cuentas: {e}")
            return []

    def get_all_balances(self):
        all_balances = []

        for banco, link_token in self.links.items():
            if not link_token:
                continue
                
            accounts = self.get_accounts(link_token)
            
            for acc in accounts:
                if acc.get("type") != "checking_account":
                    continue
                
                disponible = acc.get("balance", {}).get("available", 0)
                moneda = acc.get("currency")
                
                # USD y EUR vienen en centavos
                if moneda in ("USD", "EUR"):
                    disponible = disponible / 100
                
                all_balances.append({
                    "banco": banco,
                    "cuenta_nombre": acc.get("official_name", acc.get("name", "N/A")),
                    "numero": acc.get("number"),
                    "moneda": moneda,
                    "disponible": disponible,
                    "actual": acc.get("balance", {}).get("current", 0),
                })

        return all_balances
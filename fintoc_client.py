"""
Cliente Fintoc para obtener saldos bancarios reales.
Fintoc conecta directamente a los bancos y proporciona saldos en tiempo real.
"""
import os
import requests
from dotenv import load_dotenv
from typing import Dict, List, Optional

load_dotenv()


class FintocClient:
    """
    Cliente para la API de Fintoc.
    Obtiene saldos bancarios reales en tiempo real.
    """
    
    def __init__(self):
        self.secret_key = str(os.getenv("FINTOC_SECRET_KEY", "")).strip()
        self.base_url = os.getenv("FINTOC_BASE_URL", "https://api.fintoc.com")
        self.headers = {
            "Authorization": self.secret_key,
            "Accept": "application/json"
        }
        
        # Links de las cuentas bancarias (link_token format: link_XXX_token_YYY)
        self.links = {
            "Scotiabank": os.getenv("FINTOC_LINK_SCOTIA"),
            "BCI": os.getenv("FINTOC_LINK_BCI"),
            "Banco de Chile": os.getenv("FINTOC_LINK_CHILE"),
            "Santander": os.getenv("FINTOC_LINK_SANTANDER"),
            "Bice": os.getenv("FINTOC_LINK_BICE"),
        }

    def _parse_link_token(self, link_token: str) -> tuple:
        """
        Parsea un link_token en formato 'link_XXX_token_YYY' a (link_id, token).
        """
        if not link_token or "_token_" not in link_token:
            return None, None
        parts = link_token.split("_token_")
        return parts[0], parts[1] if len(parts) == 2 else (None, None)

    def get_accounts(self, banco: str) -> List[Dict]:
        """
        Obtiene las cuentas de un banco específico.
        
        Args:
            banco: Nombre del banco (ej: "Bice", "Santander")
            
        Returns:
            Lista de cuentas con sus saldos
        """
        link_token = self.links.get(banco)
        if not link_token:
            print(f"No hay link configurado para {banco}")
            return []
        
        # Fintoc API: GET /v1/accounts con link_token COMPLETO como query param
        url = f"{self.base_url}/v1/accounts"
        params = {"link_token": link_token}
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"ERROR obteniendo cuentas de {banco}: {e}")
            return []

    def get_all_balances(self) -> Dict:
        """
        Obtiene los saldos de todas las cuentas bancarias.
        Solo considera checking_account (cuentas corrientes), ignora tarjetas de crédito.
        
        Returns:
            Dict con saldos por banco y moneda:
            {
                "clp": {"Santander": 100000, "BCI": 50000, "total": 150000},
                "usd": {"Bice USD": 264.68, "Santander USD": 84000, "total": 84264.68},
                "eur": {"Bice EUR": 80.0, "total": 80.0}
            }
        """
        result = {
            "clp": {"total": 0},
            "usd": {"total": 0},
            "eur": {"total": 0}
        }
        
        for banco, link_token in self.links.items():
            if not link_token:
                continue
                
            accounts = self.get_accounts(banco)
            
            for account in accounts:
                # Procesar cuentas de activo (evitar tarjetas de crédito si es posible)
                account_type = account.get("type", "")
                if account_type in ["credit_card"]:
                    continue
                    
                currency = account.get("currency", "CLP").upper()
                balance_raw = account.get("balance", {}).get("available", 0)
                
                # Fintoc devuelve valores en centavos para USD/EUR
                if currency in ["USD", "EUR"]:
                    balance = balance_raw / 100.0
                else:
                    balance = balance_raw  # CLP se mantiene como está
                
                # Determinar la categoría por moneda
                if currency == "CLP":
                    if banco not in result["clp"]:
                        result["clp"][banco] = 0
                    result["clp"][banco] += balance
                    result["clp"]["total"] += balance
                elif currency == "USD":
                    key = f"{banco} USD"
                    if key not in result["usd"]:
                        result["usd"][key] = 0
                    result["usd"][key] += balance
                    result["usd"]["total"] += balance
                elif currency == "EUR":
                    key = f"{banco} EUR"
                    if key not in result["eur"]:
                        result["eur"][key] = 0
                    result["eur"][key] += balance
                    result["eur"]["total"] += balance
        
        return result

    def get_usd_eur_balances(self) -> Dict:
        """
        Obtiene solo los saldos USD y EUR.
        """
        all_balances = self.get_all_balances()
        return {
            "usd": all_balances["usd"],
            "eur": all_balances["eur"]
        }


if __name__ == "__main__":
    client = FintocClient()
    
    print("=== Saldos Fintoc ===\n")
    balances = client.get_all_balances()
    
    print("CLP:")
    for k, v in balances["clp"].items():
        print(f"  {k}: ${v:,.0f}")
    
    print("\nUSD:")
    for k, v in balances["usd"].items():
        print(f"  {k}: ${v:,.2f}")
    
    print("\nEUR:")
    for k, v in balances["eur"].items():
        print(f"  {k}: €{v:,.2f}")

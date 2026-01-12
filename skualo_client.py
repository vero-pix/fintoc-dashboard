import requests
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()


class SkualoClient:
    def __init__(self):
        self.token = os.getenv("SKUALO_TOKEN")
        self.base_url = "https://api.skualo.cl/76243957-3"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "accept": "application/json"
        }
        
        self.cuentas = {
            "fondos_mutuos": "1105002",
            "por_cobrar": "1107001",
            "por_pagar_nacional": "2110001",
            "por_pagar_internacional": "2110002",
        }

    def get_balance_tributario(self):
        periodo = datetime.now().strftime("%Y%m")
        url = f"{self.base_url}/contabilidad/reportes/balancetributario/{periodo}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"ERROR Skualo: {e}")
            return []

    def get_saldos_cuentas(self):
        data = self.get_balance_tributario()
        
        resultado = {
            "fondos_mutuos": 0,
            "por_cobrar": 0,
            "por_pagar_nacional": 0,
            "por_pagar_internacional": 0,
            "por_pagar_total": 0,
        }
        
        for item in data:
            id_cuenta = item.get("idCuenta", "")
            activos = item.get("activos", 0)
            pasivos = item.get("pasivos", 0)
            saldo = activos if activos > 0 else pasivos
            
            if id_cuenta == self.cuentas["fondos_mutuos"]:
                resultado["fondos_mutuos"] = saldo
            elif id_cuenta == self.cuentas["por_cobrar"]:
                resultado["por_cobrar"] = saldo
            elif id_cuenta == self.cuentas["por_pagar_nacional"]:
                resultado["por_pagar_nacional"] = saldo
            elif id_cuenta == self.cuentas["por_pagar_internacional"]:
                resultado["por_pagar_internacional"] = saldo
        
        resultado["por_pagar_total"] = resultado["por_pagar_nacional"] + resultado["por_pagar_internacional"]
        
        return resultado


if __name__ == "__main__":
    client = SkualoClient()
    saldos = client.get_saldos_cuentas()
    print("Saldos Skualo:")
    for k, v in saldos.items():
        print(f"  {k}: ${v:,.0f}")
import os
from dotenv import load_dotenv
# from fintoc_client import FintocClient
from mailer import Mailer
from datetime import datetime

load_dotenv()


class AlertChecker:
    def __init__(self):
        # self.client = FintocClient()
        self.mailer = Mailer()
        
        # Configuración de umbrales
        self.umbral_total_clp = 150_000_000
        self.umbrales_cuenta = {
            "67946987": {"banco": "Santander", "umbral": 100_000_000, "moneda": "CLP"},
            "76798861": {"banco": "BCI", "umbral": 6_000_000, "moneda": "CLP"},
        }

    def check_alerts(self):
        # balances = self.client.get_all_balances()
        print("Alerts disabled during Skualo migration")
        return False
        
        # Fintoc Deprecated Logic
        # ...

    def _enviar_alerta(self, alertas, balances):
        pass

if __name__ == "__main__":
    checker = AlertChecker()
    checker.check_alerts()
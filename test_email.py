from fintoc_client import FintocClient
from mailer import Mailer

client = FintocClient()
accounts = client.get_accounts()

if accounts:
    print(f"Enviando email con {len(accounts)} cuentas...")
    mailer = Mailer()
    mailer.send_daily_balances(accounts)
else:
    print("ERROR: No hay cuentas para enviar")
from fintoc_client import FintocClient
from mailer import Mailer
from alerts import AlertChecker

def main():
    # Enviar reporte de saldos
    client = FintocClient()
    balances = client.get_all_balances()
    
    mailer = Mailer()
    mailer.send_daily_balances(balances)
    
    # Verificar alertas
    checker = AlertChecker()
    checker.check_alerts()

if __name__ == "__main__":
    main()
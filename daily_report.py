from fintoc_client import FintocClient
from skualo_client import SkualoClient
from mailer import Mailer
from alerts import AlertChecker

def main():
    # Obtener datos Fintoc
    fintoc = FintocClient()
    balances = fintoc.get_all_balances()
    
    # Obtener datos Skualo
    skualo = SkualoClient()
    saldos_skualo = skualo.get_saldos_cuentas()
    
    # Enviar reporte
    mailer = Mailer()
    mailer.send_daily_balances(balances, saldos_skualo)
    
    # Verificar alertas
    checker = AlertChecker()
    checker.check_alerts()

if __name__ == "__main__":
    main()
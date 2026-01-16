from fintoc_client import FintocClient
from skualo_client import SkualoClient
from historico_client import HistoricoClient
from mailer import Mailer

def main():
    # Obtener datos Fintoc
    fintoc = FintocClient()
    balances = fintoc.get_all_balances()
    total_clp = sum(b['disponible'] for b in balances if b['moneda'] == 'CLP')
    total_usd = sum(b['disponible'] for b in balances if b['moneda'] == 'USD')
    total_eur = sum(b['disponible'] for b in balances if b['moneda'] == 'EUR')
    
    # Obtener datos Skualo
    skualo = SkualoClient()
    saldos_skualo = skualo.get_saldos_cuentas()
    
    # Obtener histórico y calcular variaciones
    historico = HistoricoClient()
    anterior = historico.obtener_saldo_anterior()
    
    actual = {
        'total_clp': total_clp,
        'total_usd': total_usd,
        'total_eur': total_eur,
        'fondos_mutuos': saldos_skualo['fondos_mutuos'],
        'por_cobrar': saldos_skualo['por_cobrar'],
        'por_pagar_nacional': saldos_skualo['por_pagar_nacional'],
        'por_pagar_internacional': saldos_skualo['por_pagar_internacional'],
        'por_pagar_total': saldos_skualo['por_pagar_total'],
    }
    
    variaciones = historico.calcular_variaciones(actual, anterior)
    
    # Enviar reporte CON variaciones
    mailer = Mailer()
    mailer.send_daily_balances(balances, saldos_skualo, variaciones)
    
    # Guardar saldos actuales DESPUÉS de enviar (ahora con nacional/internacional separado)
    historico.guardar_saldos(
        total_clp, total_usd, total_eur,
        saldos_skualo['fondos_mutuos'],
        saldos_skualo['por_cobrar'],
        saldos_skualo['por_pagar_nacional'],
        saldos_skualo['por_pagar_internacional']
    )
    
if __name__ == "__main__":
    main()

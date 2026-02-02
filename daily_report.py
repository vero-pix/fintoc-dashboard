#!/usr/bin/env python3
"""
Script standalone para envío de reporte diario de saldos.
Ejecutado por launchd a las 8:00 y 18:00.

Usa Fintoc para saldos bancarios reales (CLP, USD, EUR)
Usa Skualo para CxC, CxP y Fondos Mutuos
Usa Google Sheets para histórico y variaciones
"""
from fintoc_client import FintocClient
from skualo_client import SkualoClient
from historico_client import HistoricoClient
from mailer import Mailer
from dotenv import load_dotenv
import os
import sys
import requests

load_dotenv()


def get_exchange_rates():
    """Obtiene tipos de cambio USD y EUR desde API gratuita"""
    try:
        # Usar exchangerate-api (gratuito, no requiere key)
        response = requests.get('https://api.exchangerate-api.com/v4/latest/USD', timeout=10)
        if response.status_code == 200:
            data = response.json()
            clp_per_usd = data['rates'].get('CLP', 890)
            
            # EUR/CLP = USD/CLP / USD/EUR
            usd_per_eur = data['rates'].get('EUR', 0.92)
            clp_per_eur = clp_per_usd / usd_per_eur if usd_per_eur > 0 else 1030
            
            print(f"  → TC obtenido: USD={clp_per_usd:.0f} | EUR={clp_per_eur:.0f}")
            return round(clp_per_usd), round(clp_per_eur)
    except Exception as e:
        print(f"  → Error obteniendo TC, usando valores por defecto: {e}")
    
    # Valores por defecto si falla la API
    return 890, 1030


# Tipo de cambio (se obtiene dinámicamente)
TC_USD, TC_EUR = get_exchange_rates()


def enviar_reporte():
    """Genera y envía reporte de saldos diarios con variaciones"""
    print("🔄 Iniciando reporte diario de saldos...")
    
    try:
        fintoc = FintocClient()
        skualo = SkualoClient()
        historico = HistoricoClient()
        mailer = Mailer()
        
        # 1. Saldos Bancarios desde Fintoc (datos reales)
        print("  → Obteniendo saldos Fintoc...")
        fintoc_balances = fintoc.get_all_balances()
        
        # Construir lista de balances para el mailer (detalle por banco)
        balances = []
        
        # CLP - detalle por banco
        for banco, saldo in fintoc_balances["clp"].items():
            if banco != "total" and saldo > 0:
                balances.append({
                    "banco": banco,
                    "disponible": saldo,
                    "moneda": "CLP"
                })
        
        # USD - detalle por banco
        for banco, saldo in fintoc_balances["usd"].items():
            if banco != "total" and saldo > 0:
                balances.append({
                    "banco": banco,
                    "disponible": saldo,
                    "moneda": "USD"
                })
        
        # EUR - detalle por banco
        for banco, saldo in fintoc_balances["eur"].items():
            if banco != "total" and saldo > 0:
                balances.append({
                    "banco": banco,
                    "disponible": saldo,
                    "moneda": "EUR"
                })
        
        # Totales Fintoc
        total_clp = fintoc_balances["clp"]["total"]
        total_usd = fintoc_balances["usd"]["total"]
        total_eur = fintoc_balances["eur"]["total"]
        
        print(f"  → CLP: ${total_clp:,.0f} | USD: ${total_usd:,.2f} | EUR: €{total_eur:,.2f}")
        
        # 2. Saldos CxC/CxP y Fondos Mutuos desde Skualo
        print("  → Obteniendo saldos Skualo...")
        saldos_skualo = skualo.get_saldos_cuentas()
        fondos_mutuos = saldos_skualo.get('fondos_mutuos', 0)
        por_cobrar = saldos_skualo.get('por_cobrar', 0)
        por_pagar_nacional = saldos_skualo.get('por_pagar_nacional', 0)
        por_pagar_internacional = saldos_skualo.get('por_pagar_internacional', 0)
        
        # 3. Obtener histórico y calcular variaciones
        print("  → Calculando variaciones...")
        anterior = historico.obtener_saldo_anterior()
        
        actual = {
            'total_clp': total_clp,
            'total_usd': total_usd,
            'total_eur': total_eur,
            'fondos_mutuos': fondos_mutuos,
            'por_cobrar': por_cobrar,
            'por_pagar_nacional': por_pagar_nacional,
            'por_pagar_internacional': por_pagar_internacional,
            'por_pagar_total': por_pagar_nacional + por_pagar_internacional,
        }
        
        variaciones = historico.calcular_variaciones(actual, anterior) if anterior else None
        
        if variaciones:
            print(f"  → Variación CLP: {variaciones['total_clp']:+,.0f}")
            print(f"  → Variación USD: {variaciones['total_usd']:+,.2f}")
        
        # 4. Guardar saldos actuales en histórico
        print("  → Guardando en histórico...")
        historico.guardar_saldos(
            total_clp, total_usd, total_eur, fondos_mutuos,
            por_cobrar, por_pagar_nacional, por_pagar_internacional
        )
        
        # 5. Preparar datos para el mailer
        saldos_skualo['total_clp'] = total_clp
        saldos_skualo['total_usd'] = total_usd
        saldos_skualo['total_eur'] = total_eur
        saldos_skualo['tc_usd'] = TC_USD
        saldos_skualo['tc_eur'] = TC_EUR
        
        # 6. Enviar reporte
        print("  → Enviando email...")
        resultado = mailer.send_daily_balances(balances, saldos_skualo, variaciones)
        
        if resultado:
            print("✅ Reporte diario enviado exitosamente")
            return 0
        else:
            print("❌ Error al enviar reporte")
            return 1
            
    except Exception as e:
        print(f"❌ Error reporte diario: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(enviar_reporte())

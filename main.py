from apscheduler.schedulers.background import BackgroundScheduler
# from fintoc_client import FintocClient
from skualo_bancos import SkualoBancosClient
from skualo_client import SkualoClient
from mailer import Mailer
import os
from dotenv import load_dotenv
import signal
import sys

load_dotenv()

class CathproMonitor:
    def __init__(self):
        # self.fintoc = FintocClient()
        self.skualo_bancos = SkualoBancosClient()
        self.skualo = SkualoClient()
        self.mailer = Mailer()
        self.scheduler = BackgroundScheduler()
        self.umbral_pago = int(os.getenv("UMBRAL_PAGO", 1000000))

    def reporte_diario_saldos(self):
        """Task: Envía reporte de saldos a las 08:00"""
        print("🔄 Iniciando reporte diario de saldos...")
        
        # Logic Skualo
        try:
             # 1. Saldos Bancos (Accounting)
             data_contable = self.skualo.get_balance_tributario()
             mapa_bancos = {
                 "1102002": {"nombre": "Santander", "moneda": "CLP"},
                 "1102003": {"nombre": "BCI", "moneda": "CLP"},
                 "1102004": {"nombre": "Scotiabank", "moneda": "CLP"},
                 "1102005": {"nombre": "Banco de Chile", "moneda": "CLP"},
                 "1102013": {"nombre": "Bice", "moneda": "CLP"},
             }
             balances = []
             for item in data_contable:
                 id_cta = item.get("idCuenta")
                 if id_cta in mapa_bancos:
                     info = mapa_bancos[id_cta]
                     balances.append({
                         "banco": info["nombre"],
                         "disponible": item.get("activos", 0) - item.get("pasivos", 0),
                         "moneda": info["moneda"]
                     })
             
             # 2. Saldos Generales Skualo
             saldos_skualo = self.skualo.get_saldos_cuentas()

             # 3. Variaciones (Opcional, por ahora None)
             variaciones = None

             # Enviar reporte
             self.mailer.send_daily_balances(balances, saldos_skualo, variaciones)
             print("✅ Reporte diario enviado")

        except Exception as e:
             print(f"Error reporte diario: {e}")

    def detectar_pago_umbral(self, account_id):
        """Task: Verifica transacciones recientes y alerta si superan umbral"""
        # print(f"🔍 Verificando pagos en cuenta {account_id}...")
        pass 
        # Fintoc Deprecated logic removed

    def start(self):
        """Inicia scheduler con tasks"""
        # Task 1: Reporte diario a las 08:00
        self.scheduler.add_job(
            self.reporte_diario_saldos,
            'cron',
            hour=8,
            minute=0,
            id='reporte_diario'
        )
        
        # Task 2: Verificar pagos cada 30 minutos - DESHABILITADO
        # self.scheduler.add_job(
        #     self._verificar_todas_cuentas,
        #     'interval',
        #     minutes=30,
        #     id='vigilancia_pagos'
        # )
        
        self.scheduler.start()
        print("✅ Scheduler iniciado (Modo Skualo). Presiona Ctrl+C para detener.")
        
        # Mantener ejecutándose
        try:
            while True:
                pass
        except KeyboardInterrupt:
            self.stop()

    def _verificar_todas_cuentas(self):
        """Itera sobre todas las cuentas verificando pagos"""
        # accounts = self.fintoc.get_accounts()
        pass

    def stop(self):
        """Detiene scheduler"""
        self.scheduler.shutdown()
        print("\n❌ Scheduler detenido.")
        sys.exit(0)

if __name__ == "__main__":
    monitor = CathproMonitor()
    monitor.start()
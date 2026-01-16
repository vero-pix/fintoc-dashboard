from apscheduler.schedulers.background import BackgroundScheduler
# from fintoc_client import FintocClient
from skualo_bancos import SkualoBancosClient
from mailer import Mailer
import os
from dotenv import load_dotenv
import signal
import sys

load_dotenv()

class CathproMonitor:
    def __init__(self):
        # self.fintoc = FintocClient()
        self.skualo = SkualoBancosClient()
        self.mailer = Mailer()
        self.scheduler = BackgroundScheduler()
        self.umbral_pago = int(os.getenv("UMBRAL_PAGO", 1000000))

    def reporte_diario_saldos(self):
        """Task: Envía reporte de saldos a las 08:00"""
        print("🔄 Iniciando reporte diario de saldos...")
        
        # Fintoc Deprecated
        # accounts = self.fintoc.get_accounts()
        # ... logic ...
        
        # Placeholder for Skualo integration
        print("⚠️ Reporte diario deshabilitado por migración a Skualo.")
        try:
             resumen = self.skualo.get_resumen_todos_bancos()
             print(f"Resumen Skualo: {resumen}")
             # TODO: Adaptar mailer para usar datos de Skualo
        except Exception as e:
             print(f"Error obteniendo datos Skualo: {e}")

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
        print("✅ Scheduler iniciado (Modo Migración). Presiona Ctrl+C para detener.")
        
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
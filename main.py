from apscheduler.schedulers.background import BackgroundScheduler
from fintoc_client import FintocClient
from mailer import Mailer
import os
from dotenv import load_dotenv
import signal
import sys

load_dotenv()

class CathproMonitor:
    def __init__(self):
        self.fintoc = FintocClient()
        self.mailer = Mailer()
        self.scheduler = BackgroundScheduler()
        self.umbral_pago = int(os.getenv("UMBRAL_PAGO", 1000000))

    def reporte_diario_saldos(self):
        """Task: Envía reporte de saldos a las 08:00"""
        print("🔄 Iniciando reporte diario de saldos...")
        accounts = self.fintoc.get_accounts()
        
        if not accounts:
            print("Error: No se obtuvieron cuentas")
            return
        
        accounts_data = []
        for account in accounts.get('accounts', []):
            account_id = account['id']
            balance_info = self.fintoc.get_account_balance(account_id)
            
            if balance_info:
                accounts_data.append(balance_info)
        
        if accounts_data:
            self.mailer.send_balances_report(accounts_data)
        else:
            print("⚠️ No se obtuvieron saldos")

    def detectar_pago_umbral(self, account_id):
        """Task: Verifica transacciones recientes y alerta si superan umbral"""
        print(f"🔍 Verificando pagos en cuenta {account_id}...")
        
        transactions = self.fintoc.get_transactions(account_id, limit=10)
        account_info = self.fintoc.get_account_balance(account_id)
        
        if not transactions or not account_info:
            return
        
        for tx in transactions.get('transactions', []):
            # Solo ingresos (depósitos)
            if tx.get('amount', 0) > 0 and tx.get('amount', 0) >= self.umbral_pago:
                self.mailer.send_payment_alert(account_info, tx)

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
        
        # Task 2: Verificar pagos cada 30 minutos
        # (alternativa: usar webhook de Fintoc si disponible)
        self.scheduler.add_job(
            self._verificar_todas_cuentas,
            'interval',
            minutes=30,
            id='vigilancia_pagos'
        )
        
        self.scheduler.start()
        print("✅ Scheduler iniciado. Presiona Ctrl+C para detener.")
        
        # Mantener ejecutándose
        try:
            while True:
                pass
        except KeyboardInterrupt:
            self.stop()

    def _verificar_todas_cuentas(self):
        """Itera sobre todas las cuentas verificando pagos"""
        accounts = self.fintoc.get_accounts()
        if accounts:
            for account in accounts.get('accounts', []):
                self.detectar_pago_umbral(account['id'])

    def stop(self):
        """Detiene scheduler"""
        self.scheduler.shutdown()
        print("\n❌ Scheduler detenido.")
        sys.exit(0)

if __name__ == "__main__":
    monitor = CathproMonitor()
    monitor.start()
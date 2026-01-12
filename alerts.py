import os
from dotenv import load_dotenv
from fintoc_client import FintocClient
from mailer import Mailer
from datetime import datetime

load_dotenv()


class AlertChecker:
    def __init__(self):
        self.client = FintocClient()
        self.mailer = Mailer()
        
        # Configuración de umbrales
        self.umbral_total_clp = 250_000_000
        self.umbrales_cuenta = {
            "67946987": {"banco": "Santander", "umbral": 100_000_000, "moneda": "CLP"},
            "76798861": {"banco": "BCI", "umbral": 6_000_000, "moneda": "CLP"},
        }

    def check_alerts(self):
        balances = self.client.get_all_balances()
        alertas = []

        # Alerta 1: Total CLP
        total_clp = sum(b['disponible'] for b in balances if b['moneda'] == 'CLP')
        if total_clp < self.umbral_total_clp:
            alertas.append({
                "tipo": "Total CLP",
                "actual": total_clp,
                "umbral": self.umbral_total_clp,
                "moneda": "CLP"
            })

        # Alertas por cuenta específica
        for b in balances:
            numero = b['numero']
            if numero in self.umbrales_cuenta:
                config = self.umbrales_cuenta[numero]
                if b['disponible'] < config['umbral']:
                    alertas.append({
                        "tipo": f"{config['banco']} - {numero}",
                        "actual": b['disponible'],
                        "umbral": config['umbral'],
                        "moneda": config['moneda']
                    })

        if alertas:
            self._enviar_alerta(alertas, balances)
            return True
        
        print(f"[{datetime.now()}] Sin alertas - Todo OK")
        return False

    def _enviar_alerta(self, alertas, balances):
        fecha = datetime.now().strftime('%d-%m-%Y %H:%M')
        
        # Construir filas de alertas
        alertas_html = ""
        for a in alertas:
            if a['moneda'] == 'CLP':
                actual = f"${a['actual']:,.0f}"
                umbral = f"${a['umbral']:,.0f}"
            else:
                actual = f"${a['actual']:,.2f}"
                umbral = f"${a['umbral']:,.2f}"
            
            alertas_html += f"""
            <tr>
                <td style="padding:12px 15px;border-bottom:1px solid #ecf0f1">{a['tipo']}</td>
                <td style="padding:12px 15px;border-bottom:1px solid #ecf0f1;text-align:right;font-family:monospace;color:#e74c3c;font-weight:bold">{actual}</td>
                <td style="padding:12px 15px;border-bottom:1px solid #ecf0f1;text-align:right;font-family:monospace">{umbral}</td>
            </tr>"""

        html = f"""
        <html>
        <head><meta charset="UTF-8"></head>
        <body style="font-family:Arial,sans-serif;margin:0;padding:0;background:#f4f4f4">
            <div style="background:#e74c3c;padding:20px 40px">
                <h1 style="color:white;margin:0;font-size:24px">⚠️ ALERTA Saldos Bajos - CathPro</h1>
            </div>
            <div style="max-width:600px;margin:0 auto;padding:20px">
                <p style="color:#7f8c8d;margin-bottom:20px">Detectado: {fecha}</p>
                
                <table style="width:100%;border-collapse:collapse;background:white;border-radius:10px;overflow:hidden;margin-bottom:20px">
                    <tr>
                        <th style="background:#e74c3c;color:white;padding:15px;text-align:left">Cuenta/Total</th>
                        <th style="background:#e74c3c;color:white;padding:15px;text-align:right">Saldo Actual</th>
                        <th style="background:#e74c3c;color:white;padding:15px;text-align:right">Umbral</th>
                    </tr>
                    {alertas_html}
                </table>
                
                <p style="color:#7f8c8d;font-size:12px;text-align:center">CathPro - Corrosion Control</p>
            </div>
        </body>
        </html>
        """

        subject = "⚠️ ALERTA Saldos Bajos - CathPro"
        self.mailer._send_email(subject, html)
        print(f"[{datetime.now()}] ALERTA ENVIADA - {len(alertas)} alertas detectadas")


if __name__ == "__main__":
    checker = AlertChecker()
    checker.check_alerts()
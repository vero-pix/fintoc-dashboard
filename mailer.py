import smtplib
import os
from dotenv import load_dotenv
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()


class Mailer:
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender = os.getenv("EMAIL_FROM")
        self.password = os.getenv("EMAIL_APP_PASSWORD", "").replace(" ", "").strip()
        recipients = os.getenv("EMAIL_TO", "")
        self.recipient = [r.strip() for r in recipients.split(",") if r.strip()]

    def send_daily_balances(self, balances, saldos_skualo, variaciones=None):
        subject = "Saldos Diarios CathPro"
        body = self._build_body(balances, saldos_skualo, variaciones)
        return self._send_email(subject, body)

    def _formato_variacion(self, valor, moneda='CLP'):
        if valor is None or valor == 0:
            return ""
        
        if moneda == 'EUR':
            simbolo = "€"
            formato = f"{abs(valor):,.0f}"
        elif moneda == 'USD':
            simbolo = "$"
            formato = f"{abs(valor):,.2f}"
        else:
            simbolo = "$"
            formato = f"{abs(valor):,.0f}"
        
        if valor > 0:
            return f"<span style='color:#55b245;font-size:12px'>▲ +{simbolo}{formato}</span>"
        else:
            return f"<span style='color:#e74c3c;font-size:12px'>▼ -{simbolo}{formato}</span>"

    def _build_body(self, balances, saldos_skualo, variaciones=None):
        total_clp = sum(b['disponible'] for b in balances if b['moneda'] == 'CLP')
        total_usd = sum(b['disponible'] for b in balances if b['moneda'] == 'USD')
        total_eur = sum(b['disponible'] for b in balances if b['moneda'] == 'EUR')
        fecha = datetime.now().strftime('%d-%m-%Y %H:%M')
        
        posicion_neta = saldos_skualo['por_cobrar'] - saldos_skualo['por_pagar_total']
        posicion_color = "#55b245" if posicion_neta >= 0 else "#e74c3c"
        
        # Variaciones
        var_clp = self._formato_variacion(variaciones.get('total_clp'), 'CLP') if variaciones else ""
        var_usd = self._formato_variacion(variaciones.get('total_usd'), 'USD') if variaciones else ""
        var_eur = self._formato_variacion(variaciones.get('total_eur'), 'EUR') if variaciones else ""
        var_fondos = self._formato_variacion(variaciones.get('fondos_mutuos'), 'CLP') if variaciones else ""
        var_cobrar = self._formato_variacion(variaciones.get('por_cobrar'), 'CLP') if variaciones else ""
        var_pagar = self._formato_variacion(variaciones.get('por_pagar_total'), 'CLP') if variaciones else ""

        rows = ""
        for b in balances:
            moneda = b['moneda']
            if moneda == 'USD':
                monto = f"${b['disponible']:,.2f}"
            elif moneda == 'EUR':
                monto = f"€{b['disponible']:,.0f}"
            else:
                monto = f"${b['disponible']:,.0f}"
            rows += f"<tr><td style='padding:10px 15px;border-bottom:1px solid #ecf0f1'>{b['banco']}</td><td style='padding:10px 15px;border-bottom:1px solid #ecf0f1;text-align:right;font-family:monospace;font-weight:bold'>{monto}</td><td style='padding:10px 15px;border-bottom:1px solid #ecf0f1'>{moneda}</td></tr>"

        html = f"""<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;margin:0;padding:0;background:#f4f4f4">
    <div style="background:#242625;padding:20px 40px">
        <h1 style="color:#f4f4f4;margin:0;font-size:24px">Saldos Diarios CathPro</h1>
    </div>
    <div style="max-width:800px;margin:0 auto;padding:20px">
        <p style="color:#7f8c8d;margin-bottom:20px">Actualizado: {fecha}</p>
        
        <table style="width:100%;margin-bottom:20px;border-collapse:separate;border-spacing:10px 0">
            <tr>
                <td colspan="3" style="padding-bottom:10px;font-size:16px;font-weight:bold;color:#242625">Saldos Bancos</td>
                <td style="padding-bottom:10px;font-size:16px;font-weight:bold;color:#242625;text-align:right">Inversiones</td>
            </tr>
            <tr>
                <td style="background:white;padding:15px;border-radius:10px;border-left:4px solid #55b245">
                    <span style="color:#7f8c8d;font-size:11px;font-weight:600">TOTAL CLP</span><br>
                    <span style="font-size:20px;font-weight:800;color:#242625">${total_clp:,.0f}</span><br>{var_clp}
                </td>
                <td style="background:white;padding:15px;border-radius:10px;border-left:4px solid #f46302">
                    <span style="color:#7f8c8d;font-size:11px;font-weight:600">TOTAL USD</span><br>
                    <span style="font-size:20px;font-weight:800;color:#242625">${total_usd:,.2f}</span><br>{var_usd}
                </td>
                <td style="background:white;padding:15px;border-radius:10px;border-left:4px solid #3498db">
                    <span style="color:#7f8c8d;font-size:11px;font-weight:600">TOTAL EUR</span><br>
                    <span style="font-size:20px;font-weight:800;color:#242625">€{total_eur:,.0f}</span><br>{var_eur}
                </td>
                <td style="background:white;padding:15px;border-radius:10px;border-left:4px solid #9b59b6">
                    <span style="color:#7f8c8d;font-size:11px;font-weight:600">FONDOS MUTUOS</span><br>
                    <span style="font-size:20px;font-weight:800;color:#242625">${saldos_skualo['fondos_mutuos']:,.0f}</span><br>{var_fondos}
                </td>
            </tr>
        </table>
        
        <p style="font-size:16px;font-weight:bold;color:#242625;margin:25px 0 10px">Cuentas por Cobrar / Pagar</p>
        <table style="width:100%;margin-bottom:20px;border-collapse:separate;border-spacing:10px 0">
            <tr>
                <td style="background:white;padding:15px;border-radius:10px;border-left:4px solid #55b245;width:33%">
                    <span style="color:#7f8c8d;font-size:11px;font-weight:600">POR COBRAR</span><br>
                    <span style="font-size:20px;font-weight:800;color:#242625">${saldos_skualo['por_cobrar']:,.0f}</span><br>{var_cobrar}
                </td>
                <td style="background:white;padding:15px;border-radius:10px;border-left:4px solid #e74c3c;width:33%">
                    <span style="color:#7f8c8d;font-size:11px;font-weight:600">POR PAGAR NACIONAL</span><br>
                    <span style="font-size:20px;font-weight:800;color:#242625">${saldos_skualo['por_pagar_nacional']:,.0f}</span>
                </td>
                <td style="background:white;padding:15px;border-radius:10px;border-left:4px solid #f46302;width:33%">
                    <span style="color:#7f8c8d;font-size:11px;font-weight:600">POR PAGAR INTERNACIONAL</span><br>
                    <span style="font-size:20px;font-weight:800;color:#242625">${saldos_skualo['por_pagar_internacional']:,.0f}</span>
                </td>
            </tr>
        </table>
        
        <div style="background:#242625;padding:20px;border-radius:10px;text-align:center;margin-bottom:20px">
            <span style="color:#7f8c8d;font-size:12px">POSICIÓN NETA (Por Cobrar - Por Pagar)</span><br>
            <span style="font-size:28px;font-weight:800;color:{posicion_color}">${posicion_neta:,.0f}</span>
        </div>
        
        <div style="background:#fff3cd;border-left:4px solid #f46302;padding:12px;border-radius:5px;margin-bottom:25px">
            <span style="color:#856404;font-size:12px"><strong>Nota:</strong> Las cuentas por pagar internacional NO incluyen las OCX (órdenes de compra internacional) sobre las que aún no se ha recibido invoice.</span>
        </div>
        
        <p style="font-size:16px;font-weight:bold;color:#242625;margin:25px 0 10px">Detalle Saldos Bancarios</p>
        <table style="width:100%;border-collapse:collapse;background:white;border-radius:10px;overflow:hidden">
            <tr>
                <th style="background:#242625;color:white;padding:12px 15px;text-align:left;font-size:13px">Banco</th>
                <th style="background:#242625;color:white;padding:12px 15px;text-align:right;font-size:13px">Disponible</th>
                <th style="background:#242625;color:white;padding:12px 15px;text-align:left;font-size:13px">Moneda</th>
            </tr>
            {rows}
        </table>
        
        <div style="background:#e8f5e9;border-left:4px solid #55b245;padding:12px;border-radius:5px;margin-top:20px;text-align:center">
            <span style="color:#2e7d32;font-size:12px">Envío automático diario 8:00 y 18:00</span>
        </div>
    </div>
</body>
</html>"""
        return html

    def _send_email(self, subject, body):
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender
            msg['To'] = ", ".join(self.recipient)
            part = MIMEText(body, 'html', 'utf-8')
            msg.attach(part)
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.send_message(msg)
            print(f"OK Email enviado: {subject}")
            return True
        except Exception as e:
            print(f"ERROR: {e}")
            return False
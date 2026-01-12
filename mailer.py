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
        self.recipient = os.getenv("EMAIL_TO")

    def send_daily_balances(self, balances):
        subject = "Saldos Bancos CathPro"
        body = self._build_body(balances)
        return self._send_email(subject, body)

    def _build_body(self, balances):
        total_clp = sum(b['disponible'] for b in balances if b['moneda'] == 'CLP')
        total_usd = sum(b['disponible'] for b in balances if b['moneda'] == 'USD')
        total_eur = sum(b['disponible'] for b in balances if b['moneda'] == 'EUR')
        fecha = datetime.now().strftime('%d-%m-%Y %H:%M')

        rows = ""
        for b in balances:
            moneda = b['moneda']
            if moneda == 'USD':
                monto = f"${b['disponible']:,.2f}"
            elif moneda == 'EUR':
                monto = f"€{b['disponible']:,.0f}"
            else:
                monto = f"${b['disponible']:,.0f}"
            rows += f"""
            <tr>
                <td style="padding:12px 15px;border-bottom:1px solid #ecf0f1">{b['banco']}</td>
                <td style="padding:12px 15px;border-bottom:1px solid #ecf0f1">{b['cuenta_nombre']}</td>
                <td style="padding:12px 15px;border-bottom:1px solid #ecf0f1">{b['numero']}</td>
                <td style="padding:12px 15px;border-bottom:1px solid #ecf0f1;text-align:right;font-family:monospace;font-weight:bold">{monto}</td>
                <td style="padding:12px 15px;border-bottom:1px solid #ecf0f1">{moneda}</td>
            </tr>"""

        html = f"""
        <html>
        <head>
            <meta charset="UTF-8">
        </head>
        <body style="font-family:Arial,sans-serif;margin:0;padding:0;background:#f4f4f4">
            <div style="background:#242625;padding:20px 40px">
                <h1 style="color:#f4f4f4;margin:0;font-size:24px">Saldos Bancos CathPro</h1>
            </div>
            <div style="max-width:700px;margin:0 auto;padding:20px">
                <p style="color:#7f8c8d;margin-bottom:20px">Actualizado: {fecha}</p>
                <table style="width:100%;border-collapse:collapse;background:white;border-radius:10px;overflow:hidden">
                    <tr>
                        <th style="background:#242625;color:white;padding:15px;text-align:left">Banco</th>
                        <th style="background:#242625;color:white;padding:15px;text-align:left">Cuenta</th>
                        <th style="background:#242625;color:white;padding:15px;text-align:left">Numero</th>
                        <th style="background:#242625;color:white;padding:15px;text-align:right">Disponible</th>
                        <th style="background:#242625;color:white;padding:15px;text-align:left">Moneda</th>
                    </tr>
                    {rows}
                </table>
                <table style="width:100%;margin-top:20px;border-collapse:separate;border-spacing:10px 0">
                    <tr>
                        <td style="background:white;padding:20px;border-radius:10px;border-left:4px solid #55b245;width:33%">
                            <span style="color:#7f8c8d;font-size:12px;font-weight:600">TOTAL CLP</span><br>
                            <span style="font-size:24px;font-weight:800;color:#242625">${total_clp:,.0f}</span>
                        </td>
                        <td style="background:white;padding:20px;border-radius:10px;border-left:4px solid #f46302;width:33%">
                            <span style="color:#7f8c8d;font-size:12px;font-weight:600">TOTAL USD</span><br>
                            <span style="font-size:24px;font-weight:800;color:#242625">${total_usd:,.2f}</span>
                        </td>
                        <td style="background:white;padding:20px;border-radius:10px;border-left:4px solid #3498db;width:33%">
                            <span style="color:#7f8c8d;font-size:12px;font-weight:600">TOTAL EUR</span><br>
                            <span style="font-size:24px;font-weight:800;color:#242625">€{total_eur:,.0f}</span>
                        </td>
                    </tr>
                </table>
                <p style="color:#7f8c8d;font-size:11px;margin-top:30px;text-align:center">CathPro - Corrosion Control</p>
            </div>
        </body>
        </html>
        """
        return html

    def _send_email(self, subject, body):
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.sender
            msg['To'] = self.recipient
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
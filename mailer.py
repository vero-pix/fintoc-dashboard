import smtplib
import os
from dotenv import load_dotenv
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

load_dotenv()

# Tipo de cambio referencial
TC_USD = 970
TC_EUR = 1020


class Mailer:
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender = os.getenv("EMAIL_FROM")
        self.password = os.getenv("EMAIL_APP_PASSWORD", "").replace(" ", "").strip()
        # MODO PRUEBA: Solo Verónica recibe los emails
        self.recipient = ["vvelasquez@cathpro.cl"]

    def send_daily_balances(self, balances, saldos_skualo, variaciones=None):
        subject = "Saldos Diarios CathPro"
        body = self._build_body(balances, saldos_skualo, variaciones)
        return self._send_email(subject, body)

    def _formato_variacion(self, valor, moneda='CLP', invertir=False, size='11px'):
        """
        Formatea variación con flecha y color.
        invertir=True para CxP (subir es malo = rojo, bajar es bueno = verde)
        """
        if valor is None or valor == 0:
            return ""
        
        if moneda == 'EUR':
            simbolo = "€"
            formato = f"{abs(valor):,.2f}"
        elif moneda == 'USD':
            simbolo = "US$"
            formato = f"{abs(valor):,.2f}"
        else:
            simbolo = "$"
            formato = f"{abs(valor):,.0f}"
        
        if invertir:
            if valor > 0:
                return f"<span style='color:#e74c3c;font-size:{size}'>▲ +{simbolo}{formato}</span>"
            else:
                return f"<span style='color:#55b245;font-size:{size}'>▼ {simbolo}{formato}</span>"
        else:
            if valor > 0:
                return f"<span style='color:#55b245;font-size:{size}'>▲ +{simbolo}{formato}</span>"
            else:
                return f"<span style='color:#e74c3c;font-size:{size}'>▼ {simbolo}{formato}</span>"

    def _build_body(self, balances, saldos_skualo, variaciones=None):
        # Totales por moneda desde balances (Fintoc)
        total_clp = sum(b['disponible'] for b in balances if b['moneda'] == 'CLP')
        total_usd = sum(b['disponible'] for b in balances if b['moneda'] == 'USD')
        total_eur = sum(b['disponible'] for b in balances if b['moneda'] == 'EUR')
        
        # Fondos Mutuos (separado - menor liquidez)
        fondos_mutuos = saldos_skualo.get('fondos_mutuos', 0)
        
        # Convertir USD/EUR a CLP
        total_usd_clp = total_usd * TC_USD
        total_eur_clp = total_eur * TC_EUR
        
        fecha = datetime.now().strftime('%d-%m-%Y %H:%M')
        
        # CxC / CxP
        por_cobrar = saldos_skualo.get('por_cobrar', 0)
        por_pagar_nacional = saldos_skualo.get('por_pagar_nacional', 0)
        por_pagar_internacional = saldos_skualo.get('por_pagar_internacional', 0)
        por_pagar_total = por_pagar_nacional + por_pagar_internacional
        
        posicion_neta = por_cobrar - por_pagar_total
        posicion_color = "#55b245" if posicion_neta >= 0 else "#e74c3c"
        
        # Variaciones
        var_clp = self._formato_variacion(variaciones.get('total_clp'), 'CLP') if variaciones else ""
        var_usd = self._formato_variacion(variaciones.get('total_usd'), 'USD') if variaciones else ""
        var_eur = self._formato_variacion(variaciones.get('total_eur'), 'EUR') if variaciones else ""
        var_fondos = self._formato_variacion(variaciones.get('fondos_mutuos'), 'CLP') if variaciones else ""
        var_cobrar = self._formato_variacion(variaciones.get('por_cobrar'), 'CLP') if variaciones else ""
        var_pagar_nac = self._formato_variacion(variaciones.get('por_pagar_nacional'), 'CLP', invertir=True) if variaciones else ""
        var_pagar_int = self._formato_variacion(variaciones.get('por_pagar_internacional'), 'CLP', invertir=True) if variaciones else ""

        # Detalle de saldos bancarios
        rows = ""
        for b in balances:
            moneda = b['moneda']
            banco = b['banco']
            if moneda == 'USD':
                monto = f"US${b['disponible']:,.2f}"
            elif moneda == 'EUR':
                monto = f"€{b['disponible']:,.2f}"
            else:
                monto = f"${b['disponible']:,.0f}"
            
            if moneda == 'USD':
                border_color = '#f46302'
            elif moneda == 'EUR':
                border_color = '#3498db'
            else:
                border_color = '#55b245'
            
            rows += f"""<tr>
                <td style='padding:10px 15px;border-bottom:1px solid #ecf0f1;border-left:3px solid {border_color}'>{banco}</td>
                <td style='padding:10px 15px;border-bottom:1px solid #ecf0f1;text-align:right;font-family:monospace;font-weight:bold'>{monto}</td>
                <td style='padding:10px 15px;border-bottom:1px solid #ecf0f1'>{moneda}</td>
            </tr>"""

        html = f"""<html>
<head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;margin:0;padding:0;background:#f4f4f4">
    <div style="background:#242625;padding:20px 40px">
        <h1 style="color:#f4f4f4;margin:0;font-size:24px">Saldos Diarios CathPro</h1>
    </div>
    <div style="max-width:800px;margin:0 auto;padding:20px">
        <p style="color:#7f8c8d;margin-bottom:20px">Actualizado: {fecha}</p>
        
        <!-- TARJETAS SALDOS BANCOS / INVERSIONES -->
        <p style="font-size:16px;font-weight:bold;color:#242625;margin:0 0 10px">Saldos Bancos / Inversiones</p>
        <table style="width:100%;margin-bottom:25px;border-collapse:separate;border-spacing:8px 0">
            <tr>
                <td style="background:white;padding:15px;border-radius:10px;border-left:5px solid #55b245;width:25%;vertical-align:top">
                    <span style="color:#7f8c8d;font-size:11px;font-weight:600">TOTAL CLP</span><br>
                    <span style="font-size:20px;font-weight:800;color:#242625">${total_clp:,.0f}</span><br>
                    {var_clp}
                </td>
                <td style="background:white;padding:15px;border-radius:10px;border-left:5px solid #f46302;width:25%;vertical-align:top">
                    <span style="color:#7f8c8d;font-size:11px;font-weight:600">TOTAL USD (EN CLP)</span><br>
                    <span style="font-size:20px;font-weight:800;color:#242625">${total_usd_clp:,.0f}</span><br>
                    <span style="color:#f46302;font-size:12px">~ US${total_usd:,.2f}</span><br>
                    {var_usd}
                </td>
                <td style="background:white;padding:15px;border-radius:10px;border-left:5px solid #3498db;width:25%;vertical-align:top">
                    <span style="color:#7f8c8d;font-size:11px;font-weight:600">TOTAL EUR (EN CLP)</span><br>
                    <span style="font-size:20px;font-weight:800;color:#242625">${total_eur_clp:,.0f}</span><br>
                    <span style="color:#3498db;font-size:12px">~ €{total_eur:,.2f}</span><br>
                    {var_eur}
                </td>
                <td style="background:white;padding:15px;border-radius:10px;border-left:5px solid #9b59b6;width:25%;vertical-align:top">
                    <span style="color:#7f8c8d;font-size:11px;font-weight:600">FONDOS MUTUOS</span><br>
                    <span style="font-size:20px;font-weight:800;color:#242625">${fondos_mutuos:,.0f}</span><br>
                    <span style="color:#9b59b6;font-size:10px">* Cierre mes anterior</span><br>
                    {var_fondos}
                </td>
            </tr>
        </table>
        
        <!-- CUENTAS POR COBRAR / PAGAR -->
        <p style="font-size:16px;font-weight:bold;color:#242625;margin:25px 0 10px">Cuentas por Cobrar / Pagar</p>
        <table style="width:100%;margin-bottom:20px;border-collapse:separate;border-spacing:8px 0">
            <tr>
                <td style="background:white;padding:15px;border-radius:10px;border-left:4px solid #55b245;width:33%">
                    <span style="color:#7f8c8d;font-size:11px;font-weight:600">POR COBRAR</span><br>
                    <span style="font-size:20px;font-weight:800;color:#242625">${por_cobrar:,.0f}</span><br>
                    {var_cobrar}
                </td>
                <td style="background:white;padding:15px;border-radius:10px;border-left:4px solid #e74c3c;width:33%">
                    <span style="color:#7f8c8d;font-size:11px;font-weight:600">POR PAGAR NACIONAL</span><br>
                    <span style="font-size:20px;font-weight:800;color:#242625">${por_pagar_nacional:,.0f}</span><br>
                    {var_pagar_nac}
                </td>
                <td style="background:white;padding:15px;border-radius:10px;border-left:4px solid #f46302;width:33%">
                    <span style="color:#7f8c8d;font-size:11px;font-weight:600">POR PAGAR INTERNACIONAL</span><br>
                    <span style="font-size:20px;font-weight:800;color:#242625">${por_pagar_internacional:,.0f}</span><br>
                    {var_pagar_int}
                </td>
            </tr>
        </table>
        
        <!-- POSICIÓN NETA -->
        <div style="background:#242625;padding:20px;border-radius:10px;text-align:center;margin-bottom:20px">
            <span style="color:#7f8c8d;font-size:12px">POSICIÓN NETA (Por Cobrar - Por Pagar)</span><br>
            <span style="font-size:28px;font-weight:800;color:{posicion_color}">${posicion_neta:,.0f}</span>
        </div>
        
        <div style="background:#fff3cd;border-left:4px solid #f46302;padding:12px;border-radius:5px;margin-bottom:25px">
            <span style="color:#856404;font-size:12px"><strong>Nota:</strong> Las cuentas por pagar internacional NO incluyen las OCX sin invoice.</span>
        </div>
        
        <!-- DETALLE SALDOS BANCARIOS -->
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
            <span style="color:#2e7d32;font-size:12px">Envío automático diario 8:00 y 18:00 | TC Ref: USD ${TC_USD} | EUR ${TC_EUR}</span>
        </div>
        
        <div style="margin-top:25px;text-align:center;padding:20px;background:#f8f9fa;border-radius:10px">
            <span style="font-size:14px;font-weight:600;color:#242625">📊 Ver Tableros en Línea</span><br><br>
            <a href="https://fintoc-dashboard.onrender.com/tablero?key=Ale234de" style="display:inline-block;background:#55b245;color:white;padding:10px 20px;border-radius:5px;text-decoration:none;font-size:13px;margin:5px">Saldos Diarios</a>
            <a href="https://fintoc-dashboard.onrender.com/cashflow?key=Ale234de" style="display:inline-block;background:#17a2b8;color:white;padding:10px 20px;border-radius:5px;text-decoration:none;font-size:13px;margin:5px">Cash Flow Anual</a>
            <a href="https://fintoc-dashboard.onrender.com/cashflow/semanal?key=Ale234de" style="display:inline-block;background:#f7941d;color:white;padding:10px 20px;border-radius:5px;text-decoration:none;font-size:13px;margin:5px">Cash Flow Semanal</a>
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

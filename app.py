from flask import Flask, render_template_string, request
from dotenv import load_dotenv
from fintoc_client import FintocClient
from datetime import datetime
import os
import base64

load_dotenv()

app = Flask(__name__)
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "cathpro2024")

# Logo en base64 (lo cargaremos del archivo)
def get_logo_base64():
    try:
        with open("logo_fondo_negro.png", "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except:
        return ""

LOGIN_HTML = """
<html>
<head>
    <title>CathPro - Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css2?family=Raleway:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body{font-family:'Raleway',Arial,sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#242625}
        .login-box{background:#242625;padding:40px;border-radius:10px;text-align:center;border:1px solid #3a3b3a}
        .logo{margin-bottom:30px}
        .logo img{height:60px}
        input{width:100%;padding:12px;margin:10px 0;border:1px solid #3a3b3a;border-radius:5px;box-sizing:border-box;font-family:'Raleway',sans-serif;background:#1a1b1a;color:white}
        input::placeholder{color:#7f8c8d}
        button{width:100%;padding:12px;background:#55b245;color:white;border:none;border-radius:5px;cursor:pointer;font-size:16px;font-family:'Raleway',sans-serif;font-weight:600}
        button:hover{background:#4a9e3d}
        h2{color:#f4f4f4;margin-bottom:20px;font-weight:700}
    </style>
</head>
<body>
    <div class="login-box">
        <div class="logo"><img src="data:image/png;base64,LOGO_BASE64" alt="CathPro"></div>
        <form action="/dashboard" method="get">
            <input type="password" name="key" placeholder="Contraseña" required>
            <button type="submit">Ingresar</button>
        </form>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<html>
<head>
    <title>CathPro - Saldos Bancos</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="300">
    <link href="https://fonts.googleapis.com/css2?family=Raleway:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body{font-family:'Raleway',Arial,sans-serif;margin:0;padding:0;background:#f4f4f4}
        .header{background:#242625;padding:20px 40px;display:flex;align-items:center;gap:20px}
        .header img{height:50px}
        .header h1{color:#f4f4f4;margin:0;font-weight:700;font-size:24px}
        .container{max-width:900px;margin:0 auto;padding:20px}
        .fecha{color:#7f8c8d;margin-bottom:20px}
        table{width:100%;border-collapse:collapse;background:white;border-radius:10px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.1)}
        th{background:#242625;color:white;padding:15px;text-align:left;font-weight:600}
        td{padding:12px 15px;border-bottom:1px solid #ecf0f1}
        tr:hover{background:#f8f9fa}
        .monto{text-align:right;font-family:monospace;font-weight:bold}
        .totales{display:flex;gap:20px;margin-top:20px}
        .total-box{flex:1;background:white;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1)}
        .total-box h3{margin:0;color:#7f8c8d;font-size:14px;font-weight:600}
        .total-box p{margin:10px 0 0;font-size:28px;font-weight:800;color:#242625}
        .clp{border-left:4px solid #55b245}
        .usd{border-left:4px solid #f46302}
        .eur{border-left:4px solid #3498db}
        @media(max-width:600px){.totales{flex-direction:column}table{font-size:14px}td,th{padding:8px}.header{flex-direction:column;text-align:center;padding:15px}}
    </style>
</head>
<body>
    <div class="header">
        <img src="data:image/png;base64,LOGO_BASE64" alt="CathPro">
        <h1>Saldos Bancos</h1>
    </div>
    <div class="container">
        <p class="fecha">Actualizado: FECHA_PLACEHOLDER (auto-refresh 5 min)</p>
        <table>
            <tr><th>Banco</th><th>Cuenta</th><th>Numero</th><th style="text-align:right">Disponible</th><th>Moneda</th></tr>
            ROWS_PLACEHOLDER
        </table>
        <div class="totales">
            <div class="total-box clp"><h3>TOTAL CLP</h3><p>TOTAL_CLP_PLACEHOLDER</p></div>
            <div class="total-box usd"><h3>TOTAL USD</h3><p>TOTAL_USD_PLACEHOLDER</p></div>
            <div class="total-box eur"><h3>TOTAL EUR</h3><p>TOTAL_EUR_PLACEHOLDER</p></div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def login():
    logo_b64 = get_logo_base64()
    return LOGIN_HTML.replace('LOGO_BASE64', logo_b64)

@app.route('/dashboard')
def dashboard():
    key = request.args.get('key', '')
    if key != DASHBOARD_PASSWORD:
        return "<script>alert('Contraseña incorrecta');window.location='/';</script>"
    client = FintocClient()
    balances = client.get_all_balances()
    total_clp = sum(b['disponible'] for b in balances if b['moneda'] == 'CLP')
    total_usd = sum(b['disponible'] for b in balances if b['moneda'] == 'USD')
    total_eur = sum(b['disponible'] for b in balances if b['moneda'] == 'EUR')
    rows = ""
    for b in balances:
        moneda = b['moneda']
        if moneda == 'USD':
            monto = f"${b['disponible']:,.2f}"
        elif moneda == 'EUR':
            monto = f"€{b['disponible']:,.0f}"
        else:
            monto = f"${b['disponible']:,.0f}"
        rows += f"<tr><td>{b['banco']}</td><td>{b['cuenta_nombre']}</td><td>{b['numero']}</td><td class='monto'>{monto}</td><td>{moneda}</td></tr>"
    logo_b64 = get_logo_base64()
    html = DASHBOARD_HTML.replace('LOGO_BASE64', logo_b64)
    html = html.replace('FECHA_PLACEHOLDER', datetime.now().strftime('%d-%m-%Y %H:%M'))
    html = html.replace('ROWS_PLACEHOLDER', rows)
    html = html.replace('TOTAL_CLP_PLACEHOLDER', f"${total_clp:,.0f}")
    html = html.replace('TOTAL_USD_PLACEHOLDER', f"${total_usd:,.2f}")
    html = html.replace('TOTAL_EUR_PLACEHOLDER', f"€{total_eur:,.0f}")
    return html
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
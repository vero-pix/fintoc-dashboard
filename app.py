from flask import Flask, request
from dotenv import load_dotenv
from fintoc_client import FintocClient
from skualo_client import SkualoClient
from datetime import datetime
import os
import base64

load_dotenv()

app = Flask(__name__)
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "cathpro2024")

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
    <title>CathPro - Saldos Diarios</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="300">
    <link href="https://fonts.googleapis.com/css2?family=Raleway:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body{font-family:'Raleway',Arial,sans-serif;margin:0;padding:0;background:#f4f4f4}
        .header{background:#242625;padding:20px 40px;display:flex;align-items:center;gap:20px}
        .header img{height:50px}
        .header h1{color:#f4f4f4;margin:0;font-weight:700;font-size:24px}
        .container{max-width:1100px;margin:0 auto;padding:20px}
        .fecha{color:#7f8c8d;margin-bottom:20px}
        .section-row{display:flex;justify-content:space-between;align-items:center;margin:30px 0 15px}
        .section-title{color:#242625;font-size:18px;font-weight:700;margin:0}
        .section-title-right{color:#242625;font-size:18px;font-weight:700;margin:0}
        .cards{display:flex;gap:15px;flex-wrap:wrap;margin-bottom:20px}
        .card{flex:1;min-width:150px;background:white;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1)}
        .card h3{margin:0;color:#7f8c8d;font-size:12px;font-weight:600;text-transform:uppercase}
        .card p{margin:10px 0 0;font-size:22px;font-weight:800;color:#242625}
        .card.green{border-left:4px solid #55b245}
        .card.orange{border-left:4px solid #f46302}
        .card.blue{border-left:4px solid #3498db}
        .card.red{border-left:4px solid #e74c3c}
        .card.purple{border-left:4px solid #9b59b6}
        .cards-split{display:flex;gap:15px;margin-bottom:20px}
        .cards-left{flex:3;display:flex;gap:15px}
        .cards-right{flex:1;display:flex;gap:15px}
        .divider{width:2px;background:#ddd;margin:0 10px}
        table{width:100%;border-collapse:collapse;background:white;border-radius:10px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.1)}
        th{background:#242625;color:white;padding:12px 15px;text-align:left;font-weight:600;font-size:14px}
        td{padding:10px 15px;border-bottom:1px solid #ecf0f1;font-size:14px}
        tr:hover{background:#f8f9fa}
        .monto{text-align:right;font-family:monospace;font-weight:bold}
        .posicion{margin-top:20px;background:#242625;color:white;padding:20px;border-radius:10px;text-align:center}
        .posicion h3{margin:0;font-size:14px;color:#7f8c8d}
        .posicion p{margin:10px 0 0;font-size:32px;font-weight:800}
        .posicion.positive p{color:#55b245}
        .posicion.negative p{color:#e74c3c}
        .note-ocx{margin-top:20px;margin-bottom:30px;padding:15px;background:#fff3cd;border-left:4px solid #f46302;border-radius:5px;font-size:13px;color:#856404}
        .footer-note{margin-top:20px;padding:15px;background:#e8f5e9;border-left:4px solid #55b245;border-radius:5px;font-size:13px;color:#2e7d32;text-align:center}
        @media(max-width:768px){.cards{flex-direction:column}.cards-split{flex-direction:column}.cards-left,.cards-right{flex:1}.divider{display:none}.card{min-width:auto}td,th{padding:8px;font-size:12px}.header{flex-direction:column;text-align:center;padding:15px}}
    </style>
</head>
<body>
    <div class="header">
        <img src="data:image/png;base64,LOGO_BASE64" alt="CathPro">
        <h1>Saldos Diarios CathPro</h1>
    </div>
    <div class="container">
        <p class="fecha">Actualizado: FECHA_PLACEHOLDER (auto-refresh 5 min)</p>
        
        <div class="section-row">
            <div class="section-title">Saldos Bancos</div>
            <div class="section-title-right">Inversiones</div>
        </div>
        <div class="cards-split">
            <div class="cards-left">
                <div class="card green"><h3>Total CLP</h3><p>TOTAL_CLP_PLACEHOLDER</p></div>
                <div class="card orange"><h3>Total USD</h3><p>TOTAL_USD_PLACEHOLDER</p></div>
                <div class="card blue"><h3>Total EUR</h3><p>TOTAL_EUR_PLACEHOLDER</p></div>
            </div>
            <div class="divider"></div>
            <div class="cards-right">
                <div class="card purple"><h3>Fondos Mutuos</h3><p>FONDOS_MUTUOS_PLACEHOLDER</p></div>
            </div>
        </div>
        
        <div class="section-row">
            <div class="section-title">Cuentas por Cobrar / Pagar</div>
        </div>
        <div class="cards">
            <div class="card green"><h3>Por Cobrar</h3><p>POR_COBRAR_PLACEHOLDER</p></div>
            <div class="card red"><h3>Por Pagar Nacional</h3><p>POR_PAGAR_NAC_PLACEHOLDER</p></div>
            <div class="card orange"><h3>Por Pagar Internacional</h3><p>POR_PAGAR_INT_PLACEHOLDER</p></div>
        </div>
        
        <div class="posicion POSICION_CLASS">
            <h3>POSICIÓN NETA (Por Cobrar - Por Pagar)</h3>
            <p>POSICION_NETA_PLACEHOLDER</p>
        </div>
        
        <div class="note-ocx">
            <strong>Nota:</strong> Las cuentas por pagar internacional NO incluyen las OCX (órdenes de compra internacional) sobre las que aún no se ha recibido invoice.
        </div>
        
        <div class="section-row">
            <div class="section-title">Detalle Saldos Bancarios</div>
        </div>
        <table>
            <tr><th>Banco</th><th style="text-align:right">Disponible</th><th>Moneda</th></tr>
            ROWS_PLACEHOLDER
        </table>
        
        <div class="footer-note">
            Envío automático diario 8:00 y 18:00
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
    
    # Datos Fintoc
    fintoc = FintocClient()
    balances = fintoc.get_all_balances()
    total_clp = sum(b['disponible'] for b in balances if b['moneda'] == 'CLP')
    total_usd = sum(b['disponible'] for b in balances if b['moneda'] == 'USD')
    total_eur = sum(b['disponible'] for b in balances if b['moneda'] == 'EUR')
    
    # Datos Skualo
    skualo = SkualoClient()
    saldos_skualo = skualo.get_saldos_cuentas()
    
    # Calcular posición neta
    posicion_neta = saldos_skualo['por_cobrar'] - saldos_skualo['por_pagar_total']
    posicion_class = "positive" if posicion_neta >= 0 else "negative"
    
    # Construir filas tabla bancos
    rows = ""
    for b in balances:
        moneda = b['moneda']
        if moneda == 'USD':
            monto = f"${b['disponible']:,.2f}"
        elif moneda == 'EUR':
            monto = f"€{b['disponible']:,.0f}"
        else:
            monto = f"${b['disponible']:,.0f}"
        rows += f"<tr><td>{b['banco']}</td><td class='monto'>{monto}</td><td>{moneda}</td></tr>"
    
    # Construir HTML
    logo_b64 = get_logo_base64()
    html = DASHBOARD_HTML.replace('LOGO_BASE64', logo_b64)
    html = html.replace('FECHA_PLACEHOLDER', datetime.now().strftime('%d-%m-%Y %H:%M'))
    html = html.replace('ROWS_PLACEHOLDER', rows)
    html = html.replace('TOTAL_CLP_PLACEHOLDER', f"${total_clp:,.0f}")
    html = html.replace('TOTAL_USD_PLACEHOLDER', f"${total_usd:,.2f}")
    html = html.replace('TOTAL_EUR_PLACEHOLDER', f"€{total_eur:,.0f}")
    html = html.replace('FONDOS_MUTUOS_PLACEHOLDER', f"${saldos_skualo['fondos_mutuos']:,.0f}")
    html = html.replace('POR_COBRAR_PLACEHOLDER', f"${saldos_skualo['por_cobrar']:,.0f}")
    html = html.replace('POR_PAGAR_NAC_PLACEHOLDER', f"${saldos_skualo['por_pagar_nacional']:,.0f}")
    html = html.replace('POR_PAGAR_INT_PLACEHOLDER', f"${saldos_skualo['por_pagar_internacional']:,.0f}")
    html = html.replace('POSICION_NETA_PLACEHOLDER', f"${posicion_neta:,.0f}")
    html = html.replace('POSICION_CLASS', posicion_class)
    
    return html

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
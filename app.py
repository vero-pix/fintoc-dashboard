from flask import Flask, request
from dotenv import load_dotenv
from fintoc_client import FintocClient
from skualo_client import SkualoClient
from datetime import datetime
import os
import base64
import json
import requests
import pandas as pd
from io import BytesIO

load_dotenv()

app = Flask(__name__)
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "cathpro2024")

# ============================================
# CONFIGURACIÓN CASHFLOW
# ============================================
FORECAST_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSCnSKEn66rdSM8T1R-lWIi79kzK1I2kDnS2ms7viozTdOW9tV5Gt7FBXRB-aErK-nhMFMU4C00Wbg7/pub?output=xlsx"
MESES_SOLO_COMPROMISO = ['Enero', 'Febrero', 'Marzo']
MESES_ORDEN = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
               'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
MES_NUM = {m: i+1 for i, m in enumerate(MESES_ORDEN)}

RECURRENTES = [
    {'dia': 5, 'concepto': 'ARRIENDO OFICINA', 'monto': 1800000},
    {'dia': 5, 'concepto': 'Leasing BCI1', 'monto': 3200000},
    {'dia': 7, 'concepto': 'PREVIRED', 'monto': 32000000},
    {'dia': 10, 'concepto': 'Leasing Oficina', 'monto': 1229177},
    {'dia': 15, 'concepto': 'LEASING BCI', 'monto': 3200000},
    {'dia': 15, 'concepto': 'Leaseback', 'monto': 1800000},
    {'dia': 16, 'concepto': 'SII - IVA', 'monto': 115000000},
    {'dia': 27, 'concepto': 'REMUNERACIONES', 'monto': 105000000},
]
TOTAL_RECURRENTES = sum(r['monto'] for r in RECURRENTES)

def get_logo_base64():
    try:
        with open("logo_fondo_negro.png", "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except:
        return ""

def parse_clp(val):
    if pd.isna(val) or val == '' or val == '$0':
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    val = str(val).replace('$', '').replace(',', '')
    try:
        return float(val)
    except:
        return 0

def get_forecast_2026():
    """Obtener forecast desde Google Sheet con lógica Q1 solo Compromiso"""
    try:
        response = requests.get(FORECAST_URL, timeout=30)
        df = pd.read_excel(BytesIO(response.content))
        df_año = df[df['Año'] == 2026].copy()
        
        # Nombres de columnas actualizados
        col_forecast = 'Forecast del mes\n(Se modifica del día 3 de cada mes)'
        col_compromiso = 'Compromiso Inicio Mes'
        
        df_año['Forecast'] = df_año[col_forecast].apply(parse_clp)
        df_año['Compromiso'] = df_año[col_compromiso].apply(parse_clp)
        
        resultado = []
        for mes in MESES_ORDEN:
            df_mes = df_año[df_año['Mes'] == mes]
            c = df_mes['Compromiso'].sum()
            f = df_mes['Forecast'].sum()
            
            if mes in MESES_SOLO_COMPROMISO:
                usar = c
                vta_nueva = 0
            else:
                usar = c if c > 0 else f
                vta_nueva = max(0, usar - c)
            
            pct = int(c / usar * 100) if usar > 0 else 0
            
            resultado.append({
                'mes': mes[:3],
                'mes_full': mes,
                'compromiso': round(c),
                'forecast': round(f),
                'usar': round(usar),
                'apalancada': round(c),
                'vta_nueva': round(vta_nueva),
                'pct_certeza': pct
            })
        
        return resultado
    except Exception as e:
        print(f"Error forecast: {e}")
        return None


# ============================================
# LOGIN HTML
# ============================================
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


# ============================================
# DASHBOARD SALDOS HTML
# ============================================
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
        .nav-links{margin-left:auto;display:flex;gap:15px}
        .nav-links a{color:#7f8c8d;text-decoration:none;padding:8px 15px;border-radius:5px;font-size:14px}
        .nav-links a:hover,.nav-links a.active{background:#55b245;color:white}
        .container{max-width:1100px;margin:0 auto;padding:20px}
        .fecha{color:#7f8c8d;margin-bottom:20px}
        .section-row{display:flex;justify-content:space-between;align-items:center;margin:30px 0 15px}
        .section-title{color:#242625;font-size:18px;font-weight:700;margin:0}
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
        @media(max-width:768px){.cards{flex-direction:column}.cards-split{flex-direction:column}.cards-left,.cards-right{flex:1}.divider{display:none}.card{min-width:auto}td,th{padding:8px;font-size:12px}.header{flex-direction:column;text-align:center;padding:15px}.nav-links{margin:10px 0 0}}
    </style>
</head>
<body>
    <div class="header">
        <img src="data:image/png;base64,LOGO_BASE64" alt="CathPro">
        <h1>Saldos Diarios CathPro</h1>
        <div class="nav-links">
            <a href="/dashboard?key=KEY_PLACEHOLDER" class="active">Saldos</a>
            <a href="/cashflow?key=KEY_PLACEHOLDER">Cash Flow</a>
        </div>
    </div>
    <div class="container">
        <p class="fecha">Actualizado: FECHA_PLACEHOLDER (auto-refresh 5 min)</p>
        
        <div class="section-row">
            <div class="section-title">Saldos Bancos</div>
            <div class="section-title">Inversiones</div>
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


# ============================================
# CASHFLOW HTML
# ============================================
CASHFLOW_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>CathPro - Cash Flow</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="300">
    <link href="https://fonts.googleapis.com/css2?family=Raleway:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Raleway',sans-serif;background:#fff;color:#242625}
        .header{background:#242625;padding:15px 30px;display:flex;align-items:center;justify-content:space-between}
        .header-left{display:flex;align-items:center;gap:15px}
        .header img{height:50px}
        .header h1{color:#fff;font-size:20px;font-weight:600}
        .header-sub{color:#888;font-size:12px}
        .header-right{text-align:right}
        .header-saldo{color:#55b245;font-size:20px;font-weight:700}
        .nav-links{display:flex;gap:10px;margin-left:30px}
        .nav-links a{color:#888;text-decoration:none;padding:8px 15px;border-radius:5px;font-size:13px}
        .nav-links a:hover,.nav-links a.active{background:#55b245;color:white}
        .container{max-width:1200px;margin:0 auto;padding:25px}
        .tabs{display:flex;gap:8px;margin-bottom:20px}
        .tab{padding:10px 25px;background:#e0e0e0;border:none;border-radius:6px;cursor:pointer;font-size:13px;font-weight:500;font-family:'Raleway',sans-serif}
        .tab.active{background:#55b245;color:white}
        .view{display:none}
        .view.active{display:block}
        .legend{background:#f8f9fa;border-radius:10px;padding:15px 20px;margin-bottom:25px;display:flex;gap:30px;align-items:center;flex-wrap:wrap}
        .legend-item{display:flex;align-items:center;gap:10px}
        .legend-box{width:18px;height:18px;border-radius:4px}
        .legend-box.apal{background:#2e7d32}
        .legend-box.vta{background:#ff9800}
        .legend-title{font-weight:600;font-size:12px}
        .legend-desc{font-size:11px;color:#666}
        .legend-rule{margin-left:auto;font-size:12px;color:#666}
        .q1-box{background:#e8f5e9;border-radius:10px;padding:20px;margin-bottom:25px}
        .q1-title{font-size:14px;margin-bottom:15px;color:#2e7d32;font-weight:600}
        .q1-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:15px}
        .q1-card{background:#fff;border-radius:8px;padding:15px;text-align:center}
        .q1-mes{font-size:12px;color:#666}
        .q1-value{font-size:22px;font-weight:700;color:#2e7d32}
        .badge{display:inline-block;padding:3px 10px;border-radius:4px;font-size:10px;font-weight:600}
        .badge-apal{background:#e8f5e9;color:#2e7d32}
        .badge-vta{background:#fff3e0;color:#e65100}
        table{width:100%;border-collapse:collapse;background:#fafafa;border-radius:8px;overflow:hidden;margin-bottom:25px}
        th{background:#242625;color:#fff;padding:12px;font-size:11px;font-weight:500;text-align:left}
        th.right{text-align:right}
        th.center{text-align:center}
        td{padding:12px;font-size:12px;border-bottom:1px solid #eee}
        td.right{text-align:right;font-family:monospace}
        td.center{text-align:center}
        td.apal{color:#2e7d32}
        td.vta{color:#ff9800}
        tr.q1{background:#e8f5e9}
        tr.total{background:#f0f0f0;font-weight:700}
        .bar-container{height:10px;background:#eee;border-radius:5px;overflow:hidden;display:flex}
        .bar-apal{background:#2e7d32}
        .bar-vta{background:#ff9800}
        .certeza{font-size:12px}
        .summary{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin-bottom:25px}
        .summary-card{border-radius:10px;padding:20px;text-align:center}
        .summary-card.apal{background:#e8f5e9}
        .summary-card.vta{background:#fff3e0}
        .summary-card.q1{background:#e3f2fd}
        .summary-card.total{background:#f5f5f5}
        .summary-label{font-size:10px;color:#666;margin-bottom:8px;text-transform:uppercase}
        .summary-value{font-size:24px;font-weight:700}
        .summary-value.apal{color:#2e7d32}
        .summary-value.vta{color:#ff9800}
        .summary-value.azul{color:#17a2b8}
        .summary-sub{font-size:11px;color:#666;margin-top:4px}
        .insight{background:#fff8e1;border:1px solid #ffcc80;border-radius:10px;padding:15px 20px;margin-bottom:20px}
        .insight-title{font-weight:600;margin-bottom:8px}
        .insight-text{font-size:13px;color:#666}
        .footer{text-align:center;padding:15px;color:#888;font-size:10px}
        h3{font-size:14px;font-weight:600;margin-bottom:12px;padding-bottom:8px;border-bottom:2px solid #55b245}
        .kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:20px}
        .kpi{background:#fff;border-radius:8px;padding:15px;box-shadow:0 2px 6px rgba(0,0,0,0.08);border-left:4px solid #55b245}
        .kpi.azul{border-left-color:#17a2b8}
        .kpi.naranja{border-left-color:#f7941d}
        .kpi.morado{border-left-color:#6f42c1}
        .kpi-label{font-size:10px;color:#666;text-transform:uppercase;margin-bottom:4px}
        .kpi-value{font-size:18px;font-weight:700}
        .kpi-value.verde{color:#55b245}
        .kpi-sub{font-size:10px;color:#888;margin-top:2px}
        .alert{background:linear-gradient(135deg,#f7941d,#e8850a);color:#fff;padding:12px 18px;border-radius:8px;margin-bottom:20px;display:flex;align-items:center;gap:12px;font-size:13px}
        @media(max-width:768px){.header{flex-direction:column;gap:10px}.nav-links{margin:10px 0}.q1-grid{grid-template-columns:1fr}.summary{grid-template-columns:repeat(2,1fr)}.kpis{grid-template-columns:repeat(2,1fr)}.legend{flex-direction:column;align-items:flex-start}.legend-rule{margin-left:0;margin-top:10px}}
    </style>
</head>
<body>
    <div class="header">
        <div class="header-left">
            <img src="data:image/png;base64,LOGO_BASE64" alt="CathPro">
            <div>
                <h1>Cash Flow CathPro</h1>
                <div class="header-sub">Proyección 2026 | FECHA_PLACEHOLDER</div>
            </div>
            <div class="nav-links">
                <a href="/dashboard?key=KEY_PLACEHOLDER">Saldos</a>
                <a href="/cashflow?key=KEY_PLACEHOLDER" class="active">Cash Flow</a>
            </div>
        </div>
        <div class="header-right">
            <div class="header-saldo">SALDO_PLACEHOLDER</div>
            <div class="header-sub">Saldo Fintoc CLP</div>
        </div>
    </div>
    
    <div class="container">
        <div class="tabs">
            <button class="tab active" onclick="showView('resumen')">📊 Resumen</button>
            <button class="tab" onclick="showView('anual')">📈 Vista Anual</button>
            <button class="tab" onclick="showView('recurrentes')">💰 Recurrentes</button>
        </div>
        
        <!-- VISTA RESUMEN -->
        <div id="resumen" class="view active">
            ALERT_PLACEHOLDER
            
            <div class="kpis">
                <div class="kpi azul">
                    <div class="kpi-label">Saldo Inicial</div>
                    <div class="kpi-value">SALDO_PLACEHOLDER</div>
                    <div class="kpi-sub">Hoy</div>
                </div>
                <div class="kpi">
                    <div class="kpi-label">Entradas 90d</div>
                    <div class="kpi-value verde">ENTRADAS_PLACEHOLDER</div>
                    <div class="kpi-sub">Compromiso Q1</div>
                </div>
                <div class="kpi naranja">
                    <div class="kpi-label">Salidas 90d</div>
                    <div class="kpi-value">SALIDAS_PLACEHOLDER</div>
                    <div class="kpi-sub">Recurrentes</div>
                </div>
                <div class="kpi morado">
                    <div class="kpi-label">Saldo Final</div>
                    <div class="kpi-value verde">SALDO_FINAL_PLACEHOLDER</div>
                    <div class="kpi-sub">Proyectado</div>
                </div>
                <div class="kpi">
                    <div class="kpi-label">Saldo Mínimo</div>
                    <div class="kpi-value verde">SALDO_MIN_PLACEHOLDER</div>
                    <div class="kpi-sub">En período</div>
                </div>
            </div>
            
            <div class="q1-box">
                <div class="q1-title">Q1 2026 - 100% Apalancada (Alta Certeza)</div>
                <div class="q1-grid">
                    Q1_CARDS_PLACEHOLDER
                </div>
            </div>
            
            <div class="summary">
                <div class="summary-card apal">
                    <div class="summary-label">Apalancada Total</div>
                    <div class="summary-value apal">TOTAL_APAL_PLACEHOLDER</div>
                    <div class="summary-sub">43% del total</div>
                </div>
                <div class="summary-card vta">
                    <div class="summary-label">Vta Nueva Total</div>
                    <div class="summary-value vta">TOTAL_VTA_PLACEHOLDER</div>
                    <div class="summary-sub">57% del total</div>
                </div>
                <div class="summary-card q1">
                    <div class="summary-label">Q1 (100% Certeza)</div>
                    <div class="summary-value azul">TOTAL_Q1_PLACEHOLDER</div>
                    <div class="summary-sub">Solo Compromiso</div>
                </div>
                <div class="summary-card total">
                    <div class="summary-label">Total 2026</div>
                    <div class="summary-value">TOTAL_ANUAL_PLACEHOLDER</div>
                    <div class="summary-sub">Proyección completa</div>
                </div>
            </div>
        </div>
        
        <!-- VISTA ANUAL -->
        <div id="anual" class="view">
            <div class="legend">
                <div class="legend-item">
                    <div class="legend-box apal"></div>
                    <div>
                        <div class="legend-title">Apalancada</div>
                        <div class="legend-desc">Proyectos confirmados (Compromiso)</div>
                    </div>
                </div>
                <div class="legend-item">
                    <div class="legend-box vta"></div>
                    <div>
                        <div class="legend-title">Venta Nueva</div>
                        <div class="legend-desc">Proyección comercial</div>
                    </div>
                </div>
                <div class="legend-rule"><strong>Regla:</strong> Q1 = Solo Compromiso | Q2-Q4 = Compromiso > Forecast</div>
            </div>
            
            <h3>Detalle Mensual con Nivel de Certeza</h3>
            <table>
                <thead>
                    <tr>
                        <th>Mes</th>
                        <th class="right">Apalancada</th>
                        <th class="right">Vta Nueva</th>
                        <th class="right">Total</th>
                        <th class="center">Certeza</th>
                        <th style="width:150px">Composición</th>
                    </tr>
                </thead>
                <tbody>
                    ROWS_ANUAL_PLACEHOLDER
                </tbody>
            </table>
            
            <div class="insight">
                <div class="insight-title">💡 Insight Clave</div>
                <div class="insight-text">
                    La certeza del forecast <strong>decrece</strong> a lo largo del año: Q1 tiene 100% certeza (solo Compromiso), mientras que Q4 promedia solo 25% certeza. Esto es normal y refleja que los proyectos a largo plazo aún no están confirmados.
                </div>
            </div>
        </div>
        
        <!-- VISTA RECURRENTES -->
        <div id="recurrentes" class="view">
            <h3>Pagos Recurrentes Mensuales</h3>
            <table>
                <thead>
                    <tr>
                        <th>Día</th>
                        <th>Concepto</th>
                        <th class="right">Monto</th>
                    </tr>
                </thead>
                <tbody>
                    ROWS_RECURRENTES_PLACEHOLDER
                    <tr class="total">
                        <td colspan="2">TOTAL MENSUAL</td>
                        <td class="right">TOTAL_REC_PLACEHOLDER</td>
                    </tr>
                </tbody>
            </table>
            
            <div class="insight" style="background:#e3f2fd;border-color:#90caf9">
                <div class="insight-title">📋 Distribución de Pagos</div>
                <div class="insight-text">
                    Los pagos críticos son <strong>SII-IVA</strong> (día 16, $115M) y <strong>Remuneraciones</strong> (día 27, $105M), representando el 84% del total mensual.
                </div>
            </div>
        </div>
        
        <div class="footer">
            Cash Flow CathPro | Apalancada = Compromiso | Vta Nueva = Forecast sin Compromiso | FECHA_PLACEHOLDER
        </div>
    </div>
    
    <script>
        function showView(id) {
            document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            event.target.classList.add('active');
        }
    </script>
</body>
</html>
"""


# ============================================
# RUTAS
# ============================================

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
    
    posicion_neta = saldos_skualo['por_cobrar'] - saldos_skualo['por_pagar_total']
    posicion_class = "positive" if posicion_neta >= 0 else "negative"
    
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
    
    logo_b64 = get_logo_base64()
    html = DASHBOARD_HTML.replace('LOGO_BASE64', logo_b64)
    html = html.replace('FECHA_PLACEHOLDER', datetime.now().strftime('%d-%m-%Y %H:%M'))
    html = html.replace('KEY_PLACEHOLDER', key)
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


@app.route('/cashflow')
def cashflow():
    key = request.args.get('key', '')
    if key != DASHBOARD_PASSWORD:
        return "<script>alert('Contraseña incorrecta');window.location='/';</script>"
    
    # Obtener saldo Fintoc
    try:
        fintoc = FintocClient()
        balances = fintoc.get_all_balances()
        saldo_clp = sum(b['disponible'] for b in balances if b['moneda'] == 'CLP')
    except:
        saldo_clp = 160000000
    
    # Obtener forecast
    forecast = get_forecast_2026()
    
    if not forecast:
        return "<h1>Error cargando datos del forecast</h1>"
    
    # Calcular totales
    total_apal = sum(m['apalancada'] for m in forecast)
    total_vta = sum(m['vta_nueva'] for m in forecast)
    total_anual = sum(m['usar'] for m in forecast)
    total_q1 = sum(m['usar'] for m in forecast[:3])
    
    # Calcular proyección 90 días simplificada
    entradas_90d = sum(m['usar'] for m in forecast[:3])  # Q1
    salidas_90d = TOTAL_RECURRENTES * 3
    saldo_final = saldo_clp + entradas_90d - salidas_90d
    saldo_min = saldo_clp - TOTAL_RECURRENTES  # Aprox primer mes
    
    # Formatear
    fmt = lambda x: f"${x/1e6:.0f}M"
    fmt_full = lambda x: f"${x:,.0f}"
    
    # Q1 cards
    q1_cards = ""
    for m in forecast[:3]:
        q1_cards += f'''
        <div class="q1-card">
            <div class="q1-mes">{m['mes_full']}</div>
            <div class="q1-value">{fmt(m['usar'])}</div>
            <span class="badge badge-apal">100% Compromiso</span>
        </div>
        '''
    
    # Rows anual
    rows_anual = ""
    for i, m in enumerate(forecast):
        is_q1 = 'q1' if i < 3 else ''
        vta_display = fmt(m['vta_nueva']) if m['vta_nueva'] > 0 else '-'
        vta_class = 'vta' if m['vta_nueva'] > 0 else ''
        pct = m['pct_certeza']
        icon = '🟢' if pct >= 70 else '🟡' if pct >= 40 else '🔴'
        
        rows_anual += f'''
        <tr class="{is_q1}">
            <td{"style='font-weight:600'" if i < 3 else ""}>{m['mes_full']} 2026</td>
            <td class="right apal">{fmt(m['apalancada'])}</td>
            <td class="right {vta_class}">{vta_display}</td>
            <td class="right" style="font-weight:600">{fmt(m['usar'])}</td>
            <td class="center certeza">{pct}% {icon}</td>
            <td>
                <div class="bar-container">
                    <div class="bar-apal" style="width:{pct}%"></div>
                    <div class="bar-vta" style="width:{100-pct}%"></div>
                </div>
            </td>
        </tr>
        '''
    
    rows_anual += f'''
    <tr class="total">
        <td>TOTAL 2026</td>
        <td class="right apal">{fmt(total_apal)}</td>
        <td class="right vta">{fmt(total_vta)}</td>
        <td class="right" style="font-size:14px">{fmt(total_anual)}</td>
        <td colspan="2"></td>
    </tr>
    '''
    
    # Rows recurrentes
    rows_rec = ""
    for r in RECURRENTES:
        bg = 'style="background:#fff8e1"' if r['monto'] > 30000000 else ''
        fw = 'style="font-weight:600"' if r['monto'] > 50000000 else ''
        rows_rec += f'<tr {bg}><td>{r["dia"]}</td><td>{r["concepto"]}</td><td class="right" {fw}>{fmt_full(r["monto"])}</td></tr>'
    
    # Alerta
    alert_html = ""
    if saldo_min < 50000000:
        alert_html = '<div class="alert"><span>⚠️</span><div><strong>Alerta:</strong> Saldo mínimo proyectado bajo el umbral de $50M</div></div>'
    else:
        alert_html = '<div class="alert" style="background:linear-gradient(135deg,#55b245,#449636)"><span>✅</span><div>Sin alertas de liquidez - Saldo mínimo: ' + fmt(saldo_min) + '</div></div>'
    
    # Construir HTML
    logo_b64 = get_logo_base64()
    html = CASHFLOW_HTML.replace('LOGO_BASE64', logo_b64)
    html = html.replace('FECHA_PLACEHOLDER', datetime.now().strftime('%d-%m-%Y %H:%M'))
    html = html.replace('KEY_PLACEHOLDER', key)
    html = html.replace('SALDO_PLACEHOLDER', fmt_full(saldo_clp))
    html = html.replace('ENTRADAS_PLACEHOLDER', fmt(entradas_90d))
    html = html.replace('SALIDAS_PLACEHOLDER', fmt(salidas_90d))
    html = html.replace('SALDO_FINAL_PLACEHOLDER', fmt(saldo_final))
    html = html.replace('SALDO_MIN_PLACEHOLDER', fmt(saldo_min))
    html = html.replace('Q1_CARDS_PLACEHOLDER', q1_cards)
    html = html.replace('TOTAL_APAL_PLACEHOLDER', fmt(total_apal))
    html = html.replace('TOTAL_VTA_PLACEHOLDER', fmt(total_vta))
    html = html.replace('TOTAL_Q1_PLACEHOLDER', fmt(total_q1))
    html = html.replace('TOTAL_ANUAL_PLACEHOLDER', fmt(total_anual))
    html = html.replace('ROWS_ANUAL_PLACEHOLDER', rows_anual)
    html = html.replace('ROWS_RECURRENTES_PLACEHOLDER', rows_rec)
    html = html.replace('TOTAL_REC_PLACEHOLDER', fmt_full(TOTAL_RECURRENTES))
    html = html.replace('ALERT_PLACEHOLDER', alert_html)
    
    return html


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

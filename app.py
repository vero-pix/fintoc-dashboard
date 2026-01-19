from flask import Flask, request, Response, jsonify
from dotenv import load_dotenv
from fintoc_client import FintocClient
from skualo_client import SkualoClient
from skualo_cashflow import SkualoCashFlow
from skualo_bancos import SkualoBancosClient
from skualo_documentos import SkualoDocumentosClient
from datetime import datetime, timedelta
import pytz
import os
import base64
import json
import requests
import pandas as pd
try:
    from xhtml2pdf import pisa
    PDF_ENABLED = True
except ImportError:
    PDF_ENABLED = False
    print("WARNING: xhtml2pdf not found. PDF export disabled.")
# from fintoc_webhook import get_total_entradas_hoy, get_resumen_hoy, set_movimientos_hoy, procesar_evento_fintoc
# Importar asistente de chat (lazy load para evitar error si no hay API key)
try:
    from chat_assistant import CathProAssistant
    CHAT_ENABLED = True
except Exception as e:
    print(f"Chat assistant no disponible: {e}")
    CHAT_ENABLED = False

load_dotenv()

app = Flask(__name__)
TABLERO_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "cathpro2024")
TZ_CHILE = pytz.timezone('America/Santiago')

# ============================================
# CONFIGURACIÓN CASHFLOW
# ============================================
FORECAST_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSCnSKEn66rdSM8T1R-lWIi79kzK1I2kDnS2ms7viozTdOW9tV5Gt7FBXRB-aErK-nhMFMU4C00Wbg7/pub?output=xlsx"
MESES_SOLO_COMPROMISO = ['Enero', 'Febrero', 'Marzo']
MESES_ORDEN = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
               'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

RECURRENTES = [
    {'dia': 1, 'concepto': 'Crédito Hipotecario', 'monto': 1000000},
    {'dia': 5, 'concepto': 'ARRIENDO OFICINA', 'monto': 1800000},
    {'dia': 5, 'concepto': 'Leasing BCI1', 'monto': 3200000},
    {'dia': 7, 'concepto': 'PREVIRED', 'monto': 32000000},
    {'dia': 7, 'concepto': 'Leasing Progreso', 'monto': 1500000},
    {'dia': 10, 'concepto': 'Leasing Oficina', 'monto': 1229177},
    {'dia': 15, 'concepto': 'LEASING BCI', 'monto': 3200000},
    {'dia': 15, 'concepto': 'Leaseback', 'monto': 1800000},
    {'dia': 16, 'concepto': 'SII - IVA', 'monto': 115000000},
    {'dia': 19, 'concepto': 'Crédito Santander', 'monto': 6000000},
    {'dia': 27, 'concepto': 'REMUNERACIONES', 'monto': 105000000},
    {'dia': 28, 'concepto': 'Honorarios', 'monto': 2100000},
]
TOTAL_RECURRENTES = sum(r['monto'] for r in RECURRENTES)

DIAS_PAGO_CLIENTES = [
    {'cliente': 'CENTINELA', 'dias': 10},
    {'cliente': 'COLLAHUASI', 'dias': 10},
    {'cliente': 'COPEC', 'dias': 15},
    {'cliente': 'PELAMBRES', 'dias': 15},
    {'cliente': 'ENAP', 'dias': 20},
    {'cliente': 'CODELCO', 'dias': 30},
    {'cliente': 'TECHINT', 'dias': 30},
    {'cliente': 'MONTEC', 'dias': 60},
]

def get_logo_base64():
    try:
        with open("logo_fondo_negro.png", "rb") as f:
            return base64.b64encode(f.read()).decode('utf-8')
    except:
        return ""

def now_chile():
    """Retorna datetime actual en zona horaria Chile"""
    return datetime.now(TZ_CHILE)

DIAS_SEMANA_ES = {
    'Mon': 'Lun', 'Tue': 'Mar', 'Wed': 'Mié', 'Thu': 'Jue',
    'Fri': 'Vie', 'Sat': 'Sáb', 'Sun': 'Dom'
}

MESES_ES = {
    'Jan': 'Ene', 'Feb': 'Feb', 'Mar': 'Mar', 'Apr': 'Abr',
    'May': 'May', 'Jun': 'Jun', 'Jul': 'Jul', 'Aug': 'Ago',
    'Sep': 'Sep', 'Oct': 'Oct', 'Nov': 'Nov', 'Dec': 'Dic'
}

def fecha_es(fecha):
    """Convierte fecha a formato dd-Mes en español"""
    if not fecha:
        return '-'
    if hasattr(fecha, 'strftime'):
        fecha_str = fecha.strftime('%d-%b')
        for en, es in MESES_ES.items():
            fecha_str = fecha_str.replace(en, es)
        return fecha_str
    return str(fecha)[:6]

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
    """Obtener forecast desde Google Sheet. Lógica: siempre G, si G vacío entonces E"""
    try:
        response = requests.get(FORECAST_URL, timeout=30)
        df = pd.read_excel(BytesIO(response.content))
        df_año = df[df['Año'] == 2026].copy()
        
        col_presupuesto = 'Presupuesto 2026'
        col_compromiso = 'Compromiso Inicio Mes'
        col_forecast = 'Forecast del mes\n(Se modifica del día 3 de cada mes)'
        
        df_año['Presupuesto'] = df_año[col_presupuesto].apply(parse_clp)
        df_año['Compromiso'] = df_año[col_compromiso].apply(parse_clp)
        df_año['Forecast_G'] = df_año[col_forecast].apply(parse_clp)
        
        # Lógica: Siempre G, si G vacío entonces E
        df_año['Forecast'] = df_año.apply(
            lambda row: row['Forecast_G'] if row['Forecast_G'] > 0 else row['Presupuesto'],
            axis=1
        )
        
        resultado = []
        for mes in MESES_ORDEN:
            df_mes = df_año[df_año['Mes'] == mes]
            c = df_mes['Compromiso'].sum()
            f = df_mes['Forecast'].sum()
            
            if mes in MESES_SOLO_COMPROMISO:
                usar = c
                vta_nueva = 0
            else:
                usar = f  # Siempre usar Forecast (G > E)
                vta_nueva = max(0, f - c)
            
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
# HTML TEMPLATES
# ============================================

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>CathPro - Login</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body{font-family:'Segoe UI',sans-serif;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;background:#242625}
        .login-box{background:#242625;padding:40px;border-radius:10px;text-align:center;border:1px solid #3a3b3a}
        .logo img{height:60px;margin-bottom:30px}
        input{width:100%;padding:12px;margin:10px 0;border:1px solid #3a3b3a;border-radius:5px;box-sizing:border-box;background:#1a1b1a;color:white}
        button{width:100%;padding:12px;background:#55b245;color:white;border:none;border-radius:5px;cursor:pointer;font-size:16px;font-weight:600}
        button:hover{background:#4a9e3d}
    </style>
</head>
<body>
    <div class="login-box">
        <div class="logo"><img src="data:image/png;base64,LOGO_BASE64" alt="CathPro"></div>
        <form action="/tablero" method="get">
            <input type="password" name="key" placeholder="Contraseña" required>
            <button type="submit">Ingresar</button>
        </form>
    </div>
</body>
</html>
"""

NAV_HTML = """
<div class="nav-links">
    <a href="/tablero?key=KEY_PLACEHOLDER" class="NAV_SALDOS">Saldos</a>
    <a href="/tesoreria?key=KEY_PLACEHOLDER" class="NAV_TESORERIA">Tesorería</a>
    <a href="/cashflow/semanal?key=KEY_PLACEHOLDER" class="NAV_SEMANAL">Cash Flow Semanal</a>
    <a href="/cashflow?key=KEY_PLACEHOLDER" class="NAV_ANUAL">Cash Flow Anual</a>
    <a href="/pipeline?key=KEY_PLACEHOLDER" class="NAV_PIPELINE">Pipeline</a>
    <a href="/nomina/scotiabank?key=KEY_PLACEHOLDER" class="NAV_NOMINA" style="background:#dc3545;color:white">Nomina Scotiabank</a>
</div>
"""

TABLERO_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>CathPro - Saldos Diarios</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="300">
    <style>
        body{font-family:'Segoe UI',sans-serif;margin:0;padding:0;background:#f4f4f4}
        .header{background:#242625;padding:20px 40px;display:flex;align-items:center;gap:20px}
        .header img{height:50px}
        .header h1{color:#f4f4f4;margin:0;font-weight:700;font-size:24px}
        .nav-links{margin-left:auto;display:flex;gap:10px}
        .nav-links a{color:#888;text-decoration:none;padding:8px 15px;border-radius:5px;font-size:13px}
        .nav-links a:hover,.nav-links a.active{background:#55b245;color:white}
        .container{max-width:1100px;margin:0 auto;padding:20px}
        .fecha{color:#7f8c8d;margin-bottom:20px}
        .section-title{color:#242625;font-size:18px;font-weight:700;margin:30px 0 15px}
        .cards{display:flex;gap:15px;flex-wrap:wrap;margin-bottom:20px}
        .card{flex:1;min-width:150px;background:white;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1)}
        .card h3{margin:0;color:#7f8c8d;font-size:12px;font-weight:600;text-transform:uppercase}
        .card p{margin:10px 0 0;font-size:22px;font-weight:800;color:#242625}
        .card.green{border-left:4px solid #55b245}
        .card.orange{border-left:4px solid #f46302}
        .card.blue{border-left:4px solid #3498db}
        .card.red{border-left:4px solid #e74c3c}
        .card.purple{border-left:4px solid #9b59b6}
        table{width:100%;border-collapse:collapse;background:white;border-radius:10px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.1)}
        th{background:#242625;color:white;padding:12px 15px;text-align:left;font-weight:600;font-size:14px}
        td{padding:10px 15px;border-bottom:1px solid #ecf0f1;font-size:14px}
        .monto{text-align:right;font-family:monospace;font-weight:bold}
        .posicion{margin-top:20px;background:#242625;color:white;padding:20px;border-radius:10px;text-align:center}
        .posicion h3{margin:0;font-size:14px;color:#7f8c8d}
        .posicion p{margin:10px 0 0;font-size:32px;font-weight:800}
        .posicion.positive p{color:#55b245}
        .posicion.negative p{color:#e74c3c}
        .note{margin-top:20px;padding:15px;background:#fff3cd;border-left:4px solid #f46302;border-radius:5px;font-size:13px;color:#856404}
        .table-responsive{overflow-x:auto;-webkit-overflow-scrolling:touch}
    </style>
</head>
<body>
    <div class="header">
        <img src="data:image/png;base64,LOGO_BASE64" alt="CathPro">
        <h1>Saldos Diarios CathPro</h1>
        NAV_PLACEHOLDER
    </div>
    <div class="container">
        <p class="fecha">Actualizado: FECHA_PLACEHOLDER</p>
        
        <div class="section-title">Saldos Bancos / Inversiones</div>
        <div class="cards">
            <div class="card green"><h3>Total CLP</h3><p>TOTAL_CLP_PLACEHOLDER</p></div>
            <div class="card orange">
                <h3>Total USD (en CLP)</h3>
                <p>TOTAL_USD_CLP_PLACEHOLDER</p>
                <div style="font-size:14px;color:#d35400;margin-top:5px">~ TOTAL_USD_ORIG_PLACEHOLDER</div>
            </div>
            <div class="card blue">
                <h3>Total EUR (en CLP)</h3>
                <p>TOTAL_EUR_CLP_PLACEHOLDER</p>
                <div style="font-size:14px;color:#2980b9;margin-top:5px">~ TOTAL_EUR_ORIG_PLACEHOLDER</div>
            </div>
            <div class="card purple"><h3>Fondos Mutuos</h3><p>FONDOS_MUTUOS_PLACEHOLDER</p></div>
        </div>
        
        <div class="section-title">Cuentas por Cobrar / Pagar</div>
        <div class="cards">
            <div class="card green"><h3>Por Cobrar</h3><p>POR_COBRAR_PLACEHOLDER</p></div>
            <div class="card red"><h3>Por Pagar Nacional</h3><p>POR_PAGAR_NAC_PLACEHOLDER</p></div>
            <div class="card orange"><h3>Por Pagar Internacional</h3><p>POR_PAGAR_INT_PLACEHOLDER</p></div>
        </div>
        
        <div class="posicion POSICION_CLASS">
            <h3>POSICIÓN NETA (Por Cobrar - Por Pagar)</h3>
            <p>POSICION_NETA_PLACEHOLDER</p>
        </div>
        
        <div class="note">
            <strong>Nota:</strong> Las cuentas por pagar internacional NO incluyen las OCX sin invoice.
            <br>
            <strong>* Cambio:</strong> Los saldos USD/EUR se muestran en CLP según contabilidad. El valor en divisa original es estimado (USD: $885, EUR: $1027).
        </div>
        
        <div class="section-title">Detalle Saldos Bancarios</div>
        <div class="table-responsive">
            <table>
                <tr><th>Banco</th><th style="text-align:right">Disponible</th><th>Moneda</th></tr>
                ROWS_PLACEHOLDER
            </table>
        </div>
    </div>
</body>
</html>
"""

TESORERIA_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>CathPro - Tesorería</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="300">
    <style>
        body{font-family:'Segoe UI',sans-serif;margin:0;padding:0;background:#f4f4f4}
        .header{background:#242625;padding:20px 40px;display:flex;align-items:center;gap:20px}
        .header img{height:50px}
        .header h1{color:#f4f4f4;margin:0;font-weight:700;font-size:24px}
        .nav-links{margin-left:auto;display:flex;gap:10px}
        .nav-links a{color:#888;text-decoration:none;padding:8px 15px;border-radius:5px;font-size:13px}
        .nav-links a:hover,.nav-links a.active{background:#55b245;color:white}
        .container{max-width:1200px;margin:0 auto;padding:20px}
        .fecha{color:#7f8c8d;margin-bottom:20px;font-size:14px}
        .section-title{color:#242625;font-size:18px;font-weight:700;margin:30px 0 15px}
        .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin-bottom:20px}
        .card{background:white;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1)}
        .card h3{margin:0;color:#7f8c8d;font-size:12px;font-weight:600;text-transform:uppercase}
        .card p{margin:10px 0 0;font-size:24px;font-weight:800;color:#242625}
        .card small{color:#7f8c8d;font-size:11px}
        .card.green{border-left:4px solid #55b245}
        .card.orange{border-left:4px solid #f46302}
        .card.red{border-left:4px solid #e74c3c}
        .card.blue{border-left:4px solid #3498db}
        .card.purple{border-left:4px solid #9b59b6}
        .alert{background:#fff3cd;border-left:4px solid #f46302;padding:15px 20px;border-radius:8px;margin-bottom:20px}
        .alert.success{background:#d4edda;border-left-color:#55b245}
        .alert.danger{background:#f8d7da;border-left-color:#e74c3c}
        .alert h4{margin:0 0 5px;font-size:14px;font-weight:600}
        .alert p{margin:0;font-size:13px;color:#856404}
        .alert.success p{color:#155724}
        .alert.danger p{color:#721c24}
        table{width:100%;border-collapse:collapse;background:white;border-radius:10px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.1);margin-bottom:20px}
        th{background:#242625;color:white;padding:12px 15px;text-align:left;font-weight:600;font-size:13px}
        td{padding:10px 15px;border-bottom:1px solid #ecf0f1;font-size:13px}
        .monto{text-align:right;font-family:monospace;font-weight:bold}
        .monto.ingreso{color:#55b245}
        .monto.egreso{color:#e74c3c}
        .center{text-align:center}
        .badge{display:inline-block;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:600}
        .badge-ingreso{background:#d4edda;color:#155724}
        .badge-egreso{background:#f8d7da;color:#721c24}
        .two-col{display:grid;grid-template-columns:1fr 1fr;gap:20px}
        @media(max-width:768px){.cards{grid-template-columns:1fr}.two-col{grid-template-columns:1fr}}
        .table-responsive{overflow-x:auto;-webkit-overflow-scrolling:touch}
    </style>
</head>
<body>
    <div class="header">
        <img src="data:image/png;base64,LOGO_BASE64" alt="CathPro">
        <h1>Tesorería CathPro</h1>
        NAV_PLACEHOLDER
    </div>
    <div class="container">
        <p class="fecha">Actualizado: FECHA_PLACEHOLDER</p>

        ALERTAS_PLACEHOLDER

        <div class="section-title">Resumen Consolidado (Hoy)</div>
        <div class="cards">
            <div class="card blue">
                <h3>Total Movimientos</h3>
                <p>TOTAL_MOVIMIENTOS</p>
                <small>Todas las cuentas</small>
            </div>
            <div class="card green">
                <h3>Total Ingresos</h3>
                <p>TOTAL_INGRESOS</p>
            </div>
            <div class="card red">
                <h3>Total Egresos</h3>
                <p>TOTAL_EGRESOS</p>
            </div>
            <div class="card SALDO_CLASS">
                <h3>Variación Neta</h3>
                <p>SALDO_NETO</p>
            </div>
        </div>

        <div class="section-title">Movimientos por Banco (Hoy)</div>
        <div class="table-responsive">
            <table>
                <tr>
                    <th>Banco</th>
                    <th class="center">Cuenta</th>
                    <th class="monto">Saldo Actual</th>
                    <th class="center">Movimientos</th>
                    <th class="monto">Ingresos</th>
                    <th class="monto">Egresos</th>
                </tr>
                ROWS_BANCOS
            </table>
        </div>

        <div class="section-title">Detalle de Movimientos (Hoy)</div>
        <div class="two-col">
            <div>
                <h4 style="font-size:15px;margin-bottom:10px;color:#55b245">💰 Top 10 Ingresos</h4>
                <div class="table-responsive">
                    <table>
                        <tr>
                            <th>Banco</th>
                            <th>Cliente / Descripción</th>
                            <th>Nº Factura</th>
                            <th class="monto">Monto</th>
                            <th class="center">Conciliado</th>
                        </tr>
                        ROWS_TOP_INGRESOS
                    </table>
                </div>
            </div>
            <div>
                <h4 style="font-size:15px;margin-bottom:10px;color:#e74c3c">💸 Top 10 Egresos</h4>
                <div class="table-responsive">
                    <table>
                        <tr>
                            <th>Banco</th>
                            <th>Proveedor / Descripción</th>
                            <th>Nº Factura</th>
                            <th class="monto">Monto</th>
                            <th class="center">Conciliado</th>
                        </tr>
                        ROWS_TOP_EGRESOS
                    </table>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""

PIPELINE_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>CathPro - Pipeline de Compromisos</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="300">
    <style>
        body{font-family:'Segoe UI',sans-serif;margin:0;padding:0;background:#f4f4f4}
        .header{background:#242625;padding:20px 40px;display:flex;align-items:center;gap:20px}
        .header img{height:50px}
        .header h1{color:#f4f4f4;margin:0;font-weight:700;font-size:24px}
        .nav-links{margin-left:auto;display:flex;gap:10px}
        .nav-links a{color:#888;text-decoration:none;padding:8px 15px;border-radius:5px;font-size:13px}
        .nav-links a:hover,.nav-links a.active{background:#55b245;color:white}
        .container{max-width:1400px;margin:0 auto;padding:20px}
        .fecha{color:#7f8c8d;margin-bottom:20px;font-size:14px}
        .section-title{color:#242625;font-size:18px;font-weight:700;margin:30px 0 15px}
        .section-title.warning{color:#856404}
        .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:15px;margin-bottom:20px}
        .card{background:white;padding:20px;border-radius:10px;box-shadow:0 2px 10px rgba(0,0,0,0.1)}
        .card h3{margin:0;color:#7f8c8d;font-size:12px;font-weight:600;text-transform:uppercase}
        .card p{margin:10px 0 0;font-size:24px;font-weight:800;color:#242625}
        .card small{color:#7f8c8d;font-size:11px;display:block;margin-top:5px}
        .card.blue{border-left:4px solid #3498db}
        .card.orange{border-left:4px solid #f46302}
        .card.purple{border-left:4px solid #9b59b6}
        .card.yellow{border-left:4px solid #f1c40f}
        .card.gray{border-left:4px solid #95a5a6}
        table{width:100%;border-collapse:collapse;background:white;border-radius:10px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,0.1);margin-bottom:20px}
        th{background:#242625;color:white;padding:12px 15px;text-align:left;font-weight:600;font-size:13px}
        th.warning{background:#856404}
        td{padding:10px 15px;border-bottom:1px solid #ecf0f1;font-size:13px}
        .monto{text-align:right;font-family:monospace;font-weight:bold}
        .center{text-align:center}
        .badge{display:inline-block;padding:3px 8px;border-radius:4px;font-size:10px;font-weight:600}
        .badge-critico{background:#f8d7da;color:#721c24}
        .badge-alerta{background:#fff3cd;color:#856404}
        .badge-ok{background:#d4edda;color:#155724}
        .badge-pendiente{background:#e2e3e5;color:#383d41}
        .table-responsive{overflow-x:auto;-webkit-overflow-scrolling:touch}
        tr.highlight{background:#fff9e6}
        .two-col{display:grid;grid-template-columns:1fr 1fr;gap:20px}
        @media(max-width:768px){.cards{grid-template-columns:1fr}.two-col{grid-template-columns:1fr}}
    </style>
</head>
<body>
    <div class="header">
        <img src="data:image/png;base64,LOGO_BASE64" alt="CathPro">
        <h1>Pipeline de Compromisos</h1>
        NAV_PLACEHOLDER
    </div>
    <div class="container">
        <p class="fecha">Actualizado: FECHA_PLACEHOLDER</p>

        <div class="section-title">Resumen Ejecutivo - Aprobados</div>
        <div class="cards">
            <div class="card blue">
                <h3>SOLIs sin OC</h3>
                <p>SOLI_CANTIDAD</p>
                <small>Monto: SOLI_MONTO CLP</small>
            </div>
            <div class="card orange">
                <h3>OCs sin Factura</h3>
                <p>OC_CANTIDAD</p>
                <small>Monto: OC_MONTO CLP</small>
            </div>
            <div class="card purple">
                <h3>OCXs sin Invoice</h3>
                <p>OCX_CANTIDAD</p>
                <small>Monto: OCX_MONTO USD</small>
            </div>
        </div>

        <div class="section-title warning">Visibilidad Temprana - Pendientes Aprobación (15d)</div>
        <div class="cards">
            <div class="card yellow">
                <h3>OCs Pendientes</h3>
                <p>OC_PEND_CANTIDAD</p>
                <small>Monto: OC_PEND_MONTO CLP</small>
            </div>
            <div class="card gray">
                <h3>OCXs Pendientes</h3>
                <p>OCX_PEND_CANTIDAD</p>
                <small>Monto: OCX_PEND_MONTO USD</small>
            </div>
        </div>

        <div class="section-title">📋 SOLIs Aprobadas sin OC</div>
        <table>
            <tr>
                <th>Folio</th>
                <th>Fecha</th>
                <th>Proveedor</th>
                <th>Proyecto</th>
                <th class="monto">Monto CLP</th>
            </tr>
            ROWS_SOLI
        </table>

        <div class="section-title">📄 OCs Aprobadas sin Factura</div>
        <table>
            <tr>
                <th>Folio</th>
                <th>Fecha</th>
                <th>Proveedor</th>
                <th class="center">Días Pendiente</th>
                <th class="monto">Monto CLP</th>
            </tr>
            ROWS_OC
        </table>

        <div class="section-title">🌐 OCXs Aprobadas sin Invoice</div>
        <table>
            <tr>
                <th>Folio</th>
                <th>Fecha</th>
                <th>Proveedor</th>
                <th class="center">Días Pendiente</th>
                <th class="monto">Monto USD</th>
            </tr>
            ROWS_OCX
        </table>

        <div class="section-title warning">⏳ OCs Pendientes de Aprobación (15d)</div>
        <table>
            <tr>
                <th class="warning">Folio</th>
                <th class="warning">Fecha</th>
                <th class="warning">Proveedor</th>
                <th class="warning">Estado</th>
                <th class="warning center">Días</th>
                <th class="warning monto">Monto CLP</th>
            </tr>
            ROWS_OC_PEND
        </table>

        <div class="section-title warning">⏳ OCXs Pendientes de Aprobación (15d)</div>
        <table>
            <tr>
                <th class="warning">Folio</th>
                <th class="warning">Fecha</th>
                <th class="warning">Proveedor</th>
                <th class="warning">Estado</th>
                <th class="warning center">Días</th>
                <th class="warning monto">Monto USD</th>
            </tr>
            ROWS_OCX_PEND
        </table>
    </div>
</body>
</html>
"""

CASHFLOW_SEMANAL_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>CathPro - Cash Flow Semanal</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="300">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Segoe UI',sans-serif;background:#f5f5f5;color:#242625}
        .header{background:#242625;padding:15px 30px;display:flex;align-items:center;gap:20px}
        .header img{height:50px}
        .header h1{color:#fff;font-size:20px;font-weight:500}
        .header-sub{color:#888;font-size:12px}
        .header-right{margin-left:auto;text-align:right}
        .header-saldo{color:#55b245;font-size:18px;font-weight:600}
        .nav-links{display:flex;gap:10px;margin-left:20px}
        .nav-links a{color:#888;text-decoration:none;padding:8px 15px;border-radius:5px;font-size:13px}
        .nav-links a:hover,.nav-links a.active{background:#55b245;color:white}
        .container{max-width:1300px;margin:0 auto;padding:25px}
        .alert{background:linear-gradient(135deg,#f7941d,#e8850a);color:#fff;padding:15px 20px;border-radius:10px;margin-bottom:20px;display:flex;align-items:center;gap:12px}
        .alert.success{background:linear-gradient(135deg,#55b245,#449636)}
        .kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin-bottom:25px}
        .kpi{background:#fff;border-radius:10px;padding:18px;box-shadow:0 2px 8px rgba(0,0,0,0.08);border-left:4px solid #55b245}
        .kpi.azul{border-left-color:#17a2b8}
        .kpi.naranja{border-left-color:#f7941d}
        .kpi.rojo{border-left-color:#dc3545}
        .kpi-label{font-size:11px;color:#666;text-transform:uppercase;margin-bottom:6px}
        .kpi-value{font-size:22px;font-weight:700}
        .kpi-value.verde{color:#55b245}
        .kpi-value.rojo{color:#dc3545}
        .kpi-sub{font-size:11px;color:#888;margin-top:4px}
        .chart-container{background:#fff;border-radius:10px;padding:20px;box-shadow:0 2px 8px rgba(0,0,0,0.08);margin-bottom:25px}
        .chart-container h3{font-size:15px;margin-bottom:15px}
        .config-box{background:#f8f9fa;border-radius:10px;padding:15px;margin-bottom:25px}
        .config-title{font-size:12px;color:#666;margin-bottom:10px}
        .tags{display:flex;flex-wrap:wrap;gap:8px}
        .tag{background:#fff;border:1px solid #ddd;border-radius:15px;padding:4px 12px;font-size:11px}
        .tag strong{color:#55b245}
        h3.section{font-size:15px;font-weight:600;margin-bottom:12px;padding-bottom:8px;border-bottom:2px solid #55b245}
        table{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);margin-bottom:25px}
        th{background:#242625;color:#fff;padding:12px 15px;font-size:12px;font-weight:500;text-align:left}
        th.right{text-align:right}
        th.center{text-align:center}
        td{padding:12px 15px;font-size:13px;border-bottom:1px solid #eee}
        td.right{text-align:right;font-family:monospace}
        td.center{text-align:center}
        td.verde{color:#55b245}
        td.rojo{color:#dc3545}
        tr.critico{background:#fff5f5}
        tr.positivo{background:#f0fff0}
        .badge{display:inline-block;padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600;margin-left:4px}
        .badge-skualo{background:#e3f2fd;color:#1565c0}
        .badge-forecast{background:#fff3e0;color:#e65100}
        .badge-rec{background:#e8f5e9;color:#2e7d32}
        .badge-cxp{background:#fce4ec;color:#c2185b}
        .badge-dias{background:#f3e5f5;color:#7b1fa2}
        .two-col{display:grid;grid-template-columns:1fr 1fr;gap:25px}
        .footer{text-align:center;padding:20px;color:#888;font-size:11px;margin-top:20px}
        .chat-btn{position:fixed;bottom:30px;right:30px;background:linear-gradient(135deg,#55b245,#449636);color:white;border:none;border-radius:50px;padding:15px 25px;font-size:16px;font-weight:600;box-shadow:0 4px 15px rgba(85,178,69,0.4);cursor:pointer;text-decoration:none;display:flex;align-items:center;gap:8px;transition:all 0.3s ease;z-index:1000}
        .chat-btn:hover{transform:translateY(-3px);box-shadow:0 6px 20px rgba(85,178,69,0.6);background:linear-gradient(135deg,#449636,#55b245)}
        @media(max-width:768px){.kpis{grid-template-columns:repeat(2,1fr)}.two-col{grid-template-columns:1fr}.header{flex-wrap:wrap}.nav-links{margin:10px 0}.chat-btn{padding:12px 20px;font-size:14px}}
    </style>
</head>
<body>
    <div class="header">
        <img src="data:image/png;base64,LOGO_BASE64" alt="CathPro">
        <div>
            <h1>Cash Flow CathPro</h1>
            <div class="header-sub">Vista Semanal Detallada | FECHA_PLACEHOLDER</div>
        </div>
        NAV_PLACEHOLDER
        <div class="header-right">
            <div class="header-saldo">SALDO_PLACEHOLDER</div>
            <div class="header-sub">Saldo Apis CLP</div>
        </div>
    </div>
    
    <div class="container">
        ALERT_PLACEHOLDER
        
        <div class="kpis">
            <div class="kpi azul">
                <div class="kpi-label">Saldo Inicial</div>
                <div class="kpi-value">SALDO_PLACEHOLDER</div>
                <div class="kpi-sub">Hoy</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Entradas Semana</div>
                <div class="kpi-value verde">ENTRADAS_PLACEHOLDER</div>
                <div class="kpi-sub">CxC Skualo</div>
            </div>
            <div class="kpi naranja">
                <div class="kpi-label">Salidas Semana</div>
                <div class="kpi-value">SALIDAS_PLACEHOLDER</div>
                <div class="kpi-sub">CxP + Recurrentes</div>
            </div>
            <div class="kpi SALDO_FINAL_CLASS">
                <div class="kpi-label">Variación Neta</div>
                <div class="kpi-value SALDO_FINAL_COLOR">VARIACION_NETA_PLACEHOLDER</div>
                <div class="kpi-sub">Entradas - Salidas</div>
            </div>
        </div>
        
        <div class="chart-container">
            <h3>Evolución del Saldo Proyectado</h3>
            <canvas id="chartSemanal" height="100"></canvas>
        </div>
        
        <div class="config-box">
            <div class="config-title">📋 Días de Pago Configurados</div>
            <div class="tags">
                TAGS_DIAS_PAGO
            </div>
        </div>
        
        <h3 class="section">Detalle Diario</h3>
        <table>
            <thead>
                <tr>
                    <th>Fecha</th>
                    <th>Día</th>
                    <th class="right">Entradas</th>
                    <th class="center">Fuente</th>
                    <th class="right">Salidas</th>
                    <th class="right">Neto</th>
                    <th class="right">Saldo</th>
                </tr>
            </thead>
            <tbody>
                ROWS_DIARIO
            </tbody>
        </table>
        
        <div class="two-col">
            <div>
                <h3 class="section">Top 5 Entradas <span class="badge badge-skualo">Skualo CxC</span></h3>
                <table>
                    <thead>
                        <tr><th>Cliente</th><th class="center">Fecha</th><th class="right">Monto</th></tr>
                    </thead>
                    <tbody>
                        ROWS_TOP_ENTRADAS
                    </tbody>
                </table>
            </div>
            <div>
                <h3 class="section">Salidas Semana <span class="badge badge-rec">Rec + CxP 7d</span></h3>
                <table>
                    <thead>
                        <tr><th>Concepto</th><th class="center">Fecha</th><th class="center">Tipo</th><th class="right">Monto</th></tr>
                    </thead>
                    <tbody>
                        ROWS_SALIDAS_SEMANA
                    </tbody>
                </table>
            </div>
        </div>
        
        <h3 class="section">Top 5 CxP Pendientes <span class="badge badge-cxp">Todas las fechas</span></h3>
        <table>
            <thead>
                <tr><th>Proveedor</th><th>Documento</th><th class="center">Vencimiento</th><th class="center">Días</th><th class="right">Monto</th></tr>
            </thead>
            <tbody>
                ROWS_CXP_PENDIENTES
            </tbody>
        </table>
        
        <div class="footer">
            Cash Flow CathPro | Apis + Skualo CxC/CxP + Recurrentes | FECHA_PLACEHOLDER
        </div>
    </div>
    
    <script>
        const ctx = document.getElementById('chartSemanal').getContext('2d');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: CHART_LABELS,
                datasets: [
                    {
                        label: 'Entradas',
                        data: CHART_ENTRADAS,
                        backgroundColor: '#55b245',
                        order: 2
                    },
                    {
                        label: 'Salidas',
                        data: CHART_SALIDAS,
                        backgroundColor: '#dc3545',
                        order: 2
                    },
                    {
                        label: 'Saldo',
                        data: CHART_SALDOS,
                        type: 'line',
                        borderColor: '#f7941d',
                        backgroundColor: 'transparent',
                        borderWidth: 3,
                        pointBackgroundColor: '#f7941d',
                        pointRadius: 5,
                        yAxisID: 'y1',
                        order: 1
                    }
                ]
            },
            options: {
                responsive: true,
                interaction: { intersect: false, mode: 'index' },
                scales: {
                    y: { 
                        position: 'left',
                        ticks: { callback: v => '$' + (v/1000000).toFixed(0) + 'M' }
                    },
                    y1: { 
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        ticks: { callback: v => '$' + (v/1000000).toFixed(0) + 'M' }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: ctx => ctx.dataset.label + ': $' + ctx.raw.toLocaleString('es-CL')
                        }
                    }
                }
            }
        });
    </script>

    <a href="/chat?key=KEY_PLACEHOLDER" class="chat-btn">
        💬 VeriCosas
    </a>
</body>
</html>
"""

CASHFLOW_ANUAL_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>CathPro - Cash Flow Anual</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta http-equiv="refresh" content="300">
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Segoe UI',sans-serif;background:#fff;color:#242625}
        .header{background:#242625;padding:15px 30px;display:flex;align-items:center;gap:20px}
        .header img{height:50px}
        .header h1{color:#fff;font-size:20px;font-weight:500}
        .header-sub{color:#888;font-size:12px}
        .header-right{margin-left:auto;text-align:right}
        .header-saldo{color:#55b245;font-size:20px;font-weight:700}
        .nav-links{display:flex;gap:10px;margin-left:20px}
        .nav-links a{color:#888;text-decoration:none;padding:8px 15px;border-radius:5px;font-size:13px}
        .nav-links a:hover,.nav-links a.active{background:#55b245;color:white}
        .container{max-width:1200px;margin:0 auto;padding:25px}
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
        @media(max-width:768px){.q1-grid{grid-template-columns:1fr}.summary{grid-template-columns:repeat(2,1fr)}.legend{flex-direction:column;align-items:flex-start}}
    </style>
</head>
<body>
    <div class="header">
        <img src="data:image/png;base64,LOGO_BASE64" alt="CathPro">
        <div>
            <h1>Cash Flow CathPro</h1>
            <div class="header-sub">Proyección Anual 2026 | FECHA_PLACEHOLDER</div>
        </div>
        NAV_PLACEHOLDER
        <div class="header-right">
            <div class="header-saldo">SALDO_PLACEHOLDER</div>
            <div class="header-sub">Saldo Apis CLP</div>
        </div>
    </div>
    
    <div class="container">
        <div class="legend">
            <div class="legend-item">
                <div class="legend-box apal"></div>
                <div><div class="legend-title">Apalancada</div><div class="legend-desc">Proyectos confirmados (Compromiso)</div></div>
            </div>
            <div class="legend-item">
                <div class="legend-box vta"></div>
                <div><div class="legend-title">Venta Nueva</div><div class="legend-desc">Proyección comercial</div></div>
            </div>
            <div class="legend-rule"><strong>Regla:</strong> Q1 = Solo Compromiso | Q2-Q4 = Forecast (G > E)</div>
        </div>
        
        <div class="q1-box">
            <div class="q1-title">Q1 2026 - 100% Apalancada (Alta Certeza)</div>
            <div class="q1-grid">
                Q1_CARDS_PLACEHOLDER
            </div>
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
        
        <div class="summary">
            <div class="summary-card apal">
                <div class="summary-label">Apalancada Total</div>
                <div class="summary-value apal">TOTAL_APAL_PLACEHOLDER</div>
                <div class="summary-sub">PCT_APAL% del total</div>
            </div>
            <div class="summary-card vta">
                <div class="summary-label">Vta Nueva Total</div>
                <div class="summary-value vta">TOTAL_VTA_PLACEHOLDER</div>
                <div class="summary-sub">PCT_VTA% del total</div>
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
        
        <div class="insight">
            <div class="insight-title">💡 Insight Clave</div>
            <div class="insight-text">
                La certeza del forecast <strong>decrece</strong> a lo largo del año: Q1 tiene 100% certeza (solo Compromiso), mientras que Q4 promedia solo 25% certeza.
            </div>
        </div>
        
        <div class="footer">
            Cash Flow CathPro | Apalancada = Compromiso | Vta Nueva = Forecast sin Compromiso | FECHA_PLACEHOLDER
        </div>
    </div>
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


# Ruta legacy para compatibilidad
@app.route('/dashboard')
def dashboard_redirect():
    key = request.args.get('key', '')
    return f"<script>window.location='/tablero?key={key}';</script>"


@app.route('/tablero')
def tablero():
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return "<script>alert('Contraseña incorrecta');window.location='/';</script>"
    
    return generate_tablero_html(key)


# ============================================
# FUNCIONES HISTORIAL DE SALDOS
# ============================================

def get_saldos_historicos():
    """Lee el historial de saldos desde archivo JSON"""
    archivo = 'saldos_historicos.json'
    try:
        if os.path.exists(archivo):
            with open(archivo, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Error leyendo historial: {e}")
        return {}


def guardar_saldo_historico(banco, saldo, moneda='CLP'):
    """Guarda el saldo actual de un banco en el historial"""
    archivo = 'saldos_historicos.json'
    historial = get_saldos_historicos()

    # Obtener fecha actual en Chile
    hoy = now_chile().date().isoformat()

    # Estructura: {banco: {fecha: {saldo, moneda}}}
    if banco not in historial:
        historial[banco] = {}

    historial[banco][hoy] = {
        'saldo': saldo,
        'moneda': moneda,
        'timestamp': now_chile().isoformat()
    }

    try:
        with open(archivo, 'w') as f:
            json.dump(historial, f, indent=2)
    except Exception as e:
        print(f"Error guardando historial: {e}")


def comparar_saldo_anterior(banco, saldo_actual):
    """
    Compara el saldo actual con el saldo del día anterior o último registro.
    Retorna: dict con diferencia, porcentaje y dirección (up/down/equal)
    """
    historial = get_saldos_historicos()

    if banco not in historial or not historial[banco]:
        return {'diferencia': 0, 'porcentaje': 0, 'direccion': 'equal', 'saldo_anterior': 0}

    # Obtener fechas ordenadas (más reciente primero)
    fechas = sorted(historial[banco].keys(), reverse=True)
    hoy = now_chile().date().isoformat()

    # Buscar el último registro que no sea de hoy
    saldo_anterior = None
    for fecha in fechas:
        if fecha != hoy:
            saldo_anterior = historial[banco][fecha]['saldo']
            break

    if saldo_anterior is None:
        return {'diferencia': 0, 'porcentaje': 0, 'direccion': 'equal', 'saldo_anterior': 0}

    # Calcular diferencia y porcentaje
    diferencia = saldo_actual - saldo_anterior
    porcentaje = (diferencia / saldo_anterior * 100) if saldo_anterior != 0 else 0

    # Determinar dirección
    if abs(diferencia) < 1:  # Considerar igual si diferencia < 1 CLP
        direccion = 'equal'
    elif diferencia > 0:
        direccion = 'up'
    else:
        direccion = 'down'

    return {
        'diferencia': diferencia,
        'porcentaje': porcentaje,
        'direccion': direccion,
        'saldo_anterior': saldo_anterior
    }


@app.route('/tesoreria')
def tesoreria():
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return "<script>alert('Contraseña incorrecta');window.location='/';</script>"

    # Obtener saldos CLP desde Skualo (calculado desde movimientos bancarios)
    skualo_bancos = SkualoBancosClient()
    saldos_clp = skualo_bancos.get_saldos_clp()
    
    # Obtener saldos USD/EUR desde Fintoc (conexión directa banco)
    fintoc = FintocClient()
    saldos_usd_eur = fintoc.get_usd_eur_balances()
    
    # Convertir a lista de balances para la tabla
    balances = []
    # CLP desde Skualo
    for banco, saldo in saldos_clp.items():
        if banco != "total":
            balances.append({"banco": banco, "disponible": saldo, "moneda": "CLP"})
    # USD desde Fintoc
    for banco, saldo in saldos_usd_eur["usd"].items():
        if banco != "total":
            balances.append({"banco": banco, "disponible": saldo, "moneda": "USD"})
    # EUR desde Fintoc
    for banco, saldo in saldos_usd_eur["eur"].items():
        if banco != "total":
            balances.append({"banco": banco, "disponible": saldo, "moneda": "EUR"})

    # Guardar saldos históricos y obtener comparaciones
    comparaciones = {}
    for balance in balances:
        banco = balance['banco']
        saldo_actual = balance['disponible']
        moneda = balance['moneda']

        # Guardar saldo histórico
        guardar_saldo_historico(banco, saldo_actual, moneda)

        # Comparar con saldo anterior
        if moneda == 'CLP':  # Solo comparar CLP por ahora
            comparacion = comparar_saldo_anterior(banco, saldo_actual)
            comparaciones[banco] = comparacion

    # Obtener resumen de movimientos de hoy (skualo_bancos ya está instanciado arriba)
    resumen = skualo_bancos.get_resumen_todos_bancos()

    # Calcular totales
    total_movimientos = resumen['total_movimientos']
    total_ingresos = resumen['total_ingresos']
    total_egresos = resumen['total_egresos']
    saldo_neto = resumen['saldo_neto']

    # Determinar clase de saldo
    saldo_class = "green" if saldo_neto >= 0 else "red"

    # Generar alertas
    alertas_html = ""
    if saldo_neto < 0:
        alertas_html = f'''
        <div class="alert danger">
            <h4>⚠️ Alerta de Tesorería</h4>
            <p>Los egresos del día superan los ingresos en ${abs(saldo_neto):,.0f} CLP</p>
        </div>
        '''
    elif total_movimientos > 30:
        alertas_html = f'''
        <div class="alert">
            <h4>📊 Alta actividad bancaria</h4>
            <p>Se han registrado {total_movimientos} movimientos en el día</p>
        </div>
        '''
    else:
        alertas_html = f'''
        <div class="alert success">
            <h4>✓ Operación normal</h4>
            <p>Los ingresos superan los egresos en ${saldo_neto:,.0f} CLP</p>
        </div>
        '''

    # Generar filas de bancos
    rows_bancos = ""
    for banco_info in resumen['bancos']:
        banco_nombre = banco_info['banco']

        # Obtener saldo actual de Fintoc para este banco
        balance_actual = 0
        moneda_saldo = 'CLP'
        for b in balances:
            if b['banco'] == banco_nombre:
                # Preferir CLP, pero si solo hay USD/EUR, mostrar eso
                if b['moneda'] == 'CLP':
                    balance_actual = b['disponible']
                    moneda_saldo = 'CLP'
                    break
                elif balance_actual == 0:  # Si no hay CLP, usar la primera moneda disponible
                    balance_actual = b['disponible']
                    moneda_saldo = b['moneda']

        # Generar indicador de cambio
        cambio_html = '<span style="color:#888">-</span>'  # Default si no hay datos
        if banco_nombre in comparaciones:
            comp = comparaciones[banco_nombre]
            diferencia = comp['diferencia']
            porcentaje = comp.get('porcentaje', 0)

            if comp['direccion'] == 'up':
                cambio_html = f'<span style="color:#55b245;font-weight:bold">↑ ${abs(diferencia):,.0f} ({abs(porcentaje):.1f}%)</span>'
            elif comp['direccion'] == 'down':
                cambio_html = f'<span style="color:#e74c3c;font-weight:bold">↓ ${abs(diferencia):,.0f} ({abs(porcentaje):.1f}%)</span>'
            else:
                cambio_html = '<span style="color:#888">= Sin cambio</span>'

        # Formatear saldo con moneda
        if moneda_saldo == 'USD':
            saldo_display = f"${balance_actual:,.2f} USD"
        elif moneda_saldo == 'EUR':
            saldo_display = f"${balance_actual:,.2f} EUR"
        else:
            saldo_display = f"${balance_actual:,.0f}"

        rows_bancos += f'''
        <tr>
            <td>{banco_nombre}</td>
            <td class="center">{banco_info['cuenta']}</td>
            <td class="monto">{saldo_display}</td>
            <td class="center">{banco_info['num_movimientos']}</td>
            <td class="monto ingreso">${banco_info['ingresos']:,.0f}</td>
            <td class="monto egreso">${banco_info['egresos']:,.0f}</td>
        </tr>
        '''

    # Obtener CxC y CxP de Skualo para vincular movimientos
    try:
        from skualo_cashflow import SkualoCashFlow
        cf = SkualoCashFlow()
        cxp_detalle = cf.get_cxp_detalle()
        cxc_detalle = cf.get_cxc_detalle()
    except Exception as e:
        print(f"Error obteniendo CxC/CxP: {e}")
        cxp_detalle = []
        cxc_detalle = []

    # Obtener movimientos detallados de todos los bancos
    todos_movimientos = []
    for banco, cuenta_id in skualo_bancos.cuentas.items():
        mov_banco = skualo_bancos.get_movimientos_hoy(cuenta_id)
        for mov in mov_banco['movimientos']:
            mov['banco'] = banco
            todos_movimientos.append(mov)

    # Separar ingresos y egresos
    ingresos = []
    egresos = []
    for mov in todos_movimientos:
        cargo = mov.get('montoCargo', 0)
        abono = mov.get('montoAbono', 0)
        conciliado = mov.get('conciliado', False)

        if abono > 0:
            glosa = mov.get('glosa', 'Sin descripción')

            # Intentar vincular con CxC si es pago de cliente
            cliente = None
            num_factura = None
            vinculado = False

            # Buscar coincidencia por monto en CxC
            for cxc in cxc_detalle:
                # Buscar facturas con monto similar (+/- 2% para tolerar diferencias menores)
                if abs(cxc['saldo'] - abono) / abono < 0.02:
                    cliente = cxc['cliente']
                    num_factura = cxc.get('documento', '')
                    vinculado = True
                    break

            ingresos.append({
                'banco': mov['banco'],
                'glosa': glosa,
                'monto': abono,
                'conciliado': conciliado,
                'cliente': cliente,
                'num_factura': num_factura,
                'vinculado': vinculado
            })
        if cargo > 0:
            glosa = mov.get('glosa', 'Sin descripción')
            glosa_upper = glosa.upper()

            # Intentar vincular con CxP si es pago a proveedor
            proveedor = None
            num_factura = None
            vinculado = False

            if 'PAGO PROVEEDOR' in glosa_upper or 'TRANSF' in glosa_upper:
                # Buscar coincidencia por monto en CxP
                for cxp in cxp_detalle:
                    # Buscar facturas con monto similar (+/- 1%)
                    if abs(cxp['saldo'] - cargo) / cargo < 0.01:
                        proveedor = cxp['proveedor']
                        num_factura = cxp.get('documento', '')
                        vinculado = True
                        break

            egresos.append({
                'banco': mov['banco'],
                'glosa': glosa,
                'monto': cargo,
                'conciliado': conciliado,
                'proveedor': proveedor,
                'num_factura': num_factura,
                'vinculado': vinculado
            })

    # Ordenar y tomar top 10
    ingresos_top = sorted(ingresos, key=lambda x: x['monto'], reverse=True)[:10]
    egresos_top = sorted(egresos, key=lambda x: x['monto'], reverse=True)[:10]

    # Generar filas de top ingresos
    rows_top_ingresos = ""
    for ing in ingresos_top:
        conciliado_icon = '✓' if ing['conciliado'] else '✗'
        conciliado_color = '#55b245' if ing['conciliado'] else '#e74c3c'

        if ing['vinculado']:
            cliente_texto = ing['cliente']
            num_factura = ing['num_factura'][:15] if ing['num_factura'] else '-'
        else:
            # Mostrar glosa y marcar como sin vincular
            cliente_texto = ing['glosa'][:40] + ' <small style="color:#888">(Sin vincular)</small>'
            num_factura = '-'

        rows_top_ingresos += f'''
        <tr>
            <td>{ing['banco']}</td>
            <td>{cliente_texto}</td>
            <td>{num_factura}</td>
            <td class="monto ingreso">${ing['monto']:,.0f}</td>
            <td class="center" style="color:{conciliado_color}">{conciliado_icon}</td>
        </tr>
        '''

    if not rows_top_ingresos:
        rows_top_ingresos = '<tr><td colspan="5" style="text-align:center;color:#7f8c8d">No hay ingresos registrados hoy</td></tr>'

    # Generar filas de top egresos
    rows_top_egresos = ""
    for egr in egresos_top:
        conciliado_icon = '✓' if egr['conciliado'] else '✗'
        conciliado_color = '#55b245' if egr['conciliado'] else '#e74c3c'

        if egr['vinculado']:
            proveedor_texto = egr['proveedor']
            num_factura = egr['num_factura'][:15] if egr['num_factura'] else '-'
        else:
            # Mostrar glosa y marcar como sin vincular
            proveedor_texto = egr['glosa'][:40] + ' <small style="color:#888">(Sin vincular)</small>'
            num_factura = '-'

        rows_top_egresos += f'''
        <tr>
            <td>{egr['banco']}</td>
            <td>{proveedor_texto}</td>
            <td>{num_factura}</td>
            <td class="monto egreso">${egr['monto']:,.0f}</td>
            <td class="center" style="color:{conciliado_color}">{conciliado_icon}</td>
        </tr>
        '''

    if not rows_top_egresos:
        rows_top_egresos = '<tr><td colspan="5" style="text-align:center;color:#7f8c8d">No hay egresos registrados hoy</td></tr>'

    # Construir HTML
    nav = NAV_HTML.replace('KEY_PLACEHOLDER', key).replace('NAV_SALDOS', '').replace('NAV_TESORERIA', 'active').replace('NAV_PIPELINE', '').replace('NAV_ANUAL', '').replace('NAV_SEMANAL', '')
    logo_b64 = get_logo_base64()

    html = TESORERIA_HTML.replace('LOGO_BASE64', logo_b64)
    html = html.replace('NAV_PLACEHOLDER', nav)
    html = html.replace('FECHA_PLACEHOLDER', now_chile().strftime('%d-%m-%Y %H:%M'))
    html = html.replace('ALERTAS_PLACEHOLDER', alertas_html)
    html = html.replace('TOTAL_MOVIMIENTOS', str(total_movimientos))
    html = html.replace('TOTAL_INGRESOS', f"${total_ingresos:,.0f}")
    html = html.replace('TOTAL_EGRESOS', f"${total_egresos:,.0f}")
    html = html.replace('SALDO_NETO', f"${saldo_neto:,.0f}")
    html = html.replace('SALDO_CLASS', saldo_class)
    html = html.replace('ROWS_BANCOS', rows_bancos)
    html = html.replace('ROWS_TOP_INGRESOS', rows_top_ingresos)
    html = html.replace('ROWS_TOP_EGRESOS', rows_top_egresos)

    return html


@app.route('/pipeline')
def pipeline():
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return "<script>alert('Contraseña incorrecta');window.location='/';</script>"

    # Obtener datos del pipeline
    try:
        skualo_docs = SkualoDocumentosClient()
        resumen = skualo_docs.get_resumen_pipeline()
    except Exception as e:
        print(f"Error obteniendo pipeline: {e}")
        return f"<h1>Error cargando pipeline: {e}</h1>"

    # KPIs Aprobados
    soli_cantidad = resumen['soli']['cantidad']
    soli_monto = resumen['soli']['monto_total']
    oc_cantidad = resumen['oc']['cantidad']
    oc_monto = resumen['oc']['monto_total']
    ocx_cantidad = resumen['ocx']['cantidad']
    ocx_monto_usd = resumen['ocx']['monto_total_usd']
    
    # KPIs Pendientes Aprobación
    oc_pend_cantidad = resumen['oc_pendiente']['cantidad']
    oc_pend_monto = resumen['oc_pendiente']['monto_total']
    ocx_pend_cantidad = resumen['ocx_pendiente']['cantidad']
    ocx_pend_monto_usd = resumen['ocx_pendiente']['monto_total_usd']

    # Generar filas SOLIs
    rows_soli = ""
    for soli in resumen['soli']['documentos'][:50]:
        fecha_str = soli['fecha'].strftime('%d-%m-%Y') if soli['fecha'] else '-'
        proyecto = soli['proyecto'] if soli['proyecto'] else '-'
        rows_soli += f'''<tr>
            <td>{soli['folio']}</td>
            <td>{fecha_str}</td>
            <td>{soli['proveedor'][:40]}</td>
            <td>{proyecto}</td>
            <td class="monto">${soli['monto']:,.0f}</td>
        </tr>'''

    if not rows_soli:
        rows_soli = '<tr><td colspan="5" style="text-align:center;color:#888">No hay SOLIs pendientes</td></tr>'

    # Generar filas OCs
    rows_oc = ""
    for oc in resumen['oc']['documentos'][:50]:
        fecha_str = oc['fecha'].strftime('%d-%m-%Y') if oc['fecha'] else '-'
        dias = oc['dias_pendiente']

        if dias > 30:
            badge = '<span class="badge badge-critico">+30d</span>'
            highlight = 'highlight'
        elif dias > 15:
            badge = '<span class="badge badge-alerta">15-30d</span>'
            highlight = ''
        else:
            badge = '<span class="badge badge-ok">&lt;15d</span>'
            highlight = ''

        rows_oc += f'''<tr class="{highlight}">
            <td>{oc['folio']}</td>
            <td>{fecha_str}</td>
            <td>{oc['proveedor'][:40]}</td>
            <td class="center">{dias} días {badge}</td>
            <td class="monto">${oc['monto']:,.0f}</td>
        </tr>'''

    if not rows_oc:
        rows_oc = '<tr><td colspan="5" style="text-align:center;color:#888">No hay OCs pendientes</td></tr>'

    # Generar filas OCXs
    rows_ocx = ""
    for ocx in resumen['ocx']['documentos'][:50]:
        fecha_str = ocx['fecha'].strftime('%d-%m-%Y') if ocx['fecha'] else '-'
        dias = ocx['dias_pendiente']

        if dias > 30:
            badge = '<span class="badge badge-critico">+30d</span>'
            highlight = 'highlight'
        elif dias > 15:
            badge = '<span class="badge badge-alerta">15-30d</span>'
            highlight = ''
        else:
            badge = '<span class="badge badge-ok">&lt;15d</span>'
            highlight = ''

        rows_ocx += f'''<tr class="{highlight}">
            <td>{ocx['folio']}</td>
            <td>{fecha_str}</td>
            <td>{ocx['proveedor'][:40]}</td>
            <td class="center">{dias} días {badge}</td>
            <td class="monto">${ocx['monto_usd']:,.2f}</td>
        </tr>'''

    if not rows_ocx:
        rows_ocx = '<tr><td colspan="5" style="text-align:center;color:#888">No hay OCXs pendientes</td></tr>'

    # Generar filas OCs Pendientes Aprobación
    rows_oc_pend = ""
    for oc in resumen['oc_pendiente']['documentos'][:30]:
        fecha_str = oc['fecha'].strftime('%d-%m-%Y') if oc['fecha'] else '-'
        estado = oc.get('estado', 'Pendiente')
        dias = oc.get('dias_pendiente', 0)
        
        rows_oc_pend += f'''<tr>
            <td>{oc['folio']}</td>
            <td>{fecha_str}</td>
            <td>{oc['proveedor'][:40]}</td>
            <td><span class="badge badge-pendiente">{estado}</span></td>
            <td class="center">{dias}d</td>
            <td class="monto">${oc['monto']:,.0f}</td>
        </tr>'''

    if not rows_oc_pend:
        rows_oc_pend = '<tr><td colspan="6" style="text-align:center;color:#888">No hay OCs pendientes de aprobación</td></tr>'

    # Generar filas OCXs Pendientes Aprobación
    rows_ocx_pend = ""
    for ocx in resumen['ocx_pendiente']['documentos'][:30]:
        fecha_str = ocx['fecha'].strftime('%d-%m-%Y') if ocx['fecha'] else '-'
        estado = ocx.get('estado', 'Pendiente')
        dias = ocx.get('dias_pendiente', 0)
        
        rows_ocx_pend += f'''<tr>
            <td>{ocx['folio']}</td>
            <td>{fecha_str}</td>
            <td>{ocx['proveedor'][:40]}</td>
            <td><span class="badge badge-pendiente">{estado}</span></td>
            <td class="center">{dias}d</td>
            <td class="monto">${ocx['monto_usd']:,.2f}</td>
        </tr>'''

    if not rows_ocx_pend:
        rows_ocx_pend = '<tr><td colspan="6" style="text-align:center;color:#888">No hay OCXs pendientes de aprobación</td></tr>'

    # Construir HTML
    nav = NAV_HTML.replace('KEY_PLACEHOLDER', key).replace('NAV_SALDOS', '').replace('NAV_TESORERIA', '').replace('NAV_PIPELINE', 'active').replace('NAV_ANUAL', '').replace('NAV_SEMANAL', '')
    logo_b64 = get_logo_base64()

    html = PIPELINE_HTML.replace('LOGO_BASE64', logo_b64)
    html = html.replace('NAV_PLACEHOLDER', nav)
    html = html.replace('FECHA_PLACEHOLDER', now_chile().strftime('%d-%m-%Y %H:%M'))
    html = html.replace('SOLI_CANTIDAD', str(soli_cantidad))
    html = html.replace('SOLI_MONTO', f"${soli_monto:,.0f}")
    html = html.replace('OC_CANTIDAD', str(oc_cantidad))
    html = html.replace('OC_MONTO', f"${oc_monto:,.0f}")
    html = html.replace('OCX_CANTIDAD', str(ocx_cantidad))
    html = html.replace('OCX_MONTO', f"${ocx_monto_usd:,.2f}")
    html = html.replace('OC_PEND_CANTIDAD', str(oc_pend_cantidad))
    html = html.replace('OC_PEND_MONTO', f"${oc_pend_monto:,.0f}")
    html = html.replace('OCX_PEND_CANTIDAD', str(ocx_pend_cantidad))
    html = html.replace('OCX_PEND_MONTO', f"${ocx_pend_monto_usd:,.2f}")
    html = html.replace('ROWS_SOLI', rows_soli)
    html = html.replace('ROWS_OC', rows_oc)
    html = html.replace('ROWS_OCX', rows_ocx)
    html = html.replace('ROWS_OC_PEND', rows_oc_pend)
    html = html.replace('ROWS_OCX_PEND', rows_ocx_pend)

    return html


@app.route('/cashflow')
def cashflow_anual():
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return "<script>alert('Contraseña incorrecta');window.location='/';</script>"
    
    try:
        # Usar Skualo Balance (Lógica estandarizada)
        skualo_cli = SkualoClient() 
        data_contable = skualo_cli.get_balance_tributario()
        saldo_clp = 0
        bancos_clp = ["1102002", "1102003", "1102004", "1102005", "1102013"]
        for item in data_contable:
            if item.get("idCuenta") in bancos_clp:
                 saldo_clp += (item.get("activos", 0) - item.get("pasivos", 0))    
    except:
        saldo_clp = 0
    
    forecast = get_forecast_2026()
    if not forecast:
        return "<h1>Error cargando datos del forecast</h1>"
    
    total_apal = sum(m['apalancada'] for m in forecast)
    total_vta = sum(m['vta_nueva'] for m in forecast)
    total_anual = sum(m['usar'] for m in forecast)
    total_q1 = sum(m['usar'] for m in forecast[:3])
    
    pct_apal = int(total_apal / total_anual * 100) if total_anual > 0 else 0
    pct_vta = 100 - pct_apal
    
    fmt = lambda x: f"${x/1e6:.0f}M"
    fmt_full = lambda x: f"${x:,.0f}"
    
    q1_cards = ""
    for m in forecast[:3]:
        q1_cards += f'<div class="q1-card"><div class="q1-mes">{m["mes_full"]}</div><div class="q1-value">{fmt(m["usar"])}</div><span class="badge badge-apal">100% Compromiso</span></div>'
    
    rows_anual = ""
    for i, m in enumerate(forecast):
        is_q1 = 'q1' if i < 3 else ''
        vta_display = fmt(m['vta_nueva']) if m['vta_nueva'] > 0 else '-'
        vta_class = 'vta' if m['vta_nueva'] > 0 else ''
        pct = m['pct_certeza']
        icon = '🟢' if pct >= 70 else '🟡' if pct >= 40 else '🔴'
        
        rows_anual += f'''<tr class="{is_q1}">
            <td{"style='font-weight:600'" if i < 3 else ""}>{m['mes_full']} 2026</td>
            <td class="right apal">{fmt(m['apalancada'])}</td>
            <td class="right {vta_class}">{vta_display}</td>
            <td class="right" style="font-weight:600">{fmt(m['usar'])}</td>
            <td class="center">{pct}% {icon}</td>
            <td><div class="bar-container"><div class="bar-apal" style="width:{pct}%"></div><div class="bar-vta" style="width:{100-pct}%"></div></div></td>
        </tr>'''
    
    rows_anual += f'''<tr class="total">
        <td>TOTAL 2026</td>
        <td class="right apal">{fmt(total_apal)}</td>
        <td class="right vta">{fmt(total_vta)}</td>
        <td class="right" style="font-size:14px">{fmt(total_anual)}</td>
        <td colspan="2"></td>
    </tr>'''
    
    nav = NAV_HTML.replace('KEY_PLACEHOLDER', key).replace('NAV_SALDOS', '').replace('NAV_TESORERIA', '').replace('NAV_PIPELINE', '').replace('NAV_ANUAL', 'active').replace('NAV_SEMANAL', '')
    logo_b64 = get_logo_base64()
    
    html = CASHFLOW_ANUAL_HTML.replace('LOGO_BASE64', logo_b64)
    html = html.replace('NAV_PLACEHOLDER', nav)
    html = html.replace('FECHA_PLACEHOLDER', now_chile().strftime('%d-%m-%Y %H:%M'))
    html = html.replace('SALDO_PLACEHOLDER', fmt_full(saldo_clp))
    html = html.replace('Q1_CARDS_PLACEHOLDER', q1_cards)
    html = html.replace('ROWS_ANUAL_PLACEHOLDER', rows_anual)
    html = html.replace('TOTAL_APAL_PLACEHOLDER', fmt(total_apal))
    html = html.replace('TOTAL_VTA_PLACEHOLDER', fmt(total_vta))
    html = html.replace('TOTAL_Q1_PLACEHOLDER', fmt(total_q1))
    html = html.replace('TOTAL_ANUAL_PLACEHOLDER', fmt(total_anual))
    html = html.replace('PCT_APAL', str(pct_apal))
    html = html.replace('PCT_VTA', str(pct_vta))
    
    return html


@app.route('/cashflow/semanal')
def cashflow_semanal():
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return "<script>alert('Contraseña incorrecta');window.location='/';</script>"
    
    try:
        # Fintoc deprecated -> Usando Skualo
        skualo_cli = SkualoClient() 
        saldos = skualo_cli.get_saldos_cuentas()
        
        # Calcular Total CLP (Bancos + Caja)
        # Por ahora usamos el "disponible" mapeado en /tablero o una aproximación
        # Si get_saldos_cuentas devuelve activos, usaremos eso.
        # En tablero hicimos: total_clp += saldo para ciertos bancos.
        # Aquí simplificaremos usando el calculo hecho en Tablero si pudiéramos, 
        # pero para ser dry, instanciamos logic similar.
        
        # Opcion rapida: Balance Tributario
        data_contable = skualo_cli.get_balance_tributario()
        saldo_clp = 0
        
        # IDs de bancos CLP (mismos que tablero)
        bancos_clp = ["1102002", "1102003", "1102004", "1102005", "1102013"]
        
        for item in data_contable:
            if item.get("idCuenta") in bancos_clp:
                 saldo_clp += (item.get("activos", 0) - item.get("pasivos", 0))

    except Exception as e:
        print(f"Error Skualo Balance: {e}")
        saldo_clp = 0

    # Obtener movimientos reales de hoy desde Skualo Bancos
    try:
        skualo_bancos = SkualoBancosClient()
        resumen_bancos = skualo_bancos.get_resumen_todos_bancos()
        entradas_bancos_hoy = resumen_bancos['total_ingresos']
        salidas_bancos_hoy = resumen_bancos['total_egresos']
    except Exception as e:
        print(f"Error Skualo Bancos: {e}")
        entradas_bancos_hoy = 0
        salidas_bancos_hoy = 0
    
    # Obtener datos Skualo
    try:
        cf = SkualoCashFlow()
        resumen = cf.get_resumen_semana()
        proyeccion = resumen['proyeccion_diaria']
        cxc_detalle = cf.get_cxc_detalle()
        cxp_detalle = cf.get_cxp_detalle()
    except Exception as e:
        print(f"Error Skualo: {e}")
        return f"<h1>Error cargando datos de Skualo: {e}</h1>"
    
    fmt = lambda x: f"${x/1e6:.0f}M"
    fmt_full = lambda x: f"${x:,.0f}"

    # Construir proyección diaria con saldo acumulado
    saldo_acum = saldo_clp
    dias_data = []
    hoy = datetime.now(TZ_CHILE).date()
    
    for fecha, p in proyeccion.items():
        # Para hoy: usar movimientos reales de bancos
        entradas_dia = p['entradas']
        salidas_dia = p['salidas_total']
        fuente_entradas = "Skualo CxC"

        if fecha == hoy:
            # Usar datos reales de movimientos bancarios
            if entradas_bancos_hoy > 0 or salidas_bancos_hoy > 0:
                entradas_dia = entradas_bancos_hoy
                salidas_dia = salidas_bancos_hoy
                fuente_entradas = "Bancos"

        # Recalcular neto
        neto_dia = entradas_dia - salidas_dia
        saldo_acum += neto_dia
        
        dia_en = fecha.strftime('%a')
        dia_es = DIAS_SEMANA_ES.get(dia_en, dia_en)
        dias_data.append({
            'fecha': fecha,
            'dia': dia_es,
            'entradas': entradas_dia,
            'fuente': fuente_entradas,
            'salidas': salidas_dia,
            'neto': neto_dia,
            'saldo': saldo_acum,
            'critico': salidas_dia > 100000000,
            'tiene_entradas': entradas_dia > 0,
            'tiene_recurrentes': p['salidas_recurrentes'] > 0,
        })

    # Calcular KPIs sumando desde dias_data (incluye datos reales de hoy)
    total_entradas = sum(d['entradas'] for d in dias_data)
    total_salidas = sum(d['salidas'] for d in dias_data)
    variacion_neta = total_entradas - total_salidas

    # Día crítico
    dia_critico = resumen['dia_critico']
    
    # Alerta
    if dia_critico['neto'] < -100000000:
        alert_html = f'<div class="alert"><span>⚠️</span><div><strong>Atención {dia_critico["fecha"].strftime("%d-%b")}:</strong> Salidas de {fmt_full(abs(dia_critico["neto"]))}. Confirmar cobros antes de esa fecha.</div></div>'
    else:
        alert_html = f'<div class="alert success"><span>✅</span><div>Sin alertas críticas esta semana - Flujo neto: {fmt(resumen["flujo_neto"])}</div></div>'
    
    # Tags días de pago
    tags_html = ""
    for c in DIAS_PAGO_CLIENTES:
        tags_html += f'<span class="tag">{c["cliente"]} <strong>{c["dias"]}d</strong></span>'
    
    # Rows detalle diario
    rows_diario = ""
    for d in dias_data:
        clase = 'critico' if d['critico'] else 'positivo' if d['entradas'] > 10000000 else ''
        fuente = ""
        if d['tiene_entradas']:
            fuente = '<span class="badge badge-skualo">Skualo</span>'
        if d['tiene_recurrentes']:
            fuente += '<span class="badge badge-rec">Rec</span>'
        if not fuente:
            fuente = '-'
        
        neto_color = 'verde' if d['neto'] >= 0 else 'rojo'
        neto_signo = '+' if d['neto'] >= 0 else ''
        
        rows_diario += f'''<tr class="{clase}">
            <td>{fecha_es(d['fecha'])}</td>
            <td>{d['dia']}</td>
            <td class="right verde">{fmt_full(d['entradas'])}</td>
            <td class="center">{fuente}</td>
            <td class="right{' rojo' if d['critico'] else ''}">{fmt_full(d['salidas'])}</td>
            <td class="right {neto_color}">{neto_signo}{fmt_full(d['neto'])}</td>
            <td class="right">{fmt_full(d['saldo'])}</td>
        </tr>'''
    
    # Top entradas con documento
    top_entradas = sorted(cxc_detalle, key=lambda x: x['saldo'], reverse=True)[:5]
    rows_top_entradas = ""
    for e in top_entradas:
        fecha_str = fecha_es(e['fecha_cobro_esperada'])
        doc_str = e.get('documento', '')[:12] if e.get('documento') else ''
        rows_top_entradas += f'''<tr>
            <td>{e['cliente'][:25]} <span class="badge badge-dias">{e['dias_pago_config']}d</span>{f' <small style="color:#888">{doc_str}</small>' if doc_str else ''}</td>
            <td class="center">{fecha_str}</td>
            <td class="right verde">{fmt_full(e['saldo'])}</td>
        </tr>'''
    
    # Top salidas SEMANA (recurrentes + CxP que vencen en 7 días)
    hoy = now_chile().date()
    fin_semana = hoy + timedelta(days=7)
    salidas_semana = []

    # Obtener movimientos bancarios de hoy para detectar pagos ya ejecutados
    try:
        movimientos_hoy_detalle = []
        for banco, cuenta_id in skualo_bancos.cuentas.items():
            mov_banco = skualo_bancos.get_movimientos_hoy(cuenta_id)
            movimientos_hoy_detalle.extend(mov_banco['movimientos'])
        glosas_hoy = [mov.get('glosa', '').upper() for mov in movimientos_hoy_detalle]
    except Exception as e:
        print(f"Error obteniendo movimientos detallados: {e}")
        glosas_hoy = []

    # Recurrentes de la semana
    for r in RECURRENTES:
        dia_rec = r['dia']
        if hoy.day <= dia_rec:
            fecha_rec = hoy.replace(day=dia_rec)
        else:
            if hoy.month == 12:
                fecha_rec = hoy.replace(year=hoy.year+1, month=1, day=dia_rec)
            else:
                fecha_rec = hoy.replace(month=hoy.month+1, day=dia_rec)
        # Solo si cae en los próximos 7 días
        if hoy <= fecha_rec <= fin_semana:
            # Verificar si ya fue pagado hoy y obtener monto real
            concepto_upper = r['concepto'].upper()
            ya_pagado = False
            monto_real = r['monto']  # Monto estimado por defecto

            # Buscar palabras clave del concepto en las glosas y extraer monto real
            palabras_clave = concepto_upper.split()
            for mov in movimientos_hoy_detalle:
                glosa = mov.get('glosa', '').upper()
                if any(palabra in glosa for palabra in palabras_clave if len(palabra) > 3):
                    ya_pagado = True
                    # Extraer monto real del movimiento (cargo)
                    cargo = mov.get('montoCargo', 0)
                    if cargo > 0:
                        monto_real = cargo
                    break

            # Si no fue pagado o es fecha futura, agregarlo
            if not ya_pagado or fecha_rec > hoy:
                salidas_semana.append({
                    'concepto': r['concepto'],
                    'monto': monto_real,  # Usar monto real si fue pagado
                    'tipo': 'rec',
                    'fecha': fecha_rec,
                    'pagado': ya_pagado and fecha_rec == hoy
                })
    
    # CxP que vencen en los próximos 7 días
    for c in cxp_detalle:
        fecha_cxp = c.get('vencimiento')
        if fecha_cxp and hoy <= fecha_cxp <= fin_semana:
            salidas_semana.append({'concepto': c['proveedor'], 'monto': c['saldo'], 'tipo': 'cxp', 'fecha': fecha_cxp, 'documento': c.get('documento', ''), 'pagado': False})
    
    salidas_semana = sorted(salidas_semana, key=lambda x: x['monto'], reverse=True)[:5]
    rows_salidas_semana = ""
    for s in salidas_semana:
        badge_class = 'badge-rec' if s['tipo'] == 'rec' else 'badge-cxp'
        pagado = s.get('pagado', False)
        bg = 'style="background:#f0fff0;opacity:0.7"' if pagado else ('style="background:#fff5f5"' if s['monto'] > 50000000 else '')
        fecha_str = fecha_es(s['fecha'])
        concepto_texto = s['concepto'][:35]
        if pagado:
            concepto_texto += ' ✓'
        monto_style = 'class="right" style="text-decoration:line-through;color:#888"' if pagado else 'class="right"'
        rows_salidas_semana += f'''<tr {bg}>
            <td>{concepto_texto}</td>
            <td class="center">{fecha_str}</td>
            <td class="center"><span class="badge {badge_class}">{s['tipo']}</span></td>
            <td {monto_style}>{fmt_full(s['monto'])}</td>
        </tr>'''
    
    if not rows_salidas_semana:
        rows_salidas_semana = '<tr><td colspan="4" style="text-align:center;color:#888">Sin salidas CxP en los próximos 7 días</td></tr>'
    
    # Top 5 CxP Pendientes (TODAS, sin importar fecha)
    top_cxp_pendientes = sorted(cxp_detalle, key=lambda x: x['saldo'], reverse=True)[:5]
    rows_cxp_pendientes = ""
    for c in top_cxp_pendientes:
        fecha_str = fecha_es(c.get('vencimiento'))
        dias_venc = c.get('dias_vencido', 0)
        if dias_venc > 0:
            dias_str = f'<span style="color:#dc3545">+{dias_venc}d</span>'
        elif dias_venc < 0:
            dias_str = f'<span style="color:#28a745">{dias_venc}d</span>'
        else:
            dias_str = 'Hoy'
        doc_str = c.get('documento', '')[:15]
        rows_cxp_pendientes += f'''<tr>
            <td>{c['proveedor'][:30]}</td>
            <td><small>{doc_str}</small></td>
            <td class="center">{fecha_str}</td>
            <td class="center">{dias_str}</td>
            <td class="right">{fmt_full(c['saldo'])}</td>
        </tr>'''
    
    # Datos para gráfico (fechas en español)
    chart_labels = [fecha_es(d['fecha']) for d in dias_data]
    chart_entradas = [d['entradas'] for d in dias_data]
    chart_salidas = [-d['salidas'] for d in dias_data]
    chart_saldos = [d['saldo'] for d in dias_data]
    
    # Variación neta clase
    variacion_class = '' if variacion_neta >= 0 else 'rojo'
    variacion_color = 'verde' if variacion_neta >= 0 else 'rojo'
    
    nav = NAV_HTML.replace('KEY_PLACEHOLDER', key).replace('NAV_SALDOS', '').replace('NAV_TESORERIA', '').replace('NAV_PIPELINE', '').replace('NAV_ANUAL', '').replace('NAV_SEMANAL', 'active')
    logo_b64 = get_logo_base64()
    
    html = CASHFLOW_SEMANAL_HTML.replace('LOGO_BASE64', logo_b64)
    html = html.replace('NAV_PLACEHOLDER', nav)
    html = html.replace('FECHA_PLACEHOLDER', now_chile().strftime('%d-%m-%Y %H:%M'))
    html = html.replace('SALDO_PLACEHOLDER', fmt_full(saldo_clp))
    html = html.replace('ENTRADAS_PLACEHOLDER', fmt_full(total_entradas))
    html = html.replace('SALIDAS_PLACEHOLDER', fmt_full(total_salidas))
    html = html.replace('VARIACION_NETA_PLACEHOLDER', fmt_full(variacion_neta))
    html = html.replace('SALDO_FINAL_CLASS', variacion_class)
    html = html.replace('SALDO_FINAL_COLOR', variacion_color)
    html = html.replace('ALERT_PLACEHOLDER', alert_html)
    html = html.replace('TAGS_DIAS_PAGO', tags_html)
    html = html.replace('ROWS_DIARIO', rows_diario)
    html = html.replace('ROWS_TOP_ENTRADAS', rows_top_entradas)
    html = html.replace('ROWS_SALIDAS_SEMANA', rows_salidas_semana)
    html = html.replace('ROWS_CXP_PENDIENTES', rows_cxp_pendientes)
    html = html.replace('CHART_LABELS', str(chart_labels))
    html = html.replace('CHART_ENTRADAS', str(chart_entradas))
    html = html.replace('CHART_SALIDAS', str(chart_salidas))
    html = html.replace('CHART_SALDOS', str(chart_saldos))
    html = html.replace('KEY_PLACEHOLDER', key)

    return html


# ============================================
# EXPORTACIÓN NÓMINA SCOTIABANK
# ============================================

def load_maestro_proveedores():
    """Cargar maestro de proveedores desde JSON"""
    try:
        with open('maestro_proveedores.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}

def normalizar_rut(rut):
    """Normalizar RUT para búsqueda en maestro"""
    if not rut:
        return ''
    rut = str(rut).upper().replace('.', '').replace('-', '').replace(' ', '')
    return rut

def get_proximo_viernes():
    """Obtener fecha del próximo viernes"""
    hoy = now_chile().date()
    dias_hasta_viernes = (4 - hoy.weekday()) % 7
    if dias_hasta_viernes == 0 and hoy.weekday() == 4:
        return hoy  # Hoy es viernes
    return hoy + timedelta(days=dias_hasta_viernes if dias_hasta_viernes > 0 else 7)

@app.route('/nomina/scotiabank')
def nomina_scotiabank():
    """Página de generación de nómina Scotiabank"""
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return "<script>alert('Contraseña incorrecta');window.location='/';</script>"
    
    # Obtener CxP pendientes
    try:
        cf = SkualoCashFlow()
        cxp_detalle = cf.get_cxp_detalle()
    except Exception as e:
        return f"<h1>Error cargando CxP: {e}</h1>"
    
    # Cargar maestro proveedores
    maestro = load_maestro_proveedores()
    
    # Próximo viernes
    viernes = get_proximo_viernes()
    viernes_str = viernes.strftime('%d-%b-%Y')
    for en, es in MESES_ES.items():
        viernes_str = viernes_str.replace(en, es)
    
    # Filtrar CxP para el viernes (aplicando regla de viernes)
    hoy = now_chile().date()
    cxp_viernes = []
    
    for c in cxp_detalle:
        venc = c.get('vencimiento')
        if venc:
            # Aplicar regla viernes: si vence entre hoy y viernes, pagar el viernes
            if hoy <= venc <= viernes:
                rut_limpio = normalizar_rut(c.get('rut', ''))
                datos_banco = maestro.get(rut_limpio, {})
                
                # Determinar tipo documento
                doc = c.get('documento', '')
                if 'BH' in str(doc).upper() or 'HONORARIO' in str(doc).upper():
                    tipo_doc = 'HONORARIO'
                else:
                    tipo_doc = 'FACTURA'
                
                cxp_viernes.append({
                    'rut': c.get('rut', ''),
                    'proveedor': c.get('proveedor', ''),
                    'documento': doc,
                    'monto': int(c.get('saldo', 0)),
                    'vencimiento': venc,
                    'banco': datos_banco.get('banco', ''),
                    'cuenta': datos_banco.get('cuenta', ''),
                    'forma_pago': datos_banco.get('forma_pago', 'CUENTA OTRO BANCO'),
                    'email': datos_banco.get('email', ''),
                    'tipo_doc': tipo_doc,
                    'en_maestro': bool(datos_banco)
                })
    
    # Ordenar por monto descendente
    cxp_viernes = sorted(cxp_viernes, key=lambda x: x['monto'], reverse=True)
    total_nomina = sum(c['monto'] for c in cxp_viernes)
    
    # Contar proveedores sin datos bancarios
    sin_datos = sum(1 for c in cxp_viernes if not c['en_maestro'])
    
    fmt_full = lambda x: f"${x:,.0f}"
    
    # Generar filas HTML
    rows = ""
    for i, c in enumerate(cxp_viernes, 1):
        status_class = '' if c['en_maestro'] else 'style="background:#fff3cd"'
        status_icon = '✓' if c['en_maestro'] else '⚠️'
        rows += f'''<tr {status_class}>
            <td>{i}</td>
            <td>{c['rut']}</td>
            <td>{c['proveedor'][:30]}</td>
            <td>{c['documento']}</td>
            <td>{c['tipo_doc']}</td>
            <td class="right">{fmt_full(c['monto'])}</td>
            <td>{c['banco'][:20] if c['banco'] else '-'}</td>
            <td>{c['cuenta'] if c['cuenta'] else '-'}</td>
            <td class="center">{status_icon}</td>
        </tr>'''
    
    nav = NAV_HTML.replace('KEY_PLACEHOLDER', key).replace('NAV_SALDOS', '').replace('NAV_TESORERIA', '').replace('NAV_PIPELINE', '').replace('NAV_ANUAL', '').replace('NAV_SEMANAL', '')
    logo_b64 = get_logo_base64()

    html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>CathPro - Nómina Scotiabank</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{font-family:'Segoe UI',sans-serif;background:#f5f5f5;color:#242625}}
        .header{{background:#242625;padding:15px 30px;display:flex;align-items:center;gap:20px}}
        .header img{{height:50px}}
        .header h1{{color:#fff;font-size:20px;font-weight:500}}
        .header-sub{{color:#888;font-size:12px}}
        .nav-links{{display:flex;gap:10px;margin-left:20px}}
        .nav-links a{{color:#888;text-decoration:none;padding:8px 15px;border-radius:5px;font-size:13px}}
        .nav-links a:hover,.nav-links a.active{{background:#55b245;color:white}}
        .container{{max-width:1400px;margin:0 auto;padding:25px}}
        .kpis{{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin-bottom:25px}}
        .kpi{{background:#fff;border-radius:10px;padding:18px;box-shadow:0 2px 8px rgba(0,0,0,0.08);border-left:4px solid #55b245}}
        .kpi.azul{{border-left-color:#17a2b8}}
        .kpi.naranja{{border-left-color:#f7941d}}
        .kpi.rojo{{border-left-color:#dc3545}}
        .kpi-label{{font-size:11px;color:#666;text-transform:uppercase;margin-bottom:6px}}
        .kpi-value{{font-size:22px;font-weight:700}}
        .kpi-sub{{font-size:11px;color:#888;margin-top:4px}}
        .btn{{display:inline-block;padding:12px 24px;border-radius:8px;font-size:14px;font-weight:600;text-decoration:none;cursor:pointer;border:none}}
        .btn-primary{{background:#55b245;color:white}}
        .btn-primary:hover{{background:#449636}}
        .btn-secondary{{background:#6c757d;color:white}}
        .actions{{margin-bottom:25px;display:flex;gap:15px;align-items:center}}
        table{{width:100%;border-collapse:collapse;background:#fff;border-radius:10px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08)}}
        th{{background:#242625;color:#fff;padding:12px 10px;font-size:11px;font-weight:500;text-align:left}}
        th.right{{text-align:right}}
        th.center{{text-align:center}}
        td{{padding:10px;font-size:12px;border-bottom:1px solid #eee}}
        td.right{{text-align:right;font-family:monospace}}
        td.center{{text-align:center}}
        .alert{{background:#fff3cd;border:1px solid #ffc107;padding:15px;border-radius:8px;margin-bottom:20px}}
        .alert-danger{{background:#f8d7da;border-color:#f5c6cb}}
        .footer{{text-align:center;padding:20px;color:#888;font-size:11px}}
    </style>
</head>
<body>
    <div class="header">
        <img src="data:image/png;base64,{logo_b64}" alt="CathPro">
        <div>
            <h1>Nómina Proveedores Scotiabank</h1>
            <div class="header-sub">Pagos Viernes {viernes_str}</div>
        </div>
        {nav}
    </div>
    
    <div class="container">
        <div class="kpis">
            <div class="kpi azul">
                <div class="kpi-label">Fecha Pago</div>
                <div class="kpi-value">{viernes_str}</div>
                <div class="kpi-sub">Próximo viernes</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Proveedores</div>
                <div class="kpi-value">{len(cxp_viernes)}</div>
                <div class="kpi-sub">En nómina</div>
            </div>
            <div class="kpi naranja">
                <div class="kpi-label">Total Nómina</div>
                <div class="kpi-value">{fmt_full(total_nomina)}</div>
                <div class="kpi-sub">A pagar</div>
            </div>
            <div class="kpi {'rojo' if sin_datos > 0 else ''}">
                <div class="kpi-label">Sin Datos Banco</div>
                <div class="kpi-value">{sin_datos}</div>
                <div class="kpi-sub">{'Requieren actualización' if sin_datos > 0 else 'Todo OK'}</div>
            </div>
        </div>
        
        {'<div class="alert alert-danger">⚠️ <strong>Atención:</strong> Hay ' + str(sin_datos) + ' proveedores sin datos bancarios en el maestro. Actualizar antes de exportar.</div>' if sin_datos > 0 else ''}
        
        <div class="actions">
            <a href="/nomina/scotiabank/exportar?key={key}" class="btn btn-primary">📥 Exportar Excel Scotiabank</a>
            <a href="/cashflow/semanal?key={key}" class="btn btn-secondary">← Volver al Cash Flow</a>
        </div>
        
        <table>
            <thead>
                <tr>
                    <th>#</th>
                    <th>RUT</th>
                    <th>Proveedor</th>
                    <th>Documento</th>
                    <th>Tipo</th>
                    <th class="right">Monto</th>
                    <th>Banco</th>
                    <th>Cuenta</th>
                    <th class="center">Estado</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
        
        <div class="footer">
            Nómina Scotiabank CathPro | Generada {now_chile().strftime('%d-%m-%Y %H:%M')}
        </div>
    </div>
</body>
</html>'''
    
    return html


@app.route('/nomina/scotiabank/exportar')
def exportar_nomina_scotiabank():
    """Exportar nómina en formato Excel compatible con macro Scotiabank"""
    from flask import Response
    
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return "<script>alert('Contraseña incorrecta');window.location='/';</script>"
    
    # Obtener CxP pendientes
    try:
        cf = SkualoCashFlow()
        cxp_detalle = cf.get_cxp_detalle()
    except Exception as e:
        return f"<h1>Error cargando CxP: {e}</h1>"
    
    # Cargar maestro proveedores
    maestro = load_maestro_proveedores()
    
    # Próximo viernes
    viernes = get_proximo_viernes()
    hoy = now_chile().date()
    
    # Filtrar y preparar datos
    datos_nomina = []
    for c in cxp_detalle:
        venc = c.get('vencimiento')
        if venc and hoy <= venc <= viernes:
            rut_limpio = normalizar_rut(c.get('rut', ''))
            datos_banco = maestro.get(rut_limpio, {})
            
            doc = c.get('documento', '')
            if 'BH' in str(doc).upper() or 'HONORARIO' in str(doc).upper():
                tipo_doc = 'HONORARIO'
            else:
                tipo_doc = 'FACTURA'
            
            datos_nomina.append({
                'Rut\nProveedor': c.get('rut', ''),
                'Nombre\nProveedor': c.get('proveedor', ''),
                'Banco\nProveedor': datos_banco.get('banco', ''),
                'Cuenta\nProveedor': datos_banco.get('cuenta', ''),
                'Tipo Documento': tipo_doc,
                'Nº Documento': doc,
                'Monto': int(c.get('saldo', 0)),
                'Forma Pago': datos_banco.get('forma_pago', 'CUENTA OTRO BANCO'),
                'Cód. Suc': '',
                'email aviso': datos_banco.get('email', '')
            })
    
    # Ordenar por monto descendente
    datos_nomina = sorted(datos_nomina, key=lambda x: x['Monto'], reverse=True)
    
    # Crear DataFrame
    df = pd.DataFrame(datos_nomina)
    
    # Generar Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Proveedores', index=False, startrow=3)
        
        # Agregar encabezado con datos de la empresa
        ws = writer.sheets['Proveedores']
        ws['A1'] = 'Scotiabank'
        ws['B1'] = 'Nombre empresa'
        ws['C1'] = 'CATHPRO LTDA'
        ws['D1'] = 'Rut empresa:'
        ws['E1'] = '76243957-3'
        ws['F1'] = 'N° Convenio'
        ws['G1'] = '3'
        ws['F2'] = 'Fecha nómina:'
        ws['G2'] = viernes.strftime('%Y-%m-%d')
    
    output.seek(0)
    
    # Nombre del archivo
    fecha_str = viernes.strftime('%d_%m_%y')
    filename = f'Nomina_Scotiabank_{fecha_str}.xlsx'
    
    return Response(
        output.getvalue(),
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


# ============================================
# CHAT ASISTENTE VIRTUAL
# ============================================

CHAT_HTML = """
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>CathPro - Asistente Virtual</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:'Segoe UI',sans-serif;background:#f5f5f5;height:100vh;display:flex;flex-direction:column}
        .header{background:#242625;padding:15px 30px;display:flex;align-items:center;gap:15px}
        .header img{height:40px}
        .header h1{color:#fff;font-size:18px;font-weight:500}
        .header-sub{color:#888;font-size:11px}
        .nav-links{display:flex;gap:10px;margin-left:20px}
        .nav-links a{color:#888;text-decoration:none;padding:8px 15px;border-radius:5px;font-size:13px}
        .nav-links a:hover,.nav-links a.active{background:#55b245;color:white}
        .chat-container{flex:1;max-width:900px;margin:0 auto;width:100%;display:flex;flex-direction:column;padding:20px}
        .messages{flex:1;overflow-y:auto;padding:20px;background:white;border-radius:10px;margin-bottom:15px;box-shadow:0 2px 8px rgba(0,0,0,0.08)}
        .message{margin-bottom:15px;display:flex;gap:10px}
        .message.user{flex-direction:row-reverse}
        .message .avatar{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0}
        .message.assistant .avatar{background:#55b245;color:white}
        .message.user .avatar{background:#242625;color:white}
        .message .content{max-width:70%;padding:12px 16px;border-radius:12px;font-size:14px;line-height:1.5}
        .message.assistant .content{background:#f0f0f0;border-bottom-left-radius:4px}
        .message.user .content{background:#55b245;color:white;border-bottom-right-radius:4px}
        .input-area{display:flex;gap:10px}
        .input-area input{flex:1;padding:14px 18px;border:1px solid #ddd;border-radius:25px;font-size:14px;outline:none}
        .input-area input:focus{border-color:#55b245}
        .input-area button{padding:14px 24px;background:#55b245;color:white;border:none;border-radius:25px;cursor:pointer;font-size:14px;font-weight:500}
        .input-area button:hover{background:#449636}
        .input-area button:disabled{background:#ccc;cursor:not-allowed}
        .typing{color:#888;font-style:italic;font-size:13px}
        .suggestions{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:15px}
        .suggestion{background:#e8f5e9;border:1px solid #c8e6c9;padding:8px 14px;border-radius:20px;font-size:12px;cursor:pointer;transition:all 0.2s}
        .suggestion:hover{background:#c8e6c9}
    </style>
</head>
<body>
    <div class="header">
        <img src="data:image/png;base64,LOGO_BASE64" alt="CathPro">
        <div>
            <h1>Asistente Virtual CathPro</h1>
            <div class="header-sub">Cash Flow & Contabilidad</div>
        </div>
        NAV_PLACEHOLDER
    </div>
    
    <div class="chat-container">
        <div class="suggestions">
            <span class="suggestion" onclick="enviarSugerencia('¿Cuánto tenemos en caja hoy?')">💰 Saldo en caja</span>
            <span class="suggestion" onclick="enviarSugerencia('¿Quiénes son los 5 clientes que más nos deben?')">📊 Top deudores</span>
            <span class="suggestion" onclick="enviarSugerencia('¿Qué pagos tenemos esta semana?')">📅 Pagos semana</span>
            <span class="suggestion" onclick="enviarSugerencia('¿Cuál es la posición neta?')">📈 Posición neta</span>
            <span class="suggestion" onclick="enviarSugerencia('¿Cuánto debemos a proveedores?')">💸 CxP total</span>
        </div>
        
        <div class="messages" id="messages">
            <div class="message assistant">
                <div class="avatar">🤖</div>
                <div class="content">¡Hola! Soy el asistente financiero de CathPro. Puedo ayudarte con consultas sobre saldos bancarios, cuentas por cobrar/pagar, cash flow y pagos recurrentes. ¿En qué puedo ayudarte?</div>
            </div>
        </div>
        
        <div class="input-area">
            <input type="text" id="input" placeholder="Escribe tu pregunta..." onkeypress="if(event.key==='Enter')enviar()">
            <button onclick="enviar()" id="btnEnviar">Enviar</button>
        </div>
    </div>
    
    <script>
        const KEY = 'KEY_PLACEHOLDER';
        
        function enviarSugerencia(texto) {
            document.getElementById('input').value = texto;
            enviar();
        }
        
        async function enviar() {
            const input = document.getElementById('input');
            const pregunta = input.value.trim();
            if (!pregunta) return;
            
            // Mostrar mensaje del usuario
            agregarMensaje(pregunta, 'user');
            input.value = '';
            
            // Mostrar typing
            const btn = document.getElementById('btnEnviar');
            btn.disabled = true;
            btn.textContent = '...';
            
            try {
                const response = await fetch('/chat/api?key=' + KEY, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({pregunta: pregunta})
                });
                
                const data = await response.json();
                agregarMensaje(data.respuesta || data.error, 'assistant');
            } catch (e) {
                agregarMensaje('Error de conexión: ' + e.message, 'assistant');
            }
            
            btn.disabled = false;
            btn.textContent = 'Enviar';
        }
        
        function agregarMensaje(texto, tipo) {
            const messages = document.getElementById('messages');
            const avatar = tipo === 'user' ? '👤' : '🤖';
            messages.innerHTML += `
                <div class="message ${tipo}">
                    <div class="avatar">${avatar}</div>
                    <div class="content">${texto.replace(/\n/g, '<br>')}</div>
                </div>
            `;
            messages.scrollTop = messages.scrollHeight;
        }
    </script>
</body>
</html>
"""

@app.route('/chat')
def chat_ui():
    """Interfaz de chat"""
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return "<script>alert('Contraseña incorrecta');window.location='/';</script>"
    
    if not CHAT_ENABLED:
        return "<h1>Chat no disponible - Falta configurar ANTHROPIC_API_KEY</h1>"
    
    nav = NAV_HTML.replace('KEY_PLACEHOLDER', key).replace('NAV_SALDOS', '').replace('NAV_TESORERIA', '').replace('NAV_PIPELINE', '').replace('NAV_ANUAL', '').replace('NAV_SEMANAL', '')
    logo_b64 = get_logo_base64()

    html = CHAT_HTML.replace('LOGO_BASE64', logo_b64)
    html = html.replace('NAV_PLACEHOLDER', nav)
    html = html.replace('KEY_PLACEHOLDER', key)
    
    return html


@app.route('/chat/api', methods=['POST'])
def chat_api():
    """API de chat"""
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return jsonify({'error': 'No autorizado'}), 401
    
    if not CHAT_ENABLED:
        return jsonify({'error': 'Chat no disponible'}), 503
    
    try:
        data = request.get_json()
        pregunta = data.get('pregunta', '')
        
        if not pregunta:
            return jsonify({'error': 'Pregunta vacía'}), 400
        
        # Crear instancia y responder
        assistant = CathProAssistant()
        respuesta = assistant.responder(pregunta)
        
        return jsonify({'respuesta': respuesta})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# @app.route('/webhook/fintoc', methods=['POST'])
# def webhook_fintoc():
#     """Recibe webhooks de Fintoc con movimientos bancarios reales"""
#     try:
#         evento = request.get_json()
#         if not evento:
#             return jsonify({"error": "No JSON"}), 400
#         resultado = procesar_evento_fintoc(evento)
#         print(f"[Webhook Fintoc] {resultado.get('tipo')}: {resultado.get('mensaje')}")
#         return jsonify({"status": "ok"}), 200
#     except Exception as e:
#         print(f"[Webhook Fintoc] Error: {e}")
#         return jsonify({"error": str(e)}), 500

@app.route('/api/movimientos/hoy')
def api_movimientos_hoy():
    """API para ver movimientos reales del día"""
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Usar SkualoBancosClient para obtener resumen del día actual
        skualo_bancos = SkualoBancosClient()
        resumen = skualo_bancos.get_resumen_todos_bancos()
        
        # Mapear respuesta de Skualo a la estructura esperada por el frontend
        # Espera: { movimientos_hoy: N, ingresos_hoy: $, egresos_hoy: $ }
        return jsonify({
            'movimientos_hoy': resumen['total_movimientos'],
            'ingresos_hoy': resumen['total_ingresos'],
            'egresos_hoy': resumen['total_egresos'],
            'detalle_bancos': resumen['bancos']
        })
    except Exception as e:
        print(f"Error Getting Skualo Moves: {e}")
        return jsonify({'error': str(e)}), 500



@app.route('/export/pdf')
def export_pdf():
    if not PDF_ENABLED:
        return "PDF generation disabled (missing libraries)", 501
        
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return "Unauthorized", 401
    
    # Reutilizar lógica de tablero (vamos a extraerla a una funcion)
    html = generate_tablero_html(key, for_pdf=True)
    
    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        return Response(result.getvalue(), mimetype='application/pdf')
    return "Error generating PDF", 500



def generate_tablero_html(key, for_pdf=False):
    skualo = SkualoClient()
    
    # --- SALDOS CLP desde Skualo Bancos (tiempo real, calculado desde movimientos) ---
    skualo_bancos = SkualoBancosClient()
    saldos_clp = skualo_bancos.get_saldos_clp()
    
    balances = []
    total_clp = saldos_clp["total"]
    
    # Agregar saldos CLP por banco
    for banco, saldo in saldos_clp.items():
        if banco != "total":
            balances.append({
                "banco": banco,
                "disponible": saldo,
                "moneda": "CLP"
            })
    
    # Tipo de cambio para mostrar equivalente CLP de USD/EUR (actualizar mensualmente)
    TC_USD = 885
    TC_EUR = 1027
    
    # Obtener saldos USD/EUR REALES desde Fintoc (conexión directa al banco)
    fintoc_client = FintocClient()
    saldos_usd_eur = fintoc_client.get_usd_eur_balances()
    
    total_usd_orig = saldos_usd_eur["usd"]["total"]
    total_eur_orig = saldos_usd_eur["eur"]["total"]
    
    # Calcular equivalente CLP para mostrar en cards principales
    total_usd_clp = total_usd_orig * TC_USD
    total_eur_clp = total_eur_orig * TC_EUR
    
    # Agregar cuentas USD a la tabla de detalle
    for nombre, saldo in saldos_usd_eur["usd"].items():
        if nombre != "total":
            balances.append({
                "banco": nombre,
                "disponible": saldo,
                "moneda": "USD"
            })
    
    # Agregar cuentas EUR a la tabla de detalle
    for nombre, saldo in saldos_usd_eur["eur"].items():
        if nombre != "total":
            balances.append({
                "banco": nombre,
                "disponible": saldo,
                "moneda": "EUR"
            })
            
    # Obtener Saldos Skualo (Fondos mutuos, CxC, CxP)
    saldos = skualo.get_saldos_cuentas()
    
    # Calcular posicion neta
    posicion_neta = saldos['por_cobrar'] - saldos['por_pagar_total']
    posicion_class = "positive" if posicion_neta >= 0 else "negative"
    
    # Generar filas tabla bancos
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

    if for_pdf:
        # Versión simplificada para PDF (sin nav, sin refresh)
        template = TABLERO_HTML.replace('<meta http-equiv="refresh" content="300">', '')
        nav = ""
    else:
        template = TABLERO_HTML
        nav = NAV_HTML.replace('KEY_PLACEHOLDER', key).replace('NAV_SALDOS', 'active').replace('NAV_TESORERIA', '').replace('NAV_PIPELINE', '').replace('NAV_ANUAL', '').replace('NAV_SEMANAL', '')

    logo_b64 = get_logo_base64()
    
    html = template.replace('LOGO_BASE64', logo_b64)
    html = html.replace('NAV_PLACEHOLDER', nav)
    html = html.replace('FECHA_PLACEHOLDER', now_chile().strftime('%d-%m-%Y %H:%M'))
    
    html = html.replace('TOTAL_CLP_PLACEHOLDER', f"${total_clp:,.0f}")
    
    html = html.replace('TOTAL_USD_CLP_PLACEHOLDER', f"${total_usd_clp:,.0f}")
    html = html.replace('TOTAL_USD_ORIG_PLACEHOLDER', f"US${total_usd_orig:,.2f}")
    
    html = html.replace('TOTAL_EUR_CLP_PLACEHOLDER', f"${total_eur_clp:,.0f}")
    html = html.replace('TOTAL_EUR_ORIG_PLACEHOLDER', f"€{total_eur_orig:,.0f}")
    html = html.replace('FONDOS_MUTUOS_PLACEHOLDER', f"${saldos['fondos_mutuos']:,.0f}")
    
    html = html.replace('POR_COBRAR_PLACEHOLDER', f"${saldos['por_cobrar']:,.0f}")
    html = html.replace('POR_PAGAR_NAC_PLACEHOLDER', f"${saldos['por_pagar_nacional']:,.0f}")
    html = html.replace('POR_PAGAR_INT_PLACEHOLDER', f"${saldos['por_pagar_internacional']:,.0f}")
    
    html = html.replace('POSICION_NETA_PLACEHOLDER', f"${posicion_neta:,.0f}")
    html = html.replace('POSICION_CLASS', posicion_class)
    
    html = html.replace('ROWS_PLACEHOLDER', rows)
    
    return html

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

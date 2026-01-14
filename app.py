from flask import Flask, request
from dotenv import load_dotenv
from fintoc_client import FintocClient
from skualo_client import SkualoClient
from skualo_cashflow import SkualoCashFlow
from datetime import datetime, timedelta
import pytz
import os
import base64
import json
import requests
import pandas as pd
from io import BytesIO

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
    <a href="/cashflow?key=KEY_PLACEHOLDER" class="NAV_ANUAL">Cash Flow Anual</a>
    <a href="/cashflow/semanal?key=KEY_PLACEHOLDER" class="NAV_SEMANAL">Cash Flow Semanal</a>
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
            <div class="card orange"><h3>Total USD</h3><p>TOTAL_USD_PLACEHOLDER</p></div>
            <div class="card blue"><h3>Total EUR</h3><p>TOTAL_EUR_PLACEHOLDER</p></div>
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
        </div>
        
        <div class="section-title">Detalle Saldos Bancarios</div>
        <table>
            <tr><th>Banco</th><th style="text-align:right">Disponible</th><th>Moneda</th></tr>
            ROWS_PLACEHOLDER
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
        @media(max-width:768px){.kpis{grid-template-columns:repeat(2,1fr)}.two-col{grid-template-columns:1fr}.header{flex-wrap:wrap}.nav-links{margin:10px 0}}
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
            <div class="header-sub">Saldo ApiVV CLP</div>
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
                <div class="kpi-label">Saldo Final</div>
                <div class="kpi-value SALDO_FINAL_COLOR">SALDO_FINAL_PLACEHOLDER</div>
                <div class="kpi-sub">Proyección día 7</div>
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
            Cash Flow CathPro | ApiVV + Skualo CxC/CxP + Recurrentes | FECHA_PLACEHOLDER
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
            <div class="header-sub">Saldo ApiVV CLP</div>
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
    
    fintoc = FintocClient()
    balances = fintoc.get_all_balances()
    total_clp = sum(b['disponible'] for b in balances if b['moneda'] == 'CLP')
    total_usd = sum(b['disponible'] for b in balances if b['moneda'] == 'USD')
    total_eur = sum(b['disponible'] for b in balances if b['moneda'] == 'EUR')
    
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
    
    nav = NAV_HTML.replace('KEY_PLACEHOLDER', key).replace('NAV_SALDOS', 'active').replace('NAV_ANUAL', '').replace('NAV_SEMANAL', '')
    logo_b64 = get_logo_base64()
    
    html = TABLERO_HTML.replace('LOGO_BASE64', logo_b64)
    html = html.replace('NAV_PLACEHOLDER', nav)
    html = html.replace('FECHA_PLACEHOLDER', now_chile().strftime('%d-%m-%Y %H:%M'))
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
def cashflow_anual():
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return "<script>alert('Contraseña incorrecta');window.location='/';</script>"
    
    try:
        fintoc = FintocClient()
        balances = fintoc.get_all_balances()
        saldo_clp = sum(b['disponible'] for b in balances if b['moneda'] == 'CLP')
    except:
        saldo_clp = 160000000
    
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
    
    nav = NAV_HTML.replace('KEY_PLACEHOLDER', key).replace('NAV_SALDOS', '').replace('NAV_ANUAL', 'active').replace('NAV_SEMANAL', '')
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
    
    # Obtener saldo Fintoc
    try:
        fintoc = FintocClient()
        balances = fintoc.get_all_balances()
        saldo_clp = sum(b['disponible'] for b in balances if b['moneda'] == 'CLP')
    except:
        saldo_clp = 160000000
    
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
    
    # Calcular KPIs
    total_entradas = resumen['total_entradas']
    total_salidas = resumen['total_salidas']
    saldo_final = saldo_clp + total_entradas - total_salidas
    
    # Construir proyección diaria con saldo acumulado
    saldo_acum = saldo_clp
    dias_data = []
    for fecha, p in proyeccion.items():
        saldo_acum += p['neto']
        dia_en = fecha.strftime('%a')
        dia_es = DIAS_SEMANA_ES.get(dia_en, dia_en)
        dias_data.append({
            'fecha': fecha,
            'dia': dia_es,
            'entradas': p['entradas'],
            'salidas': p['salidas_total'],
            'neto': p['neto'],
            'saldo': saldo_acum,
            'critico': p['salidas_total'] > 100000000,
            'tiene_entradas': p['entradas'] > 0,
            'tiene_recurrentes': p['salidas_recurrentes'] > 0,
        })
    
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
            salidas_semana.append({'concepto': r['concepto'], 'monto': r['monto'], 'tipo': 'rec', 'fecha': fecha_rec})
    
    # CxP que vencen en los próximos 7 días
    for c in cxp_detalle:
        fecha_cxp = c.get('vencimiento')
        if fecha_cxp and hoy <= fecha_cxp <= fin_semana:
            salidas_semana.append({'concepto': c['proveedor'], 'monto': c['saldo'], 'tipo': 'cxp', 'fecha': fecha_cxp, 'documento': c.get('documento', '')})
    
    salidas_semana = sorted(salidas_semana, key=lambda x: x['monto'], reverse=True)[:5]
    rows_salidas_semana = ""
    for s in salidas_semana:
        badge_class = 'badge-rec' if s['tipo'] == 'rec' else 'badge-cxp'
        bg = 'style="background:#fff5f5"' if s['monto'] > 50000000 else ''
        fecha_str = fecha_es(s['fecha'])
        rows_salidas_semana += f'''<tr {bg}>
            <td>{s['concepto'][:35]}</td>
            <td class="center">{fecha_str}</td>
            <td class="center"><span class="badge {badge_class}">{s['tipo']}</span></td>
            <td class="right">{fmt_full(s['monto'])}</td>
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
    
    # Saldo final clase
    saldo_final_class = '' if saldo_final >= saldo_clp else 'rojo'
    saldo_final_color = 'verde' if saldo_final >= saldo_clp else 'rojo'
    
    nav = NAV_HTML.replace('KEY_PLACEHOLDER', key).replace('NAV_SALDOS', '').replace('NAV_ANUAL', '').replace('NAV_SEMANAL', 'active')
    logo_b64 = get_logo_base64()
    
    html = CASHFLOW_SEMANAL_HTML.replace('LOGO_BASE64', logo_b64)
    html = html.replace('NAV_PLACEHOLDER', nav)
    html = html.replace('FECHA_PLACEHOLDER', now_chile().strftime('%d-%m-%Y %H:%M'))
    html = html.replace('SALDO_PLACEHOLDER', fmt_full(saldo_clp))
    html = html.replace('ENTRADAS_PLACEHOLDER', fmt_full(total_entradas))
    html = html.replace('SALIDAS_PLACEHOLDER', fmt_full(total_salidas))
    html = html.replace('SALDO_FINAL_PLACEHOLDER', fmt_full(saldo_final))
    html = html.replace('SALDO_FINAL_CLASS', saldo_final_class)
    html = html.replace('SALDO_FINAL_COLOR', saldo_final_color)
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
    
    nav = NAV_HTML.replace('KEY_PLACEHOLDER', key).replace('NAV_SALDOS', '').replace('NAV_ANUAL', '').replace('NAV_SEMANAL', '')
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


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

#!/usr/bin/env python3
"""
Cash Flow Generator v2 - CathPro
Integra: Fintoc (saldo) + Skualo (CxC/CxP) + Google Sheet Forecast + Config Recurrentes
"""

import json
import csv
import requests
from datetime import datetime, timedelta
from collections import defaultdict
from io import StringIO

# Configuración
FORECAST_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSCnSKEn66rdSM8T1R-lWIi79kzK1I2kDnS2ms7viozTdOW9tV5Gt7FBXRB-aErK-nhMFMU4C00Wbg7/pub?output=csv"
CONFIG_PATH = "cashflow_config.json"
OUTPUT_PATH = "cashflow_data_v2.json"

def parse_clp(val):
    """Parsear valores CLP desde el Sheet (formato: $65,000,000)"""
    if not val or val.strip() == '' or val.strip() == '$0':
        return 0
    val = val.replace('$', '').replace(',', '')
    try:
        return float(val)
    except:
        return 0

def get_forecast_from_sheet():
    """Descargar y parsear forecast desde Google Sheets"""
    print("📊 Descargando Forecast de Facturación...")
    
    try:
        response = requests.get(FORECAST_URL, timeout=30)
        response.raise_for_status()
        
        forecast_by_month = defaultdict(float)
        reader = csv.DictReader(StringIO(response.text))
        
        for row in reader:
            mes = row.get('Mes', '').strip()
            año = row.get('Año', '').strip()
            if año == '2026':
                forecast = parse_clp(row.get('Forecast', '0'))
                forecast_by_month[mes] += forecast
        
        # Convertir a números de mes
        month_map = {
            'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4,
            'Mayo': 5, 'Junio': 6, 'Julio': 7, 'Agosto': 8,
            'Septiembre': 9, 'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12
        }
        
        result = {}
        for mes_nombre, monto in forecast_by_month.items():
            if mes_nombre in month_map:
                result[month_map[mes_nombre]] = monto
                print(f"   {mes_nombre}: ${monto/1000000:.0f}M")
        
        return result
    
    except Exception as e:
        print(f"⚠️  Error descargando forecast: {e}")
        # Fallback con valores por defecto
        return {
            1: 419000000,
            2: 408000000,
            3: 485000000,
        }

def get_fintoc_balance():
    """Obtener saldo actual desde Fintoc"""
    # Por ahora usa valor fijo - integrar con fintoc_client.py
    return 160000000

def load_skualo_data():
    """Cargar datos de Skualo (CxC, CxP)"""
    try:
        with open('cashflow_data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("⚠️  cashflow_data.json no encontrado. Ejecuta primero el script base.")
        return None

def generate_cashflow(horizonte=90):
    """Generar proyección de cash flow integrada"""
    
    # 1. Cargar config
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
    
    # 2. Obtener saldo inicial
    saldo_inicial = get_fintoc_balance()
    print(f"💰 Saldo inicial: ${saldo_inicial/1000000:.0f}M")
    
    # 3. Cargar datos de Skualo
    skualo_data = load_skualo_data()
    if not skualo_data:
        return None
    
    # 4. Obtener forecast
    forecast_mensual = get_forecast_from_sheet()
    
    # 5. Calcular CxC ya en Skualo por mes (para no duplicar)
    cxc_skualo_por_mes = defaultdict(float)
    for p in skualo_data['proyeccion']:
        fecha = datetime.strptime(p['fecha'], '%Y-%m-%d')
        cxc_skualo_por_mes[fecha.month] += p['entradas']['total']
    
    # 6. Calcular forecast adicional (no en CxC)
    forecast_adicional = {}
    for mes, forecast in forecast_mensual.items():
        cxc_mes = cxc_skualo_por_mes.get(mes, 0)
        adicional = max(0, forecast - cxc_mes)
        if adicional > 0:
            forecast_adicional[mes] = adicional
            print(f"   Mes {mes}: Forecast ${forecast/1000000:.0f}M - CxC ${cxc_mes/1000000:.0f}M = Adicional ${adicional/1000000:.0f}M")
    
    # 7. Construir mapas de Skualo
    cxc_por_fecha = {}
    cxp_por_fecha = {}
    rec_por_fecha = {}
    
    for p in skualo_data['proyeccion']:
        fecha = p['fecha']
        cxc_por_fecha[fecha] = p['entradas']['total']
        cxp_por_fecha[fecha] = p['salidas'].get('cxp', 0)
        rec_por_fecha[fecha] = p['salidas'].get('recurrentes', 0)
    
    # 8. Distribuir forecast adicional en cada mes
    forecast_diario = {}
    for mes, monto in forecast_adicional.items():
        dias_mes = 31 if mes in [1, 3, 5, 7, 8, 10, 12] else 30 if mes != 2 else 28
        monto_diario = monto / 18  # Distribuir en días 10-28
        for dia in range(10, min(29, dias_mes + 1)):
            fecha_str = f"2026-{mes:02d}-{dia:02d}"
            forecast_diario[fecha_str] = forecast_diario.get(fecha_str, 0) + monto_diario
    
    # 9. Generar proyección
    fecha_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    proyeccion = []
    saldo = saldo_inicial
    dias_alerta = 0
    
    for i in range(horizonte):
        fecha = fecha_inicio + timedelta(days=i)
        fecha_str = fecha.strftime('%Y-%m-%d')
        dia_semana = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'][fecha.weekday()]
        
        # Entradas
        entradas_cxc = cxc_por_fecha.get(fecha_str, 0)
        entradas_forecast = forecast_diario.get(fecha_str, 0)
        total_entradas = entradas_cxc + entradas_forecast
        
        # Salidas
        salidas_cxp = cxp_por_fecha.get(fecha_str, 0)
        salidas_rec = rec_por_fecha.get(fecha_str, 0)
        total_salidas = salidas_cxp + salidas_rec
        
        # Flujo
        flujo_neto = total_entradas - total_salidas
        saldo += flujo_neto
        
        alerta = saldo < 50000000
        if alerta:
            dias_alerta += 1
        
        proyeccion.append({
            'fecha': fecha_str,
            'dia': dia_semana,
            'entradas': round(total_entradas),
            'entradas_cxc': round(entradas_cxc),
            'entradas_forecast': round(entradas_forecast),
            'salidas': round(total_salidas),
            'neto': round(flujo_neto),
            'saldo': round(saldo),
            'alerta': alerta
        })
    
    # 10. Calcular resumen
    total_entradas = sum(p['entradas'] for p in proyeccion)
    total_salidas = sum(p['salidas'] for p in proyeccion)
    saldo_min = min(p['saldo'] for p in proyeccion)
    saldo_final = proyeccion[-1]['saldo']
    
    # 11. Armar output
    output = {
        'generado': datetime.now().isoformat(),
        'horizonte_dias': horizonte,
        'saldo_inicial': saldo_inicial,
        'config': config,
        'forecast_mensual': {k: v for k, v in forecast_mensual.items()},
        'proyeccion': proyeccion,
        'resumen': {
            'total_entradas': total_entradas,
            'total_salidas': total_salidas,
            'saldo_final': saldo_final,
            'saldo_minimo': saldo_min,
            'dias_alerta': dias_alerta,
            'fuentes': ['Fintoc', 'Skualo CxC', 'Skualo CxP', 'Dashboard Facturación', 'Config Recurrentes']
        }
    }
    
    # 12. Guardar
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print("RESUMEN PROYECCIÓN CASH FLOW")
    print("=" * 60)
    print(f"Saldo inicial:    ${saldo_inicial/1000000:>10.0f}M")
    print(f"Entradas {horizonte}d:    ${total_entradas/1000000:>10.0f}M")
    print(f"Salidas {horizonte}d:     ${total_salidas/1000000:>10.0f}M")
    print(f"Saldo final:      ${saldo_final/1000000:>10.0f}M")
    print(f"Saldo mínimo:     ${saldo_min/1000000:>10.0f}M")
    print(f"Días en alerta:   {dias_alerta:>10}")
    print("=" * 60)
    print(f"✅ Archivo guardado: {OUTPUT_PATH}")
    
    return output

if __name__ == '__main__':
    generate_cashflow()

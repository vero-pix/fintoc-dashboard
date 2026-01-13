#!/usr/bin/env python3
"""
Cash Flow Generator v3 - CathPro
================================
Integra 3 capas:
  1. Fintoc (saldo bancario actual)
  2. Google Sheet Forecast (Compromiso > Forecast)
  3. Config Recurrentes

Lógica de ingresos:
  - Q1 (Ene-Feb-Mar): SOLO Compromiso
  - Q2-Q4 (Abr-Dic): Compromiso si existe, sino Forecast

Lógica de fechas:
  - Si pago cae Sábado/Domingo → mover a Viernes anterior
"""

import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

# ============================================
# CONFIGURACIÓN
# ============================================
FORECAST_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSCnSKEn66rdSM8T1R-lWIi79kzK1I2kDnS2ms7viozTdOW9tV5Gt7FBXRB-aErK-nhMFMU4C00Wbg7/pub?output=xlsx"
CONFIG_PATH = Path(__file__).parent / "cashflow_config.json"
OUTPUT_JSON = Path(__file__).parent / "cashflow_data_v3.json"
OUTPUT_FORECAST = Path(__file__).parent / "forecast_2026.json"

MESES_SOLO_COMPROMISO = ['Enero', 'Febrero', 'Marzo']
HORIZONTE_DIAS = 90
AÑO_FORECAST = 2026


# ============================================
# UTILIDADES
# ============================================
def parse_clp(val):
    """Parsear valores CLP desde el Sheet"""
    if pd.isna(val) or val == '' or val == '$0':
        return 0
    if isinstance(val, (int, float)):
        return float(val)
    val = str(val).replace('$', '').replace(',', '')
    try:
        return float(val)
    except:
        return 0


def ajustar_fin_semana(fecha):
    """Si cae Sáb/Dom, mover al Viernes anterior"""
    dia_semana = fecha.weekday()
    if dia_semana == 5:  # Sábado
        return fecha - timedelta(days=1)
    elif dia_semana == 6:  # Domingo
        return fecha - timedelta(days=2)
    return fecha


# ============================================
# OBTENER SALDO FINTOC
# ============================================
def get_fintoc_balance():
    """Obtener saldo actual desde Fintoc"""
    try:
        from fintoc_client import FintocClient
        client = FintocClient()
        balances = client.get_all_balances()
        total_clp = sum(b['disponible'] for b in balances if b['moneda'] == 'CLP')
        print(f"✅ Fintoc: ${total_clp:,.0f} CLP")
        return total_clp
    except Exception as e:
        print(f"⚠️  Error Fintoc: {e}")
        return 160000000  # Fallback


# ============================================
# OBTENER FORECAST GOOGLE SHEET
# ============================================
def get_forecast_from_sheet():
    """
    Descarga el Sheet y aplica lógica:
    - Q1: Solo Compromiso
    - Q2-Q4: Compromiso > Forecast
    """
    print("📊 Descargando Forecast...")
    
    try:
        response = requests.get(FORECAST_URL, timeout=60)
        response.raise_for_status()
        df = pd.read_excel(BytesIO(response.content))
    except Exception as e:
        print(f"❌ Error descargando Sheet: {e}")
        return None
    
    # Filtrar año
    df_año = df[df['Año'] == AÑO_FORECAST].copy()
    if df_año.empty:
        print(f"⚠️  No hay datos para {AÑO_FORECAST}")
        return None
    
    # Parsear montos
    df_año['Forecast'] = df_año['Forecast'].apply(parse_clp)
    df_año['Compromiso'] = df_año['Compromiso'].apply(parse_clp)
    
    # Aplicar lógica por fila
    def calcular_usar(row):
        if row['Mes'] in MESES_SOLO_COMPROMISO:
            return row['Compromiso']
        else:
            return row['Compromiso'] if row['Compromiso'] > 0 else row['Forecast']
    
    df_año['Usar'] = df_año.apply(calcular_usar, axis=1)
    
    # Agrupar por mes
    meses_orden = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                   'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    mes_num = {m: i+1 for i, m in enumerate(meses_orden)}
    
    resultado = {}
    total = 0
    
    print(f"\n{'Mes':<12} {'Compromiso':>12} {'Forecast':>12} {'USAR':>12}")
    print("-" * 50)
    
    for mes in meses_orden:
        df_mes = df_año[df_año['Mes'] == mes]
        c = df_mes['Compromiso'].sum()
        f = df_mes['Forecast'].sum()
        u = df_mes['Usar'].sum()
        total += u
        
        regla = "Solo C" if mes in MESES_SOLO_COMPROMISO else "C>F"
        print(f"{mes:<12} ${c/1e6:>9.1f}M ${f/1e6:>9.1f}M ${u/1e6:>9.1f}M [{regla}]")
        
        resultado[mes_num[mes]] = {
            'nombre': mes,
            'compromiso': round(c),
            'forecast': round(f),
            'usar': round(u),
            'regla': regla
        }
    
    print("-" * 50)
    print(f"{'TOTAL':<12} ${total/1e6:>35.1f}M")
    
    return resultado


# ============================================
# CARGAR CONFIGURACIÓN (RECURRENTES + DÍAS PAGO)
# ============================================
def load_config():
    """Cargar configuración de pagos recurrentes y días de pago"""
    try:
        with open(CONFIG_PATH, 'r') as f:
            config = json.load(f)
        total_rec = sum(r['monto'] for r in config.get('recurrentes', []))
        print(f"✅ Config: {len(config.get('recurrentes', []))} recurrentes (${total_rec/1e6:.0f}M/mes)")
        return config
    except FileNotFoundError:
        print("⚠️  cashflow_config.json no encontrado, usando defaults")
        return {
            'recurrentes': [
                {'dia': 5, 'concepto': 'ARRIENDO OFICINA', 'monto': 1800000},
                {'dia': 5, 'concepto': 'Leasing BCI1', 'monto': 3200000},
                {'dia': 7, 'concepto': 'PREVIRED', 'monto': 32000000},
                {'dia': 10, 'concepto': 'Leasing Oficina', 'monto': 1229177},
                {'dia': 15, 'concepto': 'LEASING BCI', 'monto': 3200000},
                {'dia': 15, 'concepto': 'Leaseback', 'monto': 1800000},
                {'dia': 16, 'concepto': 'SII - IVA', 'monto': 115000000},
                {'dia': 27, 'concepto': 'REMUNERACIONES', 'monto': 105000000},
            ],
            'dias_pago': {}
        }


# ============================================
# GENERAR PROYECCIÓN
# ============================================
def generate_cashflow():
    """Generar proyección de cash flow a 90 días"""
    
    print("=" * 60)
    print("GENERANDO CASH FLOW v3")
    print("=" * 60)
    
    # 1. Obtener datos
    saldo_inicial = get_fintoc_balance()
    forecast = get_forecast_from_sheet()
    config = load_config()
    
    if not forecast:
        print("❌ No se pudo obtener forecast")
        return None
    
    # 2. Guardar forecast JSON
    forecast_output = {
        'generado': datetime.now().isoformat(),
        'año': AÑO_FORECAST,
        'logica': 'Q1: Solo Compromiso | Q2-Q4: Compromiso > Forecast',
        'por_mes': forecast,
        'total': sum(m['usar'] for m in forecast.values())
    }
    
    with open(OUTPUT_FORECAST, 'w') as f:
        json.dump(forecast_output, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Guardado: {OUTPUT_FORECAST}")
    
    # 3. Distribuir forecast por día (días 10-28 de cada mes)
    forecast_diario = {}
    for mes_num, data in forecast.items():
        if data['usar'] > 0:
            monto_diario = data['usar'] / 18  # 18 días hábiles aprox
            for dia in range(10, 29):
                try:
                    fecha = datetime(AÑO_FORECAST, mes_num, dia)
                    fecha = ajustar_fin_semana(fecha)
                    fecha_str = fecha.strftime('%Y-%m-%d')
                    forecast_diario[fecha_str] = forecast_diario.get(fecha_str, 0) + monto_diario
                except ValueError:
                    continue  # Día inválido para el mes
    
    # 4. Generar proyección día a día
    fecha_inicio = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    proyeccion = []
    saldo = saldo_inicial
    recurrentes = config.get('recurrentes', [])
    
    print(f"\n📅 Proyección {HORIZONTE_DIAS} días desde {fecha_inicio.strftime('%Y-%m-%d')}")
    
    for i in range(HORIZONTE_DIAS):
        fecha = fecha_inicio + timedelta(days=i)
        fecha_str = fecha.strftime('%Y-%m-%d')
        dia_mes = fecha.day
        dia_semana = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'][fecha.weekday()]
        
        # Entradas (forecast distribuido)
        entradas = round(forecast_diario.get(fecha_str, 0))
        
        # Salidas (recurrentes)
        salidas = 0
        for r in recurrentes:
            if r['dia'] == dia_mes:
                salidas += r['monto']
        
        # Flujo
        neto = entradas - salidas
        saldo += neto
        
        proyeccion.append({
            'fecha': fecha_str,
            'dia': dia_semana,
            'entradas': entradas,
            'salidas': round(salidas),
            'neto': round(neto),
            'saldo': round(saldo),
            'alerta': saldo < 50000000
        })
    
    # 5. Calcular resumen
    total_entradas = sum(p['entradas'] for p in proyeccion)
    total_salidas = sum(p['salidas'] for p in proyeccion)
    saldo_min = min(p['saldo'] for p in proyeccion)
    saldo_final = proyeccion[-1]['saldo']
    dias_alerta = sum(1 for p in proyeccion if p['alerta'])
    
    # 6. Guardar JSON principal
    output = {
        'generado': datetime.now().isoformat(),
        'version': 'v3',
        'horizonte_dias': HORIZONTE_DIAS,
        'saldo_inicial': saldo_inicial,
        'proyeccion': proyeccion,
        'resumen': {
            'total_entradas': total_entradas,
            'total_salidas': total_salidas,
            'saldo_final': saldo_final,
            'saldo_minimo': saldo_min,
            'dias_alerta': dias_alerta
        },
        'fuentes': [
            'Fintoc (saldo)',
            'Google Sheet (Compromiso > Forecast)',
            'Config (recurrentes)'
        ]
    }
    
    with open(OUTPUT_JSON, 'w') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    # 7. Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(f"Saldo inicial:  ${saldo_inicial/1e6:>10.0f}M")
    print(f"Entradas:       ${total_entradas/1e6:>10.0f}M")
    print(f"Salidas:        ${total_salidas/1e6:>10.0f}M")
    print(f"Saldo final:    ${saldo_final/1e6:>10.0f}M")
    print(f"Saldo mínimo:   ${saldo_min/1e6:>10.0f}M")
    print(f"Días alerta:    {dias_alerta:>10}")
    print("=" * 60)
    print(f"✅ Guardado: {OUTPUT_JSON}")
    
    return output


# ============================================
# MAIN
# ============================================
if __name__ == '__main__':
    generate_cashflow()

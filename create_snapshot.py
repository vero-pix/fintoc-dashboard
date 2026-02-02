import json
import os
from datetime import datetime, date
import pytz
from fintoc_client import FintocClient
from skualo_client import SkualoClient
from skualo_bancos import SkualoBancosClient
from skualo_documentos import SkualoDocumentosClient
import requests
import pandas as pd
from io import BytesIO

# Configuración
TZ_CHILE = pytz.timezone('America/Santiago')
FORECAST_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSCnSKEn66rdSM8T1R-lWIi79kzK1I2kDnS2ms7viozTdOW9tV5Gt7FBXRB-aErK-nhMFMU4C00Wbg7/pub?output=xlsx"

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

class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)

def get_snapshot():
    print("🚀 Iniciando captura de datos para Snapshot Local...")
    snapshot = {
        "timestamp": datetime.now(TZ_CHILE).isoformat(),
        "data": {}
    }

    # 1. Fintoc - Todos los bancos (Intentamos CLP + USD + EUR)
    try:
        print("  → Capturando Fintoc (Todos los bancos)...")
        fintoc = FintocClient()
        snapshot["data"]["fintoc_balances"] = fintoc.get_all_balances()
    except Exception as e:
        print(f"  ❌ Error Fintoc: {e}")
        snapshot["data"]["fintoc_balances"] = {}

    # 2. Skualo - Saldos Generales e Inversiones
    try:
        print("  → Capturando Skualo (Balances y Fondos)...")
        skualo = SkualoClient()
        snapshot["data"]["skualo_balances"] = skualo.get_saldos_cuentas()
    except Exception as e:
        print(f"  ❌ Error Skualo Balances: {e}")
        snapshot["data"]["skualo_balances"] = {}

    # 3. Skualo - Pipeline de Documentos
    try:
        print("  → Capturando Skualo (Pipeline de Documentos)...")
        doc_client = SkualoDocumentosClient()
        snapshot["data"]["pipeline"] = doc_client.get_resumen_pipeline()
    except Exception as e:
        print(f"  ❌ Error Skualo Pipeline: {e}")
        snapshot["data"]["pipeline"] = {}

    # 3.5 Skualo - Libro Diario (Ingresos y Costos Reales)
    try:
        print("  → Capturando Skualo (Libro Diario - Real)...")
        sk_auth = SkualoClient() 
        url = f"https://api.skualo.cl/76243957-3/contabilidad/reportes/librodiario?desde=2026-01-01&hasta=2026-12-31&IdSucursal=0"
        headers = sk_auth.headers
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            libro = resp.json()
            real_data = {}
            proy_real_ene = {}
            for d in libro:
                id_cuenta = str(d.get("IDCuenta", ""))
                id_proy = str(d.get("IDProyecto", ""))
                monto_haber = d.get("MontoHaber", 0)
                monto_debe = d.get("MontoDebe", 0)
                fecha_str = d.get("Fecha", "")
                if not fecha_str: continue
                mes_num = int(fecha_str[5:7])
                mes_nombre = {1:"Enero", 2:"Febrero", 3:"Marzo"}.get(mes_num, "Otro")
                
                if (mes_nombre != "Otro"):
                    if mes_nombre not in real_data:
                        real_data[mes_nombre] = {"ing_real": 0, "cos_real": 0}
                    
                    # Ingresos: Cuenta 4101001
                    if id_cuenta == "4101001":
                        real_data[mes_nombre]["ing_real"] += monto_haber
                        # Desglose por proyecto para Enero
                        if mes_nombre == "Enero":
                            proy_real_ene[id_proy] = proy_real_ene.get(id_proy, 0) + monto_haber
                    
                    # Costos: Prefix 5
                    if id_cuenta.startswith("5"):
                        real_data[mes_nombre]["cos_real"] += monto_debe
            
            snapshot["data"]["contabilidad_real"] = real_data
            snapshot["data"]["proyectos_real_ene"] = proy_real_ene
        else:
            snapshot["data"]["contabilidad_real"] = {}
    except Exception as e:
        print(f"  ❌ Error Skualo Real: {e}")
        snapshot["data"]["contabilidad_real"] = {}

    # 4. Google Sheets - Forecast 2026 (Detalle por Proyecto para Desviaciones)
    try:
        print("  → Capturando Google Sheets (Detalle Proyectos)...")
        response = requests.get(FORECAST_URL, timeout=30)
        df = pd.read_excel(BytesIO(response.content))
        df_ene = df[(df['Año'] == 2026) & (df['Mes'] == 'Enero')].copy()
        
        df_ene['Presupuesto'] = df_ene['Presupuesto 2026'].apply(parse_clp)
        df_ene['Forecast'] = df_ene['Forecast del mes\n(Se modifica del día 3 de cada mes)'].apply(parse_clp)
        
        # Agrupar por Faena para el reporte de desviaciones
        proy_forecast = {}
        for _, row in df_ene.iterrows():
            faena = str(row['Faena'])
            proy_forecast[faena] = {
                "ppto": float(row['Presupuesto']),
                "fcst": float(row['Forecast'])
            }
        snapshot["data"]["proyectos_forecast_ene"] = proy_forecast
        
        # Resumen mensual (mantener lógica anterior)
        df_año = df[df['Año'] == 2026].copy()
        df_año['Presupuesto'] = df_año['Presupuesto 2026'].apply(parse_clp)
        df_año['Apalancado'] = df_año['Compromiso Inicio Mes'].apply(parse_clp)
        df_año['Forecast_D'] = df_año['Forecast del mes\n(Se modifica del día 3 de cada mes)'].apply(parse_clp)
        
        meses_orden = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                      'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        
        forecast_data = []
        for mes in meses_orden:
            df_mes = df_año[df_año['Mes'] == mes]
            p = df_mes['Presupuesto'].sum()
            a = df_mes['Apalancado'].sum()
            f = df_mes['Forecast_D'].sum()
            forecast_data.append({
                'mes': mes,
                'presupuesto': float(p),
                'apalancado': float(a),
                'forecast': float(f)
            })
        snapshot["data"]["forecast"] = forecast_data
    except Exception as e:
        print(f"  ❌ Error Forecast: {e}")
        snapshot["data"]["forecast"] = []

    # 4.5 Mapeo de Proyectos Skualo (para cruzar con Real)
    try:
        print("  → Obteniendo Mapeo de Proyectos Skualo...")
        sk_auth = SkualoClient()
        url_proy = "https://api.skualo.cl/76243957-3/tablas/proyectos?PageSize=500"
        resp_p = requests.get(url_proy, headers=sk_auth.headers)
        proy_map = {}
        if resp_p.status_code == 200:
            items = resp_p.json().get("items", [])
            for p in items:
                # Intentar extraer el nombre de la faena del nombre del proyecto
                # El nombre suele ser "14430 CMDIC..." -> Queremos "CMDIC"
                nombre = p.get("nombre", "")
                parts = nombre.split(" ")
                faena_key = parts[1] if len(parts) > 1 else nombre
                proy_map[str(p.get("id"))] = faena_key
        snapshot["data"]["proyectos_map"] = proy_map
    except:
        snapshot["data"]["proyectos_map"] = {}

    # 5. Histórico local (para variaciones)
    try:
        if os.path.exists('saldos_historicos.json'):
            with open('saldos_historicos.json', 'r') as f:
                snapshot["data"]["historico"] = json.load(f)
    except:
        snapshot["data"]["historico"] = {}

    # Guardar a archivo
    snapshot["logs"] = {
        "fintoc": "OK" if snapshot["data"].get("fintoc_balances") else "FALLO O VACIO",
        "skualo": "OK" if snapshot["data"].get("skualo_balances") else "FALLO O VACIO",
        "errors": []
    }
    
    with open('data_snapshot.json', 'w', encoding='utf-8') as f:
        json.dump(snapshot, f, indent=2, ensure_ascii=False, cls=DateTimeEncoder)
    
    print("\n✅ Snapshot completado: 'data_snapshot.json'")
    print("Ahora puedes usar este archivo para trabajar localmente sin llamar a las APIs.")

if __name__ == "__main__":
    get_snapshot()

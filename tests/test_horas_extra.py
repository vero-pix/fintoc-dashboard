#!/usr/bin/env python3
"""
Script para comparar horas extra Enero 2025 vs Enero 2026
Usando API Skualo - Endpoint de Remuneraciones/Nómina
"""
import requests
import os
from dotenv import load_dotenv
import json

load_dotenv()

# Configuración
TOKEN = os.getenv("SKUALO_TOKEN")
BASE_URL = "https://api.skualo.cl/76243957-3"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "accept": "application/json"
}

def explorar_endpoints():
    """Explora endpoints disponibles de RRHH/Remuneraciones"""
    
    endpoints_posibles = [
        # Remuneraciones
        "/remuneraciones/liquidaciones",
        "/remuneraciones/liquidaciones/202501",
        "/remuneraciones/liquidaciones/202601",
        "/remuneraciones/conceptos",
        "/remuneraciones/haberes",
        "/remuneraciones/descuentos",
        # RRHH
        "/rrhh/empleados",
        "/rrhh/trabajadores",
        "/rrhh/personal",
        # Nómina
        "/nomina/liquidaciones",
        "/nomina/202501",
        "/nomina/202601",
        # Libro de remuneraciones
        "/contabilidad/reportes/libroremuneraciones/202501",
        "/contabilidad/reportes/libroremuneraciones/202601",
        # Centros de costo
        "/remuneraciones/centroscosto",
    ]
    
    print("=" * 70)
    print("EXPLORANDO ENDPOINTS SKUALO - RRHH/REMUNERACIONES")
    print("=" * 70)
    
    resultados = []
    
    for endpoint in endpoints_posibles:
        url = f"{BASE_URL}{endpoint}"
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            status = response.status_code
            
            if status == 200:
                data = response.json()
                if isinstance(data, list):
                    info = f"✅ {len(data)} registros"
                elif isinstance(data, dict):
                    info = f"✅ {list(data.keys())[:3]}..."
                else:
                    info = f"✅ {type(data)}"
                resultados.append((endpoint, status, info, data))
            else:
                info = f"❌ {status}"
                resultados.append((endpoint, status, info, None))
                
            print(f"{endpoint}: {info}")
            
        except Exception as e:
            print(f"{endpoint}: ❌ Error - {str(e)[:50]}")
    
    return resultados


def get_libro_remuneraciones(periodo):
    """Obtiene libro de remuneraciones para un periodo YYYYMM"""
    url = f"{BASE_URL}/contabilidad/reportes/libroremuneraciones/{periodo}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error {response.status_code}: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def analizar_horas_extra(data, periodo):
    """Analiza horas extra de los datos de remuneraciones"""
    if not data:
        print(f"Sin datos para {periodo}")
        return None
    
    print(f"\n--- Análisis {periodo} ---")
    print(f"Total registros: {len(data)}")
    
    # Mostrar estructura del primer registro
    if data and len(data) > 0:
        print(f"Campos disponibles: {list(data[0].keys())}")
        print(f"Ejemplo: {json.dumps(data[0], indent=2, default=str)[:500]}")
    
    return data


if __name__ == "__main__":
    # Primero explorar qué endpoints existen
    resultados = explorar_endpoints()
    
    # Si encontramos el endpoint de libro de remuneraciones, analizar
    print("\n" + "=" * 70)
    print("COMPARATIVO HORAS EXTRA ENERO 2025 vs ENERO 2026")
    print("=" * 70)
    
    # Intentar obtener datos
    data_2025 = get_libro_remuneraciones("202501")
    data_2026 = get_libro_remuneraciones("202601")
    
    if data_2025:
        analizar_horas_extra(data_2025, "Enero 2025")
    
    if data_2026:
        analizar_horas_extra(data_2026, "Enero 2026")

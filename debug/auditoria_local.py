import json
import os
from datetime import datetime, date, timedelta
# from skualo_cashflow import SkualoCashFlow

def auditoria_local():
    SNAPSHOT_FILE = "data_snapshot.json"
    
    if not os.path.exists(SNAPSHOT_FILE):
        print("❌ No se encontró data_snapshot.json. Ejecuta 'python3 create_snapshot.py' primero.")
        return

    with open(SNAPSHOT_FILE, 'r', encoding='utf-8') as f:
        snapshot = json.load(f)

    data = snapshot.get("data", {})
    pipeline = data.get("pipeline", {})
    cashflow = data.get("cashflow", {})
    
    print("\n" + "="*60)
    print("🔍 AUDITORÍA DE CONCILIACIÓN LOCAL - CATHPRO")
    print("="*60)
    
    # 1. POSICIÓN DE CAJA INICIAL
    clp_total = data.get("fintoc_balances", {}).get("clp", {}).get("total", 0)
    ffmm = data.get("skualo_balances", {}).get("fondos_mutuos", 0)
    total_liquidez = clp_total + ffmm
    
    print(f"\n💰 LIQUIDEZ INICIAL:")
    print(f"   - Bancos (CLP):   ${clp_total:,.0f}")
    print(f"   - Fondos Mutuos:  ${ffmm:,.0f}")
    print(f"   - TOTAL DISP:     ${total_liquidez:,.0f}")

    # 2. ANÁLISIS DEL PIPELINE DE EGRESOS (Lo que el usuario ve en naranja)
    print(f"\n💸 COMPROMISOS DETECTADOS (45 DÍAS):")
    egresos = pipeline.get("egresos", {})
    total_egresos = 0
    
    for cat in ["soli", "oc", "face"]:
        monto = egresos.get(cat, {}).get("monto_total", 0)
        cantidad = egresos.get(cat, {}).get("cantidad", 0)
        total_egresos += monto
        print(f"   - {cat.upper():<5}: {cantidad:>3} docs | ${monto:,.0f}")
    
    # OCX (Internacional) - Aproximación simple CLP
    ocx_usd = egresos.get("ocx", {}).get("monto_total_usd", 0)
    total_egresos += (ocx_usd * 950) # Tasa aprox para auditoría
    print(f"   - OCX  :  USD {ocx_usd:,.2f} (~${ocx_usd*950:,.0f} CLP)")
    print(f"   - TOTAL EGRESOS:  ${total_egresos:,.0f}")

    # 3. ANÁLISIS DEL FORECAST GAP (Lo proyectado)
    print(f"\n📈 INYECCIÓN DE FORECAST (GAPS):")
    # Buscamos en el cashflow ejemplos de la inyección
    hoy = datetime.now()
    meses_detectados = {}
    
    for fecha, info in cashflow.items():
        for entrada in info.get("detalle_entradas", []):
            if "PROYECCIÓN FORECAST" in entrada.get("cliente", ""):
                mes = entrada["cliente"].split("(")[1].replace(")", "")
                if mes not in meses_detectados:
                    meses_detectados[mes] = 0
                meses_detectados[mes] += entrada["monto"]

    for mes, total_inyectado in meses_detectados.items():
        print(f"   - {mes:<10}: Inyectado ${total_inyectado:,.0f} (repartido en viernes)")

    print("\n" + "="*60)
    print("📝 CONCLUSIÓN PARA CONCILIACIÓN:")
    print(f"Si los números 'no cierran', revisa si:")
    print(f"1. La Meta en GSheets para Marzo es correcta (El sistema inyecta ${meses_detectados.get('Marzo', 0):,.0f})")
    print(f"2. Faltan OCs antiguas (más de 45 días) que Skualo no está enviando.")
    print(f"3. Los Fondos Mutuos (${ffmm:,.0f}) están sumando a tu 'Saldo Inicial' en el tablero.")
    print("="*60 + "\n")

if __name__ == "__main__":
    auditoria_local()

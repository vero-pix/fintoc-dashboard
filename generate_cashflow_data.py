"""
Generador de datos para artefacto Cash Flow Interactivo
Combina: Fintoc (saldo real) + Skualo (CxC, CxP) + Config (días pago, recurrentes)
"""

import json
import os
from datetime import datetime, timedelta
from skualo_cashflow import SkualoCashFlow
from fintoc_client import FintocClient

def generate_cashflow_data(horizonte_dias=90):
    """Genera JSON completo para el artefacto interactivo"""
    
    print("\n" + "="*60)
    print("GENERANDO DATA PARA CASH FLOW INTERACTIVO")
    print("="*60)
    
    # 1. Obtener saldo inicial desde Fintoc
    print("\n📊 Obteniendo saldo inicial desde Fintoc...")
    try:
        fintoc = FintocClient()
        saldos_fintoc = fintoc.get_all_balances()
        saldo_inicial = saldos_fintoc.get("total_clp", 0)
        print(f"   Saldo CLP: ${saldo_inicial:,.0f}")
    except Exception as e:
        print(f"   ⚠️ Error Fintoc: {e}")
        saldo_inicial = 160000000  # Fallback
    
    # 2. Cargar motor de cash flow
    print("\n📊 Cargando motor de cash flow...")
    cf = SkualoCashFlow()
    
    # 3. Obtener CxC detallada
    print("\n📊 Obteniendo CxC...")
    cxc = cf.get_cxc_detalle(con_fecha_comprobante=False)
    print(f"   {len(cxc)} documentos pendientes")
    
    # 4. Obtener CxP detallada
    print("\n📊 Obteniendo CxP...")
    cxp = cf.get_cxp_detalle("todas")
    print(f"   {len(cxp)} documentos pendientes")
    
    # 5. Generar proyección diaria
    print(f"\n📊 Generando proyección {horizonte_dias} días...")
    hoy = datetime.now().date()
    
    proyeccion = []
    saldo_acumulado = saldo_inicial
    
    for i in range(horizonte_dias):
        fecha = hoy + timedelta(days=i)
        dia_mes = fecha.day
        
        # Entradas: CxC con fecha de cobro esperada = esta fecha
        entradas_dia = []
        for doc in cxc:
            fecha_cobro = doc.get("fecha_cobro_esperada")
            if fecha_cobro and fecha_cobro == fecha:
                entradas_dia.append({
                    "cliente": doc["cliente"],
                    "documento": doc["documento"],
                    "monto": doc["saldo"],
                    "dias_config": doc["dias_pago_config"]
                })
        
        # Salidas CxP: vencimiento = esta fecha
        salidas_cxp = []
        for doc in cxp:
            venc = doc.get("vencimiento")
            if venc and venc == fecha:
                salidas_cxp.append({
                    "proveedor": doc["proveedor"],
                    "documento": doc["documento"],
                    "monto": doc["saldo"],
                    "origen": doc["origen"]
                })
        
        # Salidas recurrentes
        salidas_recurrentes = []
        for r in cf.config.get("recurrentes", []):
            if r["dia"] == dia_mes:
                salidas_recurrentes.append({
                    "concepto": r["concepto"],
                    "monto": r["monto"]
                })
        
        # Totales del día
        total_entradas = sum(e["monto"] for e in entradas_dia)
        total_salidas_cxp = sum(s["monto"] for s in salidas_cxp)
        total_salidas_rec = sum(s["monto"] for s in salidas_recurrentes)
        total_salidas = total_salidas_cxp + total_salidas_rec
        flujo_neto = total_entradas - total_salidas
        
        saldo_acumulado += flujo_neto
        
        proyeccion.append({
            "fecha": fecha.isoformat(),
            "dia_semana": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"][fecha.weekday()],
            "entradas": {
                "total": total_entradas,
                "detalle": entradas_dia
            },
            "salidas": {
                "total": total_salidas,
                "cxp": total_salidas_cxp,
                "recurrentes": total_salidas_rec,
                "detalle_cxp": salidas_cxp,
                "detalle_recurrentes": salidas_recurrentes
            },
            "flujo_neto": flujo_neto,
            "saldo_proyectado": saldo_acumulado,
            "alerta": saldo_acumulado < 50000000
        })
    
    # 6. Calcular aging
    print("\n📊 Calculando aging...")
    aging_cxc = cf.get_cxc_aging()
    aging_cxp = cf.get_cxp_aging("todas")
    
    # 7. Construir output
    output = {
        "generado": datetime.now().isoformat(),
        "horizonte_dias": horizonte_dias,
        "saldo_inicial": saldo_inicial,
        "config": cf.config,
        "proyeccion": proyeccion,
        "aging": {
            "cxc": aging_cxc,
            "cxp": aging_cxp
        },
        "resumen": {
            "total_entradas": sum(p["entradas"]["total"] for p in proyeccion),
            "total_salidas": sum(p["salidas"]["total"] for p in proyeccion),
            "saldo_final": proyeccion[-1]["saldo_proyectado"] if proyeccion else saldo_inicial,
            "saldo_minimo": min(p["saldo_proyectado"] for p in proyeccion) if proyeccion else saldo_inicial,
            "dias_alerta": sum(1 for p in proyeccion if p["alerta"]),
            "total_cxc": aging_cxc["total"],
            "total_cxp": aging_cxp["total"]
        },
        "cxc_detalle": [
            {
                "cliente": doc["cliente"],
                "documento": doc["documento"],
                "emision": doc["emision"].isoformat() if doc["emision"] else None,
                "fecha_cobro": doc["fecha_cobro_esperada"].isoformat() if doc["fecha_cobro_esperada"] else None,
                "saldo": doc["saldo"],
                "dias_config": doc["dias_pago_config"]
            }
            for doc in cxc
        ],
        "cxp_detalle": [
            {
                "proveedor": doc["proveedor"],
                "documento": doc["documento"],
                "vencimiento": doc["vencimiento"].isoformat() if doc["vencimiento"] else None,
                "saldo": doc["saldo"],
                "origen": doc["origen"],
                "vencido": doc["vencido"]
            }
            for doc in cxp
        ]
    }
    
    # 8. Guardar
    output_path = os.path.join(os.path.dirname(__file__), "cashflow_data.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n✅ Data guardada en: {output_path}")
    print(f"   Saldo inicial: ${saldo_inicial:,.0f}")
    print(f"   Saldo final proyectado: ${output['resumen']['saldo_final']:,.0f}")
    print(f"   Días con alerta: {output['resumen']['dias_alerta']}")
    
    return output


if __name__ == "__main__":
    data = generate_cashflow_data(90)
    
    print("\n" + "="*60)
    print("RESUMEN EJECUTIVO")
    print("="*60)
    r = data["resumen"]
    print(f"\n💰 Total CxC:        ${r['total_cxc']:>15,.0f}")
    print(f"💸 Total CxP:        ${r['total_cxp']:>15,.0f}")
    print(f"📈 Entradas 90d:     ${r['total_entradas']:>15,.0f}")
    print(f"📉 Salidas 90d:      ${r['total_salidas']:>15,.0f}")
    print(f"🏦 Saldo inicial:    ${data['saldo_inicial']:>15,.0f}")
    print(f"🎯 Saldo final:      ${r['saldo_final']:>15,.0f}")
    print(f"⚠️  Días en alerta:   {r['dias_alerta']}")

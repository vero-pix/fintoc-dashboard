"""
Generador de Cash Flow Dashboard
Integra Fintoc (saldo real) + Skualo (CxC/CxP) + Configuración
Genera JSON con datos para el dashboard HTML
"""

import json
import os
from datetime import datetime, timedelta
from fintoc_client import FintocClient
from skualo_cashflow import SkualoCashFlow


class CashFlowGenerator:
    def __init__(self):
        self.fintoc = FintocClient()
        self.skualo = SkualoCashFlow()
        self.hoy = datetime.now().date()
    
    def get_saldo_inicial(self):
        """Obtiene saldo bancario total en CLP desde Fintoc"""
        balances = self.fintoc.get_all_balances()
        
        total_clp = 0
        total_usd = 0
        total_eur = 0
        tipo_cambio_usd = 1000  # Aproximado, idealmente obtener de API
        tipo_cambio_eur = 1100
        
        detalle = []
        
        for b in balances:
            moneda = b["moneda"]
            disponible = b["disponible"]
            
            if moneda == "CLP":
                total_clp += disponible
            elif moneda == "USD":
                total_usd += disponible
            elif moneda == "EUR":
                total_eur += disponible
            
            detalle.append({
                "banco": b["banco"],
                "moneda": moneda,
                "disponible": disponible,
            })
        
        # Convertir todo a CLP para el saldo inicial
        total_clp_equiv = total_clp + (total_usd * tipo_cambio_usd) + (total_eur * tipo_cambio_eur)
        
        return {
            "total_clp": total_clp,
            "total_usd": total_usd,
            "total_eur": total_eur,
            "total_clp_equivalente": total_clp_equiv,
            "detalle": detalle,
            "fecha": self.hoy.isoformat(),
        }
    
    def generar_proyeccion_semanal(self):
        """Genera proyección semanal con saldo acumulado"""
        saldo_info = self.get_saldo_inicial()
        saldo_actual = saldo_info["total_clp"]  # Solo CLP para simplificar
        
        proyeccion_skualo = self.skualo.get_cashflow_proyectado(7)
        
        resultado = []
        saldo_running = saldo_actual
        
        for fecha, data in proyeccion_skualo.items():
            saldo_running = saldo_running + data["entradas"] - data["salidas_total"]
            
            resultado.append({
                "fecha": fecha.isoformat(),
                "fecha_display": fecha.strftime("%a %d-%b"),
                "entradas": data["entradas"],
                "salidas_cxp": data["salidas_cxp"],
                "salidas_recurrentes": data["salidas_recurrentes"],
                "salidas_total": data["salidas_total"],
                "neto_dia": data["neto"],
                "saldo_proyectado": saldo_running,
                "alerta_saldo_bajo": saldo_running < 50_000_000,
                "detalle_entradas": [
                    {"cliente": d["cliente"], "monto": d["monto"], "dias": d.get("dias_config", 0)}
                    for d in data["detalle_entradas"]
                ],
                "detalle_salidas": [
                    {"concepto": d["concepto"], "monto": d["monto"], "tipo": d.get("tipo", "cxp")}
                    for d in data["detalle_salidas"]
                ],
            })
        
        return resultado
    
    def generar_proyeccion_mensual(self):
        """Genera proyección mensual (4 semanas)"""
        saldo_info = self.get_saldo_inicial()
        saldo_actual = saldo_info["total_clp"]
        
        proyeccion_skualo = self.skualo.get_cashflow_proyectado(30)
        
        # Agrupar por semana
        semanas = {}
        for fecha, data in proyeccion_skualo.items():
            # Calcular número de semana
            dias_desde_hoy = (fecha - self.hoy).days
            num_semana = dias_desde_hoy // 7
            
            if num_semana not in semanas:
                semanas[num_semana] = {
                    "entradas": 0,
                    "salidas": 0,
                    "fecha_inicio": fecha,
                    "fecha_fin": fecha,
                }
            
            semanas[num_semana]["entradas"] += data["entradas"]
            semanas[num_semana]["salidas"] += data["salidas_total"]
            semanas[num_semana]["fecha_fin"] = fecha
        
        resultado = []
        saldo_running = saldo_actual
        
        for num, data in sorted(semanas.items()):
            neto = data["entradas"] - data["salidas"]
            saldo_running += neto
            
            resultado.append({
                "semana": num + 1,
                "periodo": f"{data['fecha_inicio'].strftime('%d-%b')} al {data['fecha_fin'].strftime('%d-%b')}",
                "entradas": data["entradas"],
                "salidas": data["salidas"],
                "neto": neto,
                "saldo_proyectado": saldo_running,
            })
        
        return resultado
    
    def generar_proyeccion_anual(self):
        """Genera proyección anual basada en recurrentes"""
        saldo_info = self.get_saldo_inicial()
        saldo_actual = saldo_info["total_clp"]
        
        config = self.skualo.config
        total_recurrentes_mes = sum(r["monto"] for r in config.get("recurrentes", []))
        
        # Estimación simple: ingresos promedio basado en CxC actual
        aging_cxc = self.skualo.get_cxc_aging()
        ingresos_estimados_mes = aging_cxc["total"] / 3  # Asumimos rotación de 3 meses
        
        resultado = []
        saldo_running = saldo_actual
        
        meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
        mes_actual = self.hoy.month - 1  # 0-indexed
        
        for i in range(12):
            mes_idx = (mes_actual + i) % 12
            
            # Mes actual usa proyección real, resto usa estimación
            if i == 0:
                proyeccion_mes = self.skualo.get_cashflow_proyectado(30)
                entradas = sum(d["entradas"] for d in proyeccion_mes.values())
                salidas = sum(d["salidas_total"] for d in proyeccion_mes.values())
            else:
                entradas = ingresos_estimados_mes
                salidas = total_recurrentes_mes
            
            neto = entradas - salidas
            saldo_running += neto
            
            resultado.append({
                "mes": meses[mes_idx],
                "entradas": entradas,
                "salidas": salidas,
                "neto": neto,
                "saldo_proyectado": saldo_running,
                "es_estimacion": i > 0,
            })
        
        return resultado
    
    def generar_aging(self):
        """Obtiene aging de CxC y CxP"""
        return {
            "cxc": self.skualo.get_cxc_aging(),
            "cxp": self.skualo.get_cxp_aging(),
        }
    
    def generar_resumen(self):
        """Genera resumen ejecutivo"""
        resumen = self.skualo.get_resumen_semana()
        saldo = self.get_saldo_inicial()
        
        return {
            "saldo_inicial": saldo["total_clp"],
            "total_entradas_semana": resumen["total_entradas"],
            "total_salidas_semana": resumen["total_salidas"],
            "flujo_neto_semana": resumen["flujo_neto"],
            "dia_critico": {
                "fecha": resumen["dia_critico"]["fecha"].isoformat(),
                "neto": resumen["dia_critico"]["neto"],
            },
            "alerta_pagos_altos": resumen["alerta_pagos_altos"],
        }
    
    def generar_todo(self):
        """Genera JSON completo para el dashboard"""
        print("📊 Generando datos para Cash Flow...")
        
        print("  → Obteniendo saldo inicial desde Fintoc...")
        saldo = self.get_saldo_inicial()
        
        print("  → Generando proyección semanal...")
        semanal = self.generar_proyeccion_semanal()
        
        print("  → Generando proyección mensual...")
        mensual = self.generar_proyeccion_mensual()
        
        print("  → Generando proyección anual...")
        anual = self.generar_proyeccion_anual()
        
        print("  → Calculando aging...")
        aging = self.generar_aging()
        
        print("  → Generando resumen...")
        resumen = self.generar_resumen()
        
        data = {
            "generado": datetime.now().isoformat(),
            "saldo_inicial": saldo,
            "resumen": resumen,
            "proyeccion_semanal": semanal,
            "proyeccion_mensual": mensual,
            "proyeccion_anual": anual,
            "aging": aging,
            "config": self.skualo.config,
        }
        
        # Guardar JSON
        output_path = os.path.join(os.path.dirname(__file__), "cashflow_data.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        
        print(f"\n✅ Datos guardados en: cashflow_data.json")
        print(f"   Saldo inicial: ${saldo['total_clp']:,.0f} CLP")
        
        return data


if __name__ == "__main__":
    generator = CashFlowGenerator()
    data = generator.generar_todo()
    
    print("\n" + "="*60)
    print("RESUMEN GENERADO")
    print("="*60)
    print(f"Saldo inicial:     ${data['saldo_inicial']['total_clp']:>15,.0f}")
    print(f"Entradas semana:   ${data['resumen']['total_entradas_semana']:>15,.0f}")
    print(f"Salidas semana:    ${data['resumen']['total_salidas_semana']:>15,.0f}")
    print(f"Flujo neto:        ${data['resumen']['flujo_neto_semana']:>15,.0f}")

"""
Motor de Cash Flow y Análisis de Cartera - V2
Usa configuración de días de pago por cliente y pagos recurrentes
"""

import requests
import os
import json
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict

load_dotenv()


class SkualoCashFlow:
    def __init__(self):
        self.token = os.getenv("SKUALO_TOKEN")
        self.base_url = "https://api.skualo.cl/76243957-3"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "accept": "application/json"
        }
        
        self.cuentas = {
            "cxc": "1107001",
            "cxp_nacional": "2110001",
            "cxp_internacional": "2110002",
        }
        
        self.hoy = datetime.now().date()
        
        # Cargar configuración
        self.config = self._cargar_config()

    def _cargar_config(self):
        """Carga configuración desde cashflow_config.json"""
        config_path = os.path.join(os.path.dirname(__file__), "cashflow_config.json")
        
        default_config = {
            "defaultDias": 20,
            "clientes": [],
            "recurrentes": []
        }
        
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                print(f"✅ Configuración cargada: {len(config.get('clientes', []))} clientes, {len(config.get('recurrentes', []))} recurrentes")
                return config
        except FileNotFoundError:
            print("⚠️ cashflow_config.json no encontrado, usando defaults")
            return default_config
        except json.JSONDecodeError:
            print("⚠️ Error en cashflow_config.json, usando defaults")
            return default_config

    def _get_dias_pago_cliente(self, nombre_cliente):
        """Obtiene días de pago configurados para un cliente"""
        nombre_upper = nombre_cliente.upper()
        
        for c in self.config.get("clientes", []):
            if c["nombre"].upper() in nombre_upper:
                return c["dias"]
        
        return self.config.get("defaultDias", 20)

    def _get_documentos(self, cuenta):
        """Extrae documentos pendientes de una cuenta contable"""
        url = f"{self.base_url}/contabilidad/reportes/analisisporcuenta/{cuenta}?soloPendientes=true"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"ERROR Skualo ({cuenta}): {e}")
            return []

    def _get_fecha_comprobante(self, num_comprobante):
        """Obtiene la fecha real de creación del comprobante"""
        url = f"{self.base_url}/contabilidad/comprobantes/{num_comprobante}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            creado_el = data.get("creadoEl")
            if creado_el:
                return self._parse_fecha(creado_el)
            return self._parse_fecha(data.get("fecha"))
        except:
            return None

    def _parse_fecha(self, fecha_str):
        """Convierte string ISO a date"""
        if not fecha_str:
            return None
        try:
            return datetime.fromisoformat(fecha_str.replace('Z', '+00:00')).date()
        except:
            try:
                return datetime.strptime(fecha_str[:10], "%Y-%m-%d").date()
            except:
                return None

    def _clasificar_aging(self, dias_vencido):
        """Clasifica en tramos de aging"""
        if dias_vencido <= 0:
            return "vigente"
        elif dias_vencido <= 30:
            return "1-30"
        elif dias_vencido <= 60:
            return "31-60"
        elif dias_vencido <= 90:
            return "61-90"
        else:
            return ">90"

    def _mover_a_viernes(self, fecha):
        """
        Si la fecha no es viernes, moverla al viernes más próximo.
        - Lunes a Jueves → siguiente viernes
        - Sábado/Domingo → viernes anterior
        """
        if fecha is None:
            return None
        
        dia_semana = fecha.weekday()  # 0=Lunes, 4=Viernes, 6=Domingo
        
        if dia_semana == 4:  # Ya es viernes
            return fecha
        elif dia_semana < 4:  # Lunes a Jueves → siguiente viernes
            dias_hasta_viernes = 4 - dia_semana
            return fecha + timedelta(days=dias_hasta_viernes)
        else:  # Sábado (5) o Domingo (6) → viernes anterior
            dias_desde_viernes = dia_semana - 4
            return fecha - timedelta(days=dias_desde_viernes)

    # =========================================================================
    # CUENTAS POR COBRAR - Con fecha de cobro ajustada
    # =========================================================================
    
    def get_cxc_detalle(self, con_fecha_comprobante=False):
        """Obtiene detalle de CxC con fecha de cobro proyectada"""
        docs = self._get_documentos(self.cuentas["cxc"])
        
        resultado = []
        for doc in docs:
            saldo = doc.get("saldo", 0)
            if saldo <= 0:
                continue
            
            cliente = doc.get("auxiliar", "")
            dias_pago = self._get_dias_pago_cliente(cliente)
            
            # Fecha base: preferir fecha de comprobante si está disponible
            if con_fecha_comprobante:
                fecha_base = self._get_fecha_comprobante(doc.get("comprobante"))
            else:
                fecha_base = self._parse_fecha(doc.get("emision"))
            
            # Calcular fecha de cobro esperada
            if fecha_base:
                fecha_cobro = fecha_base + timedelta(days=dias_pago)
            else:
                fecha_cobro = self._parse_fecha(doc.get("vencimiento"))
            
            # Mover cobro al viernes más próximo
            fecha_cobro = self._mover_a_viernes(fecha_cobro)
            
            resultado.append({
                "cliente": cliente,
                "rut": doc.get("idAuxiliar", ""),
                "documento": f"{doc.get('idTipoDoc', '')} {doc.get('numDoc', '')}",
                "emision": self._parse_fecha(doc.get("emision")),
                "fecha_cobro_esperada": fecha_cobro,
                "dias_pago_config": dias_pago,
                "saldo": saldo,
                "vencido": doc.get("estaVencido", False),
            })
        
        return resultado

    def get_cxc_aging(self):
        """Calcula aging de cartera por cobrar"""
        docs = self.get_cxc_detalle()
        
        aging = {
            "vigente": 0, "1-30": 0, "31-60": 0, "61-90": 0, ">90": 0, "total": 0,
        }
        
        for doc in docs:
            dias = (self.hoy - doc["emision"]).days if doc["emision"] else 0
            tramo = self._clasificar_aging(dias)
            aging[tramo] += doc["saldo"]
            aging["total"] += doc["saldo"]
        
        return aging

    # =========================================================================
    # CUENTAS POR PAGAR
    # =========================================================================
    
    def get_cxp_detalle(self, tipo="todas"):
        """Obtiene detalle de CxP con fecha de pago ajustada al viernes"""
        resultado = []
        
        cuentas_a_consultar = []
        if tipo in ["nacional", "todas"]:
            cuentas_a_consultar.append(("nacional", self.cuentas["cxp_nacional"]))
        if tipo in ["internacional", "todas"]:
            cuentas_a_consultar.append(("internacional", self.cuentas["cxp_internacional"]))
        
        for origen, cuenta in cuentas_a_consultar:
            docs = self._get_documentos(cuenta)
            
            for doc in docs:
                saldo = doc.get("saldo", 0)
                if saldo >= 0:
                    continue
                
                # Fecha de vencimiento original
                venc_original = self._parse_fecha(doc.get("vencimiento"))
                # Mover al viernes más próximo (igual que CxC)
                venc_viernes = self._mover_a_viernes(venc_original)
                    
                resultado.append({
                    "proveedor": doc.get("auxiliar", ""),
                    "rut": doc.get("idAuxiliar", ""),
                    "documento": f"{doc.get('idTipoDoc', '')} {doc.get('numDoc', '')}",
                    "vencimiento_original": venc_original,
                    "vencimiento": venc_viernes,  # Fecha ajustada al viernes
                    "dias_vencido": doc.get("diasVencido", 0),
                    "saldo": abs(saldo),
                    "vencido": doc.get("estaVencido", False),
                    "origen": origen,
                })
        
        return resultado

    def get_cxp_aging(self, tipo="todas"):
        """Calcula aging de CxP"""
        docs = self.get_cxp_detalle(tipo)
        
        aging = {
            "vigente": 0, "1-30": 0, "31-60": 0, "61-90": 0, ">90": 0, "total": 0,
        }
        
        for doc in docs:
            tramo = self._clasificar_aging(doc["dias_vencido"])
            aging[tramo] += doc["saldo"]
            aging["total"] += doc["saldo"]
        
        return aging

    # =========================================================================
    # PAGOS RECURRENTES
    # =========================================================================
    
    def get_pagos_recurrentes_periodo(self, dias=30):
        """Obtiene pagos recurrentes para los próximos N días"""
        recurrentes = self.config.get("recurrentes", [])
        pagos = []
        
        for i in range(dias):
            fecha = self.hoy + timedelta(days=i)
            dia_mes = fecha.day
            
            for r in recurrentes:
                if r["frecuencia"] == "mensual" and r["dia"] == dia_mes:
                    pagos.append({
                        "concepto": r["concepto"],
                        "fecha": fecha,
                        "monto": r["monto"],
                        "tipo": "recurrente",
                    })
                elif r["frecuencia"] == "quincenal" and dia_mes in [r["dia"], r["dia"] + 15]:
                    pagos.append({
                        "concepto": r["concepto"],
                        "fecha": fecha,
                        "monto": r["monto"],
                        "tipo": "recurrente",
                    })
        
        return pagos

    # =========================================================================
    # CASH FLOW PROYECTADO
    # =========================================================================
    
    def get_cashflow_proyectado(self, dias=14):
        """
        Proyección de cash flow usando:
        - Fecha de cobro ajustada por cliente
        - Pagos recurrentes configurados
        - CxP por fecha de vencimiento
        """
        print(f"\n📊 Calculando cash flow proyectado ({dias} días)...")
        
        cxc = self.get_cxc_detalle(con_fecha_comprobante=False)  # Sin API extra por ahora
        cxp = self.get_cxp_detalle("todas")
        recurrentes = self.get_pagos_recurrentes_periodo(dias)
        
        # Inicializar días
        proyeccion = {}
        for i in range(dias):
            fecha = self.hoy + timedelta(days=i)
            proyeccion[fecha] = {
                "entradas": 0,
                "salidas_cxp": 0,
                "salidas_recurrentes": 0,
                "salidas_total": 0,
                "neto": 0,
                "detalle_entradas": [],
                "detalle_salidas": [],
            }
        
        # Entradas: CxC por fecha de cobro esperada
        for doc in cxc:
            fecha_cobro = doc["fecha_cobro_esperada"]
            if fecha_cobro and fecha_cobro in proyeccion:
                proyeccion[fecha_cobro]["entradas"] += doc["saldo"]
                proyeccion[fecha_cobro]["detalle_entradas"].append({
                    "cliente": doc["cliente"],
                    "monto": doc["saldo"],
                    "dias_config": doc["dias_pago_config"],
                })
        
        # Salidas CxP: por fecha de vencimiento
        for doc in cxp:
            venc = doc["vencimiento"]
            if venc and venc in proyeccion:
                proyeccion[venc]["salidas_cxp"] += doc["saldo"]
                proyeccion[venc]["detalle_salidas"].append({
                    "concepto": doc["proveedor"],
                    "monto": doc["saldo"],
                    "tipo": "cxp",
                })
        
        # Salidas recurrentes
        for r in recurrentes:
            fecha = r["fecha"]
            if fecha in proyeccion:
                proyeccion[fecha]["salidas_recurrentes"] += r["monto"]
                proyeccion[fecha]["detalle_salidas"].append({
                    "concepto": r["concepto"],
                    "monto": r["monto"],
                    "tipo": "recurrente",
                })
        
        # Calcular totales
        for fecha in proyeccion:
            p = proyeccion[fecha]
            p["salidas_total"] = p["salidas_cxp"] + p["salidas_recurrentes"]
            p["neto"] = p["entradas"] - p["salidas_total"]
        
        return proyeccion

    def get_resumen_semana(self):
        """Resumen ejecutivo de la semana"""
        proyeccion = self.get_cashflow_proyectado(7)
        cxc = self.get_cxc_detalle()
        cxp = self.get_cxp_detalle("todas")
        
        # Totales semana
        total_entradas = sum(p["entradas"] for p in proyeccion.values())
        total_salidas = sum(p["salidas_total"] for p in proyeccion.values())
        
        # Top cobranzas (próximas en la semana)
        cobranzas_semana = []
        for fecha, p in proyeccion.items():
            for d in p["detalle_entradas"]:
                cobranzas_semana.append({**d, "fecha": fecha})
        cobranzas_semana.sort(key=lambda x: x["monto"], reverse=True)
        
        # Top pagos (próximos en la semana)
        pagos_semana = []
        for fecha, p in proyeccion.items():
            for d in p["detalle_salidas"]:
                pagos_semana.append({**d, "fecha": fecha})
        pagos_semana.sort(key=lambda x: x["monto"], reverse=True)
        
        # Día más crítico
        dia_critico = min(proyeccion.items(), key=lambda x: x[1]["neto"])
        
        return {
            "total_entradas": total_entradas,
            "total_salidas": total_salidas,
            "flujo_neto": total_entradas - total_salidas,
            "top_5_pagos": pagos_semana[:5],
            "top_3_cobranzas": cobranzas_semana[:3],
            "dia_critico": {
                "fecha": dia_critico[0],
                "neto": dia_critico[1]["neto"],
            },
            "alerta_pagos_altos": total_salidas > 100_000_000,
            "proyeccion_diaria": proyeccion,
        }


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    cf = SkualoCashFlow()
    
    print("\n" + "="*70)
    print("CONFIGURACIÓN DE DÍAS DE PAGO")
    print("="*70)
    print(f"Default: {cf.config.get('defaultDias')} días")
    print("\nExcepciones por cliente:")
    for c in cf.config.get("clientes", []):
        print(f"  {c['nombre']:.<30} {c['dias']} días")
    
    print("\n" + "="*70)
    print("PAGOS RECURRENTES MENSUALES")
    print("="*70)
    total_recurrentes = 0
    for r in cf.config.get("recurrentes", []):
        print(f"  Día {r['dia']:>2} | {r['concepto']:.<30} ${r['monto']:>15,.0f}")
        total_recurrentes += r["monto"]
    print(f"\n  {'TOTAL MENSUAL':.<32} ${total_recurrentes:>15,.0f}")
    
    print("\n" + "="*70)
    print("RESUMEN SEMANA")
    print("="*70)
    resumen = cf.get_resumen_semana()
    
    print(f"\n💰 Total entradas esperadas:  ${resumen['total_entradas']:>15,.0f}")
    print(f"💸 Total salidas programadas: ${resumen['total_salidas']:>15,.0f}")
    print(f"📊 Flujo neto semana:         ${resumen['flujo_neto']:>15,.0f}")
    
    if resumen["alerta_pagos_altos"]:
        print("\n⚠️  ALERTA: Salidas de la semana superan $100.000.000")
    
    print(f"\n📅 Día más crítico: {resumen['dia_critico']['fecha']} (neto: ${resumen['dia_critico']['neto']:,.0f})")
    
    print("\n--- TOP 5 PAGOS PRÓXIMOS 7 DÍAS ---")
    for i, p in enumerate(resumen["top_5_pagos"], 1):
        tipo = "🔄" if p.get("tipo") == "recurrente" else "📄"
        print(f"  {i}. {tipo} {p['concepto'][:35]:<35} ${p['monto']:>12,.0f}  ({p['fecha']})")
    
    print("\n--- TOP 3 COBRANZAS ESPERADAS ---")
    for i, c in enumerate(resumen["top_3_cobranzas"], 1):
        print(f"  {i}. {c['cliente'][:35]:<35} ${c['monto']:>12,.0f}  ({c['fecha']}) [{c['dias_config']}d]")
    
    print("\n--- CASH FLOW DIARIO ---")
    for fecha, p in resumen["proyeccion_diaria"].items():
        ind = "📈" if p["neto"] > 0 else "📉" if p["neto"] < 0 else "➖"
        rec = f" (rec: ${p['salidas_recurrentes']:,.0f})" if p["salidas_recurrentes"] > 0 else ""
        print(f"  {fecha} | In: ${p['entradas']:>12,.0f} | Out: ${p['salidas_total']:>12,.0f}{rec} | Neto: ${p['neto']:>12,.0f} {ind}")

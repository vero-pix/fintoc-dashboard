"""
Calculador de Días Reales de Pago por Cliente
Analiza histórico de bancos vs facturas para determinar comportamiento real de cobranza
"""

import requests
import os
import re
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict
import json

load_dotenv()


class AnalizadorDiasPago:
    def __init__(self):
        self.token = os.getenv("SKUALO_TOKEN")
        self.base_url = "https://api.skualo.cl/76243957-3"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "accept": "application/json"
        }
        
        # Fecha límite: 6 meses atrás
        self.fecha_limite = datetime.now() - timedelta(days=180)
        
    def _get_paginated(self, endpoint, max_pages=20):
        """Obtiene datos paginados de un endpoint"""
        all_items = []
        page = 1
        
        while page <= max_pages:
            url = f"{self.base_url}{endpoint}"
            if "?" in url:
                url += f"&Page={page}&PageSize=100"
            else:
                url += f"?Page={page}&PageSize=100"
            
            try:
                response = requests.get(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                
                items = data.get("items", [])
                if not items:
                    break
                    
                all_items.extend(items)
                
                # Verificar si hay más páginas
                if not data.get("next"):
                    break
                    
                page += 1
                print(f"  Página {page-1}: {len(items)} registros")
                
            except requests.exceptions.RequestException as e:
                print(f"ERROR en página {page}: {e}")
                break
        
        return all_items

    def get_abonos_banco(self):
        """Obtiene todos los abonos bancarios (pagos recibidos) de los últimos 6 meses"""
        print("\n📥 Extrayendo abonos bancarios...")
        
        # Cuentas de banco a consultar
        cuentas_banco = [
            "1102002",  # Santander
            "1102003",  # BCI
            "1102001",  # Chile
            "1102004",  # Bice
            "1102005",  # Scotia
        ]
        
        abonos = []
        
        for cuenta in cuentas_banco:
            print(f"\n  Cuenta {cuenta}:")
            items = self._get_paginated(f"/bancos/{cuenta}")
            
            for item in items:
                # Solo abonos (pagos recibidos)
                if item.get("montoAbono", 0) > 0:
                    fecha = self._parse_fecha(item.get("fecha"))
                    
                    # Solo últimos 6 meses
                    if fecha and fecha >= self.fecha_limite:
                        glosa = item.get("glosa", "")
                        
                        # Filtrar pagos de clientes (excluir depósitos internos, vales vista, etc.)
                        if self._es_pago_cliente(glosa):
                            abonos.append({
                                "fecha": fecha,
                                "monto": item.get("montoAbono"),
                                "glosa": glosa,
                                "cliente_extraido": self._extraer_cliente_glosa(glosa),
                                "cuenta": cuenta,
                            })
        
        print(f"\n✅ Total abonos de clientes: {len(abonos)}")
        return abonos

    def _es_pago_cliente(self, glosa):
        """Determina si un abono es pago de cliente"""
        glosa_lower = glosa.lower()
        
        # Excluir transferencias internas y otros
        exclusiones = [
            "transf a",
            "traspaso",
            "comercial y se",
            "cathpro",
            "vale vista",
            "depósito con vales",
            "otorg. crédito",
            "pac ",
        ]
        
        for excl in exclusiones:
            if excl in glosa_lower:
                return False
        
        # Incluir pagos de proveedores (clientes que pagan)
        inclusiones = [
            "pago proveedor",
            "transferencia de",
            "abono",
        ]
        
        for incl in inclusiones:
            if incl in glosa_lower:
                return True
        
        # Si tiene RUT al inicio, probablemente es pago de cliente
        if re.match(r'^\d{7,10}', glosa):
            return True
            
        return False

    def _extraer_cliente_glosa(self, glosa):
        """Extrae nombre del cliente de la glosa bancaria"""
        # Patrones comunes:
        # "0995200007 PAGO PROVEEDOR COPEC S" -> "COPEC"
        # "096709420K PAGO PROVEEDOR 0967094" -> buscar por RUT
        
        glosa_upper = glosa.upper()
        
        # Quitar RUT del inicio
        glosa_limpia = re.sub(r'^\d{7,10}[K\d]?\s*', '', glosa_upper)
        
        # Quitar "PAGO PROVEEDOR"
        glosa_limpia = glosa_limpia.replace("PAGO PROVEEDOR", "").strip()
        
        # Quitar "TRANSFERENCIA DE"
        glosa_limpia = glosa_limpia.replace("TRANSFERENCIA DE", "").strip()
        
        return glosa_limpia[:50] if glosa_limpia else glosa[:50]

    def get_facturas_pagadas(self):
        """Obtiene facturas que ya fueron pagadas (saldo = 0 o parcial)"""
        print("\n📄 Extrayendo facturas históricas...")
        
        # Necesitamos el libro mayor de la cuenta CxC para ver los movimientos
        # Alternativa: usar el endpoint de análisis sin filtro de pendientes
        
        url = f"{self.base_url}/contabilidad/reportes/analisisporcuenta/1107001"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            facturas = response.json()
            
            resultado = []
            for fac in facturas:
                fecha_emision = self._parse_fecha(fac.get("emision"))
                
                if fecha_emision and fecha_emision >= self.fecha_limite:
                    resultado.append({
                        "cliente": fac.get("auxiliar", ""),
                        "rut": fac.get("idAuxiliar", ""),
                        "documento": f"{fac.get('idTipoDoc', '')} {fac.get('numDoc', '')}",
                        "comprobante": fac.get("comprobante"),
                        "emision": fecha_emision,
                        "valor": fac.get("valor", 0),
                        "saldo": fac.get("saldo", 0),
                        "pagado": fac.get("valor", 0) - fac.get("saldo", 0),
                    })
            
            print(f"✅ Total facturas últimos 6 meses: {len(resultado)}")
            return resultado
            
        except requests.exceptions.RequestException as e:
            print(f"ERROR: {e}")
            return []

    def get_fecha_comprobante(self, num_comprobante):
        """Obtiene la fecha real de creación del comprobante"""
        url = f"{self.base_url}/contabilidad/comprobantes/{num_comprobante}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            # Usar creadoEl como fecha real
            creado_el = data.get("creadoEl")
            if creado_el:
                return self._parse_fecha(creado_el)
            
            return self._parse_fecha(data.get("fecha"))
            
        except:
            return None

    def _parse_fecha(self, fecha_str):
        """Convierte string ISO a datetime"""
        if not fecha_str:
            return None
        try:
            # Manejar diferentes formatos
            fecha_str = fecha_str.split("T")[0] if "T" in fecha_str else fecha_str
            return datetime.strptime(fecha_str[:10], "%Y-%m-%d")
        except:
            return None

    def _normalizar_nombre(self, nombre):
        """Normaliza nombre para matching"""
        if not nombre:
            return ""
        
        nombre = nombre.upper().strip()
        
        # Quitar sufijos comunes
        sufijos = [" S.A.", " S A", " SPA", " LTDA", " LIMITADA", " S.A", " SA"]
        for suf in sufijos:
            nombre = nombre.replace(suf, "")
        
        # Quitar puntuación
        nombre = re.sub(r'[^\w\s]', '', nombre)
        
        return nombre.strip()

    def calcular_dias_pago(self):
        """Calcula días promedio de pago por cliente"""
        print("\n" + "="*60)
        print("ANÁLISIS DE DÍAS DE PAGO POR CLIENTE")
        print("="*60)
        
        abonos = self.get_abonos_banco()
        facturas = self.get_facturas_pagadas()
        
        # Crear índice de facturas por cliente normalizado
        facturas_por_cliente = defaultdict(list)
        for fac in facturas:
            nombre_norm = self._normalizar_nombre(fac["cliente"])
            facturas_por_cliente[nombre_norm].append(fac)
        
        # Intentar matchear abonos con facturas
        matches = []
        sin_match = []
        
        print("\n🔍 Buscando matches entre abonos y facturas...")
        
        for abono in abonos:
            cliente_abono = self._normalizar_nombre(abono["cliente_extraido"])
            
            # Buscar en facturas
            mejor_match = None
            mejor_score = 0
            
            for nombre_fac, facs in facturas_por_cliente.items():
                # Calcular similitud
                score = self._similitud(cliente_abono, nombre_fac)
                
                if score > mejor_score and score > 0.5:
                    mejor_score = score
                    mejor_match = (nombre_fac, facs)
            
            if mejor_match:
                nombre_fac, facs = mejor_match
                
                # Buscar factura con monto similar
                for fac in facs:
                    # Tolerancia del 5% en monto
                    if abs(fac["valor"] - abono["monto"]) / max(fac["valor"], 1) < 0.05:
                        matches.append({
                            "cliente": fac["cliente"],
                            "fecha_factura": fac["emision"],
                            "fecha_pago": abono["fecha"],
                            "monto": abono["monto"],
                            "comprobante": fac["comprobante"],
                        })
                        break
            else:
                sin_match.append(abono)
        
        print(f"\n✅ Matches encontrados: {len(matches)}")
        print(f"❌ Sin match: {len(sin_match)}")
        
        # Obtener fechas reales de comprobante y calcular días
        print("\n📊 Calculando días reales de pago...")
        
        dias_por_cliente = defaultdict(list)
        
        for match in matches[:50]:  # Limitar para no hacer muchas llamadas API
            fecha_comprobante = self.get_fecha_comprobante(match["comprobante"])
            
            if fecha_comprobante and match["fecha_pago"]:
                dias = (match["fecha_pago"] - fecha_comprobante).days
                
                if 0 < dias < 180:  # Filtrar outliers
                    dias_por_cliente[match["cliente"]].append(dias)
                    print(f"  {match['cliente'][:40]}: {dias} días")
        
        # Calcular promedios
        print("\n" + "="*60)
        print("RESUMEN: DÍAS PROMEDIO DE PAGO POR CLIENTE")
        print("="*60)
        
        resultados = {}
        
        for cliente, dias_list in sorted(dias_por_cliente.items()):
            if len(dias_list) >= 1:
                promedio = sum(dias_list) / len(dias_list)
                resultados[cliente] = {
                    "promedio": round(promedio),
                    "min": min(dias_list),
                    "max": max(dias_list),
                    "n_pagos": len(dias_list),
                }
                print(f"\n{cliente[:50]}")
                print(f"  Promedio: {promedio:.0f} días | Min: {min(dias_list)} | Max: {max(dias_list)} | N={len(dias_list)}")
        
        # Guardar resultados
        self._guardar_resultados(resultados)
        
        return resultados

    def _similitud(self, s1, s2):
        """Calcula similitud entre dos strings"""
        if not s1 or not s2:
            return 0
        
        # Similitud por palabras comunes
        words1 = set(s1.split())
        words2 = set(s2.split())
        
        if not words1 or not words2:
            return 0
        
        common = words1.intersection(words2)
        return len(common) / max(len(words1), len(words2))

    def _guardar_resultados(self, resultados):
        """Guarda resultados en archivo JSON"""
        output = {
            "fecha_analisis": datetime.now().isoformat(),
            "periodo": "últimos 6 meses",
            "clientes": resultados
        }
        
        with open("dias_pago_clientes.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Resultados guardados en: dias_pago_clientes.json")


# =============================================================================
# EJECUCIÓN
# =============================================================================

if __name__ == "__main__":
    analizador = AnalizadorDiasPago()
    resultados = analizador.calcular_dias_pago()

"""
Calculador de Días Reales de Pago por Cliente - V2
Matching por RUT extraído de glosa bancaria
"""

import requests
import os
import re
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict
import json

load_dotenv()


class AnalizadorDiasPagoV2:
    def __init__(self):
        self.token = os.getenv("SKUALO_TOKEN")
        self.base_url = "https://api.skualo.cl/76243957-3"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "accept": "application/json"
        }
        
        self.fecha_limite = datetime.now() - timedelta(days=180)
        
    def _get_paginated(self, endpoint, max_pages=20):
        """Obtiene datos paginados"""
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
                
                if not data.get("next"):
                    break
                    
                page += 1
                
            except requests.exceptions.RequestException as e:
                print(f"ERROR en página {page}: {e}")
                break
        
        return all_items

    def _extraer_rut_glosa(self, glosa):
        """Extrae RUT de la glosa bancaria"""
        if not glosa:
            return None
        
        # Buscar patrón de RUT al inicio: 8-9 dígitos seguidos opcionalmente de K o dígito
        match = re.match(r'^0?(\d{7,8})(\d|K)?', glosa.upper())
        if match:
            rut_num = match.group(1)
            dv = match.group(2) if match.group(2) else ""
            
            # Formatear como XX.XXX.XXX-X
            if len(rut_num) >= 7:
                return f"{rut_num}-{dv}".upper() if dv else rut_num
        
        return None

    def _normalizar_rut(self, rut):
        """Normaliza RUT quitando puntos y guiones para comparación"""
        if not rut:
            return None
        # Quitar todo excepto números y K
        return re.sub(r'[^0-9Kk]', '', rut).upper()

    def _parse_fecha(self, fecha_str):
        """Convierte string ISO a datetime"""
        if not fecha_str:
            return None
        try:
            fecha_str = fecha_str.split("T")[0] if "T" in fecha_str else fecha_str
            return datetime.strptime(fecha_str[:10], "%Y-%m-%d")
        except:
            return None

    def get_abonos_banco(self):
        """Obtiene abonos bancarios con RUT extraído"""
        print("\n📥 Extrayendo abonos bancarios...")
        
        cuentas_banco = ["1102002", "1102003", "1102001", "1102004", "1102005"]
        abonos = []
        
        for cuenta in cuentas_banco:
            items = self._get_paginated(f"/bancos/{cuenta}")
            
            for item in items:
                if item.get("montoAbono", 0) > 0:
                    fecha = self._parse_fecha(item.get("fecha"))
                    
                    if fecha and fecha >= self.fecha_limite:
                        glosa = item.get("glosa", "")
                        rut = self._extraer_rut_glosa(glosa)
                        
                        if rut:  # Solo si pudimos extraer RUT
                            abonos.append({
                                "fecha": fecha,
                                "monto": item.get("montoAbono"),
                                "glosa": glosa,
                                "rut_extraido": rut,
                                "rut_normalizado": self._normalizar_rut(rut),
                            })
        
        print(f"✅ Abonos con RUT identificado: {len(abonos)}")
        return abonos

    def get_facturas_con_comprobante(self):
        """Obtiene facturas con fecha de comprobante"""
        print("\n📄 Extrayendo facturas y fechas de comprobante...")
        
        url = f"{self.base_url}/contabilidad/reportes/analisisporcuenta/1107001"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            facturas_raw = response.json()
        except Exception as e:
            print(f"ERROR: {e}")
            return []
        
        facturas = []
        comprobantes_consultados = {}
        
        for fac in facturas_raw:
            fecha_emision = self._parse_fecha(fac.get("emision"))
            
            if not fecha_emision or fecha_emision < self.fecha_limite:
                continue
            
            num_comprobante = fac.get("comprobante")
            rut_cliente = fac.get("idAuxiliar", "")
            
            # Obtener fecha real del comprobante (con cache)
            if num_comprobante not in comprobantes_consultados:
                fecha_comprobante = self._get_fecha_comprobante(num_comprobante)
                comprobantes_consultados[num_comprobante] = fecha_comprobante
            else:
                fecha_comprobante = comprobantes_consultados[num_comprobante]
            
            facturas.append({
                "cliente": fac.get("auxiliar", ""),
                "rut": rut_cliente,
                "rut_normalizado": self._normalizar_rut(rut_cliente),
                "documento": f"{fac.get('idTipoDoc', '')} {fac.get('numDoc', '')}",
                "valor": fac.get("valor", 0),
                "saldo": fac.get("saldo", 0),
                "emision": fecha_emision,
                "fecha_comprobante": fecha_comprobante,
            })
            
            print(f"  {fac.get('auxiliar', '')[:40]} | Comprobante: {fecha_comprobante}")
        
        print(f"✅ Total facturas procesadas: {len(facturas)}")
        return facturas

    def _get_fecha_comprobante(self, num_comprobante):
        """Obtiene fecha creadoEl del comprobante"""
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

    def calcular_dias_pago(self):
        """Calcula días de pago por cliente usando matching por RUT"""
        print("\n" + "="*60)
        print("ANÁLISIS DE DÍAS DE PAGO POR CLIENTE (v2 - por RUT)")
        print("="*60)
        
        abonos = self.get_abonos_banco()
        facturas = self.get_facturas_con_comprobante()
        
        # Índice de facturas por RUT normalizado
        facturas_por_rut = defaultdict(list)
        for fac in facturas:
            if fac["rut_normalizado"]:
                facturas_por_rut[fac["rut_normalizado"]].append(fac)
        
        print(f"\n🔍 RUTs en facturas: {list(facturas_por_rut.keys())[:10]}...")
        
        # Buscar matches
        matches = []
        
        for abono in abonos:
            rut_abono = abono["rut_normalizado"]
            
            if rut_abono in facturas_por_rut:
                facs_cliente = facturas_por_rut[rut_abono]
                
                # Buscar factura con monto similar (tolerancia 10%)
                for fac in facs_cliente:
                    ratio = abs(fac["valor"] - abono["monto"]) / max(fac["valor"], 1)
                    
                    if ratio < 0.10 and fac["fecha_comprobante"]:
                        dias = (abono["fecha"] - fac["fecha_comprobante"]).days
                        
                        if 0 < dias < 180:  # Filtrar outliers
                            matches.append({
                                "cliente": fac["cliente"],
                                "rut": fac["rut"],
                                "monto": abono["monto"],
                                "fecha_factura": fac["fecha_comprobante"],
                                "fecha_pago": abono["fecha"],
                                "dias": dias,
                            })
                            print(f"  ✓ {fac['cliente'][:35]} | {dias} días | ${abono['monto']:,.0f}")
        
        print(f"\n✅ Matches encontrados: {len(matches)}")
        
        # Calcular promedios por cliente
        dias_por_cliente = defaultdict(list)
        for m in matches:
            dias_por_cliente[m["cliente"]].append(m["dias"])
        
        print("\n" + "="*60)
        print("RESUMEN: DÍAS PROMEDIO DE PAGO POR CLIENTE")
        print("="*60)
        
        resultados = {}
        
        for cliente, dias_list in sorted(dias_por_cliente.items(), key=lambda x: sum(x[1])/len(x[1])):
            promedio = sum(dias_list) / len(dias_list)
            resultados[cliente] = {
                "promedio": round(promedio),
                "min": min(dias_list),
                "max": max(dias_list),
                "n_pagos": len(dias_list),
            }
            print(f"\n{cliente[:50]}")
            print(f"  📊 Promedio: {promedio:.0f} días | Rango: {min(dias_list)}-{max(dias_list)} | Pagos: {len(dias_list)}")
        
        # Guardar
        self._guardar_resultados(resultados)
        
        return resultados

    def _guardar_resultados(self, resultados):
        """Guarda resultados en JSON"""
        output = {
            "fecha_analisis": datetime.now().isoformat(),
            "periodo": "últimos 6 meses",
            "metodo": "matching por RUT",
            "clientes": resultados
        }
        
        with open("dias_pago_clientes.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Guardado en: dias_pago_clientes.json")


if __name__ == "__main__":
    analizador = AnalizadorDiasPagoV2()
    analizador.calcular_dias_pago()

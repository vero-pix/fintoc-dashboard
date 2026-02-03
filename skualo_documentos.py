import os
import requests
import json
from dotenv import load_dotenv
from skualo_auth import SkualoAuth
from datetime import datetime, date
from typing import Dict, List, Optional


class SkualoDocumentosClient:
    def __init__(self):
        load_dotenv() # Ensure .env is loaded for SkualoAuth
        self.token = SkualoAuth().get_token()
        self.base_url = "https://api.skualo.cl/76243957-3"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "accept": "application/json"
        }
        self.last_errors = []
        
        # Cache simple en memoria
        self._cache_detalles = {}
        self._cache_file = os.path.join(os.path.dirname(__file__), "skualo_cache_detalles.json")
        self._load_cache()

    def _load_cache(self):
        try:
            if os.path.exists(self._cache_file):
                with open(self._cache_file, 'r') as f:
                    self._cache_detalles = json.load(f)
                    print(f"📦 Cache detalles cargado: {len(self._cache_detalles)} items")
        except Exception as e:
            print(f"Error cargando cache: {e}")
            self._cache_detalles = {}

    def _save_cache(self):
        try:
            with open(self._cache_file, 'w') as f:
                json.dump(self._cache_detalles, f)
        except Exception as e:
            print(f"Error guardando cache: {e}")

    def _get_detalle_documento(self, id_documento: str) -> Optional[Dict]:
        """Obtiene detalle con caching"""
        if str(id_documento) in self._cache_detalles:
            # Si ya está cerrado o es antiguo, usar cache
            # (Podríamos invalidar si es muy viejo, pero asumimos documentos históricos no cambian mucho)
            return self._cache_detalles[str(id_documento)]
            
        url = f"{self.base_url}/documentos/{id_documento}"
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                
                # Guardar solo si tiene detalles significativos (o siempre)
                # Si el documento está "cerrado" (procesado), es seguro cachearlo por mucho tiempo
                detalles_cerrados = all(d.get("cerrado", False) for d in data.get("detalles", []))
                
                if detalles_cerrados:
                    self._cache_detalles[str(id_documento)] = data
                    # Guardamos incrementalmente o al final
                    # self._save_cache() 
                
                return data
            return None
        except requests.exceptions.RequestException as e:
            print(f"ERROR obteniendo detalle documento {id_documento}: {e}")
            return None

    def get_documentos(self, tipo_documento: str) -> List[Dict]:
        url = f"{self.base_url}/documentos"
        # Skualo exige al menos un criterio. Filtramos por tipo y fecha.
        fecha_desde = "01-01-2026"
        # Importante: El tipo de documento debe ir entre comillas simples para Skualo
        params = {
            "search": f"idTipoDocumento eq '{tipo_documento}' AND fecha gte {fecha_desde}",
            "pageSize": 200
        } 

        try:
            response = requests.get(url, headers=self.headers, params=params)
            if response.status_code != 200:
                # Capturamos el texto real del error para diagnóstico
                error_msg = response.text[:100]
                raise Exception(f"Skualo {response.status_code}: {error_msg}")
            
            data = response.json()
            items = data if isinstance(data, list) else data.get("items", [])
            
            # Diagnóstico de éxito
            if items:
                self.last_errors.append(f"Éxito {tipo_documento}: {len(items)} docs")

            return items
        except Exception as e:
            self.last_errors.append(f"Err {tipo_documento}: {str(e)}")
            return []

    def get_documento_detalle(self, id_documento: str) -> Optional[Dict]:
        """
        Obtiene el detalle completo de un documento específico.
        """
        data = self._get_detalle_documento(id_documento)
        # Si viene como lista (sucede con algunos tipos en Skualo), tomar el primero
        if isinstance(data, list) and len(data) > 0:
            return data[0]
        return data

    def documento_tiene_posterior(self, detalle_doc: Dict) -> bool:
        """
        Verifica si un documento tiene todos sus detalles cerrados.
        """
        if not detalle_doc or not isinstance(detalle_doc, dict):
            return False
            
        detalles = detalle_doc.get("detalles", [])
        
        if not detalles:
            return False
        
        return all(d.get("cerrado", False) for d in detalles)

    def get_soli_sin_oc(self) -> List[Dict]:
        """
        Obtiene SOLIs aprobadas sin OC generada.
        
        Una SOLI está "sin OC" si:
        - Estado = "Aprobado"
        - Al menos un detalle tiene cerrado=False
        """
        solis = self.get_documentos("SOLI")
        soli_sin_oc = []

        for doc in solis:
            estado = doc.get("estado", "")
            if estado != "Aprobado":
                continue

            # --- OPTIMIZACIÓN: Filtro temprano por fecha ---
            fecha_str = doc.get("fecha", "")
            try:
                fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).date() if fecha_str else None
                if fecha:
                    dias_antiguedad = (date.today() - fecha).days
                    if dias_antiguedad > 45: # Ampliamos a 45 días para SOLIs
                        continue
            except:
                pass

            # Solo si pasa el filtro de fecha, pedimos el detalle para verificar si está 'cerrado'
            id_documento = doc.get("idDocumento", "")
            detalle = self.get_documento_detalle(id_documento)
            
            if not detalle:
                continue

            if self.documento_tiene_posterior(detalle):
                continue

            monto = detalle.get("total", 0)
            
            # Filtrar: excluir montos $0 o muy pequeños y documentos muy antiguos (>15 días)
            if monto < 1000:  # Excluir montos menores a $1,000
                continue
            
            if fecha:
                dias_antiguedad = (date.today() - fecha).days
                if dias_antiguedad > 15:  # Excluir SOLIs de más de 15 días
                    continue

            soli_sin_oc.append({
                "folio": detalle.get("folio", ""),
                "fecha": fecha,
                "proveedor": detalle.get("auxiliar", "Sin proveedor"),
                "rut": detalle.get("idAuxiliar", ""),
                "monto": monto,
                "proyecto": detalle.get("proyecto", ""),
                "centro_costo": detalle.get("centroCosto", ""),
                "glosa": detalle.get("observaciones", "")
            })

        return sorted(soli_sin_oc, key=lambda x: x['fecha'] or date.min, reverse=True)

    def get_oc_sin_factura(self) -> List[Dict]:
        """
        Obtiene OCs aprobadas sin factura.
        
        Una OC está "sin factura" si:
        - Estado = "Aprobado"
        - Al menos un detalle tiene cerrado=False
        """
        ocs = self.get_documentos("OC")
        oc_sin_factura = []
        hoy = date.today()

        for doc in ocs:
            estado = doc.get("estado", "")
            if estado != "Aprobado":
                continue

            # print(f"  Procesando OC {doc.get('idDocumento')}...")

            # --- OPTIMIZACIÓN: Filtro temprano por fecha ---
            fecha_str = doc.get("fecha", "")
            try:
                fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).date() if fecha_str else None
                if fecha:
                    dias_pendiente = (hoy - fecha).days
                    if dias_pendiente > 45: # Filtro de 45 días inmediato
                        continue
            except:
                pass

            # Obtener detalle completo para verificar campo 'cerrado'
            id_documento = doc.get("idDocumento", "")
            detalle = self.get_documento_detalle(id_documento)
            
            if not detalle:
                continue

            if self.documento_tiene_posterior(detalle):
                continue

            monto = detalle.get("total", 0)
            
            # Filtrar: excluir montos muy pequeños y OCs muy antiguas (>15 días)
            if monto < 1000:
                continue
            
            if dias_pendiente > 15:  # Excluir OCs de más de 15 días
                continue

            oc_sin_factura.append({
                "folio": detalle.get("folio", ""),
                "fecha": fecha,
                "proveedor": detalle.get("auxiliar", "Sin proveedor"),
                "rut": detalle.get("idAuxiliar", ""),
                "monto": monto,
                "proyecto": detalle.get("proyecto", ""),
                "dias_pendiente": dias_pendiente,
                "glosa": detalle.get("observaciones", "")
            })

        return sorted(oc_sin_factura, key=lambda x: x['dias_pendiente'], reverse=True)

    def get_ocx_sin_invoice(self) -> List[Dict]:
        """
        Obtiene OCXs aprobadas sin invoice.
        
        Una OCX está "sin invoice" si:
        - Estado = "Aprobado"
        - Al menos un detalle tiene cerrado=False
        """
        ocxs = self.get_documentos("OCX")
        ocx_sin_invoice = []
        hoy = date.today()

        for doc in ocxs:
            estado = doc.get("estado", "")
            if estado != "Aprobado":
                continue
            
            # --- OPTIMIZACIÓN: Filtro temprano por fecha ---
            fecha_str = doc.get("fecha", "")
            try:
                fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).date() if fecha_str else None
                if fecha:
                    dias_pendiente = (hoy - fecha).days
                    if dias_pendiente > 45: # Filtro de 45 días inmediato
                        continue
            except:
                pass

            # Obtener detalle completo
            id_documento = doc.get("idDocumento", "")
            detalle = self.get_documento_detalle(id_documento)
            
            if not detalle:
                continue

            if self.documento_tiene_posterior(detalle):
                continue

            monto_usd = detalle.get("total", 0)
            
            # Filtrar: excluir montos muy pequeños y OCXs muy antiguas (>15 días)
            if monto_usd < 100:  # Excluir montos menores a $100 USD
                continue
            
            if dias_pendiente > 15:  # Excluir OCXs de más de 15 días
                continue

            ocx_sin_invoice.append({
                "folio": detalle.get("folio", ""),
                "fecha": fecha,
                "proveedor": detalle.get("auxiliar", "Sin proveedor"),
                "rut": detalle.get("idAuxiliar", ""),
                "monto_usd": monto_usd,
                "proyecto": detalle.get("proyecto", ""),
                "dias_pendiente": dias_pendiente,
                "glosa": detalle.get("observaciones", "")
            })

        return sorted(ocx_sin_invoice, key=lambda x: x['dias_pendiente'], reverse=True)

    def get_face_pendientes_pago(self, dias_max: int = 90) -> List[Dict]:
        """
        Obtiene Facturas de Compra (FACE) y otros documentos tributarios pendientes de pago.
        Horizonte temporal: 90 días.
        """
        tipos = ["FACE", "DIN", "NCE"]
        docs_pendientes = []
        hoy = date.today()

        for tipo in tipos:
            items = self.get_documentos(tipo)
            for doc in items:
                estado = doc.get("estado", "")
                if estado not in ["Aprobado", "Pendiente", ""]: # Depende de cómo Skualo marque FACE
                    continue

                id_documento = doc.get("idDocumento", "")
                detalle = self.get_documento_detalle(id_documento)
                
                if not detalle:
                    continue

                # Un documento tributario está pendiente si no está cerrado
                if self.documento_tiene_posterior(detalle):
                    continue

                fecha_str = detalle.get("fecha", "")
                try:
                    fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).date() if fecha_str else None
                    dias_pendiente = (hoy - fecha).days if fecha else 0
                except:
                    fecha = None
                    dias_pendiente = 0

                # Filtro de 90 días para FACE y otros
                if dias_pendiente > dias_max:
                    continue

                monto = detalle.get("total", 0)
                if abs(monto) < 1000: # Ignorar montos despreciables
                    continue

                docs_pendientes.append({
                    "tipo": tipo,
                    "folio": detalle.get("folio", ""),
                    "fecha": fecha,
                    "proveedor": detalle.get("auxiliar", "Sin proveedor"),
                    "rut": detalle.get("idAuxiliar", ""),
                    "monto": monto,
                    "proyecto": detalle.get("proyecto", ""),
                    "dias_pendiente": dias_pendiente,
                    "glosa": detalle.get("observaciones", "")
                })

        return sorted(docs_pendientes, key=lambda x: x['dias_pendiente'], reverse=True)

    def get_oc_pendientes_aprobacion(self, dias_max: int = 15) -> List[Dict]:
        """
        Obtiene OCs pendientes de aprobación (últimos N días).
        Visibilidad temprana de compromisos que vienen.
        """
        ocs = self.get_documentos("OC")
        oc_pendientes = []
        hoy = date.today()

        for doc in ocs:
            estado = doc.get("estado", "")
            # Solo pendientes (no aprobadas ni rechazadas)
            if estado in ["Aprobado", "Rechazado", "Anulado"]:
                continue

            id_documento = doc.get("idDocumento", "")
            detalle = self.get_documento_detalle(id_documento)
            
            if not detalle:
                continue

            fecha_str = detalle.get("fecha", "")
            try:
                fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).date() if fecha_str else None
                dias_pendiente = (hoy - fecha).days if fecha else 0
            except:
                fecha = None
                dias_pendiente = 0

            monto = detalle.get("total", 0)
            
            # Filtrar: solo últimos N días y montos significativos
            if monto < 1000:
                continue
            
            if dias_pendiente > dias_max:  # Respetar dias_max
                continue

            oc_pendientes.append({
                "folio": detalle.get("folio", ""),
                "fecha": fecha,
                "proveedor": detalle.get("auxiliar", "Sin proveedor"),
                "rut": detalle.get("idAuxiliar", ""),
                "monto": monto,
                "proyecto": detalle.get("proyecto", ""),
                "estado": estado,
                "dias_pendiente": dias_pendiente,
                "glosa": detalle.get("observaciones", "")
            })

        return sorted(oc_pendientes, key=lambda x: x['monto'], reverse=True)

    def get_ocx_pendientes_aprobacion(self, dias_max: int = 15) -> List[Dict]:
        """
        Obtiene OCXs pendientes de aprobación (últimos N días).
        Visibilidad temprana de compromisos internacionales que vienen.
        """
        ocxs = self.get_documentos("OCX")
        ocx_pendientes = []
        hoy = date.today()

        for doc in ocxs:
            estado = doc.get("estado", "")
            # Solo pendientes (no aprobadas ni rechazadas)
            if estado in ["Aprobado", "Rechazado", "Anulado"]:
                continue

            id_documento = doc.get("idDocumento", "")
            detalle = self.get_documento_detalle(id_documento)
            
            if not detalle:
                continue

            fecha_str = detalle.get("fecha", "")
            try:
                fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).date() if fecha_str else None
                dias_pendiente = (hoy - fecha).days if fecha else 0
            except:
                fecha = None
                dias_pendiente = 0

            monto_usd = detalle.get("total", 0)
            
            # Filtrar: solo últimos N días y montos significativos
            if monto_usd < 100:
                continue
            
            if dias_pendiente > dias_max:  # Respetar dias_max
                continue

            ocx_pendientes.append({
                "folio": detalle.get("folio", ""),
                "fecha": fecha,
                "proveedor": detalle.get("auxiliar", "Sin proveedor"),
                "rut": detalle.get("idAuxiliar", ""),
                "monto_usd": monto_usd,
                "proyecto": detalle.get("proyecto", ""),
                "estado": estado,
                "dias_pendiente": dias_pendiente,
                "glosa": detalle.get("observaciones", "")
            })

        return sorted(ocx_pendientes, key=lambda x: x['monto_usd'], reverse=True)

    def get_ventas_pendientes(self) -> List[Dict]:
        """
        Obtiene Órdenes de Venta (OV) o Hojas de Entrada (HE) pendientes de facturar.
        Esto representa el verdadero pipeline de INGRESOS.
        """
        tipos_venta = ["OV", "HE", "NV"] # Orden de Venta, Hoja de Entrada, Nota de Venta
        ventas_pendientes = []
        hoy = date.today()

        for tipo in tipos_venta:
            items = self.get_documentos(tipo)
            for doc in items:
                estado = doc.get("estado", "")
                # Permitir estados comunes de documentos vigentes
                if estado not in ["Aprobado", "Aceptado", "Vigente", "Pendiente", ""]: 
                    continue

                id_documento = doc.get("idDocumento", "")
                detalle = self.get_documento_detalle(id_documento)
                
                if not detalle:
                    continue

                # Si el documento ya está cerrado, es que ya se facturó
                if self.documento_tiene_posterior(detalle):
                    continue

                fecha_str = detalle.get("fecha", "")
                try:
                    fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).date() if fecha_str else None
                except:
                    fecha = None

                monto = detalle.get("total", 0)
                if monto < 1000: continue

                ventas_pendientes.append({
                    "tipo": tipo,
                    "folio": detalle.get("folio", ""),
                    "fecha": fecha,
                    "cliente": detalle.get("auxiliar", "Cliente desconocido"),
                    "rut": detalle.get("idAuxiliar", ""),
                    "monto": monto,
                    "proyecto": detalle.get("proyecto", ""),
                    "glosa": detalle.get("observaciones", "")
                })

        return sorted(ventas_pendientes, key=lambda x: x['monto'], reverse=True)

    def get_resumen_pipeline(self) -> Dict:
        """
        Obtiene resumen consolidado del pipeline distinguiendo Ingresos de Egresos.
        """
        print("🔍 Cargando Pipeline de INGRESOS (Ventas/HE)...")
        ventas = self.get_ventas_pendientes()
        print(f"  → {len(ventas)} ventas pendientes encontradas")

        print("💸 Cargando Pipeline de EGRESOS (OC/OCX)...")
        solis = self.get_soli_sin_oc()
        ocs = self.get_oc_sin_factura()
        ocxs = self.get_ocx_sin_invoice()
        ocs_pend = self.get_oc_pendientes_aprobacion(dias_max=45)
        ocxs_pend = self.get_ocx_pendientes_aprobacion(dias_max=45)
        face = self.get_face_pendientes_pago(dias_max=90)

        return {
            "ingresos": {
                "cantidad": len(ventas),
                "monto_total": sum(v['monto'] for v in ventas),
                "documentos": ventas
            },
            "egresos": {
                "soli": {
                    "cantidad": len(solis),
                    "monto_total": sum(s['monto'] for s in solis),
                    "documentos": solis
                },
                "oc": {
                    "cantidad": len(ocs),
                    "monto_total": sum(o['monto'] for o in ocs),
                    "documentos": ocs
                },
                "ocx": {
                    "cantidad": len(ocxs),
                    "monto_total_usd": sum(o['monto_usd'] for o in ocxs),
                    "documentos": ocxs
                },
                "oc_pendiente": {
                    "cantidad": len(ocs_pend),
                    "monto_total": sum(o['monto'] for o in ocs_pend),
                    "documentos": ocs_pend
                },
                "ocx_pendiente": {
                    "cantidad": len(ocxs_pend),
                    "monto_total_usd": sum(o['monto_usd'] for o in ocxs_pend),
                    "documentos": ocxs_pend
                },
                "face": {
                    "cantidad": len(face),
                    "monto_total": sum(f['monto'] for f in face),
                    "documentos": face
                }
            }
        }


if __name__ == "__main__":
    client = SkualoDocumentosClient()

    print("\n=== Resumen Pipeline de Compromisos ===\n")
    resumen = client.get_resumen_pipeline()

    print(f"\n📋 SOLIs Aprobadas sin OC: {resumen['soli']['cantidad']}")
    print(f"   Monto Total: ${resumen['soli']['monto_total']:,.0f} CLP")
    
    if resumen['soli']['documentos']:
        print("\n   Primeras 5:")
        for s in resumen['soli']['documentos'][:5]:
            print(f"   - Folio {s['folio']}: {s['proveedor'][:30]} | {s['proyecto']} | ${s['monto']:,.0f}")

    print(f"\n📄 OCs Aprobadas sin Factura: {resumen['oc']['cantidad']}")
    print(f"   Monto Total: ${resumen['oc']['monto_total']:,.0f} CLP")
    
    if resumen['oc']['documentos']:
        print("\n   Primeras 5:")
        for o in resumen['oc']['documentos'][:5]:
            print(f"   - Folio {o['folio']}: {o['proveedor'][:30]} | {o['dias_pendiente']} días | ${o['monto']:,.0f}")

    print(f"\n🌐 OCXs Aprobadas sin Invoice: {resumen['ocx']['cantidad']}")
    print(f"   Monto Total: ${resumen['ocx']['monto_total_usd']:,.2f} USD")
    
    if resumen['ocx']['documentos']:
        print("\n   Primeras 5:")
        for o in resumen['ocx']['documentos'][:5]:
            print(f"   - Folio {o['folio']}: {o['proveedor'][:30]} | {o['dias_pendiente']} días | ${o['monto_usd']:,.2f}")

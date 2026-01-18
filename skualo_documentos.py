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
        """
        Obtiene documentos por tipo desde Skualo.
        """
        url = f"{self.base_url}/documentos"
        params = {"search": f"IDTipoDocumento eq {tipo_documento}"}

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            items = data.get("items", [])
            print(f"DEBUG: get_documentos({tipo_documento}) retornó {len(items)} items")
            return items
        except requests.exceptions.RequestException as e:
            print(f"ERROR consultando documentos {tipo_documento}: {e}")
            return []

    def get_documento_detalle(self, id_documento: str) -> Optional[Dict]:
        """
        Obtiene el detalle completo de un documento específico.
        Incluye detalles con campo 'cerrado' y proyecto.
        Usando versión on caching.
        """
        return self._get_detalle_documento(id_documento)

    def documento_tiene_posterior(self, detalle_doc: Dict) -> bool:
        """
        Verifica si un documento tiene todos sus detalles cerrados
        (es decir, ya fue procesado con documento posterior).
        
        Un documento está completamente procesado si TODOS sus detalles
        tienen cerrado=True.
        """
        detalles = detalle_doc.get("detalles", [])
        
        if not detalles:
            return False
        
        # Si TODOS los detalles están cerrados, el documento tiene posterior
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

            # Obtener detalle completo para verificar campo 'cerrado'
            id_documento = doc.get("idDocumento", "")
            detalle = self.get_documento_detalle(id_documento)
            
            if not detalle:
                continue

            # Verificar si tiene documento posterior (todos cerrados)
            if self.documento_tiene_posterior(detalle):
                continue  # Ya tiene OC, no incluir

            # Extraer datos del detalle completo
            fecha_str = detalle.get("fecha", "")
            try:
                fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).date() if fecha_str else None
            except:
                fecha = None

            soli_sin_oc.append({
                "folio": detalle.get("folio", ""),
                "fecha": fecha,
                "proveedor": detalle.get("auxiliar", "Sin proveedor"),
                "rut": detalle.get("idAuxiliar", ""),
                "monto": detalle.get("total", 0),
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

            # Obtener detalle completo
            id_documento = doc.get("idDocumento", "")
            detalle = self.get_documento_detalle(id_documento)
            
            if not detalle:
                continue

            # Verificar si tiene factura (todos cerrados)
            if self.documento_tiene_posterior(detalle):
                continue  # Ya tiene factura, no incluir

            fecha_str = detalle.get("fecha", "")
            try:
                fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).date() if fecha_str else None
                dias_pendiente = (hoy - fecha).days if fecha else 0
            except:
                fecha = None
                dias_pendiente = 0

            oc_sin_factura.append({
                "folio": detalle.get("folio", ""),
                "fecha": fecha,
                "proveedor": detalle.get("auxiliar", "Sin proveedor"),
                "rut": detalle.get("idAuxiliar", ""),
                "monto": detalle.get("total", 0),
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
            
            # print(f"  Procesando OCX {doc.get('idDocumento')}...")

            # Obtener detalle completo
            id_documento = doc.get("idDocumento", "")
            detalle = self.get_documento_detalle(id_documento)
            
            if not detalle:
                continue

            # Verificar si tiene invoice (todos cerrados)
            if self.documento_tiene_posterior(detalle):
                continue  # Ya tiene invoice, no incluir

            fecha_str = detalle.get("fecha", "")
            try:
                fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00")).date() if fecha_str else None
                dias_pendiente = (hoy - fecha).days if fecha else 0
            except:
                fecha = None
                dias_pendiente = 0

            ocx_sin_invoice.append({
                "folio": detalle.get("folio", ""),
                "fecha": fecha,
                "proveedor": detalle.get("auxiliar", "Sin proveedor"),
                "rut": detalle.get("idAuxiliar", ""),
                "monto_usd": detalle.get("total", 0),
                "proyecto": detalle.get("proyecto", ""),
                "dias_pendiente": dias_pendiente,
                "glosa": detalle.get("observaciones", "")
            })

        return sorted(ocx_sin_invoice, key=lambda x: x['dias_pendiente'], reverse=True)

    def get_resumen_pipeline(self) -> Dict:
        """
        Obtiene resumen consolidado del pipeline de compromisos.
        """
        print("Cargando SOLIs sin OC...")
        solis = self.get_soli_sin_oc()
        print(f"  → {len(solis)} encontradas")
        
        print("Cargando OCs sin Factura...")
        ocs = self.get_oc_sin_factura()
        print(f"  → {len(ocs)} encontradas")
        
        print("Cargando OCXs sin Invoice...")
        ocxs = self.get_ocx_sin_invoice()
        print(f"  → {len(ocxs)} encontradas")

        return {
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

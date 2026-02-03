import requests
import os
import json
from dotenv import load_dotenv
from datetime import datetime, date

load_dotenv()

def debug_ocs():
    token = os.getenv('SKUALO_TOKEN')
    headers = {
        'Authorization': f'Bearer {token}',
        'accept': 'application/json'
    }
    
    url = "https://api.skualo.cl/76243957-3/documentos"
    params = {
        "search": "idTipoDocumento eq OC",
        "orderBy": "fecha desc",
        "pageSize": 5
    }
    
    print(f"Buscando OCs en 2026...")
    try:
        resp = requests.get(url, headers=headers, params=params)
        print(f"Status /documentos: {resp.status_code}")
        
        data = resp.json()
        if isinstance(data, list):
            items = data
            print(f"Resultado es LISTA: {len(items)} items")
        else:
            items = data.get('items', [])
            print(f"Resultado es DICT. Items: {len(items)}")
            
        for item in items[:10]:
            id_doc = item.get('idDocumento')
            estado = item.get('estado')
            fecha = item.get('fecha')
            folio = item.get('folio')
            
            print(f"\n--- Analizando Folio: {folio} ---")
            print(f"ID: {id_doc} | Estado: {estado} | Fecha: {fecha}")
            
            det_url = f"https://api.skualo.cl/76243957-3/documentos/{id_doc}"
            det_resp = requests.get(det_url, headers=headers)
            
            if det_resp.status_code == 200:
                det_data = det_resp.json()
                if isinstance(det_data, list) and len(det_data) > 0:
                    det = det_data[0]
                else:
                    det = det_data
                
                detalles = det.get('detalles', [])
                if not detalles:
                    print("AVISO: Documento sin detalles.")
                    # Quizás los detalles están en otro campo?
                
                cerrado = all(d.get('cerrado', False) for d in detalles) if detalles else False
                print(f"Cerrado (tiene posterior): {cerrado}")
                
                if cerrado:
                    print("SKIPPED: Ya tiene documento posterior (cerrado).")
                if estado != "Aprobado":
                    print(f"SKIPPED: Estado es {estado}, no 'Aprobado'.")
            else:
                print(f"Error detalle: {det_resp.status_code}")
                
    except Exception as e:
        print(f"Error general: {type(e).__name__} - {e}")

if __name__ == "__main__":
    debug_ocs()

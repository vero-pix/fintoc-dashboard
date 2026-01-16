"""
Webhook Handler para Fintoc
Recibe notificaciones de movimientos bancarios en tiempo real
"""
import os
from datetime import datetime, date
from typing import Dict, List
import hmac
import hashlib

MOVIMIENTOS_HOY: Dict[str, any] = {
    "fecha": None,
    "entradas": [],
    "salidas": [],
    "ultima_actualizacion": None
}

def verificar_firma_fintoc(payload: bytes, signature: str, secret: str) -> bool:
    if not secret:
        return True
    try:
        expected = hmac.new(secret.encode('utf-8'), payload, hashlib.sha256).hexdigest()
        if signature.startswith("sha256="):
            signature = signature[7:]
        return hmac.compare_digest(expected, signature)
    except:
        return False

def procesar_evento_fintoc(evento: dict) -> dict:
    tipo_evento = evento.get("type", "")
    data = evento.get("data", {})
    resultado = {"procesado": False, "tipo": tipo_evento, "mensaje": ""}
    
    if tipo_evento in ["account.refresh_intent.succeeded", "link.refresh_intent.succeeded"]:
        resultado["procesado"] = True
        resultado["mensaje"] = f"Actualizado: {data.get('refreshed_object_id', 'N/A')}"
    elif tipo_evento == "movement.created":
        resultado["procesado"] = True
        agregar_movimiento(data)
    return resultado

def agregar_movimiento(movimiento: dict):
    global MOVIMIENTOS_HOY
    hoy = date.today().isoformat()
    
    if MOVIMIENTOS_HOY.get("fecha") != hoy:
        MOVIMIENTOS_HOY = {"fecha": hoy, "entradas": [], "salidas": [], "ultima_actualizacion": None}
    
    amount = movimiento.get("amount", 0)
    mov_data = {
        "id": movimiento.get("id"),
        "amount": abs(amount),
        "description": movimiento.get("description", ""),
        "post_date": movimiento.get("post_date"),
        "sender": (movimiento.get("sender_account") or {}).get("holder_name", ""),
    }
    
    if amount > 0:
        MOVIMIENTOS_HOY["entradas"].append(mov_data)
    else:
        MOVIMIENTOS_HOY["salidas"].append(mov_data)
    MOVIMIENTOS_HOY["ultima_actualizacion"] = datetime.now().isoformat()

def get_entradas_hoy() -> List[dict]:
    if MOVIMIENTOS_HOY.get("fecha") != date.today().isoformat():
        return []
    return MOVIMIENTOS_HOY.get("entradas", [])

def get_total_entradas_hoy() -> int:
    return sum(m.get("amount", 0) for m in get_entradas_hoy())

def get_resumen_hoy() -> dict:
    return {
        "fecha": MOVIMIENTOS_HOY.get("fecha"),
        "total_entradas": get_total_entradas_hoy(),
        "num_entradas": len(get_entradas_hoy()),
        "entradas": get_entradas_hoy()
    }

def set_movimientos_hoy(entradas: List[dict]):
    global MOVIMIENTOS_HOY
    MOVIMIENTOS_HOY = {
        "fecha": date.today().isoformat(),
        "entradas": entradas,
        "salidas": [],
        "ultima_actualizacion": datetime.now().isoformat()
    }
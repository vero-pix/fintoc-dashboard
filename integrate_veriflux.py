#!/usr/bin/env python3
"""
Script para integrar VeriFlux en el dashboard CathPro.
Ejecutar desde: /Users/veronicavelasquez/Desktop/DEVS/cathpro-dashboard/

Uso:
    python integrate_veriflux.py
"""

import re
import shutil
from datetime import datetime

def main():
    # Backup
    backup_name = f"app_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
    
    # Leer archivo original (app_backup.py o app.py)
    try:
        with open('app_backup.py', 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"✓ Leído app_backup.py")
    except FileNotFoundError:
        with open('app.py', 'r', encoding='utf-8') as f:
            content = f.read()
        shutil.copy('app.py', backup_name)
        print(f"✓ Backup creado: {backup_name}")
    
    # ============================================
    # CAMBIO 1: Configuración VeriFlux
    # ============================================
    old_chat_import = '''# Importar asistente de chat (lazy load para evitar error si no hay API key)
try:
    from chat_assistant import CathProAssistant
    CHAT_ENABLED = True
except Exception as e:
    print(f"Chat assistant no disponible: {e}")
    CHAT_ENABLED = False

load_dotenv()'''
    
    new_chat_import = '''# Importar asistente de chat (legacy - fallback si VeriFlux no disponible)
try:
    from chat_assistant import CathProAssistant
    CHAT_LOCAL_ENABLED = True
except Exception as e:
    print(f"Chat assistant local no disponible: {e}")
    CHAT_LOCAL_ENABLED = False

load_dotenv()

# ============================================
# CONFIGURACIÓN VERIFLUX BACKEND
# ============================================
VERIFLUX_BACKEND_URL = os.getenv("VERIFLUX_BACKEND_URL", "https://veriflux.onrender.com")
VERIFLUX_ENABLED = True  # Usar VeriFlux por defecto'''
    
    if old_chat_import in content:
        content = content.replace(old_chat_import, new_chat_import)
        print("✓ Cambio 1: Configuración VeriFlux agregada")
    else:
        print("⚠ Cambio 1: Patrón no encontrado (puede que ya esté aplicado)")
    
    # ============================================
    # CAMBIO 2: NAV con enlace a VeriCosas
    # ============================================
    old_nav = '''<a href="/nomina/scotiabank?key=KEY_PLACEHOLDER" class="NAV_NOMINA" style="background:#dc3545;color:white">Nomina Scotiabank</a>'''
    
    new_nav = '''<a href="/chat?key=KEY_PLACEHOLDER" class="NAV_CHAT" style="background:#55b245;color:white">VeriCosas</a>
    <a href="/nomina/scotiabank?key=KEY_PLACEHOLDER" class="NAV_NOMINA" style="background:#dc3545;color:white">Nomina</a>'''
    
    if old_nav in content:
        content = content.replace(old_nav, new_nav)
        print("✓ Cambio 2: NAV actualizado con VeriCosas")
    else:
        print("⚠ Cambio 2: NAV ya modificado o patrón diferente")
    
    # ============================================
    # CAMBIO 3: Rutas de chat (/chat y /chat/api)
    # ============================================
    old_chat_ui = '''@app.route('/chat')
def chat_ui():
    """Interfaz de chat"""
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return "<script>alert('Contraseña incorrecta');window.location='/';</script>"
    
    if not CHAT_ENABLED:
        return "<h1>Chat no disponible - Falta configurar ANTHROPIC_API_KEY</h1>"
    
    nav = NAV_HTML.replace('KEY_PLACEHOLDER', key).replace('NAV_SALDOS', '').replace('NAV_TESORERIA', '').replace('NAV_PIPELINE', '').replace('NAV_ANUAL', '').replace('NAV_SEMANAL', '')
    logo_b64 = get_logo_base64()

    html = CHAT_HTML.replace('LOGO_BASE64', logo_b64)
    html = html.replace('NAV_PLACEHOLDER', nav)
    html = html.replace('KEY_PLACEHOLDER', key)
    
    return html


@app.route('/chat/api', methods=['POST'])
def chat_api():
    """API de chat"""
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return jsonify({'error': 'No autorizado'}), 401
    
    if not CHAT_ENABLED:
        return jsonify({'error': 'Chat no disponible - módulo no cargado'}), 503
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No se recibió JSON'}), 400
            
        pregunta = data.get('pregunta', '')
        
        if not pregunta:
            return jsonify({'error': 'Pregunta vacía'}), 400
        
        # Verificar API key
        if not os.getenv('ANTHROPIC_API_KEY'):
            return jsonify({'error': 'ANTHROPIC_API_KEY no configurada en servidor'}), 503
        
        # Crear instancia y responder
        assistant = CathProAssistant()
        respuesta = assistant.responder(pregunta)
        
        return jsonify({'respuesta': respuesta})
        
    except Exception as e:
        import traceback
        print(f"Error en chat_api: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Error: {str(e)}'}), 500'''
    
    new_chat_routes = '''@app.route('/chat')
def chat_ui():
    """Interfaz de chat VeriCosas - conecta a VeriFlux backend"""
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return "<script>alert('Contraseña incorrecta');window.location='/';</script>"
    
    nav = NAV_HTML.replace('KEY_PLACEHOLDER', key).replace('NAV_SALDOS', '').replace('NAV_TESORERIA', '').replace('NAV_PIPELINE', '').replace('NAV_ANUAL', '').replace('NAV_SEMANAL', '')
    logo_b64 = get_logo_base64()

    html = CHAT_HTML.replace('LOGO_BASE64', logo_b64)
    html = html.replace('NAV_PLACEHOLDER', nav)
    html = html.replace('KEY_PLACEHOLDER', key)
    
    return html


@app.route('/chat/api', methods=['POST'])
def chat_api():
    """API de chat - proxy a VeriFlux backend con fallback local"""
    key = request.args.get('key', '')
    if key != TABLERO_PASSWORD:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No se recibió JSON'}), 400
            
        pregunta = data.get('pregunta', '')
        
        if not pregunta:
            return jsonify({'error': 'Pregunta vacía'}), 400
        
        # ============================================
        # OPCIÓN 1: VeriFlux Backend (preferido)
        # ============================================
        if VERIFLUX_ENABLED:
            try:
                # Llamar al backend VeriFlux
                veriflux_response = requests.post(
                    f"{VERIFLUX_BACKEND_URL}/api/ask",
                    json={"question": pregunta},
                    timeout=60  # Timeout alto porque VeriFlux puede hacer múltiples tool calls
                )
                
                if veriflux_response.status_code == 200:
                    result = veriflux_response.json()
                    
                    # VeriFlux responde con estructura: {success, tipo, titulo, insight, datos?, kpis?}
                    if result.get('success', True):
                        return jsonify({
                            'success': True,
                            'tipo': result.get('tipo', 'resumen'),
                            'titulo': result.get('titulo', 'VeriFlux'),
                            'insight': result.get('insight', ''),
                            'datos': result.get('datos'),
                            'kpis': result.get('kpis'),
                            'respuesta': result.get('insight', '')  # Fallback para compatibilidad
                        })
                    else:
                        # VeriFlux reportó error
                        raise Exception(result.get('error', 'Error en VeriFlux'))
                else:
                    raise Exception(f"VeriFlux HTTP {veriflux_response.status_code}")
                    
            except requests.exceptions.Timeout:
                print("VeriFlux timeout, intentando fallback local...")
            except requests.exceptions.ConnectionError:
                print("VeriFlux no disponible, intentando fallback local...")
            except Exception as e:
                print(f"Error VeriFlux: {e}, intentando fallback local...")
        
        # ============================================
        # OPCIÓN 2: Fallback a asistente local
        # ============================================
        if CHAT_LOCAL_ENABLED:
            try:
                if not os.getenv('ANTHROPIC_API_KEY'):
                    return jsonify({'error': 'ANTHROPIC_API_KEY no configurada'}), 503
                
                assistant = CathProAssistant()
                respuesta = assistant.responder(pregunta)
                
                return jsonify({
                    'success': True,
                    'respuesta': respuesta,
                    'fuente': 'local'  # Indicar que usó el fallback
                })
            except Exception as e:
                return jsonify({'error': f'Error local: {str(e)}'}), 500
        
        # Ninguna opción disponible
        return jsonify({'error': 'Servicio de chat no disponible'}), 503
        
    except Exception as e:
        import traceback
        print(f"Error en chat_api: {e}")
        traceback.print_exc()
        return jsonify({'error': f'Error: {str(e)}'}), 500'''
    
    if old_chat_ui in content:
        content = content.replace(old_chat_ui, new_chat_routes)
        print("✓ Cambio 3: Rutas /chat y /chat/api actualizadas")
    else:
        print("⚠ Cambio 3: Rutas de chat no encontradas (verificar manualmente)")
    
    # Guardar resultado
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("\n" + "="*50)
    print("✓ Integración completada: app.py actualizado")
    print("="*50)
    print("\nPróximos pasos:")
    print("1. Probar local: python app.py")
    print("2. Abrir: http://localhost:5001/chat?key=Ale234de")
    print("3. Si funciona: git add app.py && git commit -m 'VeriFlux integration' && git push")

if __name__ == '__main__':
    main()

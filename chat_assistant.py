"""
Asistente Virtual CathPro - Cash Flow & Contabilidad
MVP v1.0
"""

import os
import json
from dotenv import load_dotenv
from anthropic import Anthropic
from skualo_client import SkualoClient
from skualo_cashflow import SkualoCashFlow
from datetime import datetime
from skualo_bancos import SkualoBancosClient

load_dotenv()


class CathProAssistant:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY no configurada")
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-20250514"
        
        # Clientes de datos
        # Clientes de datos
        self.skualo_bancos = SkualoBancosClient()
        self.skualo = SkualoClient()
        self.cashflow = SkualoCashFlow()
        
        # System prompt
        self.system_prompt = """Eres el asistente financiero virtual de CathPro, una empresa de servicios industriales en Chile.

Tu rol es responder consultas sobre:
1. Saldos bancarios (datos de Skualo Bancos)
2. Cuentas por cobrar y pagar (datos de Skualo)
3. Cash flow y proyecciones (datos combinados)
4. Pagos recurrentes configurados

REGLAS:
- Responde siempre en español chileno profesional
- Usa formato de moneda chilena: $1.234.567
- Sé conciso y directo
- Si no tienes el dato específico, indícalo claramente
- Cuando muestres listas, usa máximo 5-7 items
- Redondea montos grandes a millones cuando sea apropiado (ej: $150M)

CONTEXTO DE LA EMPRESA:
- Moneda principal: CLP (pesos chilenos)
- También maneja USD y EUR
- Clientes principales: COPEC, CODELCO, ENAP, COLLAHUASI, etc.
- Pagos se concentran los viernes (regla de tesorería)
"""

    def _obtener_contexto_datos(self):
        """Obtiene snapshot actual de todos los datos financieros"""
        try:
            # Saldos bancarios (Ahora via Skualo Bancos o Balance Tributario)
            # Usaremos Balance Tributario usando la misma logica de App.py para saldos disponibles
            saldos_contables = self.skualo.get_balance_tributario()
             
            mapa_bancos = {
                "1102002": {"nombre": "Santander", "moneda": "CLP"},
                "1102003": {"nombre": "BCI", "moneda": "CLP"},
                "1102004": {"nombre": "Scotiabank", "moneda": "CLP"},
                "1102005": {"nombre": "Banco de Chile", "moneda": "CLP"},
                "1102013": {"nombre": "Bice", "moneda": "CLP"},
            }

            balances = []
            for item in saldos_contables:
                id_cta = item.get("idCuenta")
                if id_cta in mapa_bancos:
                    info = mapa_bancos[id_cta]
                    balances.append({
                        "banco": info["nombre"],
                        "disponible": item.get("activos", 0) - item.get("pasivos", 0),
                        "moneda": info["moneda"]
                    })
            
            total_clp = sum(b['disponible'] for b in balances if b['moneda'] == 'CLP')
            total_usd = sum(b['disponible'] for b in balances if b['moneda'] == 'USD')
            total_eur = sum(b['disponible'] for b in balances if b['moneda'] == 'EUR')
            
            # Saldos Skualo
            saldos = self.skualo.get_saldos_cuentas()
            
            # CxC detalle
            cxc = self.cashflow.get_cxc_detalle()
            cxc_top = sorted(cxc, key=lambda x: x['saldo'], reverse=True)[:10]
            
            # CxP detalle
            cxp = self.cashflow.get_cxp_detalle()
            cxp_top = sorted(cxp, key=lambda x: x['saldo'], reverse=True)[:10]
            
            # Resumen semana
            resumen = self.cashflow.get_resumen_semana()
            
            # Recurrentes
            recurrentes = self.cashflow.config.get('recurrentes', [])
            total_recurrentes = sum(r['monto'] for r in recurrentes)
            
            # Construir contexto
            contexto = f"""
DATOS ACTUALIZADOS AL {datetime.now().strftime('%d/%m/%Y %H:%M')}

=== SALDOS BANCARIOS (Skualo) ===
Total CLP: ${total_clp:,.0f}
Total USD: ${total_usd:,.2f}
Total EUR: €{total_eur:,.0f}

Detalle por banco:
"""
            for b in balances:
                if b['moneda'] == 'CLP':
                    contexto += f"- {b['banco']}: ${b['disponible']:,.0f} CLP\n"
                elif b['moneda'] == 'USD':
                    contexto += f"- {b['banco']}: ${b['disponible']:,.2f} USD\n"
                elif b['moneda'] == 'EUR':
                    contexto += f"- {b['banco']}: €{b['disponible']:,.0f} EUR\n"

            contexto += f"""
=== CUENTAS SKUALO ===
Fondos Mutuos: ${saldos['fondos_mutuos']:,.0f}
Por Cobrar (CxC): ${saldos['por_cobrar']:,.0f}
Por Pagar Nacional: ${saldos['por_pagar_nacional']:,.0f}
Por Pagar Internacional: ${saldos['por_pagar_internacional']:,.0f}
Por Pagar Total: ${saldos['por_pagar_total']:,.0f}
Posición Neta (CxC - CxP): ${saldos['por_cobrar'] - saldos['por_pagar_total']:,.0f}

=== TOP 10 CUENTAS POR COBRAR ===
"""
            for i, c in enumerate(cxc_top, 1):
                fecha_str = c['fecha_cobro_esperada'].strftime('%d/%m') if c['fecha_cobro_esperada'] else 'S/F'
                contexto += f"{i}. {c['cliente']}: ${c['saldo']:,.0f} (cobro esperado: {fecha_str}, {c['dias_pago_config']} días)\n"

            contexto += f"""
=== TOP 10 CUENTAS POR PAGAR ===
"""
            for i, p in enumerate(cxp_top, 1):
                fecha_str = p['vencimiento'].strftime('%d/%m') if p['vencimiento'] else 'S/F'
                vencido = " [VENCIDO]" if p['vencido'] else ""
                contexto += f"{i}. {p['proveedor']}: ${p['saldo']:,.0f} (vence: {fecha_str}){vencido}\n"

            contexto += f"""
=== RESUMEN PRÓXIMOS 7 DÍAS ===
Entradas esperadas: ${resumen['total_entradas']:,.0f}
Salidas programadas: ${resumen['total_salidas']:,.0f}
Flujo neto semana: ${resumen['flujo_neto']:,.0f}
Día más crítico: {resumen['dia_critico']['fecha'].strftime('%d/%m/%Y')} (neto: ${resumen['dia_critico']['neto']:,.0f})

=== PAGOS RECURRENTES MENSUALES ===
Total mensual: ${total_recurrentes:,.0f}
"""
            for r in sorted(recurrentes, key=lambda x: x['dia']):
                contexto += f"- Día {r['dia']}: {r['concepto']} - ${r['monto']:,.0f}\n"

            return contexto
            
        except Exception as e:
            return f"Error obteniendo datos: {str(e)}"

    def responder(self, pregunta: str) -> str:
        """Procesa una pregunta y retorna la respuesta"""
        try:
            # Obtener contexto actualizado
            contexto = self._obtener_contexto_datos()
            
            # Construir mensaje
            mensaje = f"""
{contexto}

=== PREGUNTA DEL USUARIO ===
{pregunta}

Responde de forma clara y concisa basándote en los datos proporcionados.
"""
            
            # Llamar a Claude
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                system=self.system_prompt,
                messages=[{"role": "user", "content": mensaje}]
            )
            
            return response.content[0].text
            
        except Exception as e:
            return f"Error procesando consulta: {str(e)}"


# =============================================================================
# TEST
# =============================================================================

if __name__ == "__main__":
    assistant = CathProAssistant()
    
    # Preguntas de prueba
    preguntas = [
        "¿Cuánto tenemos en caja hoy?",
        "¿Quiénes son los 5 clientes que más nos deben?",
        "¿Qué pagos tenemos esta semana?",
        "¿Cuál es la posición neta?",
    ]
    
    for p in preguntas[:1]:  # Solo la primera para test rápido
        print(f"\n{'='*60}")
        print(f"PREGUNTA: {p}")
        print('='*60)
        respuesta = assistant.responder(p)
        print(respuesta)

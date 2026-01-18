# ESTADO DEL PROYECTO - CASHFLOW DASHBOARD (✅ MIGRADO A SKUALO)
## Documentación de avances y pendientes - 16 Enero 2026

---

## RESUMEN EJECUTIVO

Sistema completo de gestión financiera desplegado en Render con múltiples módulos:
- **Saldos**: Integración Fintoc + Skualo CxC/CxP
- **Tesorería**: Movimientos bancarios del día con indicadores de tendencia (flechitas)
- **Pipeline**: Trazabilidad SOLI → OC → Factura (corregido 16-ene)
- **Cash Flow Semanal/Anual**: Proyección con forecast Google Sheets
- **Nómina Scotiabank**: Exportación pagos proveedores

**URL Producción**: https://cathpro-dashboard.onrender.com

---

## NOTA IMPORTANTE (16-ENE-2026)
**Saldos USD/EUR**: Skualo devuelve **todos los saldos en CLP** en su Balance Tributario, incluso para cuentas en dólares o euros.
- **Solución actual**: 
    - Se muestran los montos grandes en **CLP**.
    - Se añade "Total estimativo: US$ X" (o €) en pequeño bajo el monto en peso.
    - Se usa TC fijo: USD 970, EUR 1020.
- **Feedback usuario**: "Fintoc era más confiable" para esto. Se mantiene la solución Skualo por solicitud, pero se anota esta limitación.

---

## 1. ARQUITECTURA DE DATOS

### Fuentes integradas:
| Fuente | Qué aporta | Estado |
|--------|------------|--------|
| **Fintoc API** | Saldo bancario real CLP/USD/EUR | ❌ Eliminado (Fase 3) |
| **Fintoc Webhook** | Movimientos bancarios tiempo real | ❌ Eliminado (Fase 3) |
| **Skualo CxC** | Facturas emitidas + fecha cobro | ✅ Integrado |
| **Skualo CxP** | Facturas por pagar + vencimientos | ✅ Integrado |
| **Skualo Documentos** | Pipeline SOLI/OC/OCX | ✅ Corregido 16-ene |
| **Skualo Bancos** | Movimientos bancarios Skualo | ✅ Integrado |
| **Google Sheets** | Forecast 2026 (Compromiso/Forecast) | ✅ Integrado |
| **Config Recurrentes** | Pagos fijos mensuales | ✅ En app.py |

### Estructura de archivos:
```
/Desktop/DEVS/Fintoc/
├── app.py                      # App principal Flask (todas las rutas)
## 1. Integración de Fuentes de Datos (Status: ✅ Completo)

### A. Skualo (ERP & Bancos) - ✅ INTEGRADO
- **Estado**: Fuente PRINCIPAL de datos.
- **Módulos**:
    - `skualo_client.py`: Balances contables y generales.
    - `skualo_bancos.py`: Movimientos bancarios reales (API Bancos).
    - `skualo_cashflow.py`: Proyección de flujo de caja.
    - `skualo_documentos.py`: Detalle de documentos pendientes (DTEs).
    - `skualo_auth.py`: Autenticación y renovación de tokens.

### B. Fintoc (Bancos Legacy) - ❌ DEPRECADO
- **Estado**: ELIMINADO/DEPRECADO.
- **Razón**: Reemplazado por Skualo Bancos.
- **Código**: Eliminado de `app.py`, `main.py`, `alerts.py`.

### C. Google Sheets (Metas & Forecast) - ✅ ACTIVO
- **Estado**: Integrado.
- **Uso**: Metas de venta, forecast comercial.
├── chat_assistant.py           # Asistente virtual VeriCosas
├── saldos_historicos.json      # Historial saldos para tendencias
├── maestro_proveedores.json    # Datos bancarios proveedores
├── requirements.txt            # Dependencias Python
├── render.yaml                 # Config deployment Render
└── ESTADO_PROYECTO_CASHFLOW.md # Este archivo
```

---

## 2. MÓDULOS DEL DASHBOARD

### 2.1 Saldos (/tablero)
- Saldos bancarios Fintoc (CLP, USD, EUR)
- Fondos mutuos Skualo
- CxC y CxP totales
- Posición neta

### 2.2 Tesorería (/tesoreria) ✅ COMPLETADO 16-ENE
- Movimientos bancarios del día (Skualo Bancos)
- **Indicadores de tendencia**: Flechitas ↑↓ comparando con día anterior
- Top 10 ingresos/egresos
- Vinculación egresos con CxP
- Historial guardado en `saldos_historicos.json`

**Implementación tendencias:**
```python
# En app.py líneas 994-1073
- get_saldos_historicos() - Lee JSON histórico
- guardar_saldo_historico() - Guarda saldo con timestamp
- comparar_saldo_anterior() - Calcula diferencia y porcentaje
```

### 2.3 Pipeline (/pipeline) ✅ CORREGIDO 16-ENE
Muestra compromisos pendientes en la cadena de documentos.

**Problema anterior:**
- Mostraba 100 SOLIs, 99 OCs, 56 OCXs
- Todos decían "Sin proveedor"
- No mostraba proyectos
- No detectaba documentos ya procesados

**Corrección aplicada en `skualo_documentos.py`:**
| Campo | Antes | Ahora |
|-------|-------|-------|
| Proveedor | `razonSocial` (vacío) | `auxiliar` ✅ |
| Proyecto | No consultaba | `proyecto` del detalle ✅ |
| Trazabilidad | `documentoReferenciado` | `detalles[].cerrado` ✅ |

**Resultado después de corrección:**
| Tipo | Antes | Ahora |
|------|-------|-------|
| SOLIs sin OC | 100 | **18** |
| OCs sin Factura | 99 | **45** |
| OCXs sin Invoice | 56 | **12** |

**Lógica de trazabilidad:**
- Un documento está "pendiente" si `detalles[].cerrado == false`
- Si TODOS los detalles tienen `cerrado: true`, ya fue procesado
- Ejemplo: SOLI 336 tiene OC 2698 → `cerrado: true` → no aparece en pipeline

### 2.4 Cash Flow Anual (/cashflow)
- Proyección 2026 desde Google Sheets
- Lógica: Q1 = Solo Compromiso | Q2-Q4 = Forecast (G > E)
- Barras apiladas: Apalancada vs Venta Nueva
- KPIs de certeza por mes

### 2.5 Cash Flow Semanal (/cashflow/semanal)
- Proyección 7 días
- Entradas: CxC Skualo con días de pago por cliente
- Salidas: Recurrentes + CxP próximos 7 días
- Gráfico barras + línea de saldo
- Botón acceso a VeriCosas (chat)

### 2.6 Nómina Scotiabank (/nomina/scotiabank)
- Lista CxP para pago el próximo viernes
- Cruza con maestro proveedores (datos bancarios)
- Exporta Excel formato macro Scotiabank

### 2.7 Chat VeriCosas (/chat)
- Asistente virtual para consultas financieras
- Usa `chat_assistant.py` con Anthropic API
- Consultas sobre saldos, CxC, CxP, etc.

---

## 3. CONFIGURACIÓN RECURRENTES

| Día | Concepto | Monto | Criticidad |
|-----|----------|-------|------------|
| 1 | Crédito Hipotecario | $1.0M | Normal |
| 5 | ARRIENDO OFICINA | $1.8M | Normal |
| 5 | Leasing BCI1 | $3.2M | Normal |
| 7 | PREVIRED | $32.0M | Alto |
| 7 | Leasing Progreso | $1.5M | Normal |
| 10 | Leasing Oficina | $1.2M | Normal |
| 15 | LEASING BCI | $3.2M | Normal |
| 15 | Leaseback | $1.8M | Normal |
| **16** | **SII - IVA** | **$115.0M** | **CRÍTICO** |
| 19 | Crédito Santander | $6.0M | Normal |
| **27** | **REMUNERACIONES** | **$105.0M** | **CRÍTICO** |
| 28 | Honorarios | $2.1M | Normal |
| | **TOTAL MENSUAL** | **$274.0M** | |

---

## 4. DÍAS DE PAGO POR CLIENTE

| Cliente | Días |
|---------|------|
| CENTINELA | 10d |
| COLLAHUASI | 10d |
| COPEC | 15d |
| PELAMBRES | 15d |
| ENAP | 20d |
| CODELCO | 30d |
| TECHINT | 30d |
| MONTEC | 60d |

---

## 5. API SKUALO - ENDPOINTS CLAVE

### Documentos
```
GET /documentos?search=IDTipoDocumento eq SOLI
GET /documentos/{idDocumento}  # Detalle con detalles[].cerrado
GET /documentos/{id}/posteriores/{idDetalle}  # Docs referenciados
```

### Campos importantes documento detalle:
- `auxiliar`: Nombre proveedor
- `idAuxiliar`: RUT proveedor
- `proyecto`: Nombre proyecto
- `detalles[].cerrado`: true si ya tiene doc posterior
- `detalles[].referenciasPosteriores.href`: Link a docs posteriores

### Contabilidad
```
GET /contabilidad/reportes/balancetributario/{YYYYMM}
```

### Movimientos Bancarios
```
GET /tesoreria/movimientosbancarios?IDCuentaCorreo={id}&Fecha={YYYY-MM-DD}
```

---

## 6. VARIABLES DE ENTORNO (Render)

```
SKUALO_TOKEN=...
SKUALO_USERNAME=...
SKUALO_PASSWORD=...
DASHBOARD_PASSWORD=cathpro2024
ANTHROPIC_API_KEY=sk-ant-xxxxx
# FINTOC variables eliminadas en Fase 4
```

---

## 7. DEPLOYMENT

### Render
- **URL**: https://fintoc-dashboard.onrender.com
- **Repo**: Conectado a GitHub (auto-deploy en push)
- **Build**: `pip install -r requirements.txt`
- **Start**: `gunicorn app:app`

### Local
```bash
cd ~/Desktop/DEVS/Fintoc
source venv_new/bin/activate
python app.py
# Acceder: http://127.0.0.1:5001
```

---

## 8. COLORES CATHPRO

```css
--verde-cathpro: #55b245;    /* Entradas, positivo */
--naranja-cathpro: #f46302;  /* Alertas, OCX */
--rojo: #e74c3c;             /* Salidas, crítico */
--fondo-oscuro: #242625;     /* Header */
--fondo-claro: #f4f4f4;      /* Body */
--azul: #3498db;             /* Info, EUR */
--morado: #9b59b6;           /* Fondos mutuos */
```

---

## 9. PENDIENTES

### Alta prioridad:
- [ ] Token Skualo vence frecuentemente - implementar refresh automático
- [ ] Optimizar Pipeline (hace muchas llamadas API, puede ser lento)

### Media prioridad:
- [ ] Webhook Fintoc: procesar y mostrar movimientos reales vs Skualo
- [ ] Alertas email cuando saldo < umbral

### Completados hoy (16-ene-2026):
- [✅] Scotiabank muestra $0 - Ahora detecta y muestra cuentas USD/EUR correctamente
- [✅] Cambiar "Saldo Neto" por "Variación Neta" en Tesorería
- [✅] Top Ingresos: mostrar cliente/factura en vez de código glosa

### Baja prioridad:
- [ ] Escenarios what-if en cash flow
- [x] Dashboard móvil optimizado (CSS table-responsive)
- [x] Exportar reportes PDF (/export/pdf)

---

## 10. HISTORIAL DE CAMBIOS

| Fecha | Cambio |
|-------|--------|
| 13-ene-2026 | Proyecto inicial, dashboard básico |
| 14-ene-2026 | Integración Fintoc saldos |
| 15-ene-2026 | Cash Flow semanal/anual con Google Sheets |
| 16-ene-2026 | **Tesorería con tendencias (flechitas)** |
| 16-ene-2026 | **Pipeline corregido: trazabilidad SOLI→OC→Factura** |
| 16-ene-2026 | **Tesorería mejorada**: Saldos USD/EUR, "Variación Neta", Top Ingresos con cliente/factura |

---

## 11. CÓMO RETOMAR

Al iniciar nueva conversación con Claude, indicar:

> "Lee ESTADO_PROYECTO_CASHFLOW.md en ~/Desktop/DEVS/Fintoc para contexto del proyecto Cash Flow CathPro"

O copiar sección relevante si es tema específico.

---

*Última actualización: 16-ene-2026 16:30*

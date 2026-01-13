# ESTADO PROYECTO CASH FLOW CATHPRO
## Documentación de avances y pendientes - 13 Enero 2026

---

## RESUMEN EJECUTIVO

Se ha desarrollado un sistema de proyección de cash flow a 90 días que integra múltiples fuentes de datos. El dashboard HTML está funcional con las 3 vistas (semanal, mensual, anual). Quedan pendientes ajustes de UX y la integración dinámica del saldo Fintoc.

---

## 1. ARQUITECTURA DE DATOS

### Fuentes integradas:
| Fuente | Qué aporta | Estado |
|--------|------------|--------|
| **Fintoc API** | Saldo bancario real CLP | ⚠️ Hardcodeado $160M (debe ser dinámico) |
| **Skualo CxC** | Facturas emitidas + fecha cobro estimada | ✅ Integrado |
| **Skualo CxP** | Facturas por pagar + vencimientos | ✅ Integrado |
| **Config Recurrentes** | Pagos fijos mensuales (IVA, sueldos, etc.) | ✅ Integrado |
| **Dashboard Facturación** | Forecast ingresos futuros | ✅ Integrado en cashflow_data_v2.json |

### Archivos generados:
```
/Desktop/DEVS/Fintoc/
├── cashflow_data.json          # Proyección SOLO Skualo (va a negativo)
├── cashflow_data_v2.json       # Proyección Skualo + Forecast (positivo)
├── cashflow_config.json        # Config días pago + recurrentes
├── cashflow_dashboard.html     # Dashboard funcional con Chart.js
├── fintoc_client.py            # Cliente API Fintoc
├── generate_cashflow_v2.py     # Script generador proyección
└── ESTADO_PROYECTO_CASHFLOW.md # Este archivo
```

---

## 2. PROYECCIÓN 90 DÍAS - DATOS REALES

### Solo Skualo (cashflow_data.json):
| Métrica | Valor | Problema |
|---------|-------|----------|
| Saldo inicial | $160M | Hardcodeado |
| Entradas 90d | $382M | Solo CxC enero, feb-abril = $0 |
| Salidas 90d | $857M | Recurrentes siguen todos los meses |
| Saldo final | **-$315M** | ❌ Negativo porque falta forecast |
| Días alerta | 45 | 50% del horizonte |

### Skualo + Forecast (cashflow_data_v2.json):
| Métrica | Valor | Mejora |
|---------|-------|--------|
| Saldo inicial | $160M | Hardcodeado |
| Entradas 90d | $1,311M | +$929M del forecast |
| Salidas 90d | $857M | Sin cambio |
| Saldo final | **$660M** | ✅ Positivo |
| Días alerta | 0 | ✅ Sin alertas |

---

## 3. VISTA MENSUAL - DATOS REALES

### Sin Forecast (problema):
| Mes | Entradas | Salidas | Neto | Saldo |
|-----|----------|---------|------|-------|
| Ene 2026 | $376M | $265M | +$111M | $271M |
| Feb 2026 | **$0M** | $286M | -$286M | -$15M |
| Mar 2026 | $6M | $268M | -$262M | -$277M |
| Abr 2026 | $0M | $38M | -$38M | -$315M |

### Con Forecast (solución):
| Mes | Entradas | Salidas | Neto | Saldo |
|-----|----------|---------|------|-------|
| Ene 2026 | $413M | $265M | +$148M | $308M |
| Feb 2026 | $408M | $286M | +$122M | $430M |
| Mar 2026 | $491M | $268M | +$223M | $653M |
| Abr 2026 | $7M | $38M | -$31M | $660M |

---

## 4. PAGOS RECURRENTES CONFIGURADOS

| Día | Concepto | Monto | Criticidad |
|-----|----------|-------|------------|
| 5 | ARRIENDO OFICINA | $1.8M | Normal |
| 5 | Leasing BCI1 | $3.2M | Normal |
| 7 | PREVIRED | $32.0M | Alto |
| 10 | Leasing Oficina | $1.2M | Normal |
| 15 | LEASING BCI | $3.2M | Normal |
| 15 | Leaseback | $1.8M | Normal |
| **16** | **SII - IVA** | **$115.0M** | **CRÍTICO** |
| **27** | **REMUNERACIONES** | **$105.0M** | **CRÍTICO** |
| | **TOTAL MENSUAL** | **$263.2M** | |

---

## 5. DÍAS DE PAGO POR CLIENTE

| Cliente | Días | Riesgo |
|---------|------|--------|
| CENTINELA | 10d | Bajo |
| COLLAHUASI | 10d | Bajo |
| COPEC | 15d | Bajo |
| MINERA LOS PELAMBRES | 15d | Bajo |
| ENAP | 20d | Medio |
| CODELCO | 30d | Medio |
| TECHINT | 30d | Medio |
| MONTEC | 60d | Alto |
| **Default** | **30d** | - |

---

## 6. TOP MOVIMIENTOS IDENTIFICADOS

### Top 5 Entradas (90 días):
1. TECHINT CHILE S.A. - 29-ene - $96.8M (30d)
2. MINERA LOS PELAMBRES - 14-ene - $87.9M (15d)
3. ENAEX S.A. - 25-ene - $43.4M (30d)
4. ENAP - 29-ene - $35.5M (30d)
5. TECHINT CHILE S.A. - 29-ene - $31.1M (30d)

### Top 5 Salidas CxP (90 días):
1. DAIRYLAND ELECTRICAL - 13-feb - $15.8M
2. LATAM AIRLINES - 17-ene - $8.8M
3. ELECTRICIDAD GOBANTES - 29-ene - $6.7M
4. DAIRYLAND ELECTRICAL - 01-mar - $4.3M
5. CERANODE VV - 26-feb - $4.0M

---

## 7. DASHBOARD HTML - FUNCIONALIDADES

### Vista Semanal ✅
- [x] Alerta día crítico (banner naranja)
- [x] 4 KPIs con bordes de color
- [x] Gráfico barras + línea saldo (Chart.js)
- [x] Tags días de pago configurados
- [x] Tabla detalle diario
- [x] Top 5 Salidas / Top 3 Entradas

### Vista Mensual ✅
- [x] 4 KPIs mensuales
- [x] Gráfico por semana
- [x] Tabla detalle semanal
- [x] Tabla pagos recurrentes

### Vista Anual ✅
- [x] Banner informativo
- [x] Gráfico línea proyección
- [x] Tabla detalle mensual
- [x] Aging CxC / CxP

---

## 8. PENDIENTES PRIORITARIOS

### Alta prioridad:
- [ ] **Saldo inicial dinámico de Fintoc** (no hardcoded $160M)
- [ ] **Título**: "Cash Flow CathPro" (quitar "Dashboard")
- [ ] **Fechas**: Verificar que inicie desde fecha actual

### Media prioridad:
- [ ] Artefacto React con mismo estilo que HTML
- [ ] Vista anual en React (tabs no funcionan)
- [ ] Integrar datos de cashflow_data_v2.json (con forecast)

### Baja prioridad:
- [ ] Automatizar generación diaria
- [ ] Alertas por email cuando saldo < umbral
- [ ] Escenarios what-if

---

## 9. COLORES CATHPRO

```css
--verde-cathpro: #55b245;    /* Entradas, positivo */
--naranja-cathpro: #f7941d;  /* Línea saldo, alertas */
--rojo: #dc3545;             /* Salidas, crítico */
--fondo-oscuro: #242625;     /* Header */
--fondo-claro: #f5f5f5;      /* Body */
--azul: #17a2b8;             /* Info */
--morado: #6f42c1;           /* Saldo final */
```

---

## 10. PRÓXIMOS PASOS (Mañana)

1. Obtener saldo real de Fintoc
2. Actualizar dashboard con saldo dinámico
3. Corregir título y fechas
4. Validar vista anual funcione en artifact React
5. Deploy final

---

*Última actualización: 13-ene-2026 ~01:00*

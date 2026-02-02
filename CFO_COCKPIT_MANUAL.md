# 📔 Manual de Usuario: CathPro CFO Cockpit (v2.0)

Este documento resume las funcionalidades clave de tu tablero financiero para que siempre tengas el control, incluso si no lo abres en unos días.

## 1. KPIs Maestros (Sección Superior)
Hemos evolucionado de simples saldos a **Indicadores de Salud Operativa**:

*   **Liquidez Disponible (Caja + Divisas):** 
    *   Suma de todos tus bancos en CLP + tus saldos en USD y EUR convertidos a pesos.
    *   **Interactividad:** Haz clic para ver el desglose por banco y moneda.
    *   **Fuente:** Se actualiza automáticamente cada mañana con el "Dólar Observado" del Banco Central (vía mindicador.cl).

*   **Estado de Recaudación (CxC + FFMM):**
    *   Muestra el capital que está "en la calle" (Cuentas por Cobrar de Skualo) y tus inversiones líquidas (Fondos Mutuos).
    *   **Meta:** El protocolo está fijado en **13 días** para la conversión completa de caja.

*   **Compromisos de Pago (Pasivos):**
    *   Suma total de deudas proyectadas: Gastos Recurrentes (OpEx) + Facturas por Pagar (CXP) + Órdenes de Compra (OC/OCX) aprobadas.
    *   **Alerta:** Se muestra en rojo para monitorear la presión sobre la caja.

---

## 2. Alertas Ejecutivas y Benchmarking
Ubicadas justo debajo del encabezado para que sea lo primero que veas:

*   **Lógica de Mes Parcial:** Si el tablero detecta que no ha pasado el día **12** del mes siguiente, marcará los datos de Enero como **"(PARCIAL)"**.
*   **Comparativo 2025 vs 2026:**
    *   Haz clic en el texto naranja para comparar tus ingresos y márgenes actuales contra el **Benchmark de Auditoría 2025**.
    *   **Real vs Forecast:** En la columna de 2026 verás tu avance real y, justo debajo en gris, el **FCST** (Forecast) que deberías cumplir.

---

## 3. Panel de Ajustes (⚙️ El Mando del CFO)
Al final de la sección de alertas, tienes un ícono de engranaje que te permite:
*   **Modificar el Día de Cierre:** ¿La contabilidad cerró antes este mes? Cámbialo aquí.
*   **Ajustar Benchmarks:** Cambia las metas de ingresos o margen del 2025.
*   **Tasa de Cambio:** Puedes elegir entre modo **Automático** (Internet) o **Manual** (si quieres fijar tú el precio del dólar).

---

## 4. Próximos Pasos Técnicos (Roadmap)

### A. Subir a GitHub
Para respaldar tu código y trabajar en equipo:
1.  `git init` (si no está inicializado).
2.  `git add .`
3.  `git commit -m "CFO Cockpit v2 - Interactive & Dynamic Config"`
4.  `git remote add origin [URL_DE_TU_REPO]`
5.  `git push -u origin main`

### B. Visibilidad en Celular (Deployment)
Para que lo veas desde cualquier lugar:
*   **Opción Pro:** Desplegar en **Render.com** o **Railway.app**. Es gratuito/barato y te da un link (ej: `cathpro-cfo.render.com`) que abres en tu móvil.
*   **Seguridad:** Ya tenemos el sistema de password `?key=Ale234de` integrado.

### C. App / Vericosas TipoChat
*   **Integración:** Podemos crear un "webhook" para que cuando le preguntes a tu chat de Vericosas "¿Cuál es el Runway hoy?", el chat consulte los datos de este dashboard y te responda por voz o texto.

---
**Nota:** El archivo de configuración `dashboard_config.json` guarda tus ajustes, asegúrate de no borrarlo para no perder tus metas personalizadas.

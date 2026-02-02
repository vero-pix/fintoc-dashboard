# 📔 Manual de Usuario: CathPro CFO Cockpit (v2.5) 🚀

Este documento resume las funcionalidades clave de tu ecosistema financiero desplegado en la nube para que tengas control total desde cualquier lugar.

## 📱 1. Acceso en Movimiento (Mobile First)
Tu dashboard ya no vive solo en tu computador, ahora es una aplicación web de alto rendimiento:
*   **Link de Acceso:** `https://web-production-2bda3.up.railway.app/tablero?key=Ale234de`
*   **Tip Pro:** Abre el link en tu celular y selecciona **"Añadir a la pantalla de inicio"** para usarlo como una App nativa con ícono propio.
*   **Diseño:** Optimizado para lectura rápida en móvil con tipografía corporativa *Outfit*.

## ⚙️ 2. Sincronización e Inteligencia
El sistema es autónomo pero tú tienes el control final:
*   **Actualización Automática:** El servidor se despierta cada **6 horas** para consultar saldos en Fintoc y Skualo.
*   **Sincronización Forzada:** Si necesitas ver los saldos del minuto exacto, ve a **Ajustes de Gestión (⚙️)** y presiona **`Forzar Sincronización Bancaria`**. Esto obliga al sistema a llamar a los bancos inmediatamente.
*   **Filtros Inteligentes:** El sistema limpia automáticamente espacios en blanco y errores de copiado en tus llaves API para asegurar que la conexión nunca falle.

## 🔍 3. Diagnóstico del Sistema (Transparencia Total)
Al final de la página encontrarás el panel de **Diagnóstico del Sistema**. Es tu semáforo de salud técnica:
*   **API OK:** Confirma que el servidor tiene comunicación con Fintoc y Skualo.
*   **Cuentas Encontradas:** Te dice exactamente cuántos productos bancarios (CLP, USD, EUR) está leyendo el sistema.
*   **Logs de Error:** Si algo falla (ej: una clave expiró), aparecerá una alerta en rojo indicando el código técnico del error.

## 📧 4. Gestión de Reportes por Correo
El sistema envía un resumen ejecutivo a las 8:00 y 18:00 hrs:
*   **Destinatarios:** Configurados dinámicamente desde el entorno de producción.
*   **Actualizaciones:** Para añadir o quitar personas, se modifica la variable `EMAIL_TO` en el panel de control de Railway.

---

## 🛠️ 5. Mantenimiento y Seguridad
*   **Railway.app:** Tu servidor vive en Railway. Si el dashboard no carga, revisa el estado del proyecto en tu panel de Railway.
*   **Variables de Entorno:** Nunca compartas tu `FINTOC_SECRET_KEY` o tu `DASHBOARD_PASSWORD`.
*   **Persistencia:** Tus ajustes de metas, días de cierre y tasas manuales se guardan en el servidor y no se pierden al reiniciar.

---
**CathPro Financial Intelligence Ecosystem** | Documentación actualizada al 02-02-2026

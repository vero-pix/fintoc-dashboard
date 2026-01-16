# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

VeriFlux is a financial assistant backend for CathPro that integrates Claude AI with the Skualo accounting API. The backend processes natural language financial queries and returns structured data with visualizations and insights.

## Development Commands

```bash
# Install dependencies
npm install

# Configure environment variables
# Copy .env.example to .env and fill in your API keys
cp .env.example .env

# Start production server (port 3001 by default)
npm start

# Start development server with auto-reload
npm dev
```

## Architecture

### Single-File Backend Structure

The entire backend is contained in `server.js` with these main components:

1. **Tool Definitions (lines 16-43)**: Claude function calling tools for financial data
   - `consultar_resultados`: Income statement (EERR) with revenues, costs, expenses
   - `consultar_cxc`: Accounts receivable (pending client payments)
   - `consultar_cxp`: Accounts payable (pending supplier payments)
   - `consultar_remuneraciones`: Payroll data with employee costs, top 5 by cost

2. **Tool Execution (lines 36-223)**: `ejecutarHerramienta()` fetches data from Skualo API and returns structured results with metadata for visualization
   - Returns objects with `_tipoViz`, `_titulo`, `_columnas` metadata
   - Aggregates and calculates financial metrics (margins, totals, top 5 lists)
   - Processes payroll data by summing H### (haberes) and D### (descuentos) columns

3. **Response Structuring (lines 147-208)**: `estructurarRespuesta()` transforms tool results into frontend-ready formats
   - `eerr`: Income statement visualization
   - `table`: Tabular data with top 5 and summary
   - `metric`: Single metric display
   - `resumen`: General summary

4. **Main Endpoint (lines 213-279)**: POST `/api/ask` orchestrates Claude conversation
   - Sends user question to Claude with tool definitions
   - Executes tools when Claude requests them
   - Returns structured response with data + insight

### Data Flow

```
User Question → Claude (tool_use) → ejecutarHerramienta() → Skualo API
                                            ↓
Frontend ← estructurarRespuesta() ← Claude (insight) ← Tool Result
```

## Key Integration Points

### Skualo API Integration

- **Base URL**: `https://api.skualo.cl/76243957-3`
- **Endpoints**:
  - `/contabilidad/reportes/resultados` - Income statements
  - `/contabilidad/reportes/analisisporcuenta/1-1-07-001` - Accounts receivable (CxC)
  - `/contabilidad/reportes/analisisporcuenta/2-1-10-001` - Accounts payable nacional (CxP)
  - `/contabilidad/reportes/analisisporcuenta/2-1-10-002` - Accounts payable internacional (CxP)
  - `/contabilidad/reportes/balancetributario/{YYYYMM}` - Balance tributario (saldos bancarios)
  - `/contabilidad/reportes/librodiario` - Libro diario detalle
  - `/rrhh/reportes/datosliquidados/{YYYYMM}` - Payroll data with H### and D### columns
  - `/tablas/proyectos` - Maestro de proyectos
  - `/contabilidad/plandecuentas` - Plan de cuentas

- **Authentication**: Bearer token in `SKUALO_TOKEN`

### Claude AI Configuration

- Model: `claude-sonnet-4-20250514`
- Max tokens: 1024
- System prompt emphasizes concise Spanish responses, contextual analysis (not repeating numbers), and proper date handling
- Uses Anthropic SDK v0.71.2

## Response Types

Frontend expects one of four response types (determined by `_tipoViz` metadata):

1. **eerr**: Financial statement with income, costs, margins, operating results
2. **tabla**: Table with top 5 entries and summary metrics
3. **metrica**: Single metric with value and percentage
4. **resumen**: General summary for non-tool responses

## Important Implementation Details

### Date Handling

- Current date context: January 2026
- Financial statements: use `fechaCorte=2025-12-31` for 2025 data, current date for 2026
- Payroll: use `periodo=YYYYMM` format (e.g., 202512 for December 2025, 202601 for January 2026)

### Financial Calculations

- Revenue: Account `4101001`
- Costs: Accounts starting with `5101`
- Admin expenses: Accounts starting with `52` or `53`
- Margins calculated as percentages of revenue

### Códigos de Cuenta Importantes

| Código | Descripción |
|--------|-------------|
| 1-1-07-001 | Facturas por Cobrar (CxC) |
| 2-1-10-001 | Facturas por Pagar Nacionales (CxP) |
| 2-1-10-002 | Facturas por Pagar Internacionales |
| 4-1-01-001 | Ingresos por Servicios |
| 5-1-01-xxx | Costos Directos |

### Data Processing Rules

- **CXC (receivables)**: Only positive balances included in top 5
- **CXP (payables)**: Only negative balances (converted to positive) included in top 5
- **Payroll**: Skualo returns one or more records per employee (liquidación + ajustes)
  - Each record has columns H### (haberes) and D### (descuentos) with numeric values
  - Group by RUT and sum all H### and D### columns across records
  - Top 5 employees ranked by totalHaberes (sum of all H### columns)
  - Returns: totalHaberes, totalDescuentos, totalLiquido, totalEmpleados, costoPromedioEmpleado

### Tool Use Loop

- Backend handles multi-turn tool use (lines 235-256)
- Continues calling Claude until `stop_reason !== "tool_use"`
- Final response always includes Claude's insight text

## Environment Configuration

The application uses environment variables for API keys and configuration:

**Required variables**:
- `ANTHROPIC_API_KEY`: Your Claude API key from Anthropic
- `SKUALO_TOKEN`: Bearer token for Skualo API authentication
- `SKUALO_BASE_URL`: Base URL for Skualo API (defaults to `https://api.skualo.cl/76243957-3`)
- `PORT`: Server port (defaults to 3001)

Copy `.env.example` to `.env` and configure your actual API keys. The `.env` file is gitignored to prevent accidental commits of secrets.

---

## Endpoints Pipeline Skualo (Dashboard Cash Flow)

### Movimientos Bancarios (reemplaza Fintoc)

```bash
GET /{RUT}/bancos/{cuenta}?search=fecha gte {DD-MM-YYYY}

# Ejemplo: Movimientos Santander desde 01-01-2026
curl --request GET \
  --url "https://api.skualo.cl/76243957-3/bancos/1102002?search=fecha gte 01-01-2026" \
  --header 'Authorization: Bearer {token}' \
  --header 'accept: application/json'
```

**Cuentas Bancarias Mapeadas:**
| Banco | ID Cuenta |
|-------|-----------|
| Santander | 1102002 |
| BCI | 1102003 |
| Scotiabank | 1102004 |
| Banco de Chile | 1102005 |
| Bice | 1102013 |

**Respuesta JSON:**
```json
{
  "fecha": "2026-01-16T00:00:00-03:00",
  "montoCargo": 1500000,
  "montoAbono": 0,
  "glosa": "Pago proveedor X"
}
```

### Documentos (Pipeline de Compras)

```bash
GET /{RUT}/documentos?search=IDTipoDocumento eq {tipo}

# Tipos de documento:
# SOLI = Solicitudes de compra
# OCO = Ordenes de compra nacionales  
# OCX = Ordenes de compra internacionales
# FACO = Facturas de compra
```

### Detalle Documento

```bash
GET /{RUT}/documentos/{id_documento}

# Incluye campo 'cerrado' para verificar si tiene documento posterior
```

### Métodos del Cliente Pipeline

- `get_soli_sin_oc()` - Solicitudes aprobadas sin OC
- `get_oc_sin_factura()` - OCs nacionales aprobadas sin factura
- `get_ocx_sin_invoice()` - OCs internacionales aprobadas sin invoice
- `get_resumen_pipeline()` - Resumen consolidado del pipeline

### Vencimientos Tesorería

```bash
GET /{RUT}/tesoreria/reportes/vencimientos?idCuenta={cuenta}

# Ejemplo CxP Internacionales
curl --request GET \
  --url https://api.skualo.cl/76243957-3/tesoreria/reportes/vencimientos?idCuenta=2110002 \
  --header 'Authorization: Bearer {token}'
```

### Comprobantes Contables

```bash
GET /{RUT}/contabilidad/comprobantes?fechaDesde={YYYY-MM-DD}&fechaHasta={YYYY-MM-DD}&Page={n}&PageSize=100
```

### Libro Diario (CSV)

```bash
GET /{RUT}/contabilidad/reportes/librodiario?desde={YYYY-MM-DD}&hasta={YYYY-MM-DD}&IdSucursal=0&IncluyeAjustes=true

Headers: Accept: text/csv
Response: CSV con 25 columnas
```

---

*Última actualización: Enero 2026*
*Fuente: vero-pix/veriflux repo*

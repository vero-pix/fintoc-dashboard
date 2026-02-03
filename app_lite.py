from flask import Flask, request, jsonify
import json
import os
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from create_snapshot import get_snapshot

app = Flask(__name__)

# Configuración
SNAPSHOT_FILE = "data_snapshot.json"
TZ_CHILE = pytz.timezone('America/Santiago')
PASSWORD = os.getenv("DASHBOARD_PASSWORD", "Ale234de")

# Estética de Marca CathPro
CP_ORANGE = "#f45c03"
CP_GREEN = "#3bb44b"
CP_DARK = "#2d3132"
CP_WHITE = "#ffffff"
CP_RED = "#d9534f"

# Parámetros de Gestión
DIA_CIERRE_CONTABLE = 12  # El usuario puede modificar este día según su protocolo

RECURRENTES = [
    {'dia': 1, 'concepto': 'Crédito Hipotecario', 'monto': 1000000},
    {'dia': 5, 'concepto': 'ARRIENDO OFICINA', 'monto': 1800000},
    {'dia': 5, 'concepto': 'Leasing BCI1', 'monto': 3200000},
    {'dia': 7, 'concepto': 'PREVIRED', 'monto': 32000000},
    {'dia': 7, 'concepto': 'Leasing Progreso', 'monto': 1500000},
    {'dia': 10, 'concepto': 'Leasing Oficina', 'monto': 1229177},
    {'dia': 15, 'concepto': 'LEASING BCI', 'monto': 3200000},
    {'dia': 15, 'concepto': 'Leaseback', 'monto': 1800000},
    {'dia': 16, 'concepto': 'SII - IVA', 'monto': 115000000},
    {'dia': 19, 'concepto': 'Crédito Santander', 'monto': 6000000},
    {'dia': 27, 'concepto': 'REMUNERACIONES', 'monto': 105000000},
    {'dia': 28, 'concepto': 'Honorarios', 'monto': 2100000},
]
TOTAL_REC = sum(r['monto'] for r in RECURRENTES)

def load_snapshot():
    if not os.path.exists(SNAPSHOT_FILE):
        return None
    with open(SNAPSHOT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# Helper para formato CFO: $143.3M
def format_m(value, is_q1_real=False):
    if value is None or (value == 0 and not is_q1_real): return "0,0M"
    val_abs = abs(value)
    millones = val_abs / 1_000_000
    
    prefix = "$"
    if value < 0: prefix = "-$"
    
    if is_q1_real:
        return f"{prefix}{millones:,.1f}M <span style='font-size:10px; color:#666'>+ Proy</span>"
    
    color = "inherit"
    if value < 0: color = CP_RED
    return f"<span style='color:{color}'>{prefix}{millones:,.1f}M</span>".replace(",", "X").replace(".", ",").replace("X", ".")

def format_pct(value, color_logic=False, is_cost=False):
    if value is None: return "0,0%"
    pct = value * 100
    color = "inherit"
    if color_logic:
        if is_cost:
            if pct <= 50: color = CP_GREEN
            elif pct <= 90: color = "#f1c40f"
            else: color = CP_RED
        else:
            if pct >= 90: color = CP_GREEN
            elif pct >= 70: color = "#f1c40f"
            else: color = CP_RED
    return f"<span style='color:{color}'>{pct:,.1f}%</span>".replace(".", ",")

def render_cf_horizon(data, days, active=False):
    cf_data = data.get("cashflow", {})
    if not cf_data:
        return f"<div id='cf-{days}' class='cf-row {'active' if active else ''}' style='color:#666; font-style:italic; padding:20px; text-align:center'>Datos de Cash Flow no disponibles.</div>"
    
    hoy = datetime.now().date()
    total_in = 0
    total_out = 0
    
    # Consolidar por el periodo solicitado
    for i in range(days):
        fecha_target = (hoy + timedelta(days=i)).isoformat()
        dia_info = cf_data.get(fecha_target, {})
        total_in += dia_info.get("entradas", 0)
        total_out += dia_info.get("salidas_total", 0)

    neto = total_in - total_out
    color_neto = CP_GREEN if neto >= 0 else CP_RED
    
    # Formatear números para visualización ejecutiva ($14M)
    def fmt_cf(val):
        prefix = "$" if val >= 0 else "-$"
        return f"{prefix}{abs(val)/1_000_000:,.1f}M".replace(",", "X").replace(".", ",").replace("X", ".")

    return f"""
    <div id="cf-{days}" class="cf-row {"active" if active else ""}">
        <div class="cf-grid">
            <div class="cf-stat" style="border-top-color:var(--green)">
                <h4>Entradas Esp.</h4>
                <div class="val" style="color:var(--green)">{fmt_cf(total_in)}</div>
            </div>
            <div class="cf-stat" style="border-top-color:var(--red)">
                <h4>Salidas Prog.</h4>
                <div class="val" style="color:var(--red)">{fmt_cf(total_out)}</div>
            </div>
            <div class="cf-stat" style="border-top-color:{color_neto}">
                <h4>Flujo Neto</h4>
                <div class="val" style="color:{color_neto}">{fmt_cf(neto)}</div>
            </div>
        </div>
    </div>
    """
from datetime import timedelta

@app.route('/')
def index():
    return f"<html><meta http-equiv='refresh' content='0; url=/tablero?key={PASSWORD}' /></html>"

# Gestión de Configuración Persistente
CONFIG_FILE = "dashboard_config.json"

def get_live_rates():
    """Obtiene tasas reales de mindicador.cl para Chile"""
    try:
        resp = requests.get("https://mindicador.cl/api", timeout=5).json()
        return {
            "USD": resp.get("dolar", {}).get("valor", 858),
            "EUR": resp.get("euro", {}).get("valor", 935)
        }
    except:
        return {"USD": 858, "EUR": 935}

def load_config():
    default = {
        "DIA_CIERRE_CONTABLE": 12, 
        "ING_BENCHMARK_2025": 385000000, 
        "MARGEN_BENCHMARK_2025": 0.62,
        "USE_LIVE_RATES": True,
        "TASA_USD": 858,
        "TASA_EUR": 935
    }
    if not os.path.exists(CONFIG_FILE): return default
    with open(CONFIG_FILE, 'r') as f: 
        cfg = {**default, **json.load(f)}
    
    # Si está en modo automático, intentamos pisar con la API
    if cfg.get("USE_LIVE_RATES"):
        live = get_live_rates()
        cfg["TASA_USD"] = live["USD"]
        cfg["TASA_EUR"] = live["EUR"]
    else:
        cfg["TASA_USD"] = cfg["TASA_USD_MANUAL"]
        cfg["TASA_EUR"] = cfg["TASA_EUR_MANUAL"]
    
    return cfg

def save_config(new_config):
    with open(CONFIG_FILE, 'w') as f: json.dump(new_config, f, indent=2)

@app.route('/trigger_snapshot')
def trigger_snapshot():
    key = request.args.get('key', '')
    if key != PASSWORD: return "No autorizado"
    try:
        get_snapshot()
        return f"<html><script>alert('✅ Sincronización Exitosa'); window.location='/tablero?key={PASSWORD}';</script></html>"
    except Exception as e:
        return f"Error: {str(e)}"

@app.route('/update_config', methods=['POST'])
def update_config():
    cfg = load_config()
    cfg["DIA_CIERRE_CONTABLE"] = int(request.form.get("dia_cierre", cfg["DIA_CIERRE_CONTABLE"]))
    cfg["ING_BENCHMARK_2025"] = float(request.form.get("ing_2025", cfg["ING_BENCHMARK_2025"]))
    cfg["MARGEN_BENCHMARK_2025"] = float(request.form.get("mar_2025", cfg["MARGEN_BENCHMARK_2025"])) / 100
    
    # Manejo de tasas
    use_live = request.form.get("use_live") == "on"
    cfg["USE_LIVE_RATES"] = use_live
    if not use_live:
        cfg["TASA_USD_MANUAL"] = float(request.form.get("tasa_usd", 858))
        cfg["TASA_EUR_MANUAL"] = float(request.form.get("tasa_eur", 935))
        
    save_config(cfg)
    return f"<html><meta http-equiv='refresh' content='0; url=/tablero?key={PASSWORD}' /></html>"

@app.route('/tablero')
def tablero():
    key = request.args.get('key', '')
    if key != PASSWORD: return "No autorizado"

    cfg = load_config()
    DIA_CIERRE_CONTABLE = cfg["DIA_CIERRE_CONTABLE"]
    ING_BENCHMARK_2025 = cfg["ING_BENCHMARK_2025"]
    MARGEN_BENCHMARK_2025 = cfg["MARGEN_BENCHMARK_2025"]
    TASA_USD = cfg.get("TASA_USD", 858)
    TASA_EUR = cfg.get("TASA_EUR", 935)

    snapshot = load_snapshot()
    if not snapshot: return "Error: Snapshot no encontrado."
    
    # Formatear hora de actualización
    snap_ts = snapshot.get("timestamp", "")
    try:
        dt_snap = datetime.fromisoformat(snap_ts)
        actualizacion_str = dt_snap.strftime("%d/%m/%Y %H:%M")
    except:
        actualizacion_str = "Desconocida"

    data = snapshot["data"]
    
    # 1. LIQUIDEZ CONSOLIDADA (Activo Disponible)
    fintoc = data.get("fintoc_balances", {})
    clp_total = fintoc.get("clp", {}).get("total", 0)
    usd_total = fintoc.get("usd", {}).get("total", 0)
    eur_total = fintoc.get("eur", {}).get("total", 0)
    
    liquidez_consolidada = clp_total + (usd_total * TASA_USD) + (eur_total * TASA_EUR)
    
    # 2. ESTADO DE RECAUDACIÓN (Activo Corriente)
    skualo_bal = data.get("skualo_balances", {})
    cxc = skualo_bal.get("por_cobrar", 0)
    ffmm = skualo_bal.get("fondos_mutuos", 0) # Seguir mostrando FFMM como inversión

    # 3. COMPROMISOS DE PAGO (Pasivo Exigible)
    cxp_total = skualo_bal.get("por_pagar_total", 0)
    pipeline = data.get("pipeline", {})
    egresos_pipe = pipeline.get("egresos", {})
    
    ocs_monto = egresos_pipe.get("oc", {}).get("monto_total", 0)
    ocxs_monto = egresos_pipe.get("ocx", {}).get("monto_total_usd", 0) * TASA_USD
    
    compromisos_totales = TOTAL_REC + cxp_total + ocs_monto + ocxs_monto
    cobertura_meses = liquidez_consolidada / compromisos_totales if compromisos_totales > 0 else 0
    dias_venta = 13 # Requerimiento fijo
    
    # 2. PROCESAMIENTO EERR
    forecast = data.get("forecast", [])
    real_acc = data.get("contabilidad_real", {})
    
    def get_data_mes(mes_name):
        f_data = next((m for m in forecast if m['mes'] == mes_name), {'presupuesto':0, 'forecast':0})
        r_data = real_acc.get(mes_name, {'ing_real':0, 'cos_real':0})
        i_real = r_data['ing_real']
        c_real = r_data['cos_real']
        return {
            'i_ppto': f_data['presupuesto'],
            'i_fcst': f_data['forecast'],
            'i_real': i_real,
            'c_real': c_real,
            'mb_real': (i_real - c_real) / i_real if i_real > 0 else 0,
            'cost_ratio': c_real / i_real if i_real > 0 else 0
        }

    ene = get_data_mes('Enero')
    cumpl_ing = ene['i_real'] / ene['i_fcst'] if ene['i_fcst'] > 0 else 0

    # 2.5 LÓGICA DE SUPERVIVENCIA (CFO FOCUS)
    cash_on_hand = clp_total # Solo lo que está en bancos
    burn_rate_real = ene['c_real'] if ene['c_real'] > 0 else TOTAL_REC
    runway_meses = cash_on_hand / burn_rate_real if burn_rate_real > 0 else 0

    # 2.6 BENCHMARKING HISTÓRICO (2025 vs 2026)
    ing_2026 = ene['i_real']
    mar_2026 = ene['mb_real']
    diff_ing = ((ing_2026 / ING_BENCHMARK_2025) - 1) * 100 if ING_BENCHMARK_2025 > 0 else 0
    
    # 3. ALERTAS EJECUTIVAS
    alertas = []
    if cumpl_ing < 0.7:
        gap_m = (ene['i_fcst'] - ene['i_real']) / 1_000_000
        alertas.append(f"🚩 <b>Gap Crítico de Ingresos:</b> Enero muestra una brecha de -${gap_m:.1f}M (Cumplimiento {cumpl_ing*100:.1f}%).")
    
    if ene['mb_real'] < 0.35:
        alertas.append(f"⚠️ <b>Margen Comprimido:</b> MB Real de Enero en {ene['mb_real']*100:.1f}% vs 55% Meta.")

    pipeline = data.get("pipeline", {})
    ingresos_pipe = pipeline.get("ingresos", {"cantidad": 0, "monto_total": 0, "documentos": []})
    egresos_pipe = pipeline.get("egresos", {})
    venda_pend = ingresos_pipe.get("monto_total", 0)
    
    if venda_pend == 0:
         alertas.append(f"📡 <b>Brecha de Visibilidad Comercial:</b> Pipeline no unificado en Skualo. La gestión de ventas depende de flujos externos al sistema.")
    
    # Construcción de Alertas HTML con Toggle para Comparative
    alertas_list_html = "".join([f"<div style='margin-bottom:10px; border-left:4px solid {CP_RED}; padding-left:15px;'>{a}</div>" for a in alertas])
    
    comparativo_html = f"""
    <div style="margin-top:20px; border-top:1px solid #3d2b1f; padding-top:15px;">
        <div style="display:flex; justify-content:space-between; align-items:center;">
             <span style="color:var(--orange); font-size:12px; font-weight:800; cursor:pointer;" onclick="toggleAlertsDetail()">🔍 CLICK PARA COMPARATIVO 2025 vs 2026</span>
             <span style="color:#666; font-size:11px; cursor:pointer;" onclick="toggleConfig()">⚙️ Ajustes de Gestión</span>
        </div>

        <div id="config-panel" style="display:none; margin-top:12px; background:#1a1a1a; padding:15px; border-radius:8px; border:1px solid #333;">
            <form action="/update_config" method="POST">
                <div style="margin-bottom:15px; border-bottom:1px solid #333; padding-bottom:10px;">
                    <label style="font-size:12px; font-weight:800; color:var(--orange);">
                        <input type="checkbox" name="use_live" {"checked" if cfg.get("USE_LIVE_RATES") else ""} onchange="document.getElementById('manual-rates').style.opacity = this.checked ? '0.3' : '1'"> 
                        🌐 Tasa de Cambio Automática (mindicador.cl)
                    </label>
                </div>
                
                <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px;">
                    <div>
                        <label style="font-size:10px; color:#888;">Día de Cierre</label><br>
                        <input type="number" name="dia_cierre" value="{DIA_CIERRE_CONTABLE}" style="background:#000; color:white; border:1px solid #444; padding:5px; width:60px;">
                    </div>
                    <div>
                        <label style="font-size:10px; color:#888;">Ingresos 2025 ($)</label><br>
                        <input type="number" name="ing_2025" value="{ING_BENCHMARK_2025}" style="background:#000; color:white; border:1px solid #444; padding:5px; width:100px;">
                    </div>
                    <div>
                        <label style="font-size:10px; color:#888;">Margen 2025 (%)</label><br>
                        <input type="number" step="0.1" name="mar_2025" value="{MARGEN_BENCHMARK_2025*100}" style="background:#000; color:white; border:1px solid #444; padding:5px; width:60px;">
                    </div>
                </div>

                <div id="manual-rates" style="display:grid; grid-template-columns: repeat(3, 1fr); gap:10px; margin-top:10px; opacity: {'0.3' if cfg.get('USE_LIVE_RATES') else '1'};">
                    <div>
                        <label style="font-size:10px; color:#888;">Tasa USD ($)</label><br>
                        <input type="number" step="0.1" name="tasa_usd" value="{cfg.get('TASA_USD', 858)}" style="background:#000; color:white; border:1px solid #444; padding:5px; width:60px;">
                    </div>
                    <div>
                        <label style="font-size:10px; color:#888;">Tasa EUR ($)</label><br>
                        <input type="number" step="0.1" name="tasa_eur" value="{cfg.get('TASA_EUR', 935)}" style="background:#000; color:white; border:1px solid #444; padding:5px; width:60px;">
                    </div>
                </div>

                <div style="display:flex; justify-content:space-between; align-items:flex-end; margin-top:15px;">
                    <button type="submit" style="background:var(--orange); color:white; border:none; padding:10px 20px; border-radius:4px; font-size:12px; font-weight:800; cursor:pointer;">Guardar y Refrescar</button>
                    <a href="/trigger_snapshot?key={PASSWORD}" style="color:#666; font-size:10px; text-decoration:none; border:1px solid #333; padding:5px 10px; border-radius:4px;">🔄 Forzar Sincronización Bancaria</a>
                </div>
            </form>
        </div>

        <div id="alerts-detail" style="display:none; margin-top:12px; background:#120e0a; padding:15px; border-radius:8px;">
            <table style="font-size:12px;">
                <thead><tr><th>Indicador</th><th>Enero 2025</th><th>Enero 2026</th><th>Var %</th></tr></thead>
                <tbody>
                    <tr>
                        <td>Ingresos</td>
                        <td>$ {ING_BENCHMARK_2025/1e6:.1f}M</td>
                        <td>
                            {format_m(ing_2026)}<br>
                            <span style="font-size:9px; color:#888;">FCST: {format_m(ene['i_fcst'])}</span>
                        </td>
                        <td style="color:{CP_GREEN if diff_ing > 0 else CP_RED}">{diff_ing:+.1f}%</td>
                    </tr>
                    <tr>
                        <td>Margen Bruto</td>
                        <td>{format_pct(MARGEN_BENCHMARK_2025)}</td>
                        <td>
                            {format_pct(mar_2026)}<br>
                            <span style="font-size:9px; color:#888;">FCST: {format_pct(0.55)}</span>
                        </td>
                        <td style="color:{CP_GREEN if mar_2026 > MARGEN_BENCHMARK_2025 else CP_RED}">{(mar_2026-MARGEN_BENCHMARK_2025)*100:+.1f}pts</td>
                    </tr>
                </tbody>
            </table>
            <div style="margin-top:10px; font-size:11px; color:#888; font-style:italic;">
                * Datos 2025 basados en Benchmark Histórico de Auditoría.
            </div>
        </div>
    </div>
    """
    
    alertas_html = alertas_list_html + comparativo_html

    # TABLA COCKPIT
    rows = [
        ('Ing Presupuesto', 'i_ppto'), ('Ing Forecast', 'i_fcst'), ('Ing Real', 'i_real'),
        ('Var $ (Real vs Fcst)', 'var_usd'), ('% Cumplimiento', 'cumpl'),
        ('SEPARATOR', None),
        ('Costo Real', 'c_real'), ('% Ratio Costo/Ing', 'cost_ratio'),
        ('SEPARATOR', None),
        ('Margen Real (%)', 'mb_real'),
    ]

    # LÓGICA DE CIERRE CONTABLE (CFO)
    hoy = datetime.now(TZ_CHILE)
    mes_actual_idx = hoy.month # 1 para Enero
    dia_actual = hoy.day
    
    dict_meses = {'Enero': 1, 'Febrero': 2, 'Marzo': 3}

    resumen_body = ""
    for label, key in rows:
        if label == 'SEPARATOR':
            resumen_body += "<tr style='height:10px'><td colspan='5' style='border:none'></td></tr>"
            continue
        resumen_body += f"<tr><td>{label}</td>"
        
        for mes in ['Enero', 'Febrero', 'Marzo']:
            m_data = get_data_mes(mes)
            m_idx = dict_meses[mes]
            
            # Un mes es "Parcial" si:
            # - Es el mes actual
            # - Es el mes anterior y hoy es antes del Día de Cierre configurado
            is_parcial = False
            if m_idx == mes_actual_idx:
                is_parcial = True
            elif m_idx == mes_actual_idx - 1 and dia_actual < DIA_CIERRE_CONTABLE:
                is_parcial = True
            
            is_future = m_idx > mes_actual_idx
            
            val_out = "-"
            if is_future:
                if key in ['i_ppto', 'i_fcst']: val_out = format_m(m_data[key])
                else: val_out = "<span style='color:#555;font-style:italic'>Proyectado</span>"
            else:
                if key == 'i_ppto': val_out = format_m(m_data['i_ppto'])
                elif key == 'i_fcst': val_out = format_m(m_data['i_fcst'])
                elif key == 'i_real': 
                    real_fmt = format_m(m_data['i_real'])
                    if is_parcial:
                        fcst_fmt = format_m(m_data['i_fcst'])
                        val_out = f"{real_fmt} <br><span style='font-size:9px; color:var(--orange)'>PARCIAL vs {fcst_fmt} FCST</span>"
                    else:
                        val_out = real_fmt
                elif key == 'var_usd': val_out = format_m(m_data['i_real'] - m_data['i_fcst'])
                elif key == 'cumpl': val_out = format_pct(m_data['i_real'] / m_data['i_fcst'] if m_data['i_fcst']>0 else 0, True)
                elif key == 'c_real': 
                    real_fmt = format_m(m_data['c_real'])
                    val_out = f"{real_fmt} <span style='font-size:9px; opacity:0.6'>(Parcial)</span>" if is_parcial else real_fmt
                elif key == 'cost_ratio': val_out = format_pct(m_data['cost_ratio'], True, True)
                elif key == 'mb_real': 
                    real_fmt = format_pct(m_data['mb_real'], True)
                    val_out = f"{real_fmt} <span style='font-size:9px; opacity:0.6'>(Parcial)</span>" if is_parcial else real_fmt
            
            resumen_body += f"<td class='monto'>{val_out}</td>"
        
        q1_val = 0
        if key == 'i_ppto': q1_val = sum(get_data_mes(m)['i_ppto'] for m in ['Enero', 'Febrero', 'Marzo'])
        elif key == 'i_fcst': q1_val = sum(get_data_mes(m)['i_fcst'] for m in ['Enero', 'Febrero', 'Marzo'])
        elif key == 'i_real': q1_val = ene['i_real']
        resumen_body += f"<td class='monto' style='font-weight:800'>{format_m(q1_val, key=='i_real') if q1_val else '-'}</td></tr>"

    # 4. ANÁLISIS DE DESVIACIONES POR PROYECTO (ENERO)
    proy_forecast = data.get("proyectos_forecast_ene", {})
    proy_real = data.get("proyectos_real_ene", {})
    proy_map = data.get("proyectos_map", {})
    
    desviaciones_rows = ""
    all_faenas = sorted(list(set(list(proy_forecast.keys()) + [proy_map.get(k, k) for k in proy_real.keys()])))
    
    for faena in all_faenas:
        real_val = 0
        for id_p, monto in proy_real.items():
            if proy_map.get(id_p) == faena or id_p == faena:
                real_val += monto
        
        f_data = proy_forecast.get(faena, {"ppto": 0, "fcst": 0})
        fcst_val = f_data['fcst']
        var_val = real_val - fcst_val
        
        if fcst_val > 0 or real_val > 0:
            color_var = CP_GREEN if var_val >= -100_000 else CP_RED
            desviaciones_rows += f"<tr><td>{faena}</td><td class='monto'>{format_m(fcst_val)}</td><td class='monto'>{format_m(real_val)}</td><td class='monto' style='color:{color_var}'>{format_m(var_val)}</td><td class='center'>{format_pct(real_val/fcst_val if fcst_val > 0 else 0, True)}</td></tr>"

    # 5. PIPELINE FINANCIERO (DETALLE)
    def render_pipe_table(pipe_dict, is_usd=False):
        docs = pipe_dict.get("documentos", [])
        if not docs: return "<tr><td colspan='5' style='color:#666; font-style:italic'>Sin registros detectados en Skualo</td></tr>"
        html = ""
        for d in docs[:10]:
            monto = d.get('monto_usd') if is_usd else d.get('monto')
            m_fmt = f"US$ {monto:,.2f}" if is_usd else f"$ {monto:,.0f}"
            aux = d.get('cliente') if 'cliente' in d else d.get('proveedor', '---')
            html += f"<tr><td>{d.get('fecha')}</td><td><b>{d.get('folio')}</b></td><td>{str(aux)[:25]}...</td><td>{str(d.get('proyecto'))[:20]}</td><td class='monto'>{m_fmt}</td></tr>"
        return html

    # ALERTAS Y STATUS
    status_color = CP_GREEN if cumpl_ing >= 0.9 else (CP_ORANGE if cumpl_ing >= 0.7 else CP_RED)
    
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
        <title>CathPro CFO Cockpit</title>
        <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700;800&display=swap" rel="stylesheet">
        <style>
            :root {{ --orange: {CP_ORANGE}; --green: {CP_GREEN}; --dark: {CP_DARK}; --white: {CP_WHITE}; --bg: #0b0c0c; --card-bg: #161819; }}
            body {{ font-family: 'Outfit', sans-serif; background: var(--bg); color: var(--white); margin: 0; padding: 15px; line-height: 1.4; }}
            .container {{ max-width: 1400px; margin: 0 auto; }}
            
            .header-cfo {{ 
                display: flex; 
                justify-content: space-between; 
                align-items: center; 
                margin-bottom: 20px; 
                border-bottom: 2px solid var(--orange); 
                padding-bottom: 15px; 
            }}
            .header-cfo h1 {{ font-size: 1.5rem; margin: 0; }}
            
            .grid-kpis {{ 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); 
                gap: 15px; 
                margin-bottom: 25px; 
            }}
            .kpi-card {{ 
                background: var(--card-bg); 
                padding: 22px; 
                border-radius: 12px; 
                border-left: 6px solid var(--green);
                box-shadow: 0 4px 15px rgba(0,0,0,0.3);
            }}
            .kpi-card h3 {{ font-size: 14px; margin: 0; opacity: 0.8; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }}
            .main-val {{ font-size: 32px; font-weight: 800; display: block; margin: 8px 0; letter-spacing: -1px; }}
            
            .section {{ 
                background: var(--card-bg); 
                padding: 20px; 
                border-radius: 16px; 
                margin-bottom: 25px; 
                border: 1px solid #222; 
            }}
            .section-title {{ 
                font-size: 14px; 
                font-weight: 800; 
                color: var(--orange); 
                text-transform: uppercase; 
                border-bottom: 1px solid #222; 
                padding-bottom: 10px; 
                margin-bottom: 20px;
                letter-spacing: 1px;
            }}
            
            .alerts-box {{ 
                background: linear-gradient(145deg, #1a1510, #110e0a); 
                border: 1px solid #3d2b1f; 
                padding: 18px; 
                border-radius: 12px; 
                margin-bottom: 25px; 
            }}
            
            .table-container {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
            table {{ width: 100%; border-collapse: collapse; min-width: 600px; }}
            th {{ text-align: left; padding: 12px 8px; color: #888; font-size: 11px; text-transform: uppercase; border-bottom: 2px solid #333; }}
            td {{ padding: 14px 8px; font-size: 14px; border-bottom: 1px solid #222; }}
            
            .monto {{ text-align: right; font-family: 'Outfit', sans-serif; font-weight: 700; }}
            .center {{ text-align: center; }}
            
            /* TABS CASHFLOW */
            .tabs-container {{ margin-bottom: 25px; }}
            .tabs {{ display: flex; gap: 5px; background: #1a1a1a; padding: 5px; border-radius: 8px; margin-bottom: 15px; }}
            .tab-btn {{ flex: 1; padding: 10px; border: none; background: transparent; color: #888; border-radius: 6px; cursor: pointer; font-size: 11px; font-weight: 700; text-transform: uppercase; transition: 0.3s; }}
            .tab-btn.active {{ background: var(--orange); color: white; }}
            .cf-grid {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }}
            .cf-stat {{ background: #161718; padding: 15px; border-radius: 8px; border-top: 2px solid #333; }}
            .cf-stat h4 {{ font-size: 10px; color: #888; margin: 0 0 5px 0; text-transform: uppercase; }}
            .cf-stat .val {{ font-size: 18px; font-weight: 800; }}
            .cf-row {{ display: none; }}
            .cf-row.active {{ display: block; }}
            
            @media (max-width: 768px) {{
                body {{ padding: 10px; }}
                .header-cfo {{ flex-direction: column; align-items: flex-start; gap: 10px; }}
                .main-val {{ font-size: 28px; }}
                .grid-kpis {{ grid-template-columns: 1fr; }}
                .kpi-card {{ padding: 18px; }}
                .pipe-grid {{ grid-template-columns: 1fr; }}
                table {{ min-width: 500px; }}
                td, th {{ padding: 10px 5px; font-size: 13px; }}
                .cf-grid {{ grid-template-columns: 1fr; }}
            }}
            
            .pipe-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }}
            .pipe-col {{ background: #161718; padding: 15px; border-radius: 8px; }}
            .pipe-title {{ font-size: 11px; font-weight: 700; color: #888; margin-bottom: 10px; border-bottom: 1px solid #222; padding-bottom: 5px; }}
            .warning-msg {{ font-size: 11px; color: #ff9800; background: #251d10; padding: 8px; border-radius: 5px; margin-bottom: 15px; border: 1px solid #3d2b1f; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-cfo">
                <h1>CathPro <span style="color:var(--orange)">CFO COCKPIT</span></h1>
                <div style="text-align:right">
                    <span style="background:{status_color}; padding:5px 15px; border-radius:20px; font-size:12px; font-weight:800;">STATUS: {("CRITICAL" if cumpl_ing < 0.7 else "DEVIATED") if cumpl_ing < 0.9 else "OK"}</span>
                    <div style="margin-top:10px; font-size:11px; color:#666;">Última Actualización: <b>{actualizacion_str}</b></div>
                </div>
            </div>

            <div class="alerts-box">
                <h3 style="margin-top:0; font-size:14px;">🔔 ALERTAS EJECUTIVAS</h3>
                {alertas_html}
            </div>

            <div class="grid-kpis">
                <!-- KPI 1: LIQUIDEZ DISPONIBLE -->
                <div class="kpi-card" style="cursor:pointer;" onclick="toggleLiquidez()">
                    <h3>Liquidez Disponible <span style="font-size:10px; opacity:0.6;">(Caja + Divisas)</span></h3>
                    <span class="main-val">{format_m(liquidez_consolidada)}</span>
                    <div style="font-size:12px; color:#888;">Consolidado (USD @ ${TASA_USD} | EUR @ ${TASA_EUR})</div>
                    
                    <div id="liquidez-detalle" style="display:none; margin-top:15px; padding-top:15px; border-top:1px solid #444; font-size:11px;">
                        <div style="color:var(--orange); font-weight:800; margin-bottom:5px;">EFECTIVO BANCARIO (CLP)</div>
                        { "".join([f"<div style='display:flex; justify-content:space-between; margin-bottom:4px;'><span>{b}:</span> <b>$ {m:,.0f}</b></div>" for b, m in fintoc.get('clp', {}).items() if b != 'total']) }
                        
                        <div style="color:var(--orange); font-weight:800; margin-top:10px; margin-bottom:5px;">DIVISAS (VALORIZADO)</div>
                        <div style='display:flex; justify-content:space-between;'><span>Total USD (US$ {usd_total:,.2f}):</span> <b>$ {usd_total*TASA_USD:,.0f}</b></div>
                        <div style='display:flex; justify-content:space-between; margin-top:2px;'><span>Total EUR (€ {eur_total:,.2f}):</span> <b>$ {eur_total*TASA_EUR:,.0f}</b></div>
                        <div style="margin-top:10px; font-size:9px; color:#666; font-style:italic; border-top:1px dashed #444; padding-top:5px;">
                            * Fuente: Banco Central de Chile (Dólar Observado 30/01/2026).
                        </div>
                    </div>
                </div>

                <!-- KPI 2: RECAUDACIÓN (CxC) -->
                <div class="kpi-card" style="border-left-color:var(--orange); cursor:pointer;" onclick="toggleDSO()">
                    <h3>Estado de Recaudación <span style="font-size:10px; opacity:0.6;">(CXC + FFMM)</span></h3>
                    <span class="main-val">{format_m(cxc)}</span>
                    <div style="font-size:12px; color:#888;">Cuentas por Cobrar Skualo</div>
                    
                    <div id="dso-detalle" style="display:none; margin-top:15px; padding-top:15px; border-top:1px solid #444; font-size:11px;">
                        <div style="color:var(--orange); font-weight:800; margin-bottom:10px;">CAPITAL EN TRÁNSITO</div>
                        <div style='display:flex; justify-content:space-between; margin-bottom:10px;'>
                            <span>Total Clientes:</span>
                            <b>{format_m(cxc)}</b>
                        </div>
                        <div style='display:flex; justify-content:space-between; margin-bottom:10px;'>
                            <span>Inversiones (FFMM):</span>
                            <b>{format_m(ffmm)}</b>
                        </div>
                        <div style="font-style:italic; color:#888; border-top:1px dashed #444; padding-top:5px; margin-top:5px;">Meta de Recaudación: 13 Días (T+13)</div>
                    </div>
                </div>

                <!-- KPI 3: COMPROMISOS (PASIVOS) -->
                <div class="kpi-card" style="border-left-color:var(--red); cursor:pointer;" onclick="toggleCompromisos()">
                    <h3>Compromisos de Pago</h3>
                    <span class="main-val" style="color:var(--red)">{format_m(compromisos_totales)}</span>
                    <div style="font-size:12px; color:#888;">Pasivos Exigibles (Recurrentes+CXP+OCs)</div>
                    
                    <div id="compromisos-detalle" style="display:none; margin-top:15px; padding-top:15px; border-top:1px solid #444; font-size:11px;">
                        <div style='display:flex; justify-content:space-between; margin-bottom:4px;'><span>Recurrentes (OpEx):</span> <b>{format_m(TOTAL_REC)}</b></div>
                        <div style='display:flex; justify-content:space-between; margin-bottom:4px;'><span>Proveedores (CXP):</span> <b>{format_m(cxp_total)}</b></div>
                        <div style='display:flex; justify-content:space-between; margin-bottom:4px;'><span>OCs por Facturar:</span> <b>{format_m(ocs_monto + ocxs_monto)}</b></div>
                    </div>
                </div>
            </div>

            <script>
            function toggleLiquidez() {{
                var x = document.getElementById("liquidez-detalle");
                x.style.display = (x.style.display === "none") ? "block" : "none";
            }}
            function toggleDSO() {{
                var x = document.getElementById("dso-detalle");
                x.style.display = (x.style.display === "none") ? "block" : "none";
            }}
            function toggleCompromisos() {{
                var x = document.getElementById("compromisos-detalle");
                x.style.display = (x.style.display === "none") ? "block" : "none";
            }}
            function toggleAlertsDetail() {{
                var x = document.getElementById("alerts-detail");
                x.style.display = (x.style.display === "none") ? "block" : "none";
            }}
            function toggleConfig() {{
                var x = document.getElementById("config-panel");
                x.style.display = (x.style.display === "none") ? "block" : "none";
            }}
            function switchCF(days, btn) {{
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.cf-row').forEach(r => r.classList.remove('active'));
                
                btn.classList.add('active');
                document.getElementById('cf-' + days).classList.add('active');
            }}
            </script>

            <!-- SECCIÓN: PROYECCIÓN DE FLUJO DE CAJA -->
            <div class="section">
                <h2 class="section-title">📅 Proyección de Flujo de Caja (Cash Flow)</h2>
                <div class="tabs-container">
                    <div class="tabs">
                        <button class="tab-btn active" onclick="switchCF(7, this)">7 Días</button>
                        <button class="tab-btn" onclick="switchCF(14, this)">14 Días</button>
                        <button class="tab-btn" onclick="switchCF(30, this)">1 Mes</button>
                        <button class="tab-btn" onclick="switchCF(90, this)">3 Meses</button>
                    </div>

                    {render_cf_horizon(data, 7, True)}
                    {render_cf_horizon(data, 14)}
                    {render_cf_horizon(data, 30)}
                    {render_cf_horizon(data, 90)}
                </div>
                <div style="font-size:10px; color:#555; margin-top:10px; font-style:italic;">
                    * Incluye CxC ajustada por días de pago de clientes + CxP + Pagos Recurrentes (Previred, SII, Remuneraciones).
                </div>
            </div>

            <div class="section">
                <h2 class="section-title">📊 VERICOSAS COCKPIT Q1 2026</h2>
                <div class="table-container">
                    <table>
                        <thead><tr><th>Indicador</th><th class="center">Enero</th><th class="center">Febrero</th><th class="center">Marzo</th><th class="center">Q1 Total</th></tr></thead>
                        <tbody>{resumen_body}</tbody>
                    </table>
                </div>
            </div>

            <div class="section">
                <h2 class="section-title">💰 PIPELINE DE INGRESOS (Ventas / HE por Facturar)</h2>
                <div class="warning-msg">
                    <b>Debilidad de Visibilidad Comercial:</b> Pipeline de ingresos no unificado en Skualo. La captura de datos depende de registros externos al sistema core. 
                </div>
                <div class="pipe-col" style="background:transparent; padding:0">
                    <div style="font-size:20px; font-weight:800; margin-bottom:15px; color:var(--green)">Registrado en Sistema: {format_m(ingresos_pipe['monto_total'])}</div>
                    <div class="table-container">
                        <table>
                            <thead><tr><th>Fecha</th><th>Folio</th><th>Cliente</th><th>Proyecto</th><th class="monto">Monto</th></tr></thead>
                            <tbody>
                                {render_pipe_table(ingresos_pipe)}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>

            <div class="section">
                <h2 class="section-title">🔍 DESVIACIONES: INGRESOS POR PROYECTO (ENERO)</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Proyecto / Faena</th>
                            <th class="monto">Forecast / Meta</th>
                            <th class="monto">Venta Real</th>
                            <th class="monto">Brecha ($)</th>
                            <th class="center">% Cumpl.</th>
                        </tr>
                    </thead>
                    <tbody>{desviaciones_rows}</tbody>
                </table>
            </div>

            <div class="section">
                <h2 class="section-title">💸 COMPROMISOS DE PAGO (Egresos / OCs Proveedores)</h2>
                <div class="pipe-grid">
                    <div class="pipe-col">
                        <div class="pipe-title">OC / OCX APROBADAS (POR PAGAR)</div>
                        <table>
                            <thead><tr><th>Fecha</th><th>Folio</th><th>Proveedor</th><th>Proyecto</th><th class="monto">Monto</th></tr></thead>
                            <tbody>
                                {render_pipe_table(egresos_pipe.get('oc', {}))}
                                {render_pipe_table(egresos_pipe.get('ocx', {}), True)}
                            </tbody>
                        </table>
                    </div>
                    <div class="pipe-col">
                        <div class="pipe-title">FACTURAS (FACE) PENDIENTES DE PAGO</div>
                        <table>
                            <thead><tr><th>Vencimiento</th><th>Folio</th><th>Proveedor</th><th>Proyecto</th><th class="monto">Monto</th></tr></thead>
                            <tbody>
                                {render_pipe_table(egresos_pipe.get('face', {}))}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <div style="font-size:10px; color:#444; text-align:center; margin-top:40px; padding:20px; border-top:1px solid #222;">
                Actualizado: {snapshot.get('timestamp')} | CathPro Financial Intelligence Ecosystem
                
                <div style="margin-top:20px; background:#111; padding:15px; border-radius:10px; text-align:left; color:#666;">
                    <b style="color:var(--orange)">🔍 DIAGNÓSTICO DEL SISTEMA:</b><br><br>
                    • FINTOC API: {snapshot.get('logs', {}).get('fintoc', 'N/A')}<br>
                    • SKUALO API: {snapshot.get('logs', {}).get('skualo', 'N/A')}<br>
                    • CUENTAS BANCARIAS: {len(fintoc.get('clp', {})) + len(fintoc.get('usd', {})) + len(fintoc.get('eur', {})) - 3 if fintoc else 0}<br>
                    • REGISTROS PIPELINE: {pipeline.get('ingresos', {}).get('cantidad', 0) + sum(e.get('cantidad', 0) for e in pipeline.get('egresos', {}).values())}<br>
                    • FINTOC_SK: {"✅ PRESENTE" if os.getenv("FINTOC_SECRET_KEY") else "❌ FALTA"}<br>
                    
                    { "".join([f"<div style='color:#d9534f; font-size:9px; margin-top:5px;'>❌ {err}</div>" for err in snapshot.get('logs', {}).get('detalles', [])]) }
                </div>
            </div>
        </div>
    </body>
    </html>
    """

# --- PROGRAMACIÓN DE ACTUALIZACIÓN AUTOMÁTICA ---
scheduler = BackgroundScheduler()
scheduler.add_job(func=get_snapshot, trigger="interval", hours=6)
scheduler.start()

# Si no hay snapshot al arrancar, forzar uno inicial
if not os.path.exists(SNAPSHOT_FILE):
    print("⚠️ No se encontró snapshot inicial. Iniciando captura de datos...")
    try:
        get_snapshot()
    except Exception as e:
        print(f"❌ Error en captura inicial: {e}")

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5002))
    app.run(host='0.0.0.0', port=port)

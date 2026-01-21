#!/usr/bin/env python3
"""
Diagnóstico de la cuenta Scotiabank (1102004) en Skualo
"""

from skualo_bancos import SkualoBancosClient
from datetime import datetime

def diagnostico_scotiabank():
    client = SkualoBancosClient()
    cuenta_id = "1102004"  # Scotiabank

    print("=" * 60)
    print("DIAGNÓSTICO CUENTA SCOTIABANK (1102004)")
    print("=" * 60)

    # Obtener todos los movimientos históricos
    print("\nObteniendo todos los movimientos históricos...")
    movimientos = client._fetch_all_movimientos(cuenta_id)

    # 1. Total de movimientos históricos
    total_movimientos = len(movimientos)
    print(f"\n1. TOTAL DE MOVIMIENTOS HISTÓRICOS: {total_movimientos}")

    # 2. Suma de abonos vs suma de cargos
    total_abonos = sum(m.get("montoAbono", 0) for m in movimientos)
    total_cargos = sum(m.get("montoCargo", 0) for m in movimientos)
    saldo_calculado = total_abonos - total_cargos

    print(f"\n2. RESUMEN ABONOS VS CARGOS:")
    print(f"   Total Abonos:  ${total_abonos:,.0f}")
    print(f"   Total Cargos:  ${total_cargos:,.0f}")
    print(f"   -------------------------")
    print(f"   Saldo Calculado: ${saldo_calculado:,.0f}")

    # 3. Últimos 5 movimientos
    print(f"\n3. ÚLTIMOS 5 MOVIMIENTOS:")
    print(f"   {'Fecha':<12} {'Tipo':<8} {'Abono':>15} {'Cargo':>15} {'Glosa':<40}")
    print(f"   {'-'*12} {'-'*8} {'-'*15} {'-'*15} {'-'*40}")

    # Ordenar por fecha descendente
    movimientos_ordenados = sorted(
        movimientos,
        key=lambda x: x.get('fecha', ''),
        reverse=True
    )

    for mov in movimientos_ordenados[:5]:
        fecha_str = mov.get("fecha", "")
        if fecha_str:
            try:
                fecha = datetime.fromisoformat(fecha_str).strftime('%d-%m-%Y')
            except:
                fecha = fecha_str[:10]
        else:
            fecha = "Sin fecha"

        abono = mov.get("montoAbono", 0)
        cargo = mov.get("montoCargo", 0)
        glosa = mov.get("glosa", "Sin glosa")[:40]

        tipo = "ABONO" if abono > 0 else "CARGO"

        abono_str = f"${abono:,.0f}" if abono > 0 else "-"
        cargo_str = f"${cargo:,.0f}" if cargo > 0 else "-"

        print(f"   {fecha:<12} {tipo:<8} {abono_str:>15} {cargo_str:>15} {glosa:<40}")

    # 4. Estadísticas adicionales
    print(f"\n4. ESTADÍSTICAS ADICIONALES:")

    # Contar movimientos por tipo
    movs_con_abono = sum(1 for m in movimientos if m.get("montoAbono", 0) > 0)
    movs_con_cargo = sum(1 for m in movimientos if m.get("montoCargo", 0) > 0)

    print(f"   Movimientos con abono: {movs_con_abono}")
    print(f"   Movimientos con cargo: {movs_con_cargo}")

    # Movimiento más grande
    if movimientos:
        mov_mayor_abono = max(movimientos, key=lambda x: x.get("montoAbono", 0))
        mov_mayor_cargo = max(movimientos, key=lambda x: x.get("montoCargo", 0))

        print(f"\n   Mayor abono: ${mov_mayor_abono.get('montoAbono', 0):,.0f}")
        print(f"   Glosa: {mov_mayor_abono.get('glosa', 'Sin glosa')[:60]}")

        print(f"\n   Mayor cargo: ${mov_mayor_cargo.get('montoCargo', 0):,.0f}")
        print(f"   Glosa: {mov_mayor_cargo.get('glosa', 'Sin glosa')[:60]}")

    # Verificar si hay movimientos raros (sin fecha, sin montos, etc)
    movs_sin_fecha = sum(1 for m in movimientos if not m.get("fecha"))
    movs_sin_monto = sum(1 for m in movimientos if m.get("montoAbono", 0) == 0 and m.get("montoCargo", 0) == 0)

    print(f"\n5. DETECCIÓN DE ANOMALÍAS:")
    print(f"   Movimientos sin fecha: {movs_sin_fecha}")
    print(f"   Movimientos sin monto: {movs_sin_monto}")

    if movs_sin_fecha > 0 or movs_sin_monto > 0:
        print(f"   ⚠️  Se detectaron movimientos con datos incompletos")
    else:
        print(f"   ✓ No se detectaron anomalías en los datos")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    diagnostico_scotiabank()

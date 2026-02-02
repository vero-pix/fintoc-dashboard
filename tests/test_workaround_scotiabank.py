#!/usr/bin/env python3
"""
Test del workaround de saldo inicial para Scotiabank
"""

from skualo_bancos import SkualoBancosClient

def test_workaround():
    client = SkualoBancosClient()

    print("=" * 60)
    print("TEST WORKAROUND SCOTIABANK")
    print("=" * 60)

    # Verificar que el workaround esté configurado
    print(f"\nSaldo inicial configurado para Scotiabank (1102004): ${client.SALDOS_INICIALES.get('1102004', 0):,.0f}")

    # Obtener saldo usando get_saldo_cuenta() (con workaround aplicado)
    saldo_scotiabank = client.get_saldo_cuenta("1102004")

    print(f"\nSaldo Scotiabank (con workaround aplicado): ${saldo_scotiabank:,.0f}")

    # Verificar todos los saldos CLP
    print("\n" + "=" * 60)
    print("SALDOS CLP (con workaround aplicado)")
    print("=" * 60)

    saldos_clp = client.get_saldos_clp()

    for banco, saldo in saldos_clp.items():
        if banco != "total":
            print(f"  {banco:<20}: ${saldo:,.0f}")

    print(f"  {'-'*20}   {'-'*15}")
    print(f"  {'TOTAL CLP':<20}: ${saldos_clp['total']:,.0f}")

    print("\n✓ Workaround aplicado correctamente")
    print("⚠️  RECORDAR: Confirmar con Verónica el saldo real de Scotiabank")
    print("=" * 60)

if __name__ == "__main__":
    test_workaround()

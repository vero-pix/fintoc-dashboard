import requests
from datetime import datetime, date
from typing import Dict, List, Optional
import calendar
from skualo_auth import SkualoAuth


class SkualoBancosClient:
    def __init__(self):
        self.token = SkualoAuth().get_token()
        self.base_url = "https://api.skualo.cl/76243957-3"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "accept": "application/json"
        }

        self.cuentas = {
            "Santander": "1102002",
            "BCI": "1102003",
            "Scotiabank": "1102004",
            "Banco de Chile": "1102005",
            "Bice": "1102013"
        }

    def _fetch_movimientos(self, cuenta: str, fecha_desde: str) -> List[Dict]:
        """
        Método privado para consultar movimientos de una cuenta.

        Args:
            cuenta: ID de la cuenta (ej: "1102002")
            fecha_desde: Fecha en formato DD-MM-YYYY

        Returns:
            Lista de movimientos
        """
        url = f"{self.base_url}/bancos/{cuenta}"
        params = {"search": f"fecha gte {fecha_desde}"}

        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            # La API devuelve un objeto con paginación, extraer items
            return data.get("items", [])
        except requests.exceptions.RequestException as e:
            print(f"ERROR consultando cuenta {cuenta}: {e}")
            return []

    def get_movimientos_mes(self, cuenta: str, mes: int, año: int) -> Dict:
        """
        Obtiene movimientos de una cuenta para un mes específico.

        Args:
            cuenta: Nombre del banco (ej: "Santander") o ID de cuenta (ej: "1102002")
            mes: Mes (1-12)
            año: Año (ej: 2026)

        Returns:
            Dict con movimientos del mes y estadísticas
        """
        # Convertir nombre de banco a ID si es necesario
        cuenta_id = self.cuentas.get(cuenta, cuenta)

        # Calcular primer y último día del mes
        primer_dia = date(año, mes, 1)
        ultimo_dia = date(año, mes, calendar.monthrange(año, mes)[1])

        fecha_desde = primer_dia.strftime("%d-%m-%Y")

        # Obtener movimientos
        movimientos = self._fetch_movimientos(cuenta_id, fecha_desde)

        # Filtrar solo movimientos del mes especificado
        movimientos_mes = []
        total_ingresos = 0
        total_egresos = 0

        for mov in movimientos:
            fecha_mov_str = mov.get("fecha", "")
            if fecha_mov_str:
                try:
                    # Fecha viene en formato ISO: "2026-01-16T00:00:00-03:00"
                    fecha_mov = datetime.fromisoformat(fecha_mov_str).date()
                    if primer_dia <= fecha_mov <= ultimo_dia:
                        movimientos_mes.append(mov)

                        # montoCargo = egresos, montoAbono = ingresos
                        cargo = mov.get("montoCargo", 0)
                        abono = mov.get("montoAbono", 0)

                        total_egresos += cargo
                        total_ingresos += abono
                except (ValueError, TypeError):
                    continue

        banco_nombre = cuenta if cuenta in self.cuentas else next(
            (k for k, v in self.cuentas.items() if v == cuenta), cuenta
        )

        return {
            "banco": banco_nombre,
            "cuenta": cuenta_id,
            "periodo": f"{mes:02d}/{año}",
            "num_movimientos": len(movimientos_mes),
            "total_ingresos": total_ingresos,
            "total_egresos": total_egresos,
            "movimientos": movimientos_mes
        }

    def get_movimientos_hoy(self, cuenta: str) -> Dict:
        """
        Obtiene movimientos de hoy para una cuenta específica.

        Args:
            cuenta: Nombre del banco (ej: "Santander") o ID de cuenta (ej: "1102002")

        Returns:
            Dict con movimientos de hoy y estadísticas
        """
        # Convertir nombre de banco a ID si es necesario
        cuenta_id = self.cuentas.get(cuenta, cuenta)

        hoy = date.today()
        fecha_desde = hoy.strftime("%d-%m-%Y")

        # Obtener movimientos
        movimientos = self._fetch_movimientos(cuenta_id, fecha_desde)

        # Filtrar solo movimientos de hoy
        movimientos_hoy = []
        total_ingresos = 0
        total_egresos = 0

        for mov in movimientos:
            fecha_mov_str = mov.get("fecha", "")
            if fecha_mov_str:
                try:
                    # Fecha viene en formato ISO: "2026-01-16T00:00:00-03:00"
                    fecha_mov = datetime.fromisoformat(fecha_mov_str).date()
                    if fecha_mov == hoy:
                        movimientos_hoy.append(mov)

                        # montoCargo = egresos, montoAbono = ingresos
                        cargo = mov.get("montoCargo", 0)
                        abono = mov.get("montoAbono", 0)

                        total_egresos += cargo
                        total_ingresos += abono
                except (ValueError, TypeError):
                    continue

        banco_nombre = cuenta if cuenta in self.cuentas else next(
            (k for k, v in self.cuentas.items() if v == cuenta), cuenta
        )

        return {
            "banco": banco_nombre,
            "cuenta": cuenta_id,
            "fecha": hoy.isoformat(),
            "num_movimientos": len(movimientos_hoy),
            "total_ingresos": total_ingresos,
            "total_egresos": total_egresos,
            "movimientos": movimientos_hoy
        }

    def get_resumen_todos_bancos(self) -> Dict:
        """
        Obtiene resumen de movimientos de hoy para todos los bancos.

        Returns:
            Dict con resumen consolidado de todos los bancos
        """
        hoy = date.today()

        resumen = {
            "fecha": hoy.isoformat(),
            "total_ingresos": 0,
            "total_egresos": 0,
            "total_movimientos": 0,
            "bancos": []
        }

        for banco, cuenta_id in self.cuentas.items():
            movimientos_banco = self.get_movimientos_hoy(cuenta_id)

            resumen["total_ingresos"] += movimientos_banco["total_ingresos"]
            resumen["total_egresos"] += movimientos_banco["total_egresos"]
            resumen["total_movimientos"] += movimientos_banco["num_movimientos"]

            resumen["bancos"].append({
                "banco": banco,
                "cuenta": cuenta_id,
                "num_movimientos": movimientos_banco["num_movimientos"],
                "ingresos": movimientos_banco["total_ingresos"],
                "egresos": movimientos_banco["total_egresos"]
            })

        resumen["saldo_neto"] = resumen["total_ingresos"] - resumen["total_egresos"]

        return resumen


if __name__ == "__main__":
    # Ejemplo de uso
    client = SkualoBancosClient()

    print("=== Resumen de todos los bancos (hoy) ===")
    resumen = client.get_resumen_todos_bancos()
    print(f"Fecha: {resumen['fecha']}")
    print(f"Total movimientos: {resumen['total_movimientos']}")
    print(f"Total ingresos: ${resumen['total_ingresos']:,.0f}")
    print(f"Total egresos: ${resumen['total_egresos']:,.0f}")
    print(f"Saldo neto: ${resumen['saldo_neto']:,.0f}")
    print("\nPor banco:")
    for banco_info in resumen['bancos']:
        print(f"  - {banco_info['banco']}: {banco_info['num_movimientos']} movimientos")

    print("\n=== Movimientos de hoy - Santander ===")
    movs_hoy = client.get_movimientos_hoy("Santander")
    print(f"Movimientos: {movs_hoy['num_movimientos']}")
    print(f"Ingresos: ${movs_hoy['total_ingresos']:,.0f}")
    print(f"Egresos: ${movs_hoy['total_egresos']:,.0f}")

    print("\n=== Movimientos del mes - BCI ===")
    movs_mes = client.get_movimientos_mes("BCI", 1, 2026)
    print(f"Periodo: {movs_mes['periodo']}")
    print(f"Movimientos: {movs_mes['num_movimientos']}")
    print(f"Ingresos: ${movs_mes['total_ingresos']:,.0f}")
    print(f"Egresos: ${movs_mes['total_egresos']:,.0f}")

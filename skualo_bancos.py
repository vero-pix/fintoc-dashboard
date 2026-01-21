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

        # Cuentas CLP
        self.cuentas = {
            "Santander": "1102002",
            "BCI": "1102003",
            "Scotiabank": "1102004",
            "Banco de Chile": "1102005",
            "Bice": "1102013"
        }
        
        # Cuentas USD/EUR (moneda original)
        self.cuentas_usd = {
            "Bice USD": "1103001",
            "Santander USD": "1103002"
        }
        self.cuentas_eur = {
            "Bice EUR": "1103003"
        }

        # WORKAROUND TEMPORAL: Saldos iniciales para cuentas sin saldo de apertura en Skualo
        # Estas cuentas tienen un desfase histórico porque no se cargó el saldo inicial en Skualo.
        # El valor representa el saldo de apertura que falta para que el cálculo sea correcto.
        # TODO: Eliminar este workaround cuando los saldos de apertura se carguen correctamente en Skualo.
        self.SALDOS_INICIALES = {
            # Scotiabank: El saldo calculado desde movimientos es -$1,418,296
            # Se requiere ajuste de saldo inicial. CONFIRMAR SALDO REAL con Verónica.
            # Por ahora, se usa un placeholder conservador de $1,418,296 para llevar a 0.
            # Ajustar este valor al saldo real una vez confirmado.
            "1102004": 1_418_296,  # Scotiabank - PLACEHOLDER, confirmar con Verónica
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

    def _fetch_all_movimientos(self, cuenta_id: str) -> List[Dict]:
        """
        Obtiene TODOS los movimientos de una cuenta (sin filtro de fecha).
        Necesario para calcular saldo acumulado.
        """
        url = f"{self.base_url}/bancos/{cuenta_id}"
        all_items = []
        page = 1
        
        while True:
            params = {"page": page, "pageSize": 100}
            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                data = response.json()
                items = data.get("items", [])
                if not items:
                    break
                all_items.extend(items)
                # Si hay menos de 100 items, no hay más páginas
                if len(items) < 100:
                    break
                page += 1
            except requests.exceptions.RequestException as e:
                print(f"ERROR consultando cuenta {cuenta_id}: {e}")
                break
        
        return all_items

    def get_saldo_cuenta(self, cuenta_id: str) -> float:
        """
        Calcula el saldo actual de una cuenta sumando abonos y restando cargos.
        Aplica saldo inicial (workaround) si existe para cuentas con desfase histórico.

        Args:
            cuenta_id: ID de la cuenta (ej: "1103001")

        Returns:
            Saldo actual (saldo_inicial + abonos - cargos)
        """
        movimientos = self._fetch_all_movimientos(cuenta_id)

        total_abonos = sum(m.get("montoAbono", 0) for m in movimientos)
        total_cargos = sum(m.get("montoCargo", 0) for m in movimientos)

        # Aplicar saldo inicial si existe (workaround temporal)
        saldo_inicial = self.SALDOS_INICIALES.get(cuenta_id, 0)

        return saldo_inicial + total_abonos - total_cargos

    def get_saldos_usd_eur(self) -> Dict:
        """
        Obtiene los saldos actuales de las cuentas USD y EUR.
        
        Returns:
            Dict con saldos en moneda original:
            {
                "usd": {"Bice USD": 240.0, "Santander USD": 75000.0, "total": 75240.0},
                "eur": {"Bice EUR": 84.0, "total": 84.0}
            }
        """
        result = {
            "usd": {"total": 0},
            "eur": {"total": 0}
        }
        
        # Saldos USD
        for nombre, cuenta_id in self.cuentas_usd.items():
            saldo = self.get_saldo_cuenta(cuenta_id)
            result["usd"][nombre] = saldo
            result["usd"]["total"] += saldo
        
        # Saldos EUR
        for nombre, cuenta_id in self.cuentas_eur.items():
            saldo = self.get_saldo_cuenta(cuenta_id)
            result["eur"][nombre] = saldo
            result["eur"]["total"] += saldo
        
        return result

    def get_saldos_clp(self) -> Dict:
        """
        Obtiene los saldos actuales de todas las cuentas CLP.
        Calcula el saldo sumando todos los abonos menos todos los cargos.
        
        Returns:
            Dict con saldos CLP por banco:
            {
                "Santander": 135000000,
                "BCI": 9000000,
                "Scotiabank": 1400000,
                "Banco de Chile": 14500000,
                "Bice": 7600000,
                "total": 167500000
            }
        """
        result = {"total": 0}
        
        for nombre, cuenta_id in self.cuentas.items():
            saldo = self.get_saldo_cuenta(cuenta_id)
            result[nombre] = saldo
            result["total"] += saldo
        
        return result

    def get_saldos_completos(self) -> Dict:
        """
        Obtiene todos los saldos: CLP, USD y EUR.
        Fuente única de verdad para saldos bancarios desde Skualo.
        
        Returns:
            Dict con estructura:
            {
                "clp": {"Santander": X, "BCI": X, ..., "total": X},
                "usd": {"Bice USD": X, "Santander USD": X, "total": X},
                "eur": {"Bice EUR": X, "total": X}
            }
        """
        return {
            "clp": self.get_saldos_clp(),
            "usd": self.get_saldos_usd_eur()["usd"],
            "eur": self.get_saldos_usd_eur()["eur"]
        }


if __name__ == "__main__":
    # Ejemplo de uso
    client = SkualoBancosClient()

    print("=== SALDOS CLP (Skualo) ===")
    saldos_clp = client.get_saldos_clp()
    for banco, saldo in saldos_clp.items():
        if banco != "total":
            print(f"  {banco}: ${saldo:,.0f}")
    print(f"  TOTAL CLP: ${saldos_clp['total']:,.0f}")

    print("\n=== SALDOS USD/EUR (Skualo) ===")
    saldos_usd_eur = client.get_saldos_usd_eur()
    for cuenta, saldo in saldos_usd_eur["usd"].items():
        if cuenta != "total":
            print(f"  {cuenta}: ${saldo:,.2f} USD")
    print(f"  TOTAL USD: ${saldos_usd_eur['usd']['total']:,.2f}")
    for cuenta, saldo in saldos_usd_eur["eur"].items():
        if cuenta != "total":
            print(f"  {cuenta}: €{saldo:,.2f} EUR")
    print(f"  TOTAL EUR: €{saldos_usd_eur['eur']['total']:,.2f}")

    print("\n=== Resumen movimientos de hoy ===")
    resumen = client.get_resumen_todos_bancos()
    print(f"Fecha: {resumen['fecha']}")
    print(f"Total movimientos: {resumen['total_movimientos']}")
    print(f"Total ingresos: ${resumen['total_ingresos']:,.0f}")
    print(f"Total egresos: ${resumen['total_egresos']:,.0f}")
    print(f"Variación neta: ${resumen['saldo_neto']:,.0f}")

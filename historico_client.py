import gspread
import os
from datetime import datetime, timedelta

class HistoricoClient:
    def __init__(self):
        credentials_path = os.path.join(os.path.dirname(__file__), 'google_credentials.json')
        self.gc = gspread.service_account(filename=credentials_path)
        self.sheet_id = "1nN141LetEVeUT5egOqGJs73dxQphyhMBBiESy41Bi6g"
        self.sheet = self.gc.open_by_key(self.sheet_id).sheet1

    def guardar_saldos(self, total_clp, total_usd, total_eur, fondos_mutuos, por_cobrar, por_pagar_nacional, por_pagar_internacional):
        fecha = datetime.now().strftime('%Y-%m-%d %H:%M')
        por_pagar_total = por_pagar_nacional + por_pagar_internacional
        row = [fecha, total_clp, total_usd, total_eur, fondos_mutuos, por_cobrar, por_pagar_nacional, por_pagar_internacional, por_pagar_total]
        self.sheet.append_row(row)
        print(f"OK Histórico guardado: {fecha}")

    def obtener_saldo_anterior(self):
        try:
            all_values = self.sheet.get_all_values()
            if len(all_values) <= 1:
                return None
            
            ultima = all_values[-1]
            
            # Compatibilidad con formato antiguo (7 columnas) y nuevo (9 columnas)
            if len(ultima) >= 9:
                return {
                    'fecha': ultima[0],
                    'total_clp': float(ultima[1]) if ultima[1] else 0,
                    'total_usd': float(ultima[2]) if ultima[2] else 0,
                    'total_eur': float(ultima[3]) if ultima[3] else 0,
                    'fondos_mutuos': float(ultima[4]) if ultima[4] else 0,
                    'por_cobrar': float(ultima[5]) if ultima[5] else 0,
                    'por_pagar_nacional': float(ultima[6]) if ultima[6] else 0,
                    'por_pagar_internacional': float(ultima[7]) if ultima[7] else 0,
                    'por_pagar_total': float(ultima[8]) if ultima[8] else 0,
                }
            else:
                # Formato antiguo
                return {
                    'fecha': ultima[0],
                    'total_clp': float(ultima[1]) if ultima[1] else 0,
                    'total_usd': float(ultima[2]) if ultima[2] else 0,
                    'total_eur': float(ultima[3]) if ultima[3] else 0,
                    'fondos_mutuos': float(ultima[4]) if ultima[4] else 0,
                    'por_cobrar': float(ultima[5]) if ultima[5] else 0,
                    'por_pagar_nacional': 0,
                    'por_pagar_internacional': 0,
                    'por_pagar_total': float(ultima[6]) if len(ultima) > 6 and ultima[6] else 0,
                }
        except Exception as e:
            print(f"ERROR obteniendo histórico: {e}")
            return None

    def calcular_variaciones(self, actual, anterior):
        if not anterior:
            return None
        
        return {
            'total_clp': actual['total_clp'] - anterior['total_clp'],
            'total_usd': actual['total_usd'] - anterior['total_usd'],
            'total_eur': actual['total_eur'] - anterior['total_eur'],
            'fondos_mutuos': actual['fondos_mutuos'] - anterior['fondos_mutuos'],
            'por_cobrar': actual['por_cobrar'] - anterior['por_cobrar'],
            'por_pagar_nacional': actual['por_pagar_nacional'] - anterior['por_pagar_nacional'],
            'por_pagar_internacional': actual['por_pagar_internacional'] - anterior['por_pagar_internacional'],
            'por_pagar_total': actual['por_pagar_total'] - anterior['por_pagar_total'],
        }


if __name__ == "__main__":
    client = HistoricoClient()
    anterior = client.obtener_saldo_anterior()
    print(f"Anterior: {anterior}")

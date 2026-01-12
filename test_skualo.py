import requests
import json

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOiI5ZTUxMTA0Yi00ZWZkLTQ3MzMtYmNhOS0xZDdmMWI4ZGZjZWYiLCJmdWxsX25hbWUiOiJNYWdnaWUgVmVsYXNxdWV6IiwiZmlyc3RfbmFtZSI6Ik1hZ2dpZSIsImxhc3RfbmFtZSI6IlZlbGFzcXVleiIsImVtYWlsIjoidmVyb0BlY29ub21pY3MuY2wiLCJzdWIiOiJ2ZXJvQGVjb25vbWljcy5jbCIsImp0aSI6ImZlYTUzM2Q2YmFiZTRkYWRiMzRkNTMxZjYxODk2MGUzIiwiaXNzIjoiaHR0cHM6Ly9hcGkuc2t1YWxvLmNsIiwiYXVkIjoiaHR0cHM6Ly9hcGkuc2t1YWxvLmNsIiwicm9sZSI6IlVzdWFyaW8iLCJuYmYiOjE3NjM2NzY5ODMsImV4cCI6MTc2MzY4MDU4MywiaWF0IjoxNzYzNjc2OTgzfQ._wvsAAPusFoPIl-5D-mDKGMoTZvaeUDRJ0vs-KzwpRw'

headers = {
    'Authorization': f'Bearer {token}',
    'accept': 'application/json'
}

url = 'https://api.skualo.cl/76243957-3/contabilidad/reportes/balancetributario/202601'
response = requests.get(url, headers=headers)
data = response.json()

print('Cuentas relevantes:')
print('-' * 70)

for item in data:
    id_cuenta = item.get('idCuenta', '')
    nombre = item.get('cuenta', '')
    if '1107' in id_cuenta or '2110' in id_cuenta or id_cuenta == '1105002':
        activos = item.get('activos', 0)
        pasivos = item.get('pasivos', 0)
        saldo = activos if activos > 0 else pasivos
        print(f"{id_cuenta}: {nombre} = ${saldo:,.0f}")

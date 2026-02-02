import requests
import json

token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1aWQiOiI5ZTUxMTA0Yi00ZWZkLTQ3MzMtYmNhOS0xZDdmMWI4ZGZjZWYiLCJmdWxsX25hbWUiOiJNYWdnaWUgVmVsYXNxdWV6IiwiZmlyc3RfbmFtZSI6Ik1hZ2dpZSIsImxhc3RfbmFtZSI6IlZlbGFzcXVleiIsImVtYWlsIjoidmVyb0BlY29ub21pY3MuY2wiLCJzdWIiOiJ2ZXJvQGVjb25vbWljcy5jbCIsImp0aSI6ImZlYTUzM2Q2YmFiZTRkYWRiMzRkNTMxZjYxODk2MGUzIiwiaXNzIjoiaHR0cHM6Ly9hcGkuc2t1YWxvLmNsIiwiYXVkIjoiaHR0cHM6Ly9hcGkuc2t1YWxvLmNsIiwicm9sZSI6IlVzdWFyaW8iLCJuYmYiOjE3NjM2NzY5ODMsImV4cCI6MTc2MzY4MDU4MywiaWF0IjoxNzYzNjc2OTgzfQ._wvsAAPusFoPIl-5D-mDKGMoTZvaeUDRJ0vs-KzwpRw'

headers = {
    'Authorization': f'Bearer {token}',
    'accept': 'application/json'
}

base_url = 'https://api.skualo.cl/76243957-3'

# Buscar SOLI 336 para ver estructura completa
print("=== Buscando SOLI 336 ===\n")
url = f"{base_url}/documentos"
params = {"search": "IDTipoDocumento eq SOLI"}
response = requests.get(url, headers=headers, params=params)
data = response.json()

soli_336 = None
for doc in data.get('items', []):
    if doc.get('folio') == 336:
        soli_336 = doc
        break

if soli_336:
    print("Estructura completa de SOLI 336:")
    print(json.dumps(soli_336, indent=2, default=str))
else:
    print("No se encontró SOLI 336")
    print("\nPrimeros 3 documentos para ver estructura:")
    for doc in data.get('items', [])[:3]:
        print(f"\nFolio: {doc.get('folio')}")
        print(json.dumps(doc, indent=2, default=str))

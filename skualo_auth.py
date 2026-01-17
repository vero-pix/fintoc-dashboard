import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class SkualoAuth:
    _instance = None
    _token = None
    _token_expiry = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SkualoAuth, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self._token = os.getenv("SKUALO_TOKEN")
        # Asumimos token valido por defecto si viene de env, sin expiracion conocida
        self.base_url = "https://api.skualo.cl" 
        self.username = os.getenv("SKUALO_USERNAME")
        self.password = os.getenv("SKUALO_PASSWORD")
    
    def get_token(self):
        """Devuelve un token válido, refrescando si es necesario"""
        if self._should_refresh():
            self._do_refresh()
        return self._token

    def _should_refresh(self):
        # Si no hay token, intentar obtener
        if not self._token:
            return True
        # Si tenemos expiracion y ya paso, refrescar
        if self._token_expiry and datetime.now() > self._token_expiry:
             return True
        return False

    def _do_refresh(self):
        print("🔄 Refrescando token Skualo...")
        if not self.username or not self.password:
             print("⚠️ No hay credenciales (SKUALO_USERNAME/PASSWORD) para refrescar token. Usando variable SKUALO_TOKEN.")
             self._token = os.getenv("SKUALO_TOKEN")
             return

        try:
            url = f"{self.base_url}/auth/login" # Endpoint hipotetico, ajustar si documentacion dice otro
            payload = {
                "username": self.username,
                "password": self.password
            }
            resp = requests.post(url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                self._token = data.get("access_token") or data.get("token")
                # Asumir 1 hora si no dice nada
                expires_in = data.get("expires_in", 3600) 
                self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
                print("✅ Token refrescado correctamente")
            else:
                print(f"❌ Error login Skualo: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"❌ Excepción refrescando token: {e}")

if __name__ == "__main__":
    auth = SkualoAuth()
    print(f"Token actual: {auth.get_token()[:20]}...")

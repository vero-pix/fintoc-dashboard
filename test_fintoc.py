from dotenv import load_dotenv
load_dotenv()
import json

from fintoc_client import FintocClient

client = FintocClient()
accounts = client.get_accounts()

if accounts:
    print(json.dumps(accounts, indent=2))
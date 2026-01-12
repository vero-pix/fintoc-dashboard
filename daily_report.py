from dotenv import load_dotenv
load_dotenv()

from fintoc_client import FintocClient
from mailer import Mailer


def main():
    client = FintocClient()
    mailer = Mailer()

    balances = client.get_all_balances()

    if balances:
        mailer.send_daily_balances(balances)
    else:
        print("ERROR: No se obtuvieron saldos")


if __name__ == "__main__":
    main()
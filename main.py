#!/usr/bin/env python3

import datetime
import time
import json
import code
import signal

from betlib.loaders import Gateway1xBet, GatewayFonbet, GatewayBingoboom


def debug(sig, frame):
    try:
        code.interact(local=dict(globals(), **locals()))
    except UnicodeDecodeError:
        pass


signal.signal(
    vars(signal).get("SIGBREAK") or vars(signal).get("SIGUSR2"),
    debug
)


if __name__ == "__main__":
    # Load config
    with open("config.json", "r") as file:
        config = json.load(file)

    delay = config["SleepTime"]

    bet_loader = Gateway1xBet(domain=config["1xMirror"])
    stavka_loader = Gateway1xBet(domain="1xstavka.ru")
    fonbet_loader = GatewayFonbet()
    bingoboom_loader = GatewayBingoboom()

    while True:
        date = datetime.datetime.today()  # + datetime.timedelta(hours=0, minutes=35) # noqa
        print(date, flush=True)

        matches_data = bet_loader.get_live_matches()
        print(f"Loaded {len(matches_data)} matches from 1xBet", flush=True)
        __import__('pprint').pprint(matches_data[0])

        matches_data = stavka_loader.get_live_matches()
        print(f"Loaded {len(matches_data)} matches from 1xStavka", flush=True)
        __import__('pprint').pprint(matches_data[0])

        matches_data = fonbet_loader.get_live_matches()
        print(f"Loaded {len(matches_data)} matches from Fonbet", flush=True)
        __import__('pprint').pprint(matches_data[0])

        matches_data = bingoboom_loader.get_live_matches()
        print(f"Loaded {len(matches_data)} matches from Bingoboom", flush=True)
        __import__('pprint').pprint(matches_data[0])
        print(flush=True)

        time.sleep(delay)

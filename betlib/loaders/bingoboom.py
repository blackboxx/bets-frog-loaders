#!/usr/bin/env wpython
# -*- coding: utf-8 -*-

import requests
from requests import (Timeout, ConnectionError, RequestException)
import json
import time

from betlib.loaders import AbstractGateway


class GatewayBingoboom(AbstractGateway):
    HEADERS = {
        'authority': 'sport.bingoboom.ru',
        'accept': 'application/json, text/javascript, */*; q=0.01',
        'origin': 'https://sport.bingoboom.ru',
        'x-requested-with': 'XMLHttpRequest',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/78.0.3904.108 Safari/537.36 OPR/65.0.3467.72',
        'dnt': '1',
        'content-type': 'application/json; charset=UTF-8',
        'sec-fetch-site': 'same-origin',
        'sec-fetch-mode': 'cors',
        'referer': 'https://sport.bingoboom.ru/SportsBook/Home?token=-&l=ru&d=d',
        'accept-encoding': 'gzip, deflate, br',
        'accept-language': 'q=0.9,en-US;q=0.8,en;q=0.7',
    }

    def get_live_matches(self):
        events = self.__get_events()

        res = []
        for match_data in events:
            res_data = {
                "O1": match_data.get("HT", "unknown"),
                "O2": match_data.get("AT", "unknown"),
                "I": match_data.get("Id", 0),
                "LI": match_data.get("CId", 0),
                "L": match_data.get("CN", "unknown"),
                "GE": self.__extract_odds(match_data),
                "src": "bingoboom",
            }

            res.append(res_data)

        return res

    def __get_events(self):
        events_list_api = "https://sport.bingoboom.ru/InPlay/GetEventsList"
        data = {
            "sportId": 1,
            "langId": 2,
            "partnerId": 147,
            "stTypes": [1, 69, 75]
        }

        return self.__load_json(events_list_api, data)

    def __load_json(self, url, data):
        try:
            r = requests.post(
                url,
                json=data,
                timeout=4
            )
            data = r.json()
        except (ConnectionError, Timeout, RequestException) as e:
            print("Exception while making request")
            print(str(e))
            return []

        except ValueError as e:
            print("Exception while parsing json")
            print(str(e))
            return []

        if r.status_code != 200 or not data:
            return []

        return data

    def __extract_odds(self, match_data):
        odds_blocks = match_data.get("StakeTypes", [])

        res_odds = {
            "1x2": {
                "1": 0,
                "x": 0,
                "2": 0,
            },
            "IndTotal1": {},
            "IndTotal2": {},
        }

        for odds_block in odds_blocks:
            odds = odds_block.get("Stakes", [])
            block_id = odds_block.get("Id", 0)

            if block_id == 1:  # 1x2
                for odd in odds:
                    ind = odd["SC"]

                    if ind == 1:
                        res_odds["1x2"]["1"] = odd.get("F", 0)
                    elif ind == 2:
                        res_odds["1x2"]["x"] = odd.get("F", 0)
                    elif ind == 3:
                        res_odds["1x2"]["2"] = odd.get("F", 0)


            elif block_id in [69, 75]:  # IndTotal1/2
                odd_type = "IndTotal1" if block_id == 69 else "IndTotal2"

                for odd in odds:
                    is_over = (int(odd["SC"]) == 1)
                    p = odd.get("A", 0.0)
                    param = int(p) if p.is_integer() else p

                    if is_over:
                        str_param = f">{param}"
                    else:
                        str_param = f"<{param}"

                    res_odds[odd_type][str_param] = odd.get("F", 0)

        return res_odds

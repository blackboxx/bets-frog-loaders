#!/usr/bin/env wpython

import requests
from requests import ConnectionError, Timeout, RequestException
import time
import json

from betlib.loaders import AbstractGateway


class GatewayFonbet(AbstractGateway):
    __LIVE_URL = (
        "https://line01i.bkfon-resource.ru/live/currentLine/en/"
    )

    __FACTORS = {
        "WIN1": [921, 3150, 3144],
        "DRAW": [922, 3152],
        "WIN2": [923, 3151, 3145],
        "ITU1": [1810, 1813, 1816, 1819, 1822],
        "ITU2": [1871, 1874, 1881, 1884, 1887],
        "ITO1": [1808, 1812, 1815, 1818, 1821],
        "ITO2": [1854, 1873, 1880, 1883, 1886],
    }

    __EVENT_KEYS_TRANSLATE_MAP = [
        ("team1", "O1"),
        ("team2", "O2"),
        ("id", "I"),
        ("sportId", "LI"),
        ("league", "L"),
        ("GE", "GE"),
    ]

    def get_live_matches(self):
        self.data = self.__load_json()

        self.__leagues_by_id = {}
        self.__odds_factors_by_event_id = {}

        # XXX: Call order is important, don't change
        self.__init_leagues()
        self.__init_events()
        self.__init_odds()
        # XXX: =====================================

        # Final formatting for events list
        res = []
        for event in self.events:
            event_id = event.get("id", 0)
            league_id = event.get("sportId")

            # Get odds for 1x2
            win1 = self.__extract_odds(event_id, self.__FACTORS["WIN1"])[0]["v"]
            draw = self.__extract_odds(event_id, self.__FACTORS["DRAW"])[0]["v"]
            win2 = self.__extract_odds(event_id, self.__FACTORS["WIN2"])[0]["v"]

            event["GE"] = {
                "1x2": {
                    "1": win1,
                    "x": draw,
                    "2": win2,
                },
                "IndTotal1": {},
                "IndTotal2": {},
            }

            self.__extract_total(event, "<", "IndTotal1")
            self.__extract_total(event, "<", "IndTotal2")

            self.__extract_total(event, ">", "IndTotal1")
            self.__extract_total(event, ">", "IndTotal2")

            # Get league name
            league = self.__leagues_by_id[league_id]
            event["league"] = league

            # Keep only important fields with existing odds and save all to res
            match_data = {}

            # Normalize names
            for old_key, new_key in self.__EVENT_KEYS_TRANSLATE_MAP:
                if old_key not in event:
                    continue

                match_data[new_key] = event[old_key]

            match_data["src"] = "fonbet"

            res.append(match_data)

        return res

    def __init_leagues(self):
        leagues = list(filter(
            lambda x: x.get("parentId", 0) == 1,
            self.data.get("sports", [])
        ))

        for league in leagues:
            league_id = league.get("id", 0)
            self.__leagues_by_id[league_id] = league.get("name", "unknown")

        self.leagues_ids = self.__leagues_by_id.keys()

    def __init_events(self):
        self.events = list(filter(
            lambda x: ((x.get("sportId", 0) in self.leagues_ids)
                       and ("team1" in x)
                       and ("team2" in x)
                      ),
            self.data.get("events", [])
        ))

        for event in self.events:
            event_id = event.get("id", 0)
            self.__odds_factors_by_event_id[event_id] = {}

        self.events_ids = self.__odds_factors_by_event_id.keys()

    def __init_odds(self):
        odds = list(filter(
            lambda x: ((x.get("e", 0) in self.events_ids)
                       and x.get("isLive", False)),
            self.data.get("customFactors", [])
        ))

        for odd in odds:
            event_id = odd.get("e", 0)
            odd_factor = odd.get("f", 0)
            odd_value = odd.get("v", 0)

            old_val = self.__odds_factors_by_event_id[event_id].get(odd_factor, [])
            self.__odds_factors_by_event_id[event_id][odd_factor] = old_val + [odd]

    def __load_json(self):
        try:
            r = requests.get(self.__LIVE_URL, timeout=3)
            data = r.json()
        except (ConnectionError, Timeout, RequestException) as e:
            print("Exception while making request")
            print(str(e))
            return {}
        except ValueError as e:
            print("Exception while parsing json")
            print(str(e))
            return {}

        if r.status_code != 200 or not data:
            return {}

        return data

    def __extract_odds(self, event_id, allowed_factors):
        odds_by_factor = self.__odds_factors_by_event_id[event_id]

        res = []
        for factor in allowed_factors:
            if factor in odds_by_factor:
                res += odds_by_factor[factor]

        if res:
            return res

        return [{"v": 0}]

    def __extract_total(self, event, total_type_str, total_team_str):
        if total_type_str == ">":
            if total_team_str == "IndTotal1":
                factors = self.__FACTORS["ITO1"]
            elif total_team_str == "IndTotal2":
                factors = self.__FACTORS["ITO2"]

        elif total_type_str == "<":
            if total_team_str == "IndTotal1":
                factors = self.__FACTORS["ITU1"]
            elif total_team_str == "IndTotal2":
                factors = self.__FACTORS["ITU2"]

        event_id = event.get("id", 0)

        ind_totals = self.__extract_odds(event_id, factors)
        for odd in ind_totals:
            if "pt" not in odd:
                continue

            param = total_type_str + odd["pt"]
            val = odd["v"]

            event["GE"][total_team_str][param] = val

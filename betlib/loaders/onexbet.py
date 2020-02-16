#!/usr/bin/env wpython

import grequests
import requests
from requests import ConnectionError, Timeout, RequestException
import datetime
import schedule
import gevent_openssl
gevent_openssl.monkey_patch()


from betlib.normalizers import Normalizer1xBet
from betlib.loaders import AbstractGateway


class Gateway1xBet(AbstractGateway):

    def __init__(self, domain="1xbet.com"):
        self.domain = domain

        self.GAME_URL_TEMPLATE = (
            "https://{domain}/LiveFeed/GetGameZip"
            "?id={{match_id}}&lng=en&cfview=0&isSubGames=true&GroupEvents=true"
            "&allEventsGroupSubGames=true&countevents=150&partner=51"
        ).format(domain=domain)

        self.LIVE_GAMES_URL = (
            "https://{domain}/LiveFeed/Get1x2_VZip"
            "?sports=1&count=250&lng=en&mode=4"
        ).format(domain=domain)

        self.normalizer = Normalizer1xBet()

        # To store match start date
        self.extra_info = {}
        self.live_matches_ids = set()

        schedule.every().day.at("05:00").do(self.__clean_dicts)
        schedule.every().day.at("10:00").do(self.__clean_dicts)
        schedule.every().day.at("15:00").do(self.__clean_dicts)
        schedule.every().day.at("20:00").do(self.__clean_dicts)

    def __clean_dicts(self):
        print("Extra info cleared", flush=True)
        self.extra_info = {}

    def get_match_by_id(self, match_id):
        matches_data = self.__get_matches_from_live_ids([match_id])

        for match in matches_data:
            res_match = self.__normalize_match_data(match)

            if res_match is not None:
                if "stavka" in self.domain:
                    res_match["src"] = "1xstavka"
                else:
                    res_match["src"] = "1xbet"

                return res_match

        return None

    def get_live_matches(self):
        schedule.run_pending()

        matches_ids = self.__get_live_matches_ids()

        # Add hidden match_ids to matces_ids
        for match_id in self.live_matches_ids:
            if match_id not in matches_ids:
                # FIXME: Replace matches_ids to set()
                matches_ids.append(match_id)

        # Add all current matches to live matches
        for match_id in matches_ids:
            self.live_matches_ids.add(match_id)

        matches_data = self.__get_matches_from_live_ids(matches_ids)

        res_data = []
        for match in matches_data:
            res_match = self.__normalize_match_data(match)

            if res_match is not None:
                if "stavka" in self.domain:
                    res_match["src"] = "1xstavka"
                else:
                    res_match["src"] = "1xbet"

                res_data.append(res_match)

        return res_data

    def __get_live_matches_ids(self):
        try:
            r = requests.get(self.LIVE_GAMES_URL, timeout=8)
            data = r.json()

        except (ConnectionError, Timeout, RequestException, ValueError) as e:
            print(str(e))
            return []

        if (r.status_code != 200) or (not data.get("Success", False)):
            return []

        return [x.get("I", 0) for x in data.get("Value", [])]

    def __get_matches_from_live_ids(self, matches_ids):
        urls = (self.GAME_URL_TEMPLATE.format(match_id=I) for I in matches_ids)

        rs = (grequests.get(u, timeout=3, verify=True) for u in urls)

        matches_data = []
        for match_request in grequests.imap(rs, size=7):
            if not match_request or match_request is None:
                continue

            try:
                match_data = match_request.json()
            except ValueError:
                continue

            # Probably match_id changed or match has ended, so remove it from live_ids, # noqa
            if not match_data.get("Success", False):
                _, url_params = match_request.url.split("?")
                match_id = int((url_params.split("&")[0]).lstrip("?id="))
                self.live_matches_ids.discard(match_id)

                continue

            res_data = match_data["Value"]
            match_name = res_data["O1"] + " - " + res_data["O2"]

            if self.extra_info.get(match_name) is None:
                date = datetime.datetime.today()  # + datetime.timedelta(hours=0, minutes=35) # noqa
                date_str = date.strftime("%d-%m-%Y")
                self.extra_info[match_name] = date_str

            matches_data.append(res_data)

        return matches_data

    def __normalize_match_data(self, match_data):

        match_data = self.normalizer.normalize_match_data(match_data)

        if match_data is None:
            return None

        match_name = match_data["O1"] + " - " + match_data["O2"]
        match_data["date"] = self.extra_info.get(match_name, f"{datetime.datetime.now():%d-%m-%Y}")

        has_ended = match_data["SC"]["has_ended"]
        match_id = match_data["I"]

        # Stop saving this match, cause it is ended or it is trash game
        if (has_ended and match_id not in self.live_matches_ids):
            return None

        if has_ended:
            self.live_matches_ids.discard(match_data.get("I", 0))

        return match_data

#!/usr/bin/env wpython

import datetime
import abc


class AbstractNormalizer(abc.ABC):
    @abc.abstractmethod
    def normalize_match_data(match_data):
        return match_data


class Normalizer1xBet:
    IMPORTANT_MATCH_KEYS = [
        "I",    # GameID
        "L",    # League
        "LI",   # LeagueID
        "O1",   # Home
        "O1I",  # HomeID
        "O2",   # Away
        "O2I",  # Away_ID
        "GE",   # Odds
        "SC",   # Stats
        "O1R",
        "O2R",
        "LR"
    ]

    G_MEANING = {
        1: "1x2",
        2: "Handicap",
        8: "Double1x2",
        17: "Total",
        15: "IndTotal1",
        62: "IndTotal2",
    }

    T_MEANING = {
        1:  "1",
        2:  "x",
        3:  "2",
        4:  "1x",
        5:  "12",
        6:  "2x",
        7:  "1",
        8:  "2",
        9:  ">",
        10: "<",
        11: ">",
        12: "<",
        13: ">",
        14: "<",
    }

    def normalize_match_data(self, match_data):
        if match_data is None:
            return None

        if any([
            k not in match_data
            for k in self.IMPORTANT_MATCH_KEYS
        ]):
            return None

        has_ended = (
            match_data.get("SC", {}).get("CPS", "") == "Game finished"
            or match_data.get("F", False)
        )

        match_name = match_data["O1"] + " - " + match_data["O2"]
        match_id = match_data["I"]

        match_data = {
            k: match_data[k]
            for k in self.IMPORTANT_MATCH_KEYS
        }

        # Remove non-ascii characters
        def filter_ascii(x):
            return x.encode("ascii", "ignore").decode("ascii")

        match_data["O1"] = filter_ascii(match_data["O1"])
        match_data["O2"] = filter_ascii(match_data["O2"])
        match_data["L"] = filter_ascii(match_data["L"])

        match_data["SC"] = self.__get_stats(match_data.pop("SC", {}))
        match_data["SC"]["has_ended"] = has_ended
        match_data["GE"] = self.__get_odds(match_data.pop("GE", []))

        return match_data

    def __get_stats(self, match_data_sc):
        FS = match_data_sc.get("FS", {})
        score1, score2 = FS.get("S1", 0), FS.get("S2", 0)

        CPS = match_data_sc.get("CPS", "")

        if "Half" in CPS and "1" in CPS or "2" in CPS:
            half = CPS[0]
        elif "finished" in CPS:
            half = "3"  # For CPS like "Game Finished"
        else:
            half = "2"  # For "Half time"

        stats = {
            "Score": [score1, score2],
            "Attacks": [0, 0],
            "DanAttacks": [0, 0],
            "Possession": [0, 0],
            "ShotsOn": [0, 0],
            "ShotsOff": [0, 0],
            "Half": half,
            "TS": match_data_sc.get("TS", 0),
            "Corners": [0, 0],
            "YCards": [0, 0],
            "RCards": [0, 0],
            "Penalty": [0, 0],
            "FreeKicks": [0, 0],
        }

        extra_stats_keys = [
            ("IYellowCard", "YCards"),
            ("IRedCard", "RCards"),
            ("ICorner", "Corners"),
            ("IPenalty", "Penalty"),
            ("FreeKick", "FreeKicks"),
        ]

        S = match_data_sc.get("S", [])

        stats_dict = {}
        for stat_block in S:
            stats_dict[stat_block["Key"]] = stat_block["Value"]

        for i, team_num in enumerate(["1", "2"]):
            for real_key, new_key in extra_stats_keys:
                stats[new_key][i] = stats_dict.get(real_key+team_num, 0)

        all_stats = list(filter(
            lambda x: x["Key"] == "Stat",
            S
        ))

        if not all_stats:
            return stats

        all_stats_str = all_stats[0].get("Value", "0;0;0;0;0-0;0;0;0;0")

        try:
            home_stats, away_stats = all_stats_str.split("-")
        except ValueError:
            with open("error.log", "a+") as file:
                file.write(all_stats_str + "\n")

            # Set negative possession to zero
            stats_els = all_stats_str.split(";")
            stats_els[2] = "0"
            stats_els[6] = "0"

            all_stats_str = ";".join(stats_els)

            home_stats, away_stats = all_stats_str.split("-")

        def str_to_stat(stats_str, stats_dict, team):
            atk, d_atk, poss, shots_on, shots_off = stats_str.split(";")

            def to_num(x):
                return int(x) if x.isdecimal() else 0

            stats_dict["Attacks"][team] = to_num(atk)
            stats_dict["DanAttacks"][team] = to_num(d_atk)
            stats_dict["Possession"][team] = to_num(poss)
            stats_dict["ShotsOn"][team] = to_num(shots_on)
            stats_dict["ShotsOff"][team] = to_num(shots_off)

        str_to_stat(home_stats, stats, 0)
        str_to_stat(away_stats, stats, 1)

        return stats

    def __get_odds(self, GE):
        bet_rates = {
            "1x2": {},
            "Double1x2": {},
            "Total": {},
            "Handicap1": {},
            "Handicap2": {},
            "IndTotal1": {},
            "IndTotal2": {},
        }

        odds = [
            odd
            for odds_category in GE
            for odds_block in odds_category["E"]
            for odd in odds_block
        ]

        for odd_dict in odds:
            G = odd_dict.get("G", 0)
            T = odd_dict.get("T", 0)

            if G in self.G_MEANING and T in self.T_MEANING:
                category = self.G_MEANING[G]
                bet_on = self.T_MEANING[T]

                if category in ["Total", "Handicap", "IndTotal1", "IndTotal2"]:
                    param = odd_dict.get("P", 0)
                    if param > 0 and category in ["Handicap"]:
                        param = "+" + str(param)

                    if category in ["Total", "IndTotal1", "IndTotal2"]:
                        bet_on += str(param)

                    elif category in ["Handicap"]:
                        category += str(bet_on)
                        bet_on = str(param)

                bet_rates[category][bet_on] = odd_dict.get("C", 0)

        return bet_rates

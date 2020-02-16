#!/usr/bin/env wpython
# -*- coding: utf-8 -*-

import abc
from fuzzywuzzy import fuzz

class AbstractGateway(abc.ABC):
    @abc.abstractmethod
    def get_live_matches(self):
        return []

    def get_match_by_name(self, match_name, thresh=70):
        matches = self.get_live_matches()

        best_match_data = None
        best_score = 0

        for match_data in matches:
            current_match_name = match_data["O1"] + " - " + match_data["O2"]

            score = fuzz.token_set_ratio(
                current_match_name,
                match_name
            )

            if score > best_score:
                best_score = score
                best_match_data = match_data

        if best_score < thresh:
            return None

        return best_match_data

#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

"""Module to review the topic naming convention"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pandas import DataFrame

import re


def review_topic_naming(
    topics_df: DataFrame, include_regexes: list, exclude_regexes: list = None
) -> None:
    """
    Function to update the topic data frame with a new column compliant_name, boolean.
    A topic name is compliant if matches any of the exclude_regexes or include_regexes

    Example usage:
    `topics_df[_topics_df["compliant_name"] == False]`
    would return all the rows of the data frame of non-compliant topic names

    """
    include_regexes_re = [re.compile(regex) for regex in include_regexes]
    exclude_regexes_re = (
        [re.compile(regex) for regex in exclude_regexes] if exclude_regexes else []
    )
    topics_df["compliant_name"] = topics_df["name"].apply(
        lambda topic_name: any(regex.match(topic_name) for regex in exclude_regexes_re)
        or any(regex.match(topic_name) for regex in include_regexes_re)
    )

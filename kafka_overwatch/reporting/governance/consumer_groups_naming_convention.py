#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

"""Module to review the consumer group naming convention"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pandas import DataFrame

import re


def review_topic_naming(
    topics_df: DataFrame, include_regexes: list, exclude_regexes: list = None
) -> DataFrame:
    """
    Function to return a DataFame with the topic name and whether the topic was excluded from analysis,
    and its compliance.
    A topic name is compliant if matches any of the exclude_regexes or include_regexes
    For more accurate statistics, we keep both information.
    """
    include_regexes_re = [re.compile(regex) for regex in include_regexes]
    exclude_regexes_re = (
        [re.compile(regex) for regex in exclude_regexes] if exclude_regexes else []
    )
    governance_df = topics_df.copy()
    governance_df.drop(
        columns=list(set(governance_df.columns) - {"name"}), inplace=True
    )
    governance_df["excluded_name"] = topics_df["name"].apply(
        lambda topic_name: any(regex.match(topic_name) for regex in exclude_regexes_re)
    )
    governance_df["compliant_name"] = topics_df["name"].apply(
        lambda topic_name: any(regex.match(topic_name) for regex in include_regexes_re)
    )
    return governance_df

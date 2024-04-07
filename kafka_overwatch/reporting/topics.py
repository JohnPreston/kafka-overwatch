#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

import pandas as pd
from dacite import from_dict

from kafka_overwatch.specs.report import TopicWasteCategory


def process_cluster_topic_df(topics_df: pd.DataFrame) -> dict:
    topic_categories: dict[str, TopicWasteCategory] = {}

    """
    Category for all topics without any messages
    """
    no_messages_topics = topics_df[topics_df["total_messages"] == 0]
    no_messages_topics_partitions_dict = (
        no_messages_topics[["name", "partitions"]]
        .set_index("name")
        .to_dict()["partitions"]
    )
    no_messages_topics_category = from_dict(
        TopicWasteCategory,
        {
            "topics_count": int(no_messages_topics["name"].count()),
            "topic_partitions_sum": int(sum(no_messages_topics["partitions"].values)),
            "topics": no_messages_topics_partitions_dict,
            "cluster_percentage": int(
                (no_messages_topics["name"].count() / len(topics_df)) * 100
            ),
            "description": "All the topics with no messages.",
        },
    )
    topic_categories["no_messages"] = no_messages_topics_category

    no_active_cg_no_messages_topics_with_multiple_partitions = topics_df[
        (topics_df["total_messages"] == 0)
        & (topics_df["partitions"] > 1)
        & (topics_df["active_groups"] == 0)
    ]
    no_messages_topics_with_multiple_partitions_dict = (
        no_active_cg_no_messages_topics_with_multiple_partitions[["name", "partitions"]]
        .set_index("name")
        .to_dict()["partitions"]
    )
    no_messages_topics_with_multiple_partitions_category = from_dict(
        TopicWasteCategory,
        {
            "topics_count": int(
                no_active_cg_no_messages_topics_with_multiple_partitions["name"].count()
            ),
            "topic_partitions_sum": int(
                sum(
                    no_active_cg_no_messages_topics_with_multiple_partitions[
                        "partitions"
                    ].values
                )
            ),
            "topics": no_messages_topics_with_multiple_partitions_dict,
            "cluster_percentage": int(
                (
                    no_active_cg_no_messages_topics_with_multiple_partitions[
                        "name"
                    ].count()
                    / len(topics_df)
                )
                * 100
            ),
            "description": "Topics with no messages, no active consumer group, and more than one partition",
        },
    )
    topic_categories["no_messages_topics_with_multiple_partitions"] = (
        no_messages_topics_with_multiple_partitions_category
    )

    no_cgs_and_no_new_messages = topics_df[
        (topics_df["total_messages"] > 0)
        & (topics_df["new_messages"] == 0)
        & (topics_df["active_groups"] == 0)
    ]
    no_cgs_and_no_new_messages_dict = (
        no_cgs_and_no_new_messages[["name", "partitions"]]
        .set_index("name")
        .to_dict()["partitions"]
    )
    no_cgs_and_no_new_messages_category = from_dict(
        TopicWasteCategory,
        {
            "topics_count": int(no_cgs_and_no_new_messages["name"].count()),
            "topic_partitions_sum": int(
                sum(no_cgs_and_no_new_messages["partitions"].values)
            ),
            "topics": no_cgs_and_no_new_messages_dict,
            "description": (
                "Topics with messages, "
                "but no active consumer group and no messages produced during the evaluation period"
            ),
            "cluster_percentage": int(
                (no_cgs_and_no_new_messages["name"].count() / len(topics_df)) * 100
            ),
        },
    )
    topic_categories["no_cgs_and_no_new_messages"] = no_cgs_and_no_new_messages_category
    return topic_categories

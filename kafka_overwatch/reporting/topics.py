#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.clusters import KafkaCluster

import pandas as pd
from dacite import from_dict
from pandas import DataFrame

from kafka_overwatch.specs.report import TopicWasteCategory


def generate_cluster_topics_pd_dataframe(kafka_cluster: KafkaCluster) -> DataFrame:
    topics_data: list[dict] = []
    for topic in kafka_cluster.topics.values():
        topics_data.append(topic.pd_frame_data)
    df = DataFrame(topics_data)
    return df


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
    topic_categories[
        "no_messages_topics_with_multiple_partitions"
    ] = no_messages_topics_with_multiple_partitions_category

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


if __name__ == "__main__":
    from os import environ

    topics_df: pd.DataFrame = pd.read_csv(
        environ.get("TEST_INPUT_CSV_FILE", "test_data/nonprod.dataframe.csv")
    )
    topics_df["messages_per_seconds"] = (
        topics_df["new_messages"] / topics_df["eval_elapsed_time"]
    )
    topics_df["messages_per_seconds"] = (
        topics_df["messages_per_seconds"].fillna(0).astype(int)
    )
    # print(df.to_csv())
    cats = process_cluster_topic_df(topics_df)
    new_messages_percentile_value = topics_df["new_messages"].quantile(0.75)
    total_messages_percentile_value = topics_df["total_messages"].quantile(0.75)
    most_active_topics_df = topics_df[
        (topics_df["new_messages"] > new_messages_percentile_value)
        & (topics_df["total_messages"] > total_messages_percentile_value)
        & (topics_df["active_groups"] > 0)
    ].reset_index()
    print(most_active_topics_df.to_csv())
    most_active_topics = most_active_topics_df["name"].values.tolist()
    print(most_active_topics, type(most_active_topics))

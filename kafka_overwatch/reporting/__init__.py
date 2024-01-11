#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from datetime import datetime as dt
from typing import TYPE_CHECKING

from dacite import from_dict

if TYPE_CHECKING:
    from pandas import DataFrame
    from kafka_overwatch.overwatch_resources.clusters import KafkaCluster

from kafka_overwatch.specs.report import (
    ClusterReport,
    EstimatedWaste,
    Metadata,
    Statistics,
)

from .topics import process_cluster_topic_df


def get_cluster_usage(
    cluster_name: str, kafka_cluster: KafkaCluster, topics_df: DataFrame
) -> ClusterReport:
    """
    Based on the topics to monitor, as per the configuration, evaluates the usage of the topics identified.

    """
    topic_categories: dict = process_cluster_topic_df(topics_df)
    estimate = from_dict(
        EstimatedWaste,
        {"topics": 0, "partitions": 0, "topic_categories": topic_categories},
    )
    new_messages_percentile_value = topics_df["new_messages"].quantile(0.75)
    total_messages_percentile_value = topics_df["total_messages"].quantile(0.75)
    most_active_topics_df = topics_df[
        (topics_df["new_messages"] > new_messages_percentile_value)
        & (topics_df["total_messages"] > total_messages_percentile_value)
        & (topics_df["active_groups"] > 0)
    ]

    cluster_stats = Statistics(
        topics=int(topics_df["name"].count()),
        partitions=int(sum(topics_df["partitions"].values)),
        most_active_topics=most_active_topics_df.set_index("name")[
            ["partitions", "total_messages", "new_messages", "active_groups"]
        ].to_dict(orient="index"),
    )

    cluster = ClusterReport(
        metadata=Metadata(timestamp=dt.utcnow().isoformat()),
        cluster_name=cluster_name,
        statistics=cluster_stats,
        estimated_waste=estimate,
    )
    print(f"{kafka_cluster.name} - statistics")
    return cluster

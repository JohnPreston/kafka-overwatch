#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from datetime import datetime as dt
from typing import TYPE_CHECKING

from dacite import from_dict

if TYPE_CHECKING:
    from pandas import DataFrame
    from kafka_overwatch.overwatch_resources.clusters import KafkaCluster

from kafka_overwatch.specs.config import GovernanceReportingConfig
from kafka_overwatch.specs.report import ClusterReport, EstimatedWaste
from kafka_overwatch.specs.report import Governance as GovReport
from kafka_overwatch.specs.report import (
    GovernanceNamingConventionReport,
    Metadata,
    Statistics,
)

from .governance.consumer_groups_naming_convention import review_topic_naming
from .governance.topic_naming_convention import review_topic_naming
from .schema_registry import get_schema_registry_report
from .topics import process_cluster_topic_df


def set_cluster_topic_stats(topics_df) -> tuple[Statistics, EstimatedWaste]:
    """Generates the topic stats and waste report"""
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
    return cluster_stats, estimate


def get_naming_convention_report(
    topics_df: DataFrame, governance_config: GovernanceReportingConfig
) -> GovernanceNamingConventionReport:
    gov_df = review_topic_naming(
        topics_df,
        governance_config.topic_naming_convention.regexes,
        governance_config.topic_naming_convention.ignore_regexes,
    )
    excluded_topics = gov_df[gov_df["excluded_name"] == True]["name"].values.tolist()
    non_compliant_topics = gov_df[
        (gov_df["compliant_name"] == False) & (gov_df["excluded_name"] == False)
    ]["name"].values.tolist()
    non_compliance: float = (len(non_compliant_topics) * 100) / (
        len(gov_df) - len(excluded_topics)
    )
    naming_convention_report = GovernanceNamingConventionReport(
        non_compliant_resources=non_compliant_topics,
        total_ignored=len(excluded_topics),
        total_measured=len(gov_df) - len(excluded_topics),
        compliant_percentage=100 - non_compliance,
        total=len(gov_df),
    )
    return naming_convention_report


def get_cluster_governance(
    governance_config: GovernanceReportingConfig,
    topics_df: DataFrame,
    groups_df: DataFrame,
) -> GovReport:
    if governance_config.topic_naming_convention:
        naming_convention_report = get_naming_convention_report(
            topics_df, governance_config
        )
    else:
        naming_convention_report = None
    if governance_config.consumer_groups_naming_convention:
        consumer_group_naming_convention_report = get_naming_convention_report(
            groups_df, governance_config
        )
    else:
        consumer_group_naming_convention_report = None
    gov_report = GovReport(
        topic_naming_convention=naming_convention_report,
        consumer_group_naming_convention=consumer_group_naming_convention_report,
    )
    return gov_report


def get_cluster_usage(
    cluster_name: str,
    kafka_cluster: KafkaCluster,
    topics_df: DataFrame,
    groups_df: DataFrame,
) -> ClusterReport:
    """
    Based on the topics to monitor, as per the configuration, evaluates the usage of the topics identified.

    """
    topics_stats, topics_waste_estimate = set_cluster_topic_stats(topics_df)
    if kafka_cluster.config.governance:
        governance_report = get_cluster_governance(
            kafka_cluster.config.governance, topics_df, groups_df
        )
    else:
        governance_report = None
    cluster = ClusterReport(
        metadata=Metadata(timestamp=dt.utcnow().isoformat()),
        cluster_name=cluster_name,
        statistics=topics_stats,
        estimated_waste=topics_waste_estimate,
        governance=governance_report,
        schema_registry=get_schema_registry_report(topics_df, kafka_cluster),
    )
    print(f"{kafka_cluster.name} - statistics")
    return cluster

#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pandas import DataFrame
    from kafka_overwatch.overwatch_resources.clusters import KafkaCluster

from kafka_overwatch.specs.report import SchemaRegistryReport, SchemasWasteEstimates


def get_schema_registry_report(
    topics_df: DataFrame, kafka_cluster: KafkaCluster
) -> SchemaRegistryReport | None:
    """Generate schema registry."""
    cluster_sr = kafka_cluster.get_schema_registry()
    if not cluster_sr:
        return None
    topic_names = set(topics_df["name"])
    detected_unused = [
        item
        for item in cluster_sr.subjects
        if item.replace("-value", "").replace("-key", "") not in topic_names
    ]
    report = SchemaRegistryReport(
        subjects_count=len(cluster_sr.subjects),
        schemas_count=len(cluster_sr.schemas),
        schemas_estimates=SchemasWasteEstimates(
            detected_unused=detected_unused, detected_unused_count=len(detected_unused)
        ),
    )
    return report

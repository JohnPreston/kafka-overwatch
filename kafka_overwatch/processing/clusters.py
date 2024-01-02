# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prometheus_client import Gauge
    from kafka_overwatch.config.config import OverwatchConfig

import os
import time
from datetime import datetime as dt
from datetime import timedelta as td

from kafka_overwatch.kafka_resources.groups import set_update_cluster_consumer_groups
from kafka_overwatch.kafka_resources.topics import describe_update_all_topics
from kafka_overwatch.overwatch_resources.clusters import KafkaCluster


def ensure_prometheus_multiproc(prometheus_dir_path: str):
    """
    Just in case the env_var had not propagated among processes,
    setting in child env var.
    """
    if not os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        os.environ["PROMETHEUS_MULTIPROC_DIR"] = prometheus_dir_path
    if not os.environ.get("prometheus_multiproc_dir"):
        os.environ["prometheus_multiproc_dir"] = prometheus_dir_path


def measure_consumer_group_lags(
    kafka_cluster: KafkaCluster, consumer_group_lag_gauge: Gauge
):
    """
    Evaluates, if consumer groups were retrieved, the consumer groups lags and export metrics
    to Prometheus.
    """
    for consumer_group in kafka_cluster.groups.values():
        consumer_group_lag = consumer_group.get_lag()
        for topic, topic_lag in consumer_group_lag.items():
            consumer_group_lag_gauge.labels(
                kafka_cluster.name, consumer_group.group_id, topic
            ).set(topic_lag["total"])


def generate_cluster_report(kafka_cluster: KafkaCluster) -> None:
    """
    Evaluates whether time to produce the report has passed.
    If so, generates and updates next monitoring time.
    """
    if (
        kafka_cluster.config.reporting_config
        and kafka_cluster.next_reporting
        and (dt.utcnow() > kafka_cluster.next_reporting)
    ):
        kafka_cluster.render_report()
        kafka_cluster.next_reporting = dt.utcnow() + td(
            seconds=kafka_cluster.config.reporting_config.evaluation_period_in_seconds
        )


def process_cluster(
    cluster_name: str, cluster_config, overwatch_config: OverwatchConfig
):
    """
    Initialize the Kafka cluster monitoring/evaluation loop.
    Creates the cluster, which creates the Kafka clients.
    """
    ensure_prometheus_multiproc(overwatch_config.prometheus_registry_dir.name)

    kafka_cluster = KafkaCluster(
        cluster_name, cluster_config, overwatch_config=overwatch_config
    )
    consumer_group_lag_gauge = overwatch_config.prometheus_collectors[
        "consumer_group_lag"
    ]

    while kafka_cluster.keep_running:
        with kafka_cluster.topics_describe_latency.time():
            describe_update_all_topics(kafka_cluster)
        kafka_cluster.cluster_topics_count.set(len(kafka_cluster.topics))
        kafka_cluster.cluster_partitions_count.set(
            sum([len(_topic.partitions) for _topic in kafka_cluster.topics.values()])
        )
        with kafka_cluster.groups_describe_latency.time():
            set_update_cluster_consumer_groups(kafka_cluster)
        kafka_cluster.cluster_consumer_groups_count.set(len(kafka_cluster.groups))
        kafka_cluster.render_restore_files()
        generate_cluster_report(kafka_cluster)
        measure_consumer_group_lags(kafka_cluster, consumer_group_lag_gauge)

        for _ in range(1, kafka_cluster.config.cluster_scan_interval_in_seconds):
            if not kafka_cluster.keep_running:
                break
            time.sleep(1)

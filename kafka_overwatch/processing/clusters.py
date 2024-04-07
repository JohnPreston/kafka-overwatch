# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pandas import DataFrame
    from prometheus_client import Gauge
    from kafka_overwatch.config.config import OverwatchConfig

import signal
from datetime import datetime as dt
from datetime import timedelta as td

from kafka_overwatch.config.logging import KAFKA_LOG
from kafka_overwatch.kafka_resources.groups import (
    set_update_cluster_consumer_groups,
    update_set_consumer_group_topics_partitions_offsets,
)
from kafka_overwatch.kafka_resources.topics import describe_update_all_topics
from kafka_overwatch.overwatch_resources.clusters import (
    KafkaCluster,
    generate_cluster_consumer_groups_pd_dataframe,
    generate_cluster_topics_pd_dataframe,
)

from . import FOREVER, handle_signals, stop_flag, wait_between_intervals


def measure_consumer_group_lags(
    kafka_cluster: KafkaCluster, consumer_group_lag_gauge: Gauge
):
    """
    Evaluates, if consumer groups were retrieved, the consumer groups lags and export metrics
    to Prometheus.
    """
    for consumer_group in kafka_cluster.groups.values():
        consumer_group_lag = consumer_group.fetch_set_lag()
        for topic, topic_lag in consumer_group_lag.items():
            consumer_group_lag_gauge.labels(
                kafka_cluster.name, consumer_group.group_id, topic
            ).set(topic_lag["total"])


def generate_cluster_report(
    kafka_cluster: KafkaCluster, topics_df: DataFrame, groups_df: DataFrame
) -> None:
    """
    Evaluates whether time to produce the report has passed.
    If so, generates and updates next monitoring time.
    """
    if (
        kafka_cluster.config.reporting_config
        and kafka_cluster.next_reporting
        and (dt.utcnow() > kafka_cluster.next_reporting)
    ):
        kafka_cluster.render_report(topics_df, groups_df)
        kafka_cluster.next_reporting = dt.utcnow() + td(
            seconds=kafka_cluster.config.reporting_config.evaluation_period_in_seconds
        )


def process_cluster(kafka_cluster: KafkaCluster, overwatch_config: OverwatchConfig):
    """
    Initialize the Kafka cluster monitoring/evaluation loop.
    Creates the cluster, which creates the Kafka clients.
    """
    signal.signal(signal.SIGINT, handle_signals)
    signal.signal(signal.SIGTERM, handle_signals)
    kafka_cluster.init_cluster_prometheus_reporting(overwatch_config)
    kafka_cluster.set_reporting_exporters()
    kafka_cluster.set_cluster_connections()
    consumer_group_lag_gauge = overwatch_config.prometheus_collectors[
        "consumer_group_lag"
    ]
    while FOREVER:
        try:
            kafka_cluster.check_replace_kafka_clients()
            kafka_cluster.set_cluster_properties()
            print(
                "PROCESSING LOOP - CLIENTS??",
                hex(id(kafka_cluster._admin_client)),
                hex(id(kafka_cluster._consumer_client)),
            )

            processing_start = dt.utcnow()
            if not stop_flag.is_set():
                process_cluster_resources(kafka_cluster)
            else:
                break
            topics_df = generate_cluster_topics_pd_dataframe(kafka_cluster)
            groups_df = generate_cluster_consumer_groups_pd_dataframe(kafka_cluster)
            kafka_cluster.cluster_topics_count.set(
                len(topics_df["name"].values.tolist())
            )
            kafka_cluster.cluster_partitions_count.set(
                sum(topics_df["partitions"].values.tolist())
            )
            kafka_cluster.cluster_consumer_groups_count.set(len(kafka_cluster.groups))
            if (
                kafka_cluster.config.topics_backup_config
                and kafka_cluster.config.topics_backup_config.enabled
            ):
                kafka_cluster.render_restore_files()
            elapsed_time = int((dt.utcnow() - processing_start).total_seconds())
            KAFKA_LOG.info(f"{kafka_cluster.name} - {elapsed_time}s processing time.")
            KAFKA_LOG.info(f"{kafka_cluster.name} - Cluster topics stats")
            print(topics_df.describe())
            print(groups_df.describe())
            measure_consumer_group_lags(kafka_cluster, consumer_group_lag_gauge)
            generate_cluster_report(kafka_cluster, topics_df, groups_df)
            time_to_wait = int(
                kafka_cluster.config.cluster_scan_interval_in_seconds - elapsed_time
            )
            wait_between_intervals(
                time_to_wait,
                (
                    f"{kafka_cluster.name} - interval set to {kafka_cluster.config.cluster_scan_interval_in_seconds}"
                    f", however it takes {elapsed_time}s to complete the scan. Consider changing scan interval"
                ),
            )
        except Exception as e:
            KAFKA_LOG.exception(e)
            KAFKA_LOG.error(f"{kafka_cluster.name} - {e}")
            try:
                kafka_cluster.set_cluster_connections()
            except Exception as e:
                KAFKA_LOG.exception(e)
                KAFKA_LOG.error(f"{kafka_cluster.name} - {e}")
                return
    return


def process_cluster_resources(kafka_cluster: KafkaCluster):
    """Makes sure that no signal was received in between each instruction"""
    if not stop_flag.is_set():
        with kafka_cluster.groups_describe_latency.time():
            set_update_cluster_consumer_groups(kafka_cluster)
    if not stop_flag.is_set():
        with kafka_cluster.topics_describe_latency.time():
            describe_update_all_topics(kafka_cluster)
    if not stop_flag.is_set():
        for consumer_group in kafka_cluster.groups.values():
            update_set_consumer_group_topics_partitions_offsets(
                kafka_cluster, consumer_group
            )

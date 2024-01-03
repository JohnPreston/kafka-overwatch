#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

import json
from dataclasses import asdict
from os import makedirs
from queue import Queue
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from confluent_kafka.admin import AdminClient
    from confluent_kafka import Consumer
    from kafka_overwatch.overwatch_resources.groups import ConsumerGroup
    from kafka_overwatch.overwatch_resources.topics import Topic
    from kafka_overwatch.config.config import OverwatchConfig

import signal
from datetime import datetime as dt
from datetime import timedelta as td

from confluent_kafka.admin import KafkaError
from prometheus_client import Gauge, Summary
from retry import retry

from kafka_overwatch.aws_helpers.kafka_client_secrets import eval_kafka_client_config
from kafka_overwatch.aws_helpers.s3 import S3Handler
from kafka_overwatch.config.logging import KAFKA_LOG
from kafka_overwatch.kafka_resources import get_admin_client, get_consumer_client
from kafka_overwatch.kafka_resources.topics import get_filtered_topics_list
from kafka_overwatch.specs.config import ClusterConfiguration
from kafka_overwatch.specs.report import (
    ClusterReport,
    Metadata,
    NewMessagesObserved,
    Recommendation,
    Statistics,
)
from kafka_overwatch.specs.report import Topic as ReportingTopic


class KafkaCluster:
    def __init__(
        self, name: str, config: ClusterConfiguration, overwatch_config: OverwatchConfig
    ):
        self.name = name
        self.keep_running: bool = True

        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        self._cluster_config = config
        self._overwatch_config = overwatch_config

        self.topics: dict[str, Topic] = {}
        self.groups: dict[str, ConsumerGroup] = {}
        self.metrics: dict = {}

        self.next_reporting = dt.utcnow() + td(
            seconds=config.reporting_config.evaluation_period_in_seconds
        )
        if self.config.reporting_config and self.config.reporting_config.local:
            makedirs(self.config.reporting_config.local, exist_ok=True)
            self.local_report_path = f"{self.config.reporting_config.local}/{self.name}"
        else:
            self.local_report_path = None

        cluster_partitions_count: Gauge = self.prometheus_collectors[
            "cluster_partitions_count"
        ]
        cluster_topics_count: Gauge = self.prometheus_collectors["cluster_topics_count"]
        cluster_consumer_groups_count: Gauge = self.prometheus_collectors[
            "cluster_consumer_groups_count"
        ]
        topics_describe_latency: Summary = self.prometheus_collectors[
            "topics_describe_latency"
        ]
        groups_describe_latency: Summary = self.prometheus_collectors[
            "groups_describe_latency"
        ]

        self.cluster_topics_count = cluster_topics_count.labels(cluster=self.name)
        self.cluster_partitions_count = cluster_partitions_count.labels(
            cluster=self.name
        )
        self.cluster_consumer_groups_count = cluster_consumer_groups_count.labels(
            cluster=self.name
        )
        self.topics_describe_latency = topics_describe_latency.labels(cluster=self.name)
        self.groups_describe_latency = groups_describe_latency.labels(cluster=self.name)

        if self.config.reporting_config.S3:
            try:
                self.s3_report = S3Handler(self.config.reporting_config.S3)
            except Exception:
                self.s3_report = None
        else:
            self.s3_report = None
        self.s3_backup = None
        if self.config.topics_backup_config:
            if self.config.topics_backup_config.S3:
                try:
                    self.s3_backup = S3Handler(self.config.topics_backup_config.S3)
                except Exception:
                    self.s3_backup = None

        self.topics_watermarks_queue = Queue()
        self.groups_describe_queue = Queue()

        self.admin_client: AdminClient = None
        self.consumer_client: Consumer = None
        self.set_cluster_connections()
        self.cluster_brokers_count: int = 0
        self.set_cluster_properties()

    @retry(tries=5)
    def set_cluster_connections(self) -> None:
        client_config = eval_kafka_client_config(self)
        self.admin_client: AdminClient = get_admin_client(client_config)
        self.consumer_client: Consumer = get_consumer_client(client_config)

    @retry(tries=2)
    def set_cluster_properties(self) -> None:
        try:
            cluster = self.admin_client.describe_cluster(
                include_authorized_operations=True
            )
        except KafkaError:
            cluster = self.admin_client.describe_cluster(
                include_authorized_operations=False
            )
        while not cluster.done():
            pass
        self.cluster_brokers_count = len(cluster.result().nodes)

    @property
    def config(self) -> ClusterConfiguration:
        return self._cluster_config

    @property
    def prometheus_collectors(self):
        if hasattr(self, "_prometheus_collectors"):
            return self._prometheus_collectors
        else:
            return self._overwatch_config.prometheus_collectors

    @property
    def monitored_topics(self) -> dict[str, Topic]:
        matching_topic_names = get_filtered_topics_list(self)
        return {
            topic_name: topic
            for topic_name, topic in self.topics.items()
            if topic_name in matching_topic_names
        }

    def exit_gracefully(self, pid, frame):
        KAFKA_LOG.warning(
            f"Cluster {self.name} - Attempt to exit gracefully due to signal/interruption - {pid}"
        )
        self.keep_running = False
        if not self.topics_watermarks_queue.qsize() == 0:
            KAFKA_LOG.info(f"{self.name} - Clearing non-empty topic describe queue")
            with self.topics_watermarks_queue.mutex:
                self.topics_watermarks_queue.queue.clear()
                self.topics_watermarks_queue.all_tasks_done.notify_all()
                self.topics_watermarks_queue.unfinished_tasks = 0
        if not self.groups_describe_queue.qsize() == 0:
            KAFKA_LOG.info(f"{self.name} - Clearing non-empty groups describe queue")
            with self.groups_describe_queue.mutex:
                self.groups_describe_queue.queue.clear()
                self.groups_describe_queue.all_tasks_done.notify_all()
                self.groups_describe_queue.unfinished_tasks = 0

        try:
            self.consumer_client.close()
        except AttributeError:
            pass
        try:
            self.admin_client.close()
        except AttributeError:
            pass

    def render_restore_files(self) -> None:
        """
        Generates scripts/config files to re-create the Topics of a cluster
        """

        bash_script = """#!/usr/bin/env bash

if [ -z ${BOOTSTRAP_SERVER} ]; then
    echo "You must specify the BOOTSTRAP_SERVER environment variable"
    exit 1
fi
"""
        topics_commands: list[str] = []
        for topic in self.topics.values():
            topics_commands.append(topic.generate_kafka_create_topic_command())

        topics_commands_str = "\n\n".join(topics_commands)
        bash_script += topics_commands_str + "\n"

        with open(f"/tmp/{self.name}_restore.sh", "w") as f:
            f.write(bash_script)

        if self.s3_backup:
            self.s3_backup.upload(
                bash_script, f"{self.name}_restore.sh", "application/x-sh"
            )

    def render_report(self) -> ClusterReport:
        KAFKA_LOG.info(f"Producing report for {self.name}")
        report = get_cluster_usage(self.name, self)
        if self.local_report_path:
            try:
                with open(f"{self.local_report_path}.json", "w") as f:
                    f.write(json.dumps(asdict(report), indent=2))
                KAFKA_LOG.info(f"Report saved to {self.local_report_path}")
            except PermissionError:
                KAFKA_LOG.error(
                    f"Permission denied to save report to {self.local_report_path}.json"
                )
            except OSError:
                KAFKA_LOG.error(
                    f"IOError while saving report to {self.local_report_path}.json"
                )
            except Exception as error:
                KAFKA_LOG.exception(error)
                KAFKA_LOG.error(
                    f"Error while saving report to {self.local_report_path}.json: {error}"
                )
        if self.s3_report:
            self.s3_report.upload(
                json.dumps(asdict(report), indent=2), f"{self.name}.json"
            )
        return report


def get_cluster_usage(cluster_name: str, kafka_cluster: KafkaCluster) -> ClusterReport:
    """
    Based on the topics to monitor, as per the configuration, evaluates the usage of the topics identified.

    """
    cluster_topics: dict[str, ReportingTopic] = {}
    total_topics_partitions: int = 0
    topics_without_new_messages: list = []
    for topic in kafka_cluster.monitored_topics.values():
        total_topics_partitions += len(topic.partitions)
        if not topic.has_new_messages():
            topics_without_new_messages.append(topic)
        elif topic in topics_without_new_messages and topic.has_new_messages():
            topics_without_new_messages.remove(topic)
        messages_count, elapsed_time = topic.new_messages_count()
        try:
            messages_per_second = messages_count / elapsed_time.total_seconds()
        except ZeroDivisionError:
            messages_per_second = 0
        if messages_per_second < 1:
            recommendation_str = "This topic seems inactive. Consider deletion or opt-in for concentration"
        elif messages_per_second > 1000:
            recommendation_str = (
                "This topic seems active, and has more than 1000 messages per second."
            )
        else:
            recommendation_str = (
                "This topic seems active, and has less than 1000 messages per second."
                " Consider opt-in for concentration"
            )
        report_topic = ReportingTopic(
            partitions_count=len(topic.partitions),
            new_messages_observed=NewMessagesObserved(
                messages_count, int(elapsed_time.total_seconds())
            ),
            recommendation=Recommendation(description=recommendation_str),
        )
        cluster_topics[topic.name] = report_topic
    cluster_stats = Statistics(
        topics=len(kafka_cluster.topics),
        partitions=int(kafka_cluster.cluster_topics_count._value.get()),
    )
    cluster = ClusterReport(
        metadata=Metadata(timestamp=dt.utcnow().isoformat()),
        cluster_name=cluster_name,
        topics=cluster_topics,
        statistics=cluster_stats,
    )
    return cluster

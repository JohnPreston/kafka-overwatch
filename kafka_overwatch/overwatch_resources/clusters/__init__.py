#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

import json
from dataclasses import asdict
from os import makedirs, path
from queue import Queue
from typing import TYPE_CHECKING

from kafka_overwatch.overwatch_resources.clusters.reporting import get_cluster_usage

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
from kafka_overwatch.specs.config import (
    ClusterConfiguration,
    ClusterTopicBackupConfig,
    Exports,
)
from kafka_overwatch.specs.report import ClusterReport


class KafkaCluster:
    def __init__(
        self, name: str, config: ClusterConfiguration, overwatch_config: OverwatchConfig
    ):
        self.name = name
        self.keep_running: bool = True

        if not config.reporting_config.exports:
            config.reporting_config.exports = Exports()

        if not config.topics_backup_config:
            config.topics_backup_config = ClusterTopicBackupConfig()

        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

        self._cluster_config = config
        self._overwatch_config = overwatch_config

        self.topics: dict[str, Topic] = {}
        self.groups: dict[str, ConsumerGroup] = {}
        self.metrics: dict = {}

        self._admin_client = None
        self._consumer_client = None
        self.s3_report: S3Handler = None
        self.local_reports_directory_path = None
        self.s3_backup = None

        self.next_reporting = dt.utcnow() + td(
            seconds=config.reporting_config.evaluation_period_in_seconds
        )
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

        self.topics_watermarks_queue = Queue()
        self.groups_describe_queue = Queue()

        self.cluster_brokers_count: int = 0

    @property
    def config(self) -> ClusterConfiguration:
        return self._cluster_config

    @property
    def admin_client(self) -> AdminClient:
        return self._admin_client

    @property
    def consumer_client(self) -> Consumer:
        return self._consumer_client

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

    @retry(tries=5)
    def set_cluster_connections(self) -> None:
        client_config = eval_kafka_client_config(self)
        self._admin_client: AdminClient = get_admin_client(client_config)
        self._consumer_client: Consumer = get_consumer_client(client_config)

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

    def set_reporting_exporters(self):
        if self.config.reporting_config.exports:
            if self.config.reporting_config.exports.S3:
                try:
                    self.s3_report = S3Handler(self.config.reporting_config.exports.S3)
                except Exception:
                    pass

            if self.config.reporting_config.exports.local:
                self.local_reports_directory_path = path.abspath(
                    f"{self.config.reporting_config.exports.local}/{self.name}"
                )
                makedirs(self.local_reports_directory_path, exist_ok=True)

        if self.config.topics_backup_config:
            if self.config.topics_backup_config.S3:
                try:
                    self.s3_backup = S3Handler(self.config.topics_backup_config.S3)
                except Exception:
                    pass

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

    def render_report(self) -> None:
        KAFKA_LOG.info(f"Producing report for {self.name}")
        report = get_cluster_usage(self.name, self)
        file_name = f"{self.name}.overwatch-report.json"
        if self.local_reports_directory_path:
            file_path: str = path.abspath(
                f"{self.local_reports_directory_path}/{file_name}"
            )
            try:
                with open(file_path, "w") as f:
                    f.write(json.dumps(asdict(report), indent=2))
                KAFKA_LOG.info(f"Report saved to {file_path}")
            except PermissionError:
                KAFKA_LOG.error(f"Permission denied to save report to {file_path}")
            except OSError:
                KAFKA_LOG.error(f"IOError while saving report to {file_path}")
            except Exception as error:
                KAFKA_LOG.exception(error)
                KAFKA_LOG.error(f"Error while saving report to {file_path}: {error}")
        if self.s3_report:
            self.s3_report.upload(json.dumps(asdict(report), indent=2), file_name)

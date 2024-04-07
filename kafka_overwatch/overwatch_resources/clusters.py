#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

import concurrent.futures
import json
import mmap
import pickle
from dataclasses import asdict
from os import makedirs, path
from typing import TYPE_CHECKING

from kafka_overwatch.reporting import get_cluster_usage
from kafka_overwatch.reporting.tools import export_df

if TYPE_CHECKING:
    from confluent_kafka.admin import AdminClient
    from confluent_kafka import Consumer
    from kafka_overwatch.overwatch_resources.groups import ConsumerGroup
    from kafka_overwatch.overwatch_resources.topics import Topic
    from kafka_overwatch.config.config import OverwatchConfig

from datetime import datetime as dt
from datetime import timedelta as td

from confluent_kafka.admin import KafkaException
from pandas import DataFrame
from prometheus_client import Gauge, Summary
from retry import retry

from kafka_overwatch.aws_helpers.kafka_client_secrets import eval_kafka_client_config
from kafka_overwatch.aws_helpers.s3 import S3Handler
from kafka_overwatch.config.logging import KAFKA_LOG
from kafka_overwatch.kafka_resources import set_admin_client, set_consumer_client
from kafka_overwatch.kafka_resources.topics import get_filtered_topics_list
from kafka_overwatch.overwatch_resources.schema_registry import SchemaRegistry
from kafka_overwatch.processing import ensure_prometheus_multiproc
from kafka_overwatch.specs.config import (
    ClusterConfiguration,
    ClusterTopicBackupConfig,
    Exports,
)


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

        self._cluster_config = config
        self._overwatch_config = overwatch_config

        self.topics: dict[str, Topic] = {}
        self.groups: dict[str, ConsumerGroup] = {}
        self.metrics: dict = {}

        self._admin_client = None
        self._consumer_client = None
        self.s3_report: S3Handler | None = None
        self.local_reports_directory_path = None
        self.s3_backup = None
        self.sns_channels: dict[str, dict] = {}
        self.assign_sns_channels(overwatch_config, config)
        self._schema_registry: str | None = None
        self.next_reporting = dt.utcnow() + td(
            seconds=self.config.reporting_config.evaluation_period_in_seconds
        )
        self.cluster_brokers_count: int = 0
        if (
            self.config.cluster_config.schema_registry
            in overwatch_config.schema_registries
        ):
            self._schema_registry = overwatch_config.schema_registries[
                self.config.cluster_config.schema_registry
            ].mmap_file

    def init_cluster_prometheus_reporting(self, overwatch_config):
        ensure_prometheus_multiproc(overwatch_config.prometheus_registry_dir.name)
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

    @property
    def config(self) -> ClusterConfiguration:
        return self._cluster_config

    def assign_sns_channels(
        self, overwatch_config: OverwatchConfig, config: ClusterConfiguration
    ):
        """
        Maps the SNS channels defined at the root of the configuration to the ones defined for
        the cluster. This will make it easy to send notifications for each of these channels
        """
        if (
            overwatch_config.sns_channels
            and config.reporting_config.notification_channels
            and config.reporting_config.notification_channels.sns
        ):
            for sns_channel in config.reporting_config.notification_channels.sns:
                if sns_channel.name in overwatch_config.sns_channels:
                    self.sns_channels[sns_channel.name] = {
                        "topic": overwatch_config.sns_channels[sns_channel.name],
                        "sign": sns_channel.sign_s3_url,
                    }

    def check_replace_kafka_clients(self):
        replace_admin: bool = False
        replace_consumer: bool = False
        try:
            _cluster_f = self._admin_client.describe_cluster()
            concurrent.futures.as_completed([_cluster_f])
            _cluster_f.result()
            return self._admin_client
        except (KafkaException, AttributeError) as error:
            print("Failed with AdminClient", error)
            replace_admin = True
        try:
            self._consumer_client.memberid()
        except (
            AttributeError,
            RuntimeError,
        ) as error:
            print("consumer client failed check")
            print(error)
            replace_consumer = True

        if replace_consumer and replace_admin:
            self.set_cluster_connections()
        else:
            if replace_consumer:
                client_config = eval_kafka_client_config(self)
                self._consumer_client: Consumer = set_consumer_client(client_config)
            if replace_admin:
                client_config = eval_kafka_client_config(self)
                self._admin_client: AdminClient = set_admin_client(client_config)

    def get_schema_registry(self) -> SchemaRegistry | None:
        """
        If the SR has produced a binary file for it, retrieves and loads the class.
        This works around the fact that the SR data is processed in a different process therefore
        the data it has is not updated in the cluster thread.
        If not found or not set, ignore and consider Kafka Cluster does not have SR data available yet.
        Which can occur if the SR processing has not yet yielded results.
        """
        sr_bin_file_path: str = self._schema_registry
        if sr_bin_file_path is None:
            return
        try:
            with open(sr_bin_file_path, "r+b") as schema_bin_fd:
                mm = mmap.mmap(schema_bin_fd.fileno(), 0)
            serialized_data = mm[:]
            deserialized_obj = pickle.loads(serialized_data)
            return deserialized_obj
        except OSError:
            print(f"Unable to open {sr_bin_file_path}")
        except Exception as error:
            print("Error with processing SR details")
            print(error)
        return None

    def get_admin_client(self) -> AdminClient:
        return self._admin_client

    def consumer_client(self) -> Consumer:
        try:
            self._consumer_client.memberid()
        except RuntimeError:
            KAFKA_LOG.warning("Consumer client was closed. Creating new one.")
            client_config = eval_kafka_client_config(self)
            self._consumer_client: Consumer = set_consumer_client(client_config)
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

    @retry((KafkaException,), tries=5, logger=KAFKA_LOG)
    def set_cluster_connections(self) -> None:
        client_config = eval_kafka_client_config(self)
        self._admin_client: AdminClient = set_admin_client(client_config)
        self._consumer_client: Consumer = set_consumer_client(client_config)

    @retry((KafkaException,), tries=2, logger=KAFKA_LOG)
    def set_cluster_properties(self) -> None:
        try:
            cluster = self.get_admin_client().describe_cluster(
                include_authorized_operations=True
            )
            concurrent.futures.as_completed([cluster])
            cluster.result()
        except KafkaException:
            try:
                cluster = self.get_admin_client().describe_cluster(
                    include_authorized_operations=False
                )
                concurrent.futures.as_completed([cluster])
            except KafkaException:
                raise
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

    def render_report(self, topics_df: DataFrame, groups_df: DataFrame) -> None:
        KAFKA_LOG.info(f"Producing report for {self.name}")
        report = get_cluster_usage(self.name, self, topics_df, groups_df)
        export_df(self, topics_df, "topics")
        export_df(self, groups_df, "groups")
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
            upload_path: str = self.s3_report.upload(
                json.dumps(asdict(report), indent=2), file_name
            )
            for channel_name, channel in self.sns_channels.items():
                topic = channel["topic"]
                topic.send_usage_report_notification(
                    self,
                    f"{self.name} - Kafka overwatch report available",
                    s3_uri=f"s3://{upload_path}",
                    s3_url=f"https://s3.amazonaws.com/{upload_path}",
                )


def generate_cluster_topics_pd_dataframe(kafka_cluster: KafkaCluster) -> DataFrame:
    topics_data: list[dict] = []
    for topic in kafka_cluster.topics.values():
        topics_data.append(topic.pd_frame_data)
    topics_df = DataFrame(topics_data)
    topics_df["partitions"] = topics_df["partitions"].astype(int)
    topics_df["eval_elapsed_time"] = topics_df["eval_elapsed_time"].astype(int)
    topics_df["messages_per_seconds"] = (
        topics_df["new_messages"] / topics_df["eval_elapsed_time"]
    )
    topics_df["messages_per_seconds"] = (
        topics_df["messages_per_seconds"].fillna(0).astype(int)
    )

    return topics_df


def generate_cluster_consumer_groups_pd_dataframe(
    kafka_cluster: KafkaCluster,
) -> DataFrame:
    consumer_groups_data: list[dict] = []
    for consumer_group in kafka_cluster.groups.values():
        consumer_groups_data.append(consumer_group.pd_frame_data)
    consumer_groups_df = DataFrame(consumer_groups_data)
    consumer_groups_df["eval_elapsed_time"] = consumer_groups_df[
        "eval_elapsed_time"
    ].astype(int)
    return consumer_groups_df

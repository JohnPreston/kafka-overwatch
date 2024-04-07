# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from datetime import datetime as dt
from datetime import timedelta as td
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.clusters import KafkaCluster
    from kafka_overwatch.overwatch_resources.groups import ConsumerGroup

from confluent_kafka.admin import ConfigEntry


class Partition:
    """
    Class to represent a partition of a topic, with methods to make it easy to track them
    """

    def __init__(
        self,
        topic: Topic,
        partition_id: int,
        init_start_offset: int,
        init_end_offset: int,
        init_time: dt,
    ):
        self._topic = topic
        self._id = partition_id
        self._init_start_offset: tuple[int, dt] = (init_start_offset, init_time)
        self._init_end_offset: tuple[int, dt] = (init_end_offset, init_time)
        self._end_offset = (init_end_offset, init_time)
        _topic_partition_new_messages_collector = (
            self._topic.cluster.prometheus_collectors["topic_partition_new_messages"]
        )
        self._topic_partition_new_messages_metrics_collector = (
            _topic_partition_new_messages_collector.labels(
                cluster=self._topic.cluster.name,
                topic_name=self._topic.name,
                partition_id=self.partition_id,
            )
        )
        self._first_offset = None

    def __repr__(self):
        return f"{self._topic.name}:{self.partition_id}"

    def cleanup(self):
        _topic_partition_new_messages_collector = (
            self._topic.cluster.prometheus_collectors["topic_partition_new_messages"]
        )
        topic_partition_new_messages_labels = (
            self._topic.cluster.name,
            self._topic.name,
            str(self.partition_id),
        )
        if (
            topic_partition_new_messages_labels
            in _topic_partition_new_messages_collector._metrics
        ):
            del _topic_partition_new_messages_collector._metrics[
                topic_partition_new_messages_labels
            ]

    @property
    def partition_id(self) -> int:
        return self._id

    @property
    def init_start_offset(self) -> tuple[int, dt]:
        """Represents the offsets as the kafka-overwatch started, allowing to do the long term evaluations"""
        return self._init_start_offset

    @property
    def first_offset(self) -> tuple[int, dt]:
        """Until the first offset of the partition changes, we use the init start value."""
        if self._first_offset:
            return self._first_offset
        else:
            return self.init_start_offset

    @first_offset.setter
    def first_offset(self, value: tuple[int, dt]):
        """In case the first offset of the partition moves, we need to evolve the value"""
        self._first_offset = value

    @property
    def end_offset(self) -> tuple[int, dt]:
        return self._end_offset

    @end_offset.setter
    def end_offset(self, value):
        new_end_offset, new_time = value

        self._topic_partition_new_messages_metrics_collector.observe(
            new_end_offset - self.end_offset[0]
        )
        self._end_offset = value

    @property
    def total_messages_count(self) -> int:
        end_offset, _ = self.end_offset
        start_offset, _ = self.first_offset
        return int(end_offset - start_offset)

    def get_end_offset_diff(self) -> tuple:
        """Returns the numerical difference in offset and the elapsed time between the two measures"""

        _init_end_offset, _init_offset_time = self._init_end_offset
        _end_offset, _end_time = self._end_offset
        _diff_offset = _end_offset - _init_end_offset
        _diff_time = _end_time - _init_offset_time
        return _diff_offset, _diff_time

    def has_new_messages(self) -> bool:
        """Returns True if the topic has new messages"""
        if self.get_end_offset_diff()[0] > 0:
            return True
        return False


class Topic:
    def __init__(self, name, cluster, properties: ConfigEntry = None):
        self._name = name
        self._cluster: KafkaCluster = cluster
        self.partitions: dict[int, Partition] = {}
        self.consumer_groups: dict[str, ConsumerGroup] = {}
        self._properties: ConfigEntry = properties

    def __repr__(self):
        return self.name

    def __hash__(self):
        return id(self)

    @property
    def name(self) -> str:
        return self._name

    @property
    def cluster(self):
        return self._cluster

    @property
    def config(self) -> dict[str, ConfigEntry]:
        """Returns the ConfigEntry"""
        return self._properties if isinstance(self._properties, dict) else None

    @config.setter
    def config(self, value: dict[str, ConfigEntry]):
        if not isinstance(value, dict):
            raise TypeError(f"Expected dict, got {type(value)}")
        self._properties = value

    @property
    def pd_frame_data(self) -> dict:
        new_messages, elapsed_time = self.new_messages_count()
        return {
            "name": self.name,
            "partitions": len(self.partitions),
            "total_messages": sum(
                _p.total_messages_count for _p in self.partitions.values()
            ),
            "new_messages": new_messages,
            "eval_elapsed_time": elapsed_time.total_seconds(),
            "consumer_groups": len(self.consumer_groups),
            "active_groups": len(
                [_cg for _cg in self.consumer_groups.values() if _cg.is_active]
            ),
        }

    def generate_kafka_create_topic_command(self):
        if not self.config:
            return f"kafka-topics.sh --create --topic {self.name} --partitions {len(self.partitions)}"
        configs = " \\\n".join(
            [
                f"--config {value}"
                for value in self.config.values()
                if not value.is_default
            ]
        )
        command_config = (
            "--bootstrap-server ${BOOTSTRAP_SERVER} "
            "${CLIENT_CONFIG_PATH+:--command-config CLIENT_CONFIG_PATH}"
        )
        return (
            f"kafka-topics.sh --create --topic {self.name} --partitions {len(self.partitions)} \\\n"
            f"{configs} \\\n{command_config}"
        )

    def has_active_groups(self) -> bool:
        """Returns whether any of the consumer groups are active, or not."""
        groups_status: list[bool] = [
            _group.is_active for _group in self.consumer_groups.values()
        ]
        return any(groups_status)

    def has_new_messages(self) -> bool:
        """Returns True if the topic has new messages by checking if any partition had new messages"""
        return any(
            [_partition.has_new_messages() for _partition in self.partitions.values()]
        )

    def new_messages_count(self) -> tuple[int, td]:
        total_messages: int = 0
        elapsed_time = (
            self.partitions[0].end_offset[1] - self.partitions[0].init_start_offset[1]
        )
        for partition in self.partitions.values():
            total_messages += partition.get_end_offset_diff()[0]
        return total_messages, elapsed_time

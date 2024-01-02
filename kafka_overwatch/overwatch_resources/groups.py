# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.topics import Topic
    from confluent_kafka import ConsumerGroupState

from datetime import datetime as dt

from confluent_kafka import TopicPartition


class ConsumerGroup:
    def __init__(self, group_id, init_members: list, init_state: ConsumerGroupState):
        self._group_id = group_id
        self.topic_offsets: dict[Topic, [TopicPartition]] = {}
        self._init_members = init_members
        self._init_state: ConsumerGroupState = init_state
        self._members: list = []
        self._init_time = dt.utcnow()

    def __repr__(self):
        return self._group_id

    def __hash__(self):
        return id(self)

    @property
    def group_id(self):
        return self._group_id

    @property
    def init_members(self) -> tuple:
        return self._init_members, self._init_time

    @property
    def members(self):
        return self._members

    @members.setter
    def members(self, value: list):
        self._members = value

    def get_lag(self, topic_name: str = None) -> dict[str, dict]:
        """Returns the lag for a topic"""
        lag: dict[str, dict] = {}
        for topic, topic_partitions in self.topic_offsets.items():
            partitions_lag: list = []
            total_lag: int = 0
            for partition in topic_partitions:
                _partition_lag: int = (
                    topic.partitions[partition.partition].end_offset[0]
                    - partition.offset
                )
                total_lag += _partition_lag
                partitions_lag.append((partition.partition, _partition_lag))
            lag[topic.name] = {"total": total_lag, "partitions": partitions_lag}
        if topic_name and topic_name in lag:
            return lag[topic_name]
        return lag

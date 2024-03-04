# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.topics import Topic

from datetime import datetime as dt

from confluent_kafka import ConsumerGroupState, TopicPartition
from confluent_kafka.admin import MemberDescription

from kafka_overwatch.config.logging import KAFKA_LOG


class ConsumerGroup:
    def __init__(self, group_id, init_members: list, init_state: ConsumerGroupState):
        self._group_id = group_id
        self.topic_offsets: dict[Topic, [TopicPartition]] = {}
        self._init_members = init_members
        self._init_state: ConsumerGroupState = init_state
        self._state = init_state
        self._members: list = []
        self._init_time = dt.utcnow()
        self._partitions_offsets = None
        self._lag: dict[str, dict] = {}

    def __repr__(self):
        return self._group_id

    def __hash__(self):
        return id(self)

    @property
    def group_id(self):
        return self._group_id

    @property
    def partitions_offsets(self):
        return self._partitions_offsets

    @partitions_offsets.setter
    def partitions_offsets(self, value):
        self._partitions_offsets = value

    @property
    def state(self) -> ConsumerGroupState:
        return self._state

    @state.setter
    def state(self, value: ConsumerGroupState):
        if not isinstance(value, ConsumerGroupState):
            raise TypeError("CG state must be ", ConsumerGroupState, "got", type(value))
        self._state = value

    @property
    def init_members(self) -> tuple[list[MemberDescription], dt]:
        return self._init_members, self._init_time

    @property
    def members(self) -> list[MemberDescription]:
        return self._members

    @members.setter
    def members(self, value: list[MemberDescription]):
        if not all([isinstance(_member, MemberDescription) for _member in value]):
            raise TypeError(
                "One of the members is not valid. Expected",
                MemberDescription,
                "Got",
                [type(_member) for _member in value],
            )
        self._members = value

    @property
    def is_active(self) -> bool:
        if (
            self.state not in [ConsumerGroupState.DEAD, ConsumerGroupState.EMPTY]
            and self.members
        ):
            return True
        return False

    @property
    def pd_frame_data(self) -> dict:
        elapsed_time = dt.utcnow() - self._init_time
        return {
            "name": self.group_id,
            "members": len(self.members),
            "state": self.state,
            "eval_elapsed_time": elapsed_time.total_seconds(),
            "overall_lag": sum([_topic["total"] for _topic in self._lag.values()]),
        }

    def fetch_set_lag(self, topic_name: str = None) -> dict[str, dict]:
        """
        Returns the lag for a topic and its partitions
        If topic_name is set, returns the lag for that topic alone.
        """
        lag: dict[str, dict] = {}
        for overwatch_topic, cg_topic_partitions in self.topic_offsets.items():
            partitions_lag: list = []
            total_lag: int = 0
            for partition in cg_topic_partitions:
                _overwatch_topic_partition = overwatch_topic.partitions[
                    partition.partition
                ]
                if _overwatch_topic_partition.total_messages_count == 0:
                    KAFKA_LOG.debug(
                        "{} - {}: {}.{} No messages on partition. Skipping for consumer lag.".format(
                            overwatch_topic.cluster.name,
                            self.group_id,
                            overwatch_topic.name,
                            _overwatch_topic_partition.partition_id,
                        )
                    )
                    continue
                if partition.offset < 0:
                    KAFKA_LOG.debug(
                        "{} - {} - No committed offset found for topic:partition {}:{}".format(
                            overwatch_topic.cluster.name,
                            self.group_id,
                            overwatch_topic.name,
                            _overwatch_topic_partition.partition_id,
                        )
                    )
                    break
                _partition_lag: int = (
                    _overwatch_topic_partition.end_offset[0] - partition.offset
                )
                total_lag += _partition_lag
                partitions_lag.append((partition.partition, _partition_lag))
            if total_lag and partitions_lag:
                lag[overwatch_topic.name] = {
                    "total": total_lag,
                    "partitions": partitions_lag,
                }
        self._lag = lag
        if topic_name and topic_name in lag:
            return lag[topic_name]
        return lag

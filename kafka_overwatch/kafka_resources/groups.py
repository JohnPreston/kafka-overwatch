# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.clusters import KafkaCluster
    from confluent_kafka.admin import ConsumerGroupDescription

import concurrent.futures
import signal
import threading

from confluent_kafka import ConsumerGroupTopicPartitions
from confluent_kafka.error import KafkaError
from retry import retry

from kafka_overwatch.config.logging import KAFKA_LOG
from kafka_overwatch.config.threads_settings import NUM_THREADS
from kafka_overwatch.kafka_resources import wait_for_result
from kafka_overwatch.overwatch_resources.groups import ConsumerGroup


@retry((KafkaError,), max_delay=30, delay=5, backoff=2, jitter=(2, 5))
def get_consumer_groups_desc(
    kafka_cluster: KafkaCluster, groups_list: list
) -> dict[str, ConsumerGroupDescription]:
    try:
        groups_desc = {
            _group: desc.result()
            for _group, desc in wait_for_result(
                kafka_cluster.admin_client.describe_consumer_groups(
                    [_group for _group in groups_list]
                )
            ).items()
        }
        return groups_desc
    except KafkaError as error:
        print(f"{kafka_cluster.name} - Error getting consumer group description")
        KAFKA_LOG.exception(error)
        raise


def tidy_consumer_groups(
    kafka_cluster: KafkaCluster, query_groups_list: list[str]
) -> None:
    existing_groups_list: list[str] = list(kafka_cluster.groups.keys())
    if existing_groups_list and query_groups_list:
        for group in existing_groups_list:
            if group not in query_groups_list:
                try:
                    for topic in kafka_cluster.topics.values():
                        if topic.consumer_groups and group in topic.consumer_groups:
                            del topic.consumer_groups[group]
                    print(
                        f"Consumer group {group} no longer on cluster {kafka_cluster.name} metadata"
                    )
                    del kafka_cluster.groups[group]
                except KeyError:
                    pass


def set_update_filter_cluster_consumer_groups(kafka_cluster: KafkaCluster) -> None:
    """
    Lists all the consumer groups from the Kafka cluster
    Filters out of the Kafka cluster groups attribute all the consumer groups that are not in the list
    Retrieves the consumer group description/details from the cluster
    """

    groups_list_future = kafka_cluster.admin_client.list_consumer_groups()
    while not groups_list_future.done():
        if groups_list_future.exception():
            print(f"{kafka_cluster.name} - Failed to get consumer groups list")
            return

    query_groups_list = [
        _group.group_id for _group in groups_list_future.result().valid
    ]
    if not query_groups_list:
        KAFKA_LOG.warning(f"{kafka_cluster.name}: No consumer groups to describe.")
        return
    tidy_consumer_groups(kafka_cluster, query_groups_list)

    groups_desc = get_consumer_groups_desc(kafka_cluster, query_groups_list)

    for group_desc in groups_desc.values():
        if group_desc.group_id not in kafka_cluster.groups:
            consumer_group = ConsumerGroup(
                group_desc.group_id,
                group_desc.members,
                group_desc.state,
            )
            kafka_cluster.groups[group_desc.group_id] = consumer_group
        else:
            consumer_group: ConsumerGroup = kafka_cluster.groups[group_desc.group_id]
            consumer_group.members = group_desc.members
            consumer_group.state = group_desc.state


def set_update_cluster_consumer_groups(
    kafka_cluster: KafkaCluster,
) -> None:
    """
    Lists all Consumer Groups
    Checks if all the listed CGs were present in the existing cluster CGs. If not, remove.
    Describe all Consumer Groups
    List all Consumer Group Offsets (serial, no support for list of CGs)
    If CG not in the cluster groups, add to it
    """
    set_update_filter_cluster_consumer_groups(kafka_cluster)
    _tasks = len(kafka_cluster.groups)
    completed: int = 0
    groups_jobs: dict = {
        _consumer_group_name: [_consumer_group, kafka_cluster]
        for _consumer_group_name, _consumer_group in kafka_cluster.groups.items()
    }

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=kafka_cluster.cluster_brokers_count
    ) as executor:
        futures_to_data: dict[concurrent.futures.Future, list] = {
            executor.submit(
                describe_update_consumer_group_offsets, *job_params
            ): job_params
            for job_params in groups_jobs.values()
        }
        while completed < _tasks:
            for _future in concurrent.futures.as_completed(futures_to_data):
                if not kafka_cluster.keep_running or kafka_cluster.stop_flag.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                if _future.exception():
                    data = retry_kafka_describe_update_consumer_group_offsets(
                        _future, futures_to_data, executor
                    )
                    print(f"Failure, retrying {data}")
                else:
                    KAFKA_LOG.debug(_future.result())
                    completed += 1
                futures_to_data.pop(_future)
            else:
                continue
            break


def describe_update_consumer_group_offsets(
    consumer_group: ConsumerGroup, kafka_cluster: KafkaCluster
) -> None:
    """
    Retrieve a given Consumer group details, given that the list_consumer_group_offsets cannot take
    multiple groups as argument.
    Updates the kafka_cluster.groups.
    """
    if not consumer_group or not kafka_cluster:
        return
    try:
        consumer_group.partitions_offsets = wait_for_result(
            kafka_cluster.admin_client.list_consumer_group_offsets(
                [ConsumerGroupTopicPartitions(consumer_group.group_id)],
                require_stable=True,
            )
        )
    except Exception as error:
        KAFKA_LOG.exception(error)
        KAFKA_LOG.error(
            f"{kafka_cluster.name}:{consumer_group.group_id} - "
            "Failure during retrieving consumer group details"
        )


def retry_kafka_describe_update_consumer_group_offsets(
    future, futures_to_data, executor
):
    # get the associated data for the task
    data = futures_to_data[future]
    # submit the task again
    _retry = executor.submit(describe_update_consumer_group_offsets, data)
    # store so we can track the retries
    futures_to_data[_retry] = data
    return data


def update_set_consumer_group_topics_partitions_offsets(
    kafka_cluster: KafkaCluster,
    consumer_group: ConsumerGroup,
) -> None:
    """
    Groups topic partitions offsets per topic
    Assigns partitions offsets to the consumer group
    Maps consumer group to topic
    """
    for _group, _future in consumer_group.partitions_offsets.items():
        offsets_result = _future.result()

        __topic_partitions_new_offsets: dict = {}
        for _topic_partition in offsets_result.topic_partitions:
            if _topic_partition.topic in kafka_cluster.topics:
                _topic = kafka_cluster.topics[_topic_partition.topic]
            else:
                print("Not monitored topic")
                continue

            if _topic not in __topic_partitions_new_offsets:
                __topic_partitions_new_offsets[_topic] = [_topic_partition]
            else:
                __topic_partitions_new_offsets[_topic].append(_topic_partition)
        for _topic, _topic_partitions in __topic_partitions_new_offsets.items():
            consumer_group.topic_offsets[_topic] = _topic_partitions
            if consumer_group not in _topic.consumer_groups:
                _topic.consumer_groups[consumer_group.group_id] = consumer_group

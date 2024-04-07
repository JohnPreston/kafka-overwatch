# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.clusters import KafkaCluster
    from confluent_kafka.admin import ConsumerGroupDescription

import concurrent.futures

from confluent_kafka import ConsumerGroupTopicPartitions
from confluent_kafka.error import KafkaError, KafkaException

from kafka_overwatch.common import waiting_on_futures
from kafka_overwatch.config.logging import KAFKA_LOG
from kafka_overwatch.kafka_resources import wait_for_result
from kafka_overwatch.overwatch_resources.groups import ConsumerGroup


def get_consumer_groups_desc(
    kafka_cluster: KafkaCluster,
    groups_list: list,
    groups_desc: dict[str, ConsumerGroupDescription] | None = None,
) -> dict[str, ConsumerGroupDescription]:
    if groups_desc is None:
        groups_desc: dict[str, ConsumerGroupDescription] = {}

    groups_to_describe: list[str] = [_group for _group in groups_list]
    groups_desc_r: dict[str, concurrent.futures.Future] = (
        kafka_cluster.get_admin_client().describe_consumer_groups(groups_to_describe)
    )

    to_retry: list[str] = []

    for _group_name, _future in groups_desc_r.items():
        try:
            groups_desc[_group_name] = _future.result()
        except (KafkaError, KafkaException) as error:
            KAFKA_LOG.error(
                "%s - %s - Error getting consumer group description"
                % (kafka_cluster.name, _group_name)
            )
            print(error)
            to_retry.append(_group_name)
    if to_retry:
        print(f"GOT TO RETRY {len(to_retry)} CGs")
        get_consumer_groups_desc(kafka_cluster, to_retry, groups_desc)

    return groups_desc


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

    groups_list_future = kafka_cluster.get_admin_client().list_consumer_groups()
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
        _pending = len(futures_to_data)
        KAFKA_LOG.info(f"Kafka cluster: {kafka_cluster.name} | CGs to scan: {_pending}")
        waiting_on_futures(
            executor,
            futures_to_data,
            "Kafka Cluster",
            kafka_cluster.name,
            "Consumer groups",
        )


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
            kafka_cluster.get_admin_client().list_consumer_group_offsets(
                [ConsumerGroupTopicPartitions(consumer_group.group_id)],
                require_stable=True,
            )
        )
    except Exception as error:
        if error.args[0] == KafkaError.REQUEST_TIMED_OUT:
            print("CG DESCRIBE TIMEOUT", error)
        else:
            print("CG DESCRIBE ERROR", error)


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

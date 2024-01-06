# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.clusters import KafkaCluster
    from confluent_kafka.admin import ConsumerGroupDescription

from queue import Queue
from threading import Thread

from confluent_kafka import ConsumerGroupTopicPartitions
from confluent_kafka.error import KafkaError
from retry import retry

from kafka_overwatch.config.logging import KAFKA_LOG
from kafka_overwatch.config.threads_settings import NUM_THREADS
from kafka_overwatch.kafka_resources import wait_for_result
from kafka_overwatch.overwatch_resources.groups import ConsumerGroup


@retry((KafkaError,), tries=10, delay=5, backoff=2, jitter=(2, 5))
def get_consumer_groups_desc(kafka_cluster: KafkaCluster, groups_list: list) -> dict:
    try:
        groups_desc = wait_for_result(
            kafka_cluster.admin_client.describe_consumer_groups(
                [_group for _group in groups_list]
            )
        )
        return groups_desc
    except KafkaError as error:
        print(error)
        raise


def tidy_consumer_groups(
    kafka_cluster: KafkaCluster, query_groups_list: list[str]
) -> None:
    existing_groups_list: list = list(kafka_cluster.groups.keys())
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
    groups_list_future = kafka_cluster.admin_client.list_consumer_groups()
    while not groups_list_future.done():
        pass
    query_groups_list = [
        _group.group_id for _group in groups_list_future.result().valid
    ]
    tidy_consumer_groups(kafka_cluster, query_groups_list)
    if not query_groups_list:
        KAFKA_LOG.warning(f"{kafka_cluster.name}: No consumer groups to describe.")
        return

    groups_desc = get_consumer_groups_desc(kafka_cluster, query_groups_list)
    groups_processing_threads: list[Thread] = []
    KAFKA_LOG.debug(f"{kafka_cluster.name} has {len(query_groups_list)} CGs")
    for desc_future in groups_desc.values():
        kafka_cluster.groups_describe_queue.put(
            [desc_future, kafka_cluster],
            False,
        )
    if kafka_cluster.groups_describe_queue.qsize() == 0:
        KAFKA_LOG.info(
            f"{kafka_cluster.name} -  no consumer group to describe in queue."
        )
        return
    KAFKA_LOG.info(
        f"{kafka_cluster.name} - {kafka_cluster.groups_describe_queue.qsize()}"
        " CGs to retrieve metadata for."
    )
    KAFKA_LOG.debug(f"{kafka_cluster.name} - CG list len: {len(query_groups_list)}")

    for _ in range(1, kafka_cluster.cluster_brokers_count or NUM_THREADS):
        _thread = Thread(
            target=describe_update_consumer_groups,
            daemon=True,
            args=(kafka_cluster.groups_describe_queue,),
        )
        _thread.start()
        groups_processing_threads.append(_thread)
    kafka_cluster.groups_describe_queue.join()


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


def describe_update_consumer_groups(queue: Queue) -> None:
    """
    Thread worker to retrieve a given Consumer group details, given that the list_consumer_group_offsets cannot take
    multiple groups as argument.
    Updates the kafka_cluster.groups.
    """
    while 42:
        if not queue.empty():
            desc_future, kafka_cluster = queue.get()
            group_description: ConsumerGroupDescription = desc_future.result()
            group = group_description.group_id
            KAFKA_LOG.debug(f"Describing consumer group {group} - {kafka_cluster.name}")
            try:
                if group not in kafka_cluster.groups:
                    consumer_group = ConsumerGroup(
                        group_description.group_id,
                        group_description.members,
                        group_description.state,
                    )
                    kafka_cluster.groups[group] = consumer_group
                else:
                    consumer_group: ConsumerGroup = kafka_cluster.groups[group]
                    consumer_group.members = group_description.members
                    consumer_group.state = group_description.state
                consumer_group.partitions_offsets = wait_for_result(
                    kafka_cluster.admin_client.list_consumer_group_offsets(
                        [ConsumerGroupTopicPartitions(group_description.group_id)],
                        require_stable=True,
                    )
                )
            except Exception as error:
                KAFKA_LOG.exception(error)
                KAFKA_LOG.error(
                    f"{kafka_cluster.name}:{desc_future.result().group_id} - "
                    "Failure during retrieving consumer group details"
                )
            queue.task_done()
        else:
            KAFKA_LOG.debug("Thread closing for describe_update_consumer_groups")
            return

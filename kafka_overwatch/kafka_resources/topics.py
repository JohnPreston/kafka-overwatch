# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

from retry import retry

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.clusters import KafkaCluster

import re
import threading
from datetime import datetime as dt

from confluent_kafka import TopicCollection, TopicPartition
from confluent_kafka.admin import AclOperation, ConfigResource, ResourceType
from confluent_kafka.error import KafkaError

from kafka_overwatch.config.logging import KAFKA_LOG
from kafka_overwatch.config.threads_settings import NUM_THREADS
from kafka_overwatch.kafka_resources import wait_for_result
from kafka_overwatch.overwatch_resources.topics import Partition, Topic


def get_filtered_topics_list(cluster: KafkaCluster) -> list[str]:
    """
    Lists all topics, returns them based on include and exclude regex.
    """
    if not cluster.topics:
        describe_update_all_topics(cluster)
    topics_list = list(cluster.topics.keys())
    final_list: list[str] = []
    if (
        not cluster.config.topic_include_regexes
        or not cluster.config.topic_exclude_regexes
    ):
        return topics_list
    for regex in cluster.config.topic_exclude_regexes:
        try:
            topics_list = [topic for topic in topics_list if not re.match(regex, topic)]
        except Exception as error:
            KAFKA_LOG.exception(error)
            KAFKA_LOG.error(f"Failed to parse exclude_regex with regex {regex}")

    for regex in cluster.config.topic_include_regexes:
        try:
            for topic in topics_list:
                if re.match(regex, topic):
                    final_list.append(topic)
        except Exception as error:
            KAFKA_LOG.error(f"Failed to parse include_regex with regex {regex}")

    return final_list


def describe_update_all_topics(
    cluster: KafkaCluster,
) -> None:
    """
    Lists all topics
    """
    topic_names: list[str] = list(cluster.admin_client.list_topics().topics.keys())
    desc_topics = wait_for_result(
        cluster.admin_client.describe_topics(
            TopicCollection([topic_name for topic_name in topic_names]),
            include_authorized_operations=True,
        )
    )
    for _cluster_topic_name in list(cluster.topics.keys()):
        if _cluster_topic_name not in topic_names:
            KAFKA_LOG.warning(
                f"Topic {_cluster_topic_name} no longer in cluster {cluster.name} metadata. Clearing"
            )
            _to_clear = cluster.topics[_cluster_topic_name]
            for _partition in _to_clear.partitions.values():
                _partition.cleanup()
            del cluster.topics[_cluster_topic_name]

    if desc_topics:
        describe_update_topics(cluster, desc_topics)
    else:
        KAFKA_LOG.info(f"No topics matched for {cluster.name}")


def describe_update_topics(cluster: KafkaCluster, desc_topics: dict) -> None:
    topics_configs_resources = []

    for topic in desc_topics.values():
        _topic = topic.result()
        if (
            hasattr(_topic, "authorized_operations")
            and AclOperation.DESCRIBE_CONFIGS in _topic.authorized_operations
        ):
            topics_configs_resources.append(
                ConfigResource(ResourceType.TOPIC, _topic.name)
            )
        else:
            KAFKA_LOG.debug(
                f"Cluster {cluster.name} - Topic {_topic.name}: Not authorized to perform DescribeConfig."
            )

        if _topic.name not in cluster.topics:
            _topic_obj = Topic(_topic.name, cluster)
            cluster.topics[_topic.name] = _topic_obj
        else:
            _topic_obj = cluster.topics[_topic.name]
        cluster.topics_watermarks_queue.put(
            [_topic_obj, cluster.consumer_client, _topic, dt.utcnow()], False
        )
    KAFKA_LOG.info(
        f"{cluster.name} - {cluster.topics_watermarks_queue.qsize()} topic jobs to do."
    )
    KAFKA_LOG.debug(desc_topics.keys())
    if cluster.topics_watermarks_queue.qsize() == 0:
        return
    topics_watermark_threads: list[threading.Thread] = []
    for _ in range(1, cluster.cluster_brokers_count or NUM_THREADS):
        _thread = threading.Thread(
            target=init_set_partitions,
            daemon=True,
            args=(cluster.topics_watermarks_queue,),
        )
        _thread.start()
        topics_watermark_threads.append(_thread)
    cluster.topics_watermarks_queue.join()

    if topics_configs_resources:
        try:
            topics_config = wait_for_result(
                cluster.admin_client.describe_configs(topics_configs_resources)
            )
            for __name, __topic in topics_config.items():
                if __name.name in cluster.topics:
                    cluster.topics[__name.name].config = __topic.result()

        except KafkaError as error:
            print(f"{cluster.name} - DescribeConfigs on topics failed: {error}")


@retry((KafkaError,), tries=10, delay=5, backoff=2, jitter=(2, 5), logger=KAFKA_LOG)
def get_topic_partition_watermarks(consumer_client, topic_name, partition_id):
    try:
        start_offset, end_offset = consumer_client.get_watermark_offsets(
            TopicPartition(topic_name, partition_id)
        )
        return start_offset, end_offset
    except KafkaError as error:
        KAFKA_LOG.exception(error)
        KAFKA_LOG.error(f"Failed to get topic {topic_name} watermarks")
        return None, None


def init_set_partitions(queue):
    while 42:
        if not queue.empty():
            topic_obj, consumer_client, topic, now = queue.get()
            partitions = topic.partitions
            for partition in partitions:
                try:
                    start_offset, end_offset = get_topic_partition_watermarks(
                        consumer_client, topic.name, partition.id
                    )
                    if start_offset is None or end_offset is None:
                        KAFKA_LOG.debug("No start offset or end offset data retrieved")
                        continue
                    if partition.id not in topic_obj.partitions:
                        topic_obj.partitions[partition.id] = Partition(
                            topic_obj, partition.id, start_offset, end_offset, now
                        )
                    else:
                        topic_obj.partitions[partition.id].end_offset = end_offset, now
                except Exception as error:
                    KAFKA_LOG.exception(error)
                    KAFKA_LOG.error(
                        f"Unable to update topic {topic.name} partition {partition.id} watermarks"
                    )
            queue.task_done()
        else:
            KAFKA_LOG.debug("Topic watermark worker - stopping")
            return

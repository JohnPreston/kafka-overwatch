# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from confluent_kafka.admin import TopicDescription
    from kafka_overwatch.overwatch_resources.clusters import KafkaCluster

import concurrent.futures
import re
from datetime import datetime as dt

from confluent_kafka import TopicCollection, TopicPartition
from confluent_kafka.admin import AclOperation, ConfigResource, ResourceType
from confluent_kafka.error import KafkaException
from retry.api import retry, retry_call

from kafka_overwatch.common import waiting_on_futures
from kafka_overwatch.config.logging import KAFKA_LOG
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


@retry((KafkaException,), tries=5)
def get_topic_descriptions(
    topic_names: list[str], admin_client
) -> dict[str, TopicDescription]:
    desc_topics = {
        topic_name: topic_desc.result()
        for topic_name, topic_desc in wait_for_result(
            admin_client.describe_topics(
                TopicCollection([topic_name for topic_name in topic_names]),
                include_authorized_operations=True,
            )
        ).items()
    }
    return desc_topics


@retry((KafkaException,), tries=5)
def get_topics_list(kafka_cluster: KafkaCluster) -> list[str]:
    try:
        topic_names: list[str] = list(
            kafka_cluster.get_admin_client().list_topics().topics.keys()
        )
        return topic_names
    except Exception as error:
        KAFKA_LOG.error(f"{kafka_cluster.name} - Failed to list topics: {error}")
        raise


def describe_update_all_topics(
    kafka_cluster: KafkaCluster,
) -> None:
    """
    Lists all topics
    """
    topic_names = get_topics_list(kafka_cluster)
    desc_topics = retry_call(
        get_topic_descriptions, fargs=[topic_names, kafka_cluster.get_admin_client()]
    )
    for _cluster_topic_name in list(kafka_cluster.topics.keys()):
        if _cluster_topic_name not in topic_names:
            KAFKA_LOG.warning(
                f"Topic {_cluster_topic_name} no longer in cluster {kafka_cluster.name} metadata. Clearing"
            )
            _to_clear = kafka_cluster.topics[_cluster_topic_name]
            for _partition in _to_clear.partitions.values():
                _partition.cleanup()
            del kafka_cluster.topics[_cluster_topic_name]

    if desc_topics:
        describe_update_topics(kafka_cluster, desc_topics)
    else:
        KAFKA_LOG.info(f"No topics matched for {kafka_cluster.name}")


def retry_kafka(future, futures_to_data, executor):
    # get the associated data for the task
    data = futures_to_data[future]
    # submit the task again
    _retry = executor.submit(init_set_partitions, data)
    # store so we can track the retries
    futures_to_data[_retry] = data
    return data


def update_set_topic_config(kafka_cluster, topics_configs_resources) -> None:
    if not topics_configs_resources:
        return
    try:
        topics_config = wait_for_result(
            kafka_cluster.get_admin_client().describe_configs(topics_configs_resources)
        )
        for __name, __topic in topics_config.items():
            if __name.name in kafka_cluster.topics:
                kafka_cluster.topics[__name.name].config = __topic.result()

    except KafkaException as error:
        print(f"{kafka_cluster.name} - DescribeConfigs on topics failed: {error}")


def define_topic_jobs(
    kafka_cluster: KafkaCluster, desc_topics: dict
) -> tuple[dict, list]:
    """
    Goes over all the topic configurations, and if authorization allows for describe configs, plans
    for the list of configurations to return.
    Returns the dict of topic description jobs to perform, and the topic descriptions list.
    """
    topics_configs_resources = []
    topic_jobs: dict[str, list] = {}
    now = dt.utcnow()
    for _topic_name, _topic in desc_topics.items():
        if (
            hasattr(_topic, "authorized_operations")
            and AclOperation.DESCRIBE_CONFIGS in _topic.authorized_operations
        ):
            topics_configs_resources.append(
                ConfigResource(ResourceType.TOPIC, _topic.name)
            )
        else:
            KAFKA_LOG.debug(
                f"Cluster {kafka_cluster.name} - Topic {_topic.name}: Not authorized to perform DescribeConfig."
            )

        if _topic.name not in kafka_cluster.topics:
            _topic_obj = Topic(_topic.name, kafka_cluster)
            kafka_cluster.topics[_topic.name] = _topic_obj
        else:
            _topic_obj = kafka_cluster.topics[_topic.name]
        topic_jobs[_topic_name] = [
            _topic_obj,
            kafka_cluster.consumer_client(),
            _topic,
            now,
        ]

    return topic_jobs, topics_configs_resources


def describe_update_topics(kafka_cluster: KafkaCluster, desc_topics: dict) -> None:
    """
    Leverages threads to retrieve the topic offset watermarks which cannot be sent in a single
    call to Kafka.
    """
    topic_jobs, topics_configs_resources = define_topic_jobs(kafka_cluster, desc_topics)
    _tasks = len(topic_jobs)
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=kafka_cluster.cluster_brokers_count
    ) as executor:
        futures_to_data: dict[concurrent.futures.Future, list] = {
            executor.submit(init_set_partitions, *job_params): job_params
            for job_params in topic_jobs.values()
        }
        _pending: int = len(futures_to_data)
        KAFKA_LOG.info(
            "Kafka cluster: {} | Topics to scan: {}".format(
                kafka_cluster.name, _pending
            )
        )
        waiting_on_futures(
            executor,
            futures_to_data,
            "Kafka Cluster",
            kafka_cluster.name,
            "Topics",
        )

    update_set_topic_config(kafka_cluster, topics_configs_resources)


@retry((KafkaException,), tries=10, delay=5, backoff=2, jitter=(2, 5), logger=KAFKA_LOG)
def get_topic_partition_watermarks(consumer_client, topic_name, partition_id):
    try:
        start_offset, end_offset = consumer_client.get_watermark_offsets(
            TopicPartition(topic_name, partition_id)
        )
        return start_offset, end_offset
    except KafkaException as error:
        KAFKA_LOG.exception(error)
        KAFKA_LOG.error(f"Failed to get topic {topic_name}-{partition_id} watermarks")
        return None, None


def init_set_partitions(topic_obj: Topic, consumer_client, topic, now: dt):
    partitions = topic.partitions
    for _partition in partitions:
        try:
            start_offset, end_offset = get_topic_partition_watermarks(
                consumer_client, topic.name, _partition.id
            )
        except Exception as error:
            KAFKA_LOG.exception(error)
            KAFKA_LOG.error(
                f"Unable to update topic {topic.name} partition {_partition.id} watermarks"
            )
            start_offset = None
            end_offset = None

        if start_offset is None or end_offset is None:
            KAFKA_LOG.debug("No start offset or end offset data retrieved")
            continue
        if _partition.id not in topic_obj.partitions:
            partition = Partition(
                topic_obj, _partition.id, start_offset, end_offset, now
            )
            topic_obj.partitions[_partition.id] = partition
        else:
            partition = topic_obj.partitions[_partition.id]
            partition.end_offset = end_offset, now
        if start_offset != partition.init_start_offset[0]:
            partition.first_offset = start_offset, now
    return f"{topic_obj.name} - {(dt.utcnow() - now).total_seconds()}"

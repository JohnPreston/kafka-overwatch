#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from prometheus_client import CollectorRegistry, Gauge, Summary


def set_kafka_cluster_prometheus_registry_collectors(
    prometheus_registry: CollectorRegistry,
) -> dict[str, Gauge | Summary]:
    collectors: dict = {
        "topic_partition_new_messages": Summary(
            "topic_partition_new_messages",
            "New messages added since last interval",
            labelnames=["cluster", "topic_name", "partition_id"],
            registry=prometheus_registry,
        ),
        "topics_describe_latency": Summary(
            "topics_describe_latency",
            "Time to retrieve Kafka cluster topics details",
            ["cluster"],
            registry=prometheus_registry,
        ),
        "groups_describe_latency": Summary(
            "groups_describe_latency",
            "Time to retrieve Kafka cluster groups details",
            ["cluster"],
            registry=prometheus_registry,
        ),
        "cluster_partitions_count": Gauge(
            "cluster_partitions_count",
            "Kafka cluster partitions count",
            ["cluster"],
            registry=prometheus_registry,
            # multiprocess_mode="all",
        ),
        "cluster_topics_count": Gauge(
            "cluster_topics_count",
            "Kafka cluster topics count",
            ["cluster"],
            registry=prometheus_registry,
        ),
        "cluster_consumer_groups_count": Gauge(
            "cluster_consumer_groups_count",
            "Kafka cluster consumer groups count",
            ["cluster"],
            registry=prometheus_registry,
        ),
        "consumer_group_lag": Gauge(
            "consumer_group_lag",
            "Consumer group lag",
            ["cluster", "consumer_group", "topic_name"],
            registry=prometheus_registry,
        ),
    }
    return collectors


def set_schema_registry_prometheus_registry_collectors(
    prometheus_registry: CollectorRegistry,
) -> dict[str, Gauge | Summary]:
    collectors: dict = {
        "subjects_count": Gauge(
            "subjects_count",
            "Total number of subjects",
            labelnames=["schema_registry"],
            registry=prometheus_registry,
        ),
        "schemas_count": Gauge(
            "schemas_count",
            "Total number of subjects",
            labelnames=["schema_registry"],
            registry=prometheus_registry,
        ),
    }
    return collectors

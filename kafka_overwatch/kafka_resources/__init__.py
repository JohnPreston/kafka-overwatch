# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from copy import deepcopy
from os import environ

from confluent_kafka import Consumer, KafkaException
from confluent_kafka.admin import AdminClient
from retry import retry


@retry((KafkaException,), delay=5, max_delay=30, backoff=2)
def wait_for_result(result_container: dict) -> dict:
    for _future in result_container.values():
        while not _future.done():
            _future.result()
    return result_container


def set_consumer_client(settings: dict) -> Consumer:
    """Creates a new librdkafka Consumer client"""
    client_id: str = f"consumer_partitions_hunter"
    cluster_config = deepcopy(settings)
    cluster_config.update({"client.id": client_id})
    if "group.id" not in cluster_config:
        cluster_config["group.id"] = environ.get(
            "CONSUMER_GROUP_ID", "kafka-partitions-hunter"
        )
    return Consumer(cluster_config)


def set_admin_client(settings: dict) -> AdminClient:
    """Creates a new librdkafka Admin client"""
    client_id: str = f"admin_partitions_hunter"
    timeout_ms_env = int(environ.get("ADMIN_REQUEST_TIMEOUT_MS", 60000))
    cluster_config = deepcopy(settings)
    cluster_config.update({"client.id": client_id})
    if "group.id" in cluster_config:
        del cluster_config["group.id"]
    cluster_config.update(
        {"request.timeout.ms": timeout_ms_env if timeout_ms_env >= 60000 else 60000}
    )
    return AdminClient(cluster_config)

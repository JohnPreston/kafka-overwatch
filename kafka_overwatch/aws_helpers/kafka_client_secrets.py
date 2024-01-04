#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

"""
Parses the configuration given to the configuration file and is interpolated with the values from {{resolve}}
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.clusters import KafkaCluster

from copy import deepcopy

from aws_cfn_custom_resource_resolve_parser import (
    parse_secret_resolve_string,
    retrieve_secret,
)
from boto3.session import Session

from kafka_overwatch.aws_helpers import get_session_from_iam_override
from kafka_overwatch.config.logging import KAFKA_LOG
from kafka_overwatch.specs.config import ClusterConfig, MskClusterConfig


def handle_librdkafka_config(kafka_cluster: KafkaCluster) -> dict:
    if (
        kafka_cluster.config.cluster_config.cluster_config_auth
        and kafka_cluster.config.cluster_config.cluster_config_auth.iam_override
    ):
        session = get_session_from_iam_override(
            kafka_cluster.config.cluster_config.cluster_config_auth.iam_override
        )
    else:
        session = Session()

    client_config: dict = deepcopy(kafka_cluster.config.cluster_config.kafka)
    for config_key, config_value in client_config.items():
        if isinstance(config_value, str) and config_value.startswith("{{resolve:"):
            try:
                secret_name, key, version = parse_secret_resolve_string(config_value)
                secret = retrieve_secret(secret_name, key, version, session=session)

                client_config[config_key] = secret
            except Exception as error:
                KAFKA_LOG.exception(error)
                KAFKA_LOG.error(
                    f"Error while resolving {config_value}: {error}. Using value as-is."
                )
    return client_config


def eval_kafka_client_config(kafka_cluster: KafkaCluster) -> dict:
    """
    If a configuration value is a string starting with {{resolve:}} the value is interpolated
    using AWS SecretsManager or AWS SSM.
    We create a new dict in order to preserve the original
    """
    if isinstance(kafka_cluster.config.cluster_config, MskClusterConfig):
        raise NotImplementedError("MskClusterConfig is not yet implemented.")

    client_config = handle_librdkafka_config(kafka_cluster)
    return client_config

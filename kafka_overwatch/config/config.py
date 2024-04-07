#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.specs.config import KafkaOverwatchInputConfiguration

from tempfile import TemporaryDirectory

from cryptography.fernet import Fernet
from dacite import from_dict
from prometheus_client import CollectorRegistry, multiprocess

from kafka_overwatch.monitoring.prometheus import (
    set_kafka_cluster_prometheus_registry_collectors,
    set_schema_registry_prometheus_registry_collectors,
)
from kafka_overwatch.notifications.aws_sns import SnsChannel
from kafka_overwatch.overwatch_resources.schema_registry import SchemaRegistry
from kafka_overwatch.specs.config import Global


class OverwatchConfig:
    """
    Class to store in-memory the clusters and their configurations, derived from the input configuration
    classes.
    """

    def __init__(
        self,
        config: KafkaOverwatchInputConfiguration,
        prometheus_dir: TemporaryDirectory,
    ):
        if not config.global_:
            config.global_ = from_dict(Global, {"cluster_scan_interval_in_seconds": 30})
        self._config = config
        self._prometheus_registry_dir = prometheus_dir

        self.prometheus_registry: CollectorRegistry = CollectorRegistry(
            auto_describe=True,
        )
        self.prometheus_collectors = set_kafka_cluster_prometheus_registry_collectors(
            self.prometheus_registry
        )
        self.prometheus_collectors.update(
            set_schema_registry_prometheus_registry_collectors(self.prometheus_registry)
        )
        multiprocess.MultiProcessCollector(
            self.prometheus_registry, path=self._prometheus_registry_dir.name
        )
        self.runtime_key = Fernet.generate_key()
        self.sns_channels: dict[str, SnsChannel] = {}
        self.schema_registries: dict[str, SchemaRegistry] = {}
        self.init_schema_registries()
        self.init_notification_channels()

    def __reduce__(self):
        # Return a tuple with the callable and its arguments
        return (self.__class__, (self._config, self._prometheus_registry_dir))

    @property
    def input_config(self):
        return self._config

    @property
    def prometheus_registry_dir(self) -> TemporaryDirectory:
        return self._prometheus_registry_dir

    def init_schema_registries(self):
        """Initializes the Schema Registries client if setup in the configuration"""
        for registry_name, registry in self.input_config.schema_registries.items():
            _registry = SchemaRegistry(registry_name, registry, self.runtime_key)
            self.schema_registries[registry_name] = _registry

    def init_notification_channels(self):
        if not self._config.notification_channels:
            return
        if not self._config.notification_channels.sns:
            return
        for (
            sns_channel_name,
            sns_channel_definition,
        ) in self._config.notification_channels.sns.items():
            sns_channel = SnsChannel(sns_channel_name, sns_channel_definition)
            self.sns_channels[sns_channel_name] = sns_channel

#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.clusters import KafkaCluster
    from kafka_overwatch.config.config import OverwatchConfig

from tempfile import TemporaryDirectory

import httpx
from cryptography.fernet import Fernet
from kafka_schema_registry_admin import SchemaRegistry as SchemaRegistryClient

from kafka_overwatch.specs.config import ConfluentSchemaRegistry
from kafka_overwatch.specs.config import SchemaRegistry as SchemaRegistryConfig

from .subject import Schema, Subject, refresh_subject_metadata


class BasicAuthCreds:
    def __init__(self, username: str, password, runtime_key):
        cipher_suite = Fernet(runtime_key)
        self.__username = cipher_suite.encrypt(username.encode())
        self.__password = cipher_suite.encrypt(password.encode())

    def get_sr_creds(self, runtime_key):
        cipher_suite = Fernet(runtime_key)
        return {
            "basic_auth.username": cipher_suite.decrypt(self.__username).decode(),
            "basic_auth.password": cipher_suite.decrypt(self.__password).decode(),
        }


class SchemaRegistry:
    """Manages a schema registry and its assignment to Kafka clusters"""

    def __init__(
        self, registry_name: str, registry_config: SchemaRegistryConfig, runtime_key
    ):
        self.name: str = registry_name
        self.temp_bin_dir = TemporaryDirectory()
        self.mmap_file: str = self.temp_bin_dir.name + "/mmap.bin"
        self.basic_auth: BasicAuthCreds | None = None
        if isinstance(registry_config.config, ConfluentSchemaRegistry):
            if registry_config.config.basic_auth:
                self.basic_auth = BasicAuthCreds(
                    registry_config.config.basic_auth.username,
                    registry_config.config.basic_auth.password,
                    runtime_key,
                )
                delattr(registry_config.config, "basic_auth")
        else:
            raise NotImplementedError("Only confluent style schema registry supported")
        """Index of subjects in the registry"""
        self.subjects: dict[str, Subject] = {}
        """Index of the schemas in the registry"""
        self.schemas: dict[int, Schema] = {}
        """Kafka clusters this schema registry is linked to"""
        self.kafka_clusters: dict[str, KafkaCluster] = {}
        self._config = registry_config

    @property
    def config(self) -> SchemaRegistryConfig:
        return self._config

    def __repr__(self):
        return self.name

    def get_client(self, runtime_key) -> SchemaRegistryClient | None:
        if self.basic_auth:
            kwargs: dict = self.basic_auth.get_sr_creds(runtime_key)
        else:
            kwargs: dict = {}
        if isinstance(self._config.config, ConfluentSchemaRegistry):
            return SchemaRegistryClient(
                self.config.config.schema_registry_url,
                **kwargs,
            )
        return

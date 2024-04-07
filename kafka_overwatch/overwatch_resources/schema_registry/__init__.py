#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

import tarfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.clusters import KafkaCluster
    from .subject import Subject
    from .schema import Schema

from tempfile import TemporaryDirectory

from cryptography.fernet import Fernet
from kafka_schema_registry_admin import SchemaRegistry as SchemaRegistryClient

from kafka_overwatch.aws_helpers.s3 import S3Handler
from kafka_overwatch.specs.config import ConfluentSchemaRegistry
from kafka_overwatch.specs.config import SchemaRegistry as SchemaRegistryConfig


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
        self.s3_backup_handler: S3Handler | None = None
        if self.config.backup_config and self.config.backup_config.enabled:
            self.s3_backup_handler = S3Handler(self.config.backup_config.S3)

        self.supported_types = ["JSON", "PROTOBUF", "AVRO"]

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

    def backup(self):
        if not self.s3_backup_handler:
            return
        process_folder = TemporaryDirectory()
        schemas_folder: TemporaryDirectory = TemporaryDirectory(dir=process_folder.name)
        for _subject in self.subjects.values():
            for version in _subject.versions:
                _schema: Schema = _subject.versions[version]
                schema_file_name = f"{_subject.name}::{version}::{_schema.schema_type}::{_schema.schema_id}.txt"
                with open(
                    f"{schemas_folder.name}/{schema_file_name}", "w"
                ) as subject_version_fd:
                    subject_version_fd.write(_schema.schema_string)
        with tarfile.open(f"{process_folder.name}/schemas.tar.gz", "w:gz") as tar:
            tar.add(schemas_folder.name, arcname=".")
        with open(f"{process_folder.name}/schemas.tar.gz", "rb") as gz_fd:
            self.s3_backup_handler.upload(
                body=gz_fd.read(),
                file_name="schemas.tar.gz",
                mime_type="application/gzip",
            )
        schemas_folder.cleanup()
        process_folder.cleanup()

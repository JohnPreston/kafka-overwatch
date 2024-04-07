#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.schema_registry import (
        SchemaRegistry,
        Subject,
    )


class Schema:
    """Class to maintain metadata about schema"""

    def __init__(
        self,
        schema_id: int,
        schema_string: str,
        overwatch_registry: SchemaRegistry,
        schema_type: str = None,
    ):
        self.schema_id: int = schema_id
        self.schema_string: str = schema_string
        self._schema_type: str | None = schema_type
        self._registry: SchemaRegistry = overwatch_registry

    def __str__(self):
        return f"{self.schema_id}"

    def __repr__(self):
        return f"{self.schema_id}"

    @property
    def schema_type(self) -> str | None:
        return self._schema_type

    @schema_type.setter
    def schema_type(self, value: str):
        if value not in self._registry.supported_types:
            raise ValueError(
                f"Invalid schema type: {value}. Must be one of",
                self._registry.supported_types,
            )
        self._schema_type = value

    @property
    def overwatch_registry(self) -> SchemaRegistry:
        return self._registry


def refresh_subject_metadata(subject: Subject, sr_client):
    """
    Iterates over all the versions of a given subject.
    If the version and schema is already in the registry inventory, skip.
    If not, retrieve the schema details, and store to the in-memory registry.
    """
    subject_versions = sr_client.get_subject_versions(subject.name).json()
    for version in subject_versions:
        if version in subject.versions:
            continue
        subject_version_schema = (
            sr_client.get_subject_version_id(subject.name, version)
        ).json()
        if subject_version_schema["id"] not in subject.overwatch_registry.schemas:
            _schema = Schema(subject_version_schema["id"], subject.overwatch_registry)
            subject.overwatch_registry.schemas[_schema.schema_id] = _schema
        else:
            _schema = subject.overwatch_registry.schemas[subject_version_schema["id"]]
        if subject_version_schema["version"] not in subject.versions:
            subject.versions[subject_version_schema["version"]] = _schema

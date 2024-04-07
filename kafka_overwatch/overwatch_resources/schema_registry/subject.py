#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>


from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.overwatch_resources.schema_registry import (
        Schema,
        SchemaRegistry,
    )


class Subject:
    """ "Class to maintain subject metadata information"""

    def __init__(self, name: str, overwatch_registry: SchemaRegistry):
        self.name = name
        self.schema_data = None
        self.versions: dict[int, Schema] = {}
        self._registry: SchemaRegistry = overwatch_registry

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    @property
    def overwatch_registry(self) -> SchemaRegistry:
        return self._registry

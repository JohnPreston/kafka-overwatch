# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>

from __future__ import annotations

import yaml

try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader, Dumper

from dacite import from_dict
from importlib_resources import files as pkg_files
from jsonschema import validate

from kafka_overwatch.specs.config import KafkaOverwatchInputConfiguration


def load_config_file(file_path: str) -> KafkaOverwatchInputConfiguration:
    with open(file_path) as fd:
        config = yaml.load(fd, Loader=Loader)
    schema_source = pkg_files("kafka_overwatch").joinpath("specs/config.json")
    validate(
        config,
        yaml.load(schema_source.read_text(), Loader=Loader),
    )

    if "gateways" in config:
        raise NotImplementedError("Gateways are not yet supported")
    return from_dict(data_class=KafkaOverwatchInputConfiguration, data=config)

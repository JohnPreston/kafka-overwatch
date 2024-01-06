#!/usr/bin/env bash

poetry run datamodel-codegen --input kafka_overwatch/specs/config.json --input-file-type jsonschema \
    --output kafka_overwatch/specs/config.py --output-model-type dataclasses.dataclass \
    --reuse-model --target-python-version 3.10 --disable-timestamp --use-double-quotes \
    --use-field-description --use-schema-description

poetry run datamodel-codegen --input kafka_overwatch/specs/report.json --input-file-type jsonschema \
    --output kafka_overwatch/specs/report.py --output-model-type dataclasses.dataclass \
    --reuse-model --target-python-version 3.10 --disable-timestamp --use-double-quotes \
    --use-field-description --use-schema-description

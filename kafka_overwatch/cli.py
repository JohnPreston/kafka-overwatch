# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>
import sys
from argparse import ArgumentParser
from os import environ
from tempfile import TemporaryDirectory

from kafka_overwatch.config import load_config_file


def set_parser():
    parser = ArgumentParser()
    parser.add_argument(
        "-c",
        "--config-file",
        default=None,
        dest="config_file",
        help="Path to the clusters config file",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser


def main():
    """
    Main entrypoint
    Prometheus temp dir needs to be setup before at this point. Won't work later in the code...
    """
    _parser = set_parser()
    _args = _parser.parse_args()
    _config = load_config_file(_args.config_file)

    prometheus_registry_dir: TemporaryDirectory = TemporaryDirectory()
    if not environ.get("PROMETHEUS_MULTIPROC_DIR") or not environ.get(
        "prometheus_multiproc_dir"
    ):
        print(
            "## PROMETHEUS_MULTIPROC_DIR not set. Setting to:",
            prometheus_registry_dir.name,
        )

        environ["PROMETHEUS_MULTIPROC_DIR"] = prometheus_registry_dir.name
        environ["prometheus_multiproc_dir"] = prometheus_registry_dir.name

    from kafka_overwatch.config.config import OverwatchConfig
    from kafka_overwatch.overwatch import KafkaOverwatchService

    _overwatch_config: OverwatchConfig = OverwatchConfig(
        _config, prometheus_registry_dir
    )
    watcher = KafkaOverwatchService(_overwatch_config)
    watcher.start()


if __name__ == "__main__":
    sys.exit(main())

# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>
import faulthandler
import sys
from argparse import ArgumentParser
from os import environ
from tempfile import TemporaryDirectory

try:
    from codeguru_profiler_agent import Profiler

    _ATTEMPT_PROFILING: bool = True
except ImportError:
    _ATTEMPT_PROFILING: bool = False

from boto3.session import Session

from kafka_overwatch.config import load_config_file

faulthandler.enable()


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


def profiling_setup() -> Profiler | None:
    if _ATTEMPT_PROFILING:
        _watcher_session = Session()
        try:
            profiler = Profiler(
                "overwatch", aws_session=_watcher_session, region_name="eu-west-1"
            )
            return profiler
        except Exception as error:
            print("Failed to start CodeGuru profiler")
            print(error)
            return None


def set_prometheus_env_vars() -> TemporaryDirectory:
    """Prometheus temp dir needs to be setup before at this point. Won't work later in the code..."""

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
    return prometheus_registry_dir


def main():
    """
    Main entrypoint
    """
    _parser = set_parser()
    _args = _parser.parse_args()
    _config = load_config_file(_args.config_file)
    profiler = profiling_setup()
    prometheus_registry_dir = set_prometheus_env_vars()

    from kafka_overwatch.config.config import OverwatchConfig
    from kafka_overwatch.overwatch import KafkaOverwatchService

    try:
        _overwatch_config: OverwatchConfig = OverwatchConfig(
            _config, prometheus_registry_dir
        )
        watcher = KafkaOverwatchService(_overwatch_config)
        if profiler:
            profiler.start()
        watcher.start()
        return 0
    except Exception as error:
        print(error)
        return 1


if __name__ == "__main__":
    sys.exit(main())

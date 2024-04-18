# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>

import faulthandler
from argparse import ArgumentParser

try:
    from codeguru_profiler_agent import Profiler

    _ATTEMPT_PROFILING: bool = True
except ImportError:
    _ATTEMPT_PROFILING: bool = False

from kafka_overwatch.overwatch_resources.schema_registry.schemas_restore import (
    main as restore_schemas,
)

faulthandler.enable()


def set_parser():
    parser = ArgumentParser()
    parser.add_argument(
        "-b",
        "--backup-file",
        default=None,
        dest="input_backup",
        help="Path to the backup .tar.gz file containing the schemas definitions and index.json",
        required=True,
    )
    parser.add_argument(
        "--sr-url",
        default=None,
        required=True,
        dest="url",
    )
    parser.add_argument(
        "--sr-user",
        default=None,
        required=False,
        dest="username",
    )
    parser.add_argument(
        "--sr-password",
        default=None,
        required=False,
        dest="password",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    return parser


def main():
    parser = set_parser()
    args = parser.parse_args()
    _kwargs: dict = vars(args)
    restore_schemas(**_kwargs)


if __name__ == "__main__":
    main()

# SPDX-License-Identifier: MPL-2.0
# Copyright 2024 John Mille <john@ews-network.net>

"""Module used to re-import schemas from backup to existing or new schema registry"""

from __future__ import annotations

import json
import tarfile
from tempfile import TemporaryDirectory

from kafka_schema_registry_admin.client_wrapper.errors import NotFoundException
from kafka_schema_registry_admin.kafka_schema_registry_admin import SchemaRegistry

# subject-name::subject_version::schema_type::schema_id.txt


def restore_subject_versions(
    schema_registry: SchemaRegistry,
    subject_name: str,
    subject_details: dict,
    tmp_folder: TemporaryDirectory,
    existing_versions: list = None,
) -> None:
    """Restore a full subject given it doesn't exist in Registry"""
    try:
        schema_registry.put_subject_mode(subject_name, "IMPORT")
        subject_mode_failed: bool = False
    except Exception as error:
        subject_mode_failed = True
    if existing_versions is None:
        existing_versions = []
    for version_id, file_name in subject_details.items():
        if version_id in existing_versions:
            continue
        if subject_mode_failed:
            schema_registry.put_subject_mode(subject_name, "IMPORT", force=True)
        __subject_name, _version_id, _schema_type, _schema_id = file_name.split("::")
        _schema_id: int = int(_schema_id.replace(".txt", ""))
        with open(f"{tmp_folder.name}/{file_name}") as schema_fd:
            schema_content = schema_fd.read()
        schema_registry.post_subject_schema_version(
            subject_name,
            schema_content,
            version_id=_version_id,
            schema_type=_schema_type,
            schema_id=_schema_id,
        )
    schema_registry.put_subject_mode(subject_name, "READWRITE")


def restore_subject(
    schema_registry: SchemaRegistry,
    subject_name: str,
    subject_details: dict,
    tmp_folder: TemporaryDirectory,
) -> None:
    try:
        subject_existing_versions: list = schema_registry.get_subject_versions(
            subject_name
        ).json()
        restore_subject_versions(
            schema_registry,
            subject_name,
            subject_details,
            tmp_folder,
            subject_existing_versions,
        )
    except NotFoundException:
        restore_subject_versions(
            schema_registry, subject_name, subject_details, tmp_folder
        )


def main(*args, **kwargs):
    """Main function"""
    schema_registry = SchemaRegistry(kwargs.get("url"))
    tmp_folder = TemporaryDirectory()

    with tarfile.open(kwargs.get("input_backup"), "r:gz") as gz_fd:
        gz_fd.extractall(tmp_folder.name)

    with open(f"{tmp_folder.name}/index.json") as index_fd:
        subjects_index = json.load(index_fd)

    for _subject_name in subjects_index:
        try:
            restore_subject(
                schema_registry,
                _subject_name,
                subjects_index[_subject_name],
                tmp_folder,
            )
        except Exception as error:
            print(f"Error restoring subject {_subject_name}: {error}")

#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

"""Package to perform the discovery of ACLs."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from confluent_kafka.admin import AdminClient

from confluent_kafka.admin import (
    AclBinding,
    AclBindingFilter,
    AclOperation,
    AclPermissionType,
    ResourcePatternType,
    ResourceType,
)


def retrieve_all_acls(admin_client: AdminClient):
    try:
        acl_filter = AclBindingFilter(
            resource_pattern_type=ResourcePatternType.ANY,
            restype=ResourceType.ANY,
            name=None,
            principal=None,
            host=None,
            operation=AclOperation.ANY,
            permission_type=AclPermissionType.ANY,
        )

        # Get ACLs
        acls = admin_client.describe_acls(acl_filter)
        while not acls.done():
            pass
        for acl in acls.result():
            print(
                f"Resource: {acl.resource_pattern_type}, "
                f"Principal: {acl.principal}, "
                f"Host: {acl.host}, "
                f"Operation: {acl.operation}, "
                f"Permission: {acl.permission_type}, "
                f"Name: {acl.name}"
            )

    except Exception as e:
        print(f"Failed to list ACLs: {e}")

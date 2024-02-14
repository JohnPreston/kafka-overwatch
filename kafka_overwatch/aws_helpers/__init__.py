#  SPDX-License-Identifier: MPL-2.0
#  Copyright 2024 John Mille <john@ews-network.net>

"""
AWS Helper functions
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kafka_overwatch.specs.config import IamOverride

from boto3.session import Session
from compose_x_common.aws import get_assume_role_session

from kafka_overwatch.specs.config import AssumeRole


def get_session_from_iam_override(iam_override: IamOverride) -> Session:
    """
    Returns a boto3 session from the IamOverride config.
    If profileName is set, return session for that profile name
    Elif profileName + AssumeRole, use a session of that profile name, then return AssumeRole session
    Elif not profileName and AssumeRole, just use AssumeRole
    """
    if isinstance(iam_override, str):
        _session = Session(profile_name=iam_override)
    elif isinstance(iam_override, AssumeRole):
        kwargs: dict = {}
        if iam_override.ExternalId:
            kwargs["ExternalId"] = iam_override.ExternalId
        if iam_override.RoleSessionName:
            kwargs["RoleSessionName"] = iam_override.RoleSessionName

        _session = get_assume_role_session(Session(), iam_override.RoleArn, **kwargs)
    else:
        _session = Session()
    return _session

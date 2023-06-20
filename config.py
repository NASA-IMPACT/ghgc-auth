import os

from getpass import getuser
from typing import Optional

import pydantic


class Config(pydantic.BaseSettings):
    app_name: str = pydantic.Field(
        "veda-auth",
        description="Name of the associated App.",
    )
    stage: str = pydantic.Field(
        description=" ".join(
            [
                "Stage of deployment (e.g. 'dev', 'prod').",
                "Used as suffix for stack name.",
                "Defaults to current username.",
            ]
        ),
        default_factory=getuser,
    )
    owner: str = pydantic.Field(
        description=" ".join(
            [
                "Name of primary contact for Cloudformation Stack.",
                "Used to tag generated resources",
                "Defaults to current username.",
            ]
        ),
        default_factory=getuser,
    )
    data_managers_role_arn: str = pydantic.Field(
        None,
        description="ARN of role to be assumed by authenticated users in data managers group.",
    )

    oidc_provider_url: Optional[str] = pydantic.Field(
        None,
        description="URL of OIDC provider to use for CI workers.",
    )

    oidc_thumbprint: Optional[str] = pydantic.Field(
        None,
        description="Thumbprint of OIDC provider to use for CI workers.",
    )

    permissions_boundary_policy_name: Optional[str] = pydantic.Field(
        None,
        description="Name of IAM policy to define stack permissions boundary",
    )

    # Since MCP doesn't allow creating identity pools, setting this as optional
    cognito_groups: Optional[bool] = pydantic.Field(
        True,
        description="Where to create cognito groups with bucket access permissions",
    )
    cdk_qualifier: Optional[str] = pydantic.Field(
        "hnb659fds",
        description="CDK qualifier for deployment.",
    )


auth_app_settings = Config(_env_file=os.environ.get("ENV_FILE", ".env"))


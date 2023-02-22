#!/usr/bin/env python3
import os
import subprocess

import aws_cdk as cdk

from config import Config
from infra.stack import AuthStack, BucketPermissions

config = Config(_env_file=os.environ.get("ENV_FILE", ".env"))
git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
try:
    git_tag = subprocess.check_output(["git", "describe", "--tags"]).decode().strip()
except subprocess.CalledProcessError:
    git_tag = "no-tag"

tags = {
    "Project": "veda",
    "Owner": config.owner,
    "Client": "nasa-impact",
    "Stack": config.stage,
    "GitCommit": git_sha,
    "GitTag": git_tag,
}

app = cdk.App()
stack = AuthStack(app, f"veda-auth-stack-{config.stage}")

# Create a data managers group in user pool if data managers role is provided
if data_managers_role_arn := config.data_managers_role_arn:
    stack.add_cognito_group_with_existing_role(
        "veda-data-store-managers",
        "Authenticated users assume read write veda data access role",
        role_arn=data_managers_role_arn,
    )

# Create Groups
stack.add_cognito_group(
    "veda-staging-writers",
    "Users that have read/write-access to the VEDA store and staging datastore",
    {
        "veda-data-store-dev": BucketPermissions.read_write,
        "veda-data-store": BucketPermissions.read_write,
        "veda-data-store-staging": BucketPermissions.read_write,
    },
)
stack.add_cognito_group(
    "veda-writers",
    "Users that have read/write-access to the VEDA store",
    {
        "veda-data-store-dev": BucketPermissions.read_write,
        "veda-data-store": BucketPermissions.read_write,
    },
)

stack.add_cognito_group(
    "veda-staging-readers",
    "Users that have read-access to the VEDA store and staging data store",
    {
        "veda-data-store-dev": BucketPermissions.read_only,
        "veda-data-store": BucketPermissions.read_only,
        "veda-data-store-staging": BucketPermissions.read_only,
    },
)
# TODO: Should this be the default IAM role for the user group?
stack.add_cognito_group(
    "veda-readers",
    "Users that have read-access to the VEDA store",
    {
        "veda-data-store": BucketPermissions.read_only,
    },
)

# Generate a resource server (ie something to protect behind auth) with scopes
# (permissions that we can grant to users/services).
stac_registry_scopes = stack.add_resource_server(
    "veda-stac-ingestion-registry",
    supported_scopes={
        "stac:register": "Create STAC ingestions",
        "stac:cancel": "Cancel a STAC ingestion",
        "stac:list": "Cancel a STAC ingestion",
    },
)


# Generate a client for a service, specifying the permissions it will be granted.
# In this case, we want this client to be able to only register new STAC ingestions in
# the STAC ingestion registry service.
stack.add_service_client(
    "veda-workflows",
    scopes=[
        stac_registry_scopes["stac:register"],
    ],
)

# Generate an OIDC provider, allowing CI workers to assume roles in the account

stack.add_oidc_provider(
    f"veda-oidc-provider-{config.stage}",
    config.oidc_provider_url,
    config.oidc_thumbprint,
)

# Programmatic Clients
stack.add_programmatic_client("veda-sdk")

# Frontend Clients
# stack.add_frontend_client('veda-dashboard')

for key, value in tags.items():
    cdk.Tags.of(stack).add(key, value)

app.synth()

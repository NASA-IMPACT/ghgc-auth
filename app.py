#!/usr/bin/env python3
import os
import subprocess

import aws_cdk as cdk
from os import environ
from config import Config
from infra.stack import AuthStack, BucketPermissions

config = Config(_env_file=os.environ.get("ENV_FILE", ".env"))
git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
try:
    git_tag = subprocess.check_output(["git", "describe", "--tags"]).decode().strip()
except subprocess.CalledProcessError:
    git_tag = "no-tag"
proj_prefix = environ.get("PROJ_PREFIX", "ghgc")
tags = {
    "Project": proj_prefix,
    "Owner": config.owner,
    "Client": "nasa-impact",
    "Stack": config.stage,
    "GitCommit": git_sha,
    "GitTag": git_tag,
}

app = cdk.App()
stack = AuthStack(app, f"{config.app_name}-stack-{config.stage}", synthesizer=cdk.DefaultStackSynthesizer(
        qualifier=config.cdk_qualifier
))

# Create a data managers group in user pool if data managers role is provided
if data_managers_role_arn := config.data_managers_role_arn:
    stack.add_cognito_group_with_existing_role(
        f"{proj_prefix}-data-store-managers",
        "Authenticated users assume read write GHGC data access role",
        role_arn=data_managers_role_arn,
    )

# Create Groups
stack.add_cognito_group(
    f"{proj_prefix}-staging-writers",
    "Users that have read/write-access to the GHGC store and staging datastore",
    {
        f"{proj_prefix}-data-store-dev": BucketPermissions.read_write,
        f"{proj_prefix}-data-store": BucketPermissions.read_write,
        f"{proj_prefix}-data-store-staging": BucketPermissions.read_write,
    },
)
stack.add_cognito_group(
    f"{proj_prefix}-writers",
    "Users that have read/write-access to the GHGC store",
    {
        f"{proj_prefix}-data-store-dev": BucketPermissions.read_write,
        f"{proj_prefix}-data-store": BucketPermissions.read_write,
    },
)

stack.add_cognito_group(
    f"{proj_prefix}-staging-readers",
    "Users that have read-access to the GHGC store and staging data store",
    {
        f"{proj_prefix}-data-store-dev": BucketPermissions.read_only,
        f"{proj_prefix}-data-store": BucketPermissions.read_only,
        f"{proj_prefix}-data-store-staging": BucketPermissions.read_only,
    },
)
# TODO: Should this be the default IAM role for the user group?
stack.add_cognito_group(
    f"{proj_prefix}-readers",
    "Users that have read-access to the GHGC store",
    {
        f"{proj_prefix}-data-store": BucketPermissions.read_only,
    },
)

# Generate a resource server (ie something to protect behind auth) with scopes
# (permissions that we can grant to users/services).
stac_registry_scopes = stack.add_resource_server(
    f"{proj_prefix}-stac-ingestion-registry",
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
    f"{proj_prefix}-workflows",
    scopes=[
        stac_registry_scopes["stac:register"],
    ],
)

# Generate an OIDC provider, allowing CI workers to assume roles in the account

oidc_thumbprint = config.oidc_thumbprint
oidc_provider_url = config.oidc_provider_url
if oidc_thumbprint and oidc_provider_url:
    stack.add_oidc_provider(
        f"{proj_prefix}-oidc-provider-{config.stage}",
        oidc_provider_url,
        oidc_thumbprint,
    )

# Programmatic Clients
stack.add_programmatic_client(f"{proj_prefix}-sdk")

# Frontend Clients
# stack.add_frontend_client('ghgc-dashboard')

for key, value in tags.items():
    cdk.Tags.of(stack).add(key, value)

app.synth()

#!/usr/bin/env python3
import os
import subprocess

import aws_cdk as cdk

from aws_cdk import Aspects, Stack, aws_iam
from constructs import Construct
from config import Config
from infra.stack import AuthStack, BucketPermissions
from config import auth_app_settings

config = Config(_env_file=os.environ.get("ENV_FILE", ".env"))
git_sha = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
try:
    git_tag = subprocess.check_output(["git", "describe", "--tags"]).decode().strip()
except subprocess.CalledProcessError:
    git_tag = "no-tag"

tags = {
    "Project": "ghgc",
    "Owner": config.owner,
    "Client": "nasa-impact",
    "Stack": config.stage,
    "GitCommit": git_sha,
    "GitTag": git_tag,
}

app = cdk.App()
stack = AuthStack(app, f"{config.app_name}-stack-{config.stage}")

# Set permissions boundary on CDK stack
class AuthStack(Stack):
    
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        """."""
        super().__init__(scope, construct_id, **kwargs)

        if auth_app_settings.permissions_boundary_policy_name:
            permission_boundary_policy = aws_iam.ManagedPolicy.from_managed_policy_name(
                self,
                "permission-boundary",
                auth_app_settings.permissions_boundary_policy_name,
            )
            aws_iam.PermissionsBoundary.of(self).apply(permission_boundary_policy)

            from permission_boundary import PermissionBoundaryAspect

            Aspects.of(self).add(PermissionBoundaryAspect(permission_boundary_policy))

            # Print the permissions_boundary_policy
            print(f"permissions_boundary_policy: {permission_boundary_policy}")

# Create a data managers group in user pool if data managers role is provided
if data_managers_role_arn := config.data_managers_role_arn:
    stack.add_cognito_group_with_existing_role(
        "ghgc-data-store-managers",
        "Authenticated users assume read write GHGC data access role",
        role_arn=data_managers_role_arn,
    )

# Create Groups
stack.add_cognito_group(
    "ghgc-staging-writers",
    "Users that have read/write-access to the GHGC store and staging datastore",
    {
        "ghgc-data-store-dev": BucketPermissions.read_write,
        "ghgc-data-store": BucketPermissions.read_write,
        "ghgc-data-store-staging": BucketPermissions.read_write,
    },
)
stack.add_cognito_group(
    "ghgc-writers",
    "Users that have read/write-access to the GHGC store",
    {
        "ghgc-data-store-dev": BucketPermissions.read_write,
        "ghgc-data-store": BucketPermissions.read_write,
    },
)

stack.add_cognito_group(
    "ghgc-staging-readers",
    "Users that have read-access to the GHGC store and staging data store",
    {
        "ghgc-data-store-dev": BucketPermissions.read_only,
        "ghgc-data-store": BucketPermissions.read_only,
        "ghgc-data-store-staging": BucketPermissions.read_only,
    },
)
# TODO: Should this be the default IAM role for the user group?
stack.add_cognito_group(
    "ghgc-readers",
    "Users that have read-access to the GHGC store",
    {
        "ghgc-data-store": BucketPermissions.read_only,
    },
)

# Generate a resource server (ie something to protect behind auth) with scopes
# (permissions that we can grant to users/services).
stac_registry_scopes = stack.add_resource_server(
    "ghgc-stac-ingestion-registry",
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
    "ghgc-workflows",
    scopes=[
        stac_registry_scopes["stac:register"],
    ],
)

# Generate an OIDC provider, allowing CI workers to assume roles in the account

oidc_thumbprint = config.oidc_thumbprint
oidc_provider_url = config.oidc_provider_url
if oidc_thumbprint and oidc_provider_url:
    stack.add_oidc_provider(
        f"ghgc-oidc-provider-{config.stage}",
        oidc_provider_url,
        oidc_thumbprint,
    )

# Programmatic Clients
stack.add_programmatic_client("ghgc-sdk")

# Frontend Clients
# stack.add_frontend_client('ghgc-dashboard')

for key, value in tags.items():
    cdk.Tags.of(stack).add(key, value)

app.synth()

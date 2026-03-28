import json
import os
from functools import lru_cache

import boto3


@lru_cache
def get_database_url() -> str:
    """Resolve the database URL from env vars or Secrets Manager.

    In Lambda workers: DB_SECRET_ARN is set -> fetch from Secrets Manager.
    Locally: DB_SECRET_ARN is None -> use DATABASE_URL from docker-compose env.
    In ECS: construct from the individual DB_* secret fields injected by ECS.
    """
    secret_arn = os.environ.get("DB_SECRET_ARN")
    if not secret_arn:
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            return database_url
        # ECS: construct from individual Secrets Manager fields
        return (
            f"postgresql://{os.environ['DB_USER']}:{os.environ['DB_PASSWORD']}"
            f"@{os.environ['DB_HOST']}:{os.environ['DB_PORT']}/{os.environ['DB_NAME']}"
        )
    return _fetch_from_secrets_manager(secret_arn)


def _fetch_from_secrets_manager(secret_arn: str) -> str:  # pragma: no cover
    client = boto3.client(
        "secretsmanager",
        region_name=os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION"),
    )
    response = client.get_secret_value(SecretId=secret_arn)
    secret = json.loads(response["SecretString"])

    return (
        f"postgresql://{secret['username']}:{secret['password']}"
        f"@{secret['host']}:{secret['port']}/{secret['dbname']}"
    )

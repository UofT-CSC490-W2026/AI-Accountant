import json
import os
import urllib.request
from functools import lru_cache


@lru_cache
def get_database_url() -> str:
    """Fetch DB credentials from Secrets Manager via Lambda Extension.

    In Lambda: DB_SECRET_ARN is set -> fetch from extension at localhost:2773.
    Locally: DB_SECRET_ARN is None -> use DATABASE_URL from docker-compose env.
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
    url = f"http://localhost:2773/secretsmanager/get?secretId={secret_arn}"
    headers = {"X-Aws-Parameters-Secrets-Token": os.environ["AWS_SESSION_TOKEN"]}

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        secret = json.loads(json.loads(resp.read())["SecretString"])

    return (
        f"postgresql://{secret['username']}:{secret['password']}"
        f"@{secret['host']}:{secret['port']}/{secret['dbname']}"
    )

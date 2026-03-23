import json

import boto3

from config import get_settings

_MODEL_ID = "us.cohere.embed-v4:0"


def _client():
    settings = get_settings()
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.AWS_DEFAULT_REGION,
    )


def embed_text(text: str, input_type: str = "search_query") -> list[float]:
    """Embed a single text string via Cohere Embed v4 on Bedrock.

    Args:
        text: Text to embed.
        input_type: "search_query" when embedding a query to search Qdrant;
                    "search_document" when embedding content to store in Qdrant.

    Returns:
        1536-dimensional float vector.
    """
    return embed_texts([text], input_type=input_type)[0]


def embed_texts(texts: list[str], input_type: str = "search_query") -> list[list[float]]:
    """Embed a batch of texts via Cohere Embed v4 on Bedrock.

    Args:
        texts: List of texts to embed.
        input_type: "search_query" or "search_document".

    Returns:
        List of 1536-dimensional float vectors, same length as texts.
    """
    body = json.dumps({
        "texts": texts,
        "input_type": input_type,
        "embedding_types": ["float"],
    })
    response = _client().invoke_model(
        modelId=_MODEL_ID,
        body=body,
        accept="*/*",
        contentType="application/json",
    )
    result = json.loads(response["body"].read())
    return result["embeddings"]["float"]

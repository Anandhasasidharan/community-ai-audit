"""
AWS Bedrock adapter — works with models hosted on AWS Bedrock
(Claude, Llama, Mistral, Titan, Cohere, etc.).
"""

from typing import Any, Dict, Optional
import logging

from community_ai_audit.core.interfaces import ModelAdapter, TextModelAdapter, ModelType

log = logging.getLogger(__name__)


def safe_import(name, package=None):
    import importlib
    try:
        return importlib.import_module(name, package=package)
    except ImportError:
        return None


class AWSBedrockAdapter(TextModelAdapter):
    """Adapter for AWS Bedrock-hosted models via boto3 / bedrock-runtime.

    Supports: Claude (via Messages API), Llama, Mistral, Titan, Cohere, etc.

    Config keys:
        region_name (str): AWS region (e.g. 'us-east-1').
        aws_access_key_id (str, optional): Explicit credentials.
        aws_secret_access_key (str, optional): Explicit credentials.
        profile_name (str, optional): AWS profile to use.
        endpoint_url (str, optional): Custom endpoint (e.g. for local Bedrock).
        model_family (str): 'anthropic', 'meta', 'mistral', 'amazon', 'cohere'.
    """

    name = "aws_bedrock"
    provider = "aws"
    supported_types = [ModelType.TEXT]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._client = None
        self._model_family = self.config.get("model_family", "anthropic")

    def connect(self, config: Dict[str, Any]) -> None:
        boto3 = safe_import("boto3")
        if boto3 is None:
            raise ImportError("boto3 not installed. Run: pip install boto3")

        session_kwargs = {}
        profile = config.get("profile_name")
        if profile:
            session_kwargs["profile_name"] = profile

        import os
        boto_session = boto3.Session(**session_kwargs)

        kwargs: Dict[str, Any] = {"region_name": config.get("region_name", os.environ.get("AWS_REGION", "us-east-1"))}
        if config.get("aws_access_key_id") and config.get("aws_secret_access_key"):
            kwargs["aws_access_key_id"] = config["aws_access_key_id"]
            kwargs["aws_secret_access_key"] = config["aws_secret_access_key"]

        self._client = boto_session.client(
            "bedrock-runtime",
            endpoint_url=config.get("endpoint_url"),
            **kwargs,
        )
        self._model_family = config.get("model_family", "anthropic")
        log.info("AWS Bedrock adapter connected (region: %s, family: %s)", kwargs["region_name"], self._model_family)

    def disconnect(self) -> None:
        self._client = None

    def get_model(self, model_id: str, **kwargs) -> Any:
        if self._client is None:
            raise RuntimeError("Not connected. Call connect() first.")
        return _BedrockModelWrapper(self._client, model_id, self._model_family, kwargs)

    def predict(self, model: Any, inputs: Any, **kwargs) -> Any:
        return model.predict(inputs, **kwargs)

    def get_input_spec(self, model: Any) -> Dict[str, Any]:
        return {"type": "text", "model_id": model.model_id, "provider": "aws_bedrock"}

    def supports_model_type(self, model_type: ModelType) -> bool:
        return model_type == ModelType.TEXT

    def tokenize(self, text: str, **kwargs) -> Dict[str, Any]:
        return {"prompt": text}

    def generate(self, model: Any, prompt: str, **kwargs) -> str:
        return model.predict({"prompt": prompt}, **kwargs)

    def get_logits(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError("Logits not available via AWS Bedrock (black-box).")

    def get_attention_weights(self, model: Any, tokens: Any, **kwargs) -> Any:
        raise NotImplementedError("Attention weights not available via AWS Bedrock (black-box).")

    @classmethod
    def get_config_schema(cls) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "region_name": {"type": "string", "default": "us-east-1"},
                "aws_access_key_id": {"type": "string"},
                "aws_secret_access_key": {"type": "string"},
                "profile_name": {"type": "string"},
                "endpoint_url": {"type": "string"},
                "model_family": {
                    "type": "string",
                    "enum": ["anthropic", "meta", "mistral", "amazon", "cohere"],
                },
            },
        }

    @classmethod
    def auto_config(cls) -> Dict[str, Any]:
        import os
        return {
            "region_name": os.environ.get("AWS_REGION", "us-east-1"),
            "profile_name": os.environ.get("AWS_PROFILE"),
        }


class _BedrockModelWrapper:
    """Wrapper for a Bedrock model with a consistent interface."""

    def __init__(self, client, model_id: str, model_family: str, defaults: Dict[str, Any]):
        self._client = client
        self.model_id = model_id
        self._family = model_family
        self._defaults = defaults

    def predict(self, inputs: Dict[str, Any], **kwargs) -> Any:
        import json
        merged = {**self._defaults, **kwargs}
        prompt = inputs.get("prompt", "")

        if self._family == "anthropic":
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": merged.pop("max_tokens", 1024),
            }
            body.update(merged)
            resp = self._client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            resp_body = json.loads(resp["body"].read())
            return resp_body.get("content", [{}])[0].get("text", "")

        elif self._family in ("meta", "mistral", "cohere", "amazon"):
            # Text completion format
            body = {"prompt": prompt}
            body.update(merged)
            resp = self._client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            resp_body = json.loads(resp["body"].read())
            if self._family == "cohere":
                return resp_body.get("generations", [{}])[0].get("text", "")
            return resp_body.get("outputs", [{}])[0].get("text", "")  # Mistral / Llama
        else:
            raise ValueError(f"Unsupported model family: {self._family}")
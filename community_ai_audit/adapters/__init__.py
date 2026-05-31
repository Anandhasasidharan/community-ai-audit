# Model provider adapters
# Each adapter implements the ModelAdapter ABC for a specific provider.

from .huggingface_adapter import HuggingFaceAdapter
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .aws_bedrock_adapter import AWSBedrockAdapter
from .local_adapter import LocalAdapter
from .ollama_adapter import OllamaAdapter

__all__ = [
    "HuggingFaceAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "AWSBedrockAdapter",
    "LocalAdapter",
    "OllamaAdapter",
]
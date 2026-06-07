# Model provider adapters
# Each adapter implements the ModelAdapter ABC for a specific provider.

from .huggingface_adapter import HuggingFaceAdapter
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter
from .aws_bedrock_adapter import AWSBedrockAdapter
from .local_adapter import LocalAdapter
from .ollama_adapter import OllamaAdapter
from .vertexai_adapter import VertexAIAdapter
from .groq_adapter import GroqAdapter
from .replicate_adapter import ReplicateAdapter

__all__ = [
    "HuggingFaceAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "AWSBedrockAdapter",
    "LocalAdapter",
    "OllamaAdapter",
    "VertexAIAdapter",
    "GroqAdapter",
    "ReplicateAdapter",
]

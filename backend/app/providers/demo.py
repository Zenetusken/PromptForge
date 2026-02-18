#!/usr/bin/env python3
"""Demonstration of the unified CompletionRequest/CompletionResponse API.

Shows how the same request can be sent to any registered provider via the
ProviderRegistry, with identical calling code regardless of backend.

Usage:
    cd backend && python -m app.providers.demo
"""

from __future__ import annotations

import asyncio
import sys

from app.providers import _registry, get_provider
from app.providers.errors import ProviderError
from app.providers.types import CompletionRequest


async def main() -> None:
    request = CompletionRequest(
        system_prompt="You are a helpful assistant. Be concise.",
        user_message="What is prompt engineering in one sentence?",
    )

    # Use whichever provider is currently available
    try:
        provider = get_provider()
    except ProviderError as exc:
        print(f"No provider available: {exc}")
        sys.exit(1)

    print(f"Provider : {provider.provider_name}")
    print(f"Model    : {provider.model_name}")
    print(f"Supports vision: {provider.supports('vision')}")
    print()

    response = await provider.complete(request)
    print(f"Response : {response.text}")
    print(f"Model    : {response.model}")
    print(f"Provider : {response.provider}")
    if response.usage:
        print(f"Tokens   : {response.usage.input_tokens} in / {response.usage.output_tokens} out")

    # Show all registered providers
    print("\n--- Registered providers ---")
    for info in _registry.list_providers():
        status = "available" if info["available"] else "unavailable"
        default = " (default)" if info["is_default"] else ""
        print(f"  {info['name']}: {status}{default}")


if __name__ == "__main__":
    asyncio.run(main())

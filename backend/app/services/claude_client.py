"""Client for interacting with the Anthropic Claude API."""

from dataclasses import dataclass, field

from app import config


@dataclass
class ClaudeClient:
    """Wrapper around the Anthropic API for sending prompts to Claude.

    Handles authentication, request formatting, and response parsing.
    """

    api_key: str = field(default_factory=lambda: config.ANTHROPIC_API_KEY)
    model: str = field(default_factory=lambda: config.CLAUDE_MODEL)

    async def send_message(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> str:
        """Send a message to Claude and return the text response.

        Args:
            system_prompt: The system prompt providing context and instructions.
            user_message: The user message to send.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature for response generation.

        Returns:
            The text content of Claude's response.

        Raises:
            RuntimeError: If the API key is not configured or the request fails.
        """
        if not self.api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Please configure it in .env"
            )

        # TODO: Replace with actual Anthropic SDK call
        # import anthropic
        # client = anthropic.AsyncAnthropic(api_key=self.api_key)
        # response = await client.messages.create(
        #     model=self.model,
        #     max_tokens=max_tokens,
        #     temperature=temperature,
        #     system=system_prompt,
        #     messages=[{"role": "user", "content": user_message}],
        # )
        # return response.content[0].text

        raise NotImplementedError(
            "Claude client is a stub. Install anthropic SDK and implement."
        )

    async def send_message_json(
        self,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> dict:
        """Send a message to Claude and parse the response as JSON.

        Uses a lower default temperature for more deterministic JSON output.

        Args:
            system_prompt: The system prompt providing context and instructions.
            user_message: The user message to send.
            max_tokens: Maximum tokens in the response.
            temperature: Sampling temperature for response generation.

        Returns:
            The parsed JSON response as a dictionary.

        Raises:
            ValueError: If the response cannot be parsed as JSON.
        """
        import json

        text = await self.send_message(
            system_prompt, user_message, max_tokens, temperature
        )
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse Claude response as JSON: {e}") from e

    def is_available(self) -> bool:
        """Check if the Claude API key is configured."""
        return bool(self.api_key)

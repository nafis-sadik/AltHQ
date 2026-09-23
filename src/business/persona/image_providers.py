"""Image provider strategy implementations for profile picture generation."""

from business.persona.repository_protocols import IImageProvider


class NullImageProvider(IImageProvider):
    """Placeholder strategy used until a real image provider is plugged in.

    Keeps the generation workflow end-to-end wired (button -> service ->
    provider) so a concrete provider can be added later without touching
    Layer 1 or the persona flow.
    """

    def generate_async(self, agent_id: str, sheet) -> str:
        """Raise NotImplementedError until a real provider is configured."""
        raise NotImplementedError(
            "Profile picture generation is not available in this phase. "
            "Plug in an IImageProvider implementation to enable it."
        )

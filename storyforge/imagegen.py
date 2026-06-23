from typing import Protocol

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

# Smallest valid 1x1 transparent PNG.
_TINY_PNG = (
    PNG_MAGIC
    + bytes.fromhex(
        "0000000d49484452000000010000000108060000001f15c489"
        "0000000a49444154789c6360000000020001e221bc33"
        "0000000049454e44ae426082"
    )
)


class ImageGenerator(Protocol):
    def generate(
        self,
        prompt: str,
        reference_images: list[bytes] | None = None,
        preamble_images: list[bytes] | None = None,
    ) -> bytes:
        """Return PNG bytes for the prompt.

        preamble_images: placed before prompt text (image editing source).
        reference_images: placed after prompt text (style/face references).
        """
        ...


class FakeImageGenerator:
    """Deterministic in-memory generator for tests. Records every call."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def generate(
        self,
        prompt: str,
        reference_images: list[bytes] | None = None,
        preamble_images: list[bytes] | None = None,
    ) -> bytes:
        self.calls.append({
            "prompt": prompt,
            "reference_images": reference_images,
            "preamble_images": preamble_images,
        })
        return _TINY_PNG

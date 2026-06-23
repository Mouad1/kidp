from storyforge.gemini_backend import GeminiBackend


class _FakePart:
    def __init__(self, data):
        self.inline_data = type("I", (), {"data": data})() if data else None


class _FakeResp:
    def __init__(self, data):
        self.candidates = [type("C", (), {"content": type("Ct", (), {"parts": [_FakePart(data)]})()})()]


def test_generate_returns_inline_image_bytes(monkeypatch):
    backend = GeminiBackend.__new__(GeminiBackend)

    class _Models:
        def generate_content(self, **kwargs):
            _Models.captured = kwargs
            return _FakeResp(b"PNGDATA")

    backend._client = type("Client", (), {"models": _Models()})()
    backend._image_model = "gemini-3.1-flash-image"

    out = backend.generate("draw a hero", reference_images=[b"ref"])
    assert out == b"PNGDATA"
    assert _Models.captured["model"] == "gemini-3.1-flash-image"

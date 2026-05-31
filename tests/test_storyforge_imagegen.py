from storyforge.imagegen import FakeImageGenerator, PNG_MAGIC


def test_fake_returns_png_and_records_calls():
    gen = FakeImageGenerator()
    out = gen.generate("a hero", reference_images=[b"ref"])
    assert out.startswith(PNG_MAGIC)
    assert len(gen.calls) == 1
    assert gen.calls[0]["prompt"] == "a hero"
    assert gen.calls[0]["reference_images"] == [b"ref"]


def test_fake_handles_no_reference():
    gen = FakeImageGenerator()
    gen.generate("solo")
    assert gen.calls[0]["reference_images"] is None

from PIL import Image, ImageDraw

from pipeline.clean import remove_black_fills, remove_gray_fills_preserve_edges


def test_gray_cleanup_removes_shading_but_keeps_black_lines():
    img = Image.new("RGB", (10, 1), (255, 255, 255))
    px = img.load()
    px[2, 0] = (0, 0, 0)        # dark line seed
    px[3, 0] = (180, 180, 180)  # gray pixel near line -> should be whitened
    px[8, 0] = (180, 180, 180)  # gray pixel far from edge -> should be whitened

    out = remove_gray_fills_preserve_edges(img, verbose=False)
    assert out.getpixel((2, 0)) == (0, 0, 0)
    assert out.getpixel((3, 0)) == (255, 255, 255)
    assert out.getpixel((8, 0)) == (255, 255, 255)


def test_cleanup_pipeline_removes_large_black_fill_preserves_lines():
    img = Image.new("RGB", (120, 120), (255, 255, 255))
    d = ImageDraw.Draw(img)

    # Large solid fill block should be removed.
    d.rectangle((20, 20, 95, 95), fill=(0, 0, 0))
    # Thin outline should survive.
    d.line((5, 5, 5, 110), fill=(0, 0, 0), width=2)
    # Gray shading away from lines should be removed.
    d.rectangle((100, 10, 115, 20), fill=(170, 170, 170))

    no_fills = remove_black_fills(img, radius=8, verbose=False)
    final = remove_gray_fills_preserve_edges(no_fills, verbose=False)

    # Center of former fill becomes white.
    assert final.getpixel((60, 60)) == (255, 255, 255)
    # Thin line still present as black.
    assert final.getpixel((5, 60)) == (0, 0, 0)
    # Gray shading patch is whitened.
    assert final.getpixel((108, 15)) == (255, 255, 255)

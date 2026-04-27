with open("dashboard/templates/book.html") as f:
    html = f.read()

# Our backend hasn't implemented an image viewer serving file bytes, it just serves them natively via FastAPI StaticFiles.
# However, we can trick `src` to hit the FastAPI local server directly because FastAPI probably mounted `images/`.
# Let's check `app.py` for standard mount paths.

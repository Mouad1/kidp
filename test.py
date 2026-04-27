# The image serving requires `_load_config`.
# For another book we might not need its config as long as we just grab from `images/book_name`.
# In my `book.html` inject, the path to serve image is: `<img src="/images/${book}/${img}">`
# This matches `@app.get("/images/{book_name}/{filename}")`.

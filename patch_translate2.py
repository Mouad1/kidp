with open("dashboard/translate.py") as f:
    text = f.read()

new_text = text.replace("out = response.text.strip()", """
    try:
        out = response.text.strip()
    except ValueError as e:
        if response.candidates:
            # safety blocked?
            out = "{}"
            print("Safety blocked translation")
        else:
            raise e
""")

with open("dashboard/translate.py", "w") as f:
    f.write(new_text)

with open("pipeline/story_gen.py", "r") as f:
    text = f.read()

text = text.replace(
'''    result = parse_story_script(args.script)''',
'''    with open(args.script, "r") as f:
        script_content = f.read()
    result = parse_story_script(script_content)'''
)

with open("pipeline/story_gen.py", "w") as f:
    f.write(text)

with open("dashboard/templates/book.html", "r") as f:
    html = f.read()

# I will systematically replace the character UI with Story UI.
html = html.replace('document.getElementById("cfg-subtitle").value = configData.subtitle;', 
'''document.getElementById("cfg-subtitle").value = configData.subtitle;
document.getElementById("cfg-story-base-prompt").value = configData.story_base_prompt || "";''')

html = html.replace('<!-- Idle -->', '''
      <!-- Idle -->
      <div id="panel-idle" class="hidden">
''')

html = html.replace('class="grid md:grid-cols-[1fr_800px] gap-6 items-start"', 'class="grid md:grid-cols-[300px_1fr] gap-6 items-start"')

# We will need completely custom JS for renderPages, not renderCharacters.

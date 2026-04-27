import re

with open("dashboard/templates/story.html") as f:
    text = f.read()

# Replace showToast with alert, since story.html might not have a toast element.
# Or check if it has a toast element. Let's see if we should just use alert.
text = text.replace('showToast("✅ Traductions générées avec succès");', 'alert("✅ Traductions générées avec succès");')
text = text.replace('showToast("❌ Erreur: " + err.message);', 'alert("❌ Erreur: " + err.message);')

with open("dashboard/templates/story.html", "w") as f:
    f.write(text)

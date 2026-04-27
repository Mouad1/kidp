with open("dashboard/templates/new_book.html", "r") as f:
    text = f.read()

bad_chunk = """    <div class="flex justify-end gap-3">
      <a href="/" class="border border-gray-200 text-sm rounded-lg px-4 py-2 hover:bg-gray-50 transition-colors">
        Annuler
      </a>
    <div id="story-mode" class="bg-white border border-gray-200 rounded-xl p-6 hidden">
      <h2 class="font-semibold text-sm mb-2">Étape 2 — Quick Mode : Script ("Stories")</h2>
      <p class="text-xs text-gray-500 mb-4">
        Collez ici votre script brut. L'IA va créer la "Charte Graphique" globale et diviser l'histoire page par page
        avec des prompts de génération d'images, puis traduire vos textes en FR/AR/EN/ES.
      </p>
      <textarea id="story-script" rows="15" placeholder="Collez le texte brut de l'histoire ici... (Exemple Joudia)" 
                class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-y"></textarea>
    </div>

    <div class="flex justify-end gap-3">
      <a href="/" class="border border-gray-200 text-sm rounded-lg px-4 py-2 hover:bg-gray-50 transition-colors">
        Annuler
      </a>
      <button id="btn-create" onclick="createBook()"
              class="bg-gray-900 text-white text-sm rounded-lg px-6 py-2.5 hover:bg-gray-700 transition-colors flex items-center justify-center min-w-[140px]">
        <span>✅ Create Book</span>
      </button>
    </div>"""

good_chunk = """    <div id="story-mode" class="bg-white border border-gray-200 rounded-xl p-6 hidden relative">
      <div class="flex items-center justify-between mb-2">
        <h2 class="font-semibold text-sm">Étape 2 — Story Script Template</h2>
        <button onclick="loadStoryTemplate()" class="text-xs bg-indigo-50 text-indigo-700 hover:bg-indigo-100 px-3 py-1.5 rounded-lg font-medium transition-colors">
          📝 Charger le Template Standard
        </button>
      </div>
      <p class="text-xs text-gray-500 mb-4 leading-relaxed">
        Suivez la structure du template ci-dessous pour garantir une génération parfaite. 
        L'IA s'occupera d'isoler la <strong>Charte Graphique</strong>, de générer les prompts anglais, et de <strong>traduire le texte de chaque page</strong> en 4 langues (FR, EN, ES, AR).
      </p>
      
      <div class="bg-blue-50 border border-blue-100 rounded-lg p-3 mb-4 text-xs text-blue-800">
        💡 <strong>Astuce (Photos Existantes) :</strong> Pour le moment, l'IA génère les images à partir de texte pur. Si vous voulez "réutiliser" un personnage d'un livre existant, copiez <strong>exactement</strong> sa description physique (vêtements, âge, traits) dans la Charte Graphique ci-dessous !
      </div>

      <textarea id="story-script" rows="20" placeholder="Cliquez sur 'Charger le Template Standard' pour commencer..." 
                class="w-full border border-gray-200 rounded-lg px-4 py-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-y shadow-inner bg-gray-50"></textarea>
    </div>

    <div class="flex justify-end gap-3 mt-8 border-t border-gray-200 pt-6">
      <a href="/" class="border border-gray-200 text-sm font-medium rounded-lg px-5 py-2.5 hover:bg-gray-50 transition-colors">
        Annuler
      </a>
      <button id="btn-create" onclick="createBook()"
              class="bg-indigo-600 text-white text-sm font-bold rounded-lg px-6 py-2.5 hover:bg-indigo-700 transition-colors flex items-center justify-center min-w-[140px] shadow-sm">
        <span>✅ Créer le Livre</span>
      </button>
    </div>"""

text = text.replace(bad_chunk, good_chunk)

js_addition = """    function toggleCategory() {
"""

js_addition_new = """    function loadStoryTemplate() {
      const template = `Partie 1 : La Charte Graphique des Personnages Fixes (Main Prompt)
Style Artistique : [EX: Aquarelle douce, couleurs chaudes, Pixar 3D, etc...]

Personnages Fixes :
- [Nom du Héro] : [Âge], [Description physique très précise, vêtements, couleurs exactes].
- [Nom Secondaire] : [Âge], [Description physique, accessoires constants].

Lieu Général : [Ex: Un village dans les montagnes, une école magique, etc...]

---
Partie 2 : Le Livre de Contes (Pages)
Veillez à garder cette structure par page. L'IA traduira le texte narratif.

Page 1 : [Titre indicatif]
Texte : [Le texte complet de l'histoire en français pour cette page]
Valeur/Morale : [Une phrase d'apprentissage pour l'enfant]
Image Prompt : [Description en anglais de la scène visuelle pour l'IA, ex: A textured watercolor illustration. The hero (fixed character) is doing X in the village...]

Page 2 : [Titre indicatif]
Texte : [Suite de l'histoire...]
Valeur/Morale : [...]
Image Prompt : [...]

Page 3 : [Titre indicatif]
Texte : [...]
Valeur/Morale : [...]
Image Prompt : [...]`;
      document.getElementById('story-script').value = template;
    }

    function toggleCategory() {"""

text = text.replace(js_addition, js_addition_new)

with open("dashboard/templates/new_book.html", "w") as f:
    f.write(text)

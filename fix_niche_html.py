with open("dashboard/templates/niche.html", "r") as f:
    text = f.read()

# Enhance the loading state
text = text.replace(
'''      btn.disabled = true;
      btn.innerHTML = '<span class="animate-pulse">Analyse Gemini en cours (~15s)...</span>';''',
'''      btn.disabled = true;
      btn.innerHTML = '<svg class="animate-spin inline-block -ml-1 mr-2 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg> <span class="animate-pulse">Analyse Gemini en cours (~15s)...</span>';
      
      // Cache results during processing
      resultsDiv.classList.add('hidden');
      suggestsDiv.innerHTML = '';
'''
)

# Better error catching and display
text = text.replace(
'''      } catch (err) {
        alert(err.message);
      } finally {
        btn.disabled = false;
        btn.innerText = 'Analyses Data via Gemini';
      }''',
'''      } catch (err) {
        console.error("Erreur Niche:", err);
        alert("Erreur: " + err.message);
        suggestsDiv.innerHTML = `<div class="p-4 bg-red-50 text-red-700 rounded-lg border border-red-200">Erreur : ${err.message}</div>`;
        resultsDiv.classList.remove('hidden');
      } finally {
        btn.disabled = false;
        btn.innerText = 'Analyser via Gemini';
      }'''
)

# Also fix the res.json() bug in case of HTML 500 Internal Server error
text = text.replace(
'''        if(!res.ok) {
          const err = await res.json();
          throw new Error(err.detail || err.error || 'Server Error');
        }''',
'''        if(!res.ok) {
          let errMsg = 'Server Error';
          try {
            const err = await res.json();
            errMsg = err.detail || err.error || 'Server Error';
          } catch(e) {
            errMsg = "Erreur Serveur (500) - Vérifiez les logs backend";
          }
          throw new Error(errMsg);
        }'''
)

with open("dashboard/templates/niche.html", "w") as f:
    f.write(text)

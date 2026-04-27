import requests

data = requests.get('http://127.0.0.1:8000/api/book/boo3-test/config').json()
data['story_base_prompt'] = "THIS IS A TEST PROMPT"

res = requests.put('http://127.0.0.1:8000/api/book/boo3-test/config', json=data)
print(res.status_code, res.text)

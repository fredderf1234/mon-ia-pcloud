
import json
import os
from flask import Flask, render_template_string, request
from google import genai
import requests

app = Flask(__name__)

# Vos clés récupérées
GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY", "AQ.Ab8RN6J6ouWeVgrruti_v5E1cWHrO14EnGc-j77euRCZiF6clA"
)
PCLOUD_ACCESS_TOKEN = os.environ.get("PCLOUD_ACCESS_TOKEN", "")

# Initialisation de l'IA Gemini
client_ai = genai.Client(api_key=GEMINI_API_KEY)

MEMORY_FILENAME = "memoire_ia.json"
PCLOUD_API_URL = "https://eapi.pcloud.com"  # Serveur pCloud Europe


def load_memory_from_pcloud():
  if not PCLOUD_ACCESS_TOKEN:
    return []

  try:
    url = f"{PCLOUD_API_URL}/listfolder?path=/"
    headers = {"Authorization": f"Bearer {PCLOUD_ACCESS_TOKEN}"}
    resp = requests.get(url, headers=headers).json()

    if resp.get("result") == 0:
      contents = resp["metadata"]["contents"]
      file_item = next(
          (
              item
              for item in contents
              if item.get("name") == MEMORY_FILENAME and not item.get("isfolder")
          ),
          None,
      )

      if file_item:
        file_id = file_item["fileid"]
        dl_url_resp = requests.get(
            f"{PCLOUD_API_URL}/getdlurl?fileid={file_id}", headers=headers
        ).json()
        if dl_url_resp.get("result") == 0:
          download_url = (
              f"https://{dl_url_resp['hosts'][0]}{dl_url_resp['path']}"
          )
          file_data = requests.get(download_url).json()
          return file_data.get("history", [])
  except Exception as e:
    print(f"Erreur de chargement pCloud : {e}")

  return []


def save_memory_to_pcloud(history):
  if not PCLOUD_ACCESS_TOKEN:
    return

  try:
    memory_content = json.dumps({"history": history}, ensure_ascii=False)
    url = (
        f"{PCLOUD_API_URL}/uploadfile?path=/&filename={MEMORY_FILENAME}&nopver=1"
    )
    headers = {"Authorization": f"Bearer {PCLOUD_ACCESS_TOKEN}"}
    files = {
        "file": (
            MEMORY_FILENAME,
            memory_content.encode("utf-8"),
            "application/json",
        )
    }
    requests.post(url, headers=headers, files=files)
  except Exception as e:
    print(f"Erreur de sauvegarde pCloud : {e}")


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Assistant IA H24 - pCloud & Gemini</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 20px; background: #f4f7f6; }
        .container { background: white; padding: 30px; border-radius: 10px; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; }
        textarea { width: 100%; height: 100px; padding: 10px; border-radius: 5px; border: 1px solid #ccc; margin-bottom: 10px; font-size: 14px; }
        button { background: #007BFF; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 16px; }
        button:hover { background: #0056b3; }
        .memory-box { background: #eef2f5; padding: 15px; border-radius: 5px; margin-top: 20px; max-height: 400px; overflow-y: auto; }
        .message { margin-bottom: 15px; border-bottom: 1px solid #ddd; padding-bottom: 10px; }
        .question { font-weight: bold; color: #007BFF; }
        .answer { color: #333; margin-top: 5px; white-space: pre-wrap; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Assistant IA avec Mémoire pCloud</h1>
        <form method="POST">
            <label for="prompt">Posez votre question à Gemini :</label><br>
            <textarea name="prompt" id="prompt" placeholder="Ex: Que penses-tu de mon projet..." required></textarea><br>
            <button type="submit">Envoyer</button>
        </form>

        <div class="memory-box">
            <h3>🧠 Historique en mémoire (pCloud) :</h3>
            {% if history %}
                {% for item in history|reverse %}
                    <div class="message">
                        <div class="question">Q : {{ item.q }}</div>
                        <div class="answer">R : {{ item.a }}</div>
                    </div>
                {% endfor %}
            {% else %}
                <p>Aucune mémoire enregistrée pour le moment.</p>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
  history = load_memory_from_pcloud()

  if request.method == "POST":
    user_prompt = request.form.get("prompt")
    if user_prompt:
      # Intégrer un peu d'historique récent pour le contexte de l'IA
      context_str = "\n".join(
          [f"Q: {h['q']}\nR: {h['a']}" for h in history[-5:]]
      )
      full_prompt = (
          f"Historique récent :\n{context_str}\n\nNouvelle question :"
          f" {user_prompt}"
      )

      try:
        response = client_ai.models.generate_content(
            model="gemini-2.5-flash", contents=full_prompt
        )
        ai_answer = response.text
      except Exception as e:
        ai_answer = f"Erreur Gemini : {e}"

      # Ajout à la mémoire et sauvegarde immédiate sur pCloud
      history.append({"q": user_prompt, "a": ai_answer})
      save_memory_to_pcloud(history)

  return render_template_string(HTML_TEMPLATE, history=history)


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)

import json
import os
import requests
from flask import Flask, render_template_string, request
from google import genai

app = Flask(__name__)

# Vos clés configurées directement
GEMINI_API_KEY = "AQ.Ab8RN6J6ouWeVgrruti_v5E1cWHrO14EnGc-j77euRCZiF6clA"
PCLOUD_TOKEN = "MrbSZEXNhDUAPq6zZf8MBJkZ6Fnf0yTWqbp91VmpJhTp1bPUI1qy"

client = genai.Client(api_key=GEMINI_API_KEY)
PCLOUD_FILE_NAME = "memoire_ia.json"
TARGET_FOLDER_NAME = "hh"  # Votre dossier pCloud cible


def get_folder_id_by_name(token, folder_name):
  """Cherche ou crée automatiquement le dossier 'hh' dans pCloud."""
  try:
    url = f"https://eapi.pcloud.com/listfolder?access_token={token}&folderid=0"
    res = requests.get(url).json()
    if res.get("result") == 0:
      contents = res.get("metadata", {}).get("contents", [])
      for item in contents:
        if (
            item.get("name").lower() == folder_name.lower()
            and item.get("folderid")
        ):
          return item.get("folderid")

      # Si le dossier n'existe pas, on le crée
      create_url = f"https://eapi.pcloud.com/createfolder?access_token={token}&name={folder_name}&folderid=0"
      create_res = requests.get(create_url).json()
      if create_res.get("result") == 0:
        return create_res.get("metadata", {}).get("folderid")
  except Exception as e:
    print("Erreur recherche/création dossier pCloud:", e)
  return 0


def get_pcloud_memory():
  if not PCLOUD_TOKEN:
    return []
  try:
    folder_id = get_folder_id_by_name(PCLOUD_TOKEN, TARGET_FOLDER_NAME)
    url = f"https://eapi.pcloud.com/listfolder?access_token={PCLOUD_TOKEN}&folderid={folder_id}"
    res = requests.get(url).json()
    if res.get("result") == 0:
      contents = res.get("metadata", {}).get("contents", [])
      file_id = None
      for item in contents:
        if item.get("name") == PCLOUD_FILE_NAME:
          file_id = item.get("fileid")
          break

      if file_id:
        download_url = f"https://eapi.pcloud.com/getfilelink?access_token={PCLOUD_TOKEN}&fileid={file_id}"
        dl_res = requests.get(download_url).json()
        if dl_res.get("result") == 0:
          host = dl_res.get("hosts", [""])[0]
          path = dl_res.get("path", "")
          file_content_url = f"https://{host}{path}"
          content_res = requests.get(file_content_url)
          if content_res.status_code == 200:
            return content_res.json()
  except Exception as e:
    print("Erreur lecture pCloud:", e)
  return []


def save_pcloud_memory(history):
  if not PCLOUD_TOKEN:
    return "Erreur : Token pCloud manquant"
  try:
    folder_id = get_folder_id_by_name(PCLOUD_TOKEN, TARGET_FOLDER_NAME)
    tmp_file = "/tmp/memoire_ia.json"
    with open(tmp_file, "w", encoding="utf-8") as f:
      json.dump(history, f, ensure_ascii=False, indent=2)

    url = f"https://eapi.pcloud.com/uploadfile?access_token={PCLOUD_TOKEN}&folderid={folder_id}"
    with open(tmp_file, "rb") as f:
      files = {"file": (PCLOUD_FILE_NAME, f)}
      response = requests.post(url, files=files)
      res_json = response.json()
      if res_json.get("result") == 0:
        return f"Succès : Fichier sauvegardé dans le dossier '{TARGET_FOLDER_NAME}' sur pCloud !"
      else:
        return f"Erreur pCloud API : {res_json}"
  except Exception as e:
    return f"Erreur exception pCloud: {str(e)}"


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Assistant IA avec Mémoire pCloud</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f4f4f9; margin: 0; padding: 20px; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 700px; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h2 { color: #333; text-align: center; }
        textarea { width: 100%; height: 80px; padding: 10px; border: 1px solid #ccc; border-radius: 4px; resize: vertical; box-sizing: border-box; }
        button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-size: 16px; margin-top: 10px; }
        button:hover { background: #0056b3; }
        .status { margin-top: 15px; padding: 10px; background: #e2f0d9; color: #385723; border-radius: 4px; border: 1px solid #c5e0b4; font-weight: bold; }
        .history { margin-top: 20px; background: #f8f9fa; padding: 15px; border-radius: 4px; border: 1px solid #e9ecef; max-height: 400px; overflow-y: auto; }
        .q { color: #0056b3; font-weight: bold; margin-bottom: 5px; }
        .r { color: #28a745; margin-bottom: 15px; white-space: pre-wrap; }
    </style>
</head>
<body>
    <div class="container">
        <h2>🤖 Assistant IA avec Mémoire pCloud</h2>
        <form method="POST">
            <label for="prompt">Posez votre question à Gemini :</label><br><br>
            <textarea name="prompt" id="prompt" placeholder="Ex: Que penses-tu de mon projet..."></textarea><br>
            <button type="submit">Envoyer</button>
        </form>

        {% if pcloud_status %}
            <div class="status">📌 {{ pcloud_status }}</div>
        {% endif %}

        <div class="history">
            <h3>🧠 Historique en mémoire (pCloud) :</h3>
            {% for item in history %}
                <div class="q">Q : {{ item.question }}</div>
                <div class="r">R : {{ item.answer }}</div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
  history = get_pcloud_memory()
  pcloud_status = None

  if request.method == "POST":
    user_prompt = request.form.get("prompt")
    if user_prompt:
      context_str = ""
      for h in history[-5:]:
        context_str += (
            f"Question précédente : {h['question']}\nRéponse précédente"
            f" : {h['answer']}\n"
        )

      full_prompt = (
          f"{context_str}\nNouvelle question de l'utilisateur : {user_prompt}"
      )

      try:
        response = client.models.generate_content(
            model="gemini-3.5-flash-lite", contents=full_prompt
        )
        answer = response.text
      except Exception as e:
        answer = f"Erreur Gemini : {str(e)}"

      history.append({"question": user_prompt, "answer": answer})
      pcloud_status = save_pcloud_memory(history)

  return render_template_string(
      HTML_TEMPLATE, history=reversed(history), pcloud_status=pcloud_status
  )


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)

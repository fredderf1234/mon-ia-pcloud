import json
import os
import calculs_moteur  # Module séparé pour les calculs et graphiques
import requests
from flask import Flask, render_template_string, request
from google import genai

app = Flask(__name__)

# Vos clés configurées directement
GEMINI_API_KEY = "AQ.Ab8RN6JAuXv3_1ENEAKl_SQ5Ysg-QPOo5_kzeJNTzV04er5zcg"
PCLOUD_TOKEN = "MrbSZEXNhDUAPq6zZf8MBJkZ6Fnf0yTWqbp91VmpJhTp1bPUI1qy"

client = genai.Client(api_key=GEMINI_API_KEY)
TARGET_FOLDER_NAME = "hh"  # Dossier racine pCloud


def get_or_create_pcloud_path(token, path_str):
  """Permet de naviguer ou de créer automatiquement des sous-dossiers

  (ex: 'hh/data/fiches') dans pCloud pour que l'IA puisse stocker
  autant de fichiers et sous-dossiers qu'elle le souhaite.
  """
  parts = [p for p in path_str.strip("/").split("/") if p]
  current_folder_id = 0  # 0 = Racine pCloud

  for part in parts:
    try:
      url = f"https://eapi.pcloud.com/listfolder?access_token={token}&folderid={current_folder_id}"
      res = requests.get(url).json()
      found = False

      if res.get("result") == 0:
        contents = res.get("metadata", {}).get("contents", [])
        for item in contents:
          if item.get("name").lower() == part.lower() and item.get("folderid"):
            current_folder_id = item.get("folderid")
            found = True
            break

      # Si le sous-dossier n'existe pas, on le crée
      if not found:
        create_url = f"https://eapi.pcloud.com/createfolder?access_token={token}&name={part}&folderid={current_folder_id}"
        create_res = requests.get(create_url).json()
        if create_res.get("result") == 0:
          current_folder_id = create_res.get("metadata", {}).get("folderid")
        else:
          print(f"Erreur création sous-dossier {part}:", create_res)
          return 0
    except Exception as e:
      print(f"Erreur exception parcours dossier pCloud ({part}):", e)
      return 0

  return current_folder_id


def get_pcloud_file(file_path):
  """Lit un fichier JSON depuis n'importe quel sous-dossier de pCloud (ex: 'hh/memoire_ia.json')."""
  if not PCLOUD_TOKEN:
    return None
  try:
    dir_path = "/".join(file_path.split("/")[:-1])
    file_name = file_path.split("/")[-1]
    folder_id = get_or_create_pcloud_path(PCLOUD_TOKEN, dir_path)

    url = f"https://eapi.pcloud.com/listfolder?access_token={PCLOUD_TOKEN}&folderid={folder_id}"
    res = requests.get(url).json()
    if res.get("result") == 0:
      contents = res.get("metadata", {}).get("contents", [])
      file_id = None
      for item in contents:
        if item.get("name") == file_name:
          file_id = item.get("fileid")
          break

      if file_id:
        download_url = f"https://eapi.pcloud.com/getfilelink?access_token={PCLOUD_TOKEN}&fileid={file_id}"
        dl_res = requests.get(download_url).json()
        if dl_res.get("result") == 0:
          host = dl_res.get("hosts", [""])[0]
          path = dl_res.get("path", "")
          content_res = requests.get(f"https://{host}{path}")
          if content_res.status_code == 200:
            return content_res.json()
  except Exception as e:
    print(f"Erreur lecture pCloud ({file_path}):", e)
  return None


def save_pcloud_file(file_path, data_content):
  """Permet d'enregistrer N'IMPORTE QUEL fichier dans N'IMPORTE QUEL sous-dossier

  de pCloud (ex: 'hh/data/fiches/equipe_a.json'), de manière totalement autonome.
  """
  if not PCLOUD_TOKEN:
    return "Erreur : Token pCloud manquant"
  try:
    dir_path = "/".join(file_path.split("/")[:-1])
    file_name = file_path.split("/")[-1]
    folder_id = get_or_create_pcloud_path(PCLOUD_TOKEN, dir_path)

    tmp_file = f"/tmp/{file_name}"
    with open(tmp_file, "w", encoding="utf-8") as f:
      json.dump(data_content, f, ensure_ascii=False, indent=2)

    url = f"https://eapi.pcloud.com/uploadfile?access_token={PCLOUD_TOKEN}&folderid={folder_id}"
    with open(tmp_file, "rb") as f:
      files = {"file": (file_name, f)}
      response = requests.post(url, files=files)
      res_json = response.json()
      if res_json.get("result") == 0:
        return f"Succès : Fichier '{file_name}' sauvegardé dans '{dir_path}' !"
      else:
        return f"Erreur pCloud API : {res_json}"
  except Exception as e:
    return f"Erreur exception pCloud: {str(e)}"


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Assistant IA - Force Relative V8</title>
    <style>
        body { font-family: Arial, sans-serif; background: #f4f4f9; margin: 0; padding: 20px; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 800px; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h2 { color: #333; text-align: center; }
        textarea { width: 100%; height: 80px; padding: 10px; border: 1px solid #ccc; border-radius: 4px; resize: vertical; box-sizing: border-box; }
        button { background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-size: 16px; margin-top: 10px; }
        button:hover { background: #0056b3; }
        .status { margin-top: 15px; padding: 10px; background: #e2f0d9; color: #385723; border-radius: 4px; border: 1px solid #c5e0b4; font-weight: bold; }
        .graph { margin-top: 20px; text-align: center; }
        .graph img { max-width: 100%; border-radius: 4px; border: 1px solid #ccc; }
        .history { margin-top: 20px; background: #f8f9fa; padding: 15px; border-radius: 4px; border: 1px solid #e9ecef; max-height: 400px; overflow-y: auto; }
        .q { color: #0056b3; font-weight: bold; margin-bottom: 5px; }
        .r { color: #28a745; margin-bottom: 15px; white-space: pre-wrap; }
    </style>
</head>
<body>
    <div class="container">
        <h2>⚽ Assistant IA - Force Relative V8</h2>
        <form method="POST">
            <label for="prompt">Posez votre question ou demandez une analyse :</label><br><br>
            <textarea name="prompt" id="prompt" placeholder="Ex: Analyse le match..."></textarea><br>
            <button type="submit">Envoyer & Calculer</button>
        </form>

        {% if pcloud_status %}
            <div class="status">📌 {{ pcloud_status }}</div>
        {% endif %}

        {% if graphique_url %}
            <div class="graph">
                <h3>📊 Graphique des Modèles & Simulations :</h3>
                <img src="{{ graphique_url }}?t={{ range(1000) | random }}" alt="Graphique Match">
            </div>
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
  # Chargement de la mémoire principale depuis pCloud (dossier hh)
  history = get_pcloud_file(f"{TARGET_FOLDER_NAME}/memoire_ia.json") or []
  pcloud_status = None
  graphique_url = None

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

        # Appel au module séparé pour lancer les calculs et générer le graphique
        graphique_url = calculs_moteur.executer_calculs_et_graphique()

      except Exception as e:
        answer = f"Erreur Gemini : {str(e)}"

      history.append({"question": user_prompt, "answer": answer})
      pcloud_status = save_pcloud_file(
          f"{TARGET_FOLDER_NAME}/memoire_ia.json", history
      )

  return render_template_string(
      HTML_TEMPLATE,
      history=reversed(history),
      pcloud_status=pcloud_status,
      graphique_url=graphique_url,
  )


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000)

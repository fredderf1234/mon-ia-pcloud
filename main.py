import os
from flask import Flask, jsonify
from google import genai
from webdav3.client import Client

app = Flask(__name__)

# 1. Configuration des clients via les variables d'environnement de Render
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PCLOUD_USER = os.getenv("PCLOUD_USER")          # Ton email pCloud
PCLOUD_PASSWORD = os.getenv("PCLOUD_PASSWORD")  # Ton mot de passe (ou mot de passe d'application)

# Initialisation du client Gemini
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# Configuration WebDAV pCloud (Serveur européen : webdav.pcloud.com / US : webdav.us.pcloud.com)
options = {
    'webdav_hostname': "https://webdav.pcloud.com",
    'webdav_login': PCLOUD_USER,
    'webdav_password': PCLOUD_PASSWORD
}
pcloud_client = Client(options)

@app.route("/")
def home():
    return "Service pCloud & Gemini en ligne !"

@app.route("/run-sync", methods=["GET", "POST"])
def process_data_with_gemini():
    # Exemple : Lire un fichier depuis pCloud
    remote_path = "/ai_memory.json"
    local_path = "temp_memory.json"
    
    try:
        if pcloud_client.check(remote_path):
            pcloud_client.download_sync(remote_path=remote_path, local_path=local_path)
            with open(local_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        else:
            file_content = "Aucune mémoire préalable trouvée."
    except Exception as e:
        file_content = fErreur lors de la lecture pCloud : {e}"

    # Interroger l'API Gemini
    prompt = f"Voici le contexte actuel extrait de pCloud :\n{file_content}\n\nGénère une analyse ou une mise à jour."
    
    response = ai_client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    
    return jsonify({
        "status": "success",
        "gemini_response": response.text
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

import os
import json
import uuid
from datetime import datetime, timezone
from io import BytesIO

import requests
from flask import Flask, request, jsonify
from google import genai

app = Flask(__name__)

# Configuration via les variables d'environnement de Render
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PCLOUD_TOKEN = os.environ.get("PCLOUD_TOKEN")
PCLOUD_HOST = os.environ.get("PCLOUD_HOST", "eapi.pcloud.com")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")


@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "message": "Agent Gemini + pCloud opérationnel"
    })


def ask_gemini(question):
    """Envoie la question à Gemini et récupère sa réponse."""
    if not GEMINI_API_KEY:
        raise RuntimeError("La variable GEMINI_API_KEY est absente dans Render.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=question
    )

    answer = response.text

    if not answer:
        raise RuntimeError("Gemini n'a renvoyé aucune réponse.")

    return answer


def save_to_pcloud(question, answer):
    """Enregistre la question et la réponse dans un fichier JSON."""
    if not PCLOUD_TOKEN:
        raise RuntimeError("La variable PCLOUD_TOKEN est absente dans Render.")

    now = datetime.now(timezone.utc)

    record = {
        "id": str(uuid.uuid4()),
        "date_utc": now.isoformat(),
        "question": question,
        "answer": answer,
        "model": GEMINI_MODEL
    }

    filename = f"echange_{now.strftime('%Y%m%d_%H%M%S')}_{record['id'][:8]}.json"

    url = f"https://{PCLOUD_HOST}/uploadfile"

    params = {
        "access_token": PCLOUD_TOKEN,
        "path": "/",
        "filename": filename
    }

    content = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")

    files = {
        "file": (
            filename,
            BytesIO(content),
            "application/json"
        )
    }

    response = requests.post(
        url,
        params=params,
        files=files,
        timeout=30
    )

    response.raise_for_status()
    result = response.json()

    if result.get("result") != 0:
        raise RuntimeError(f"Erreur pCloud : code {result.get('result')}")

    return {
        "filename": filename,
        "date_utc": now.isoformat()
    }


@app.route("/ask", methods=["POST"])
def ask():
    """Reçoit une question, appelle Gemini et archive l'échange."""
    data = request.get_json(silent=True) or {}
    question = data.get("question")

    if not isinstance(question, str) or not question.strip():
        return jsonify({
            "error": 'Envoie une question dans un JSON : {"question": "Ta question"}'
        }), 400

    question = question.strip()

    try:
        # 1. Demander une réponse à Gemini
        answer = ask_gemini(question)

        # 2. Enregistrer la question et la réponse sur pCloud
        archive = save_to_pcloud(question, answer)

        # 3. Retourner le résultat
        return jsonify({
            "success": True,
            "question": question,
            "answer": answer,
            "archive": archive
        })

    except Exception:
        app.logger.exception("Erreur pendant le traitement")

        return jsonify({
            "success": False,
            "error": "Le traitement a échoué. Consulte les journaux de Render."
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

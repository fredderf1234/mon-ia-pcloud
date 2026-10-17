import os
import json
import uuid
from datetime import datetime, timezone
from io import BytesIO

import requests
from flask import Flask, request, jsonify, render_template_string
from google import genai

app = Flask(__name__)

# Configuration via les variables d'environnement de Render
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PCLOUD_TOKEN = os.environ.get("PCLOUD_TOKEN")
PCLOUD_HOST = os.environ.get("PCLOUD_HOST", "eapi.pcloud.com")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")


# Interface HTML / CSS intégrée pour un rendu visuel moderne
CHAT_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mon Agent Gemini + pCloud</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
            margin: 0;
            padding: 0;
            display: flex;
            flex-direction: column;
            height: 100vh;
        }
        header {
            background-color: #1e293b;
            padding: 1rem;
            text-align: center;
            border-bottom: 1px solid #334155;
            font-size: 1.25rem;
            font-weight: 600;
        }
        #chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 1.5rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
            max-width: 800px;
            width: 100%;
            margin: 0 auto;
        }
        .message {
            padding: 1rem;
            border-radius: 0.75rem;
            max-width: 80%;
            line-height: 1.5;
            word-break: break-word;
            white-space: pre-wrap;
        }
        .user-message {
            background-color: #3b82f6;
            color: white;
            align-self: flex-end;
            border-bottom-right-radius: 0.2rem;
        }
        .ai-message {
            background-color: #1e293b;
            color: #e2e8f0;
            align-self: flex-start;
            border-bottom-left-radius: 0.2rem;
            border: 1px solid #334155;
        }
        .loading {
            font-style: italic;
            color: #94a3b8;
        }
        #input-container {
            background-color: #1e293b;
            padding: 1rem;
            border-top: 1px solid #334155;
            display: flex;
            justify-content: center;
        }
        #input-form {
            max-width: 800px;
            width: 100%;
            display: flex;
            gap: 0.75rem;
        }
        input[type="text"] {
            flex: 1;
            padding: 0.75rem 1rem;
            border-radius: 0.5rem;
            border: 1px solid #475569;
            background-color: #0f172a;
            color: white;
            font-size: 1rem;
            outline: none;
        }
        input[type="text"]:focus {
            border-color: #3b82f6;
        }
        button {
            background-color: #3b82f6;
            color: white;
            border: none;
            padding: 0.75rem 1.5rem;
            border-radius: 0.5rem;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        button:hover {
            background-color: #2563eb;
        }
        button:disabled {
            background-color: #475569;
            cursor: not-allowed;
        }
    </style>
</head>
<body>
    <header>💬 Agent Gemini + pCloud</header>
    
    <div id="chat-container">
        <div class="message ai-message">Bonjour ! Je suis ton assistant Gemini connecté à pCloud. Pose-moi une question ci-dessous, notre échange sera automatiquement archivé.</div>
    </div>

    <div id="input-container">
        <form id="input-form" onsubmit="sendMessage(event)">
            <input type="text" id="question-input" placeholder="Écris ta question ici..." autocomplete="off" required>
            <button type="submit" id="send-button">Envoyer</button>
        </form>
    </div>

    <script>
        async function sendMessage(event) {
            event.preventDefault();
            const inputField = document.getElementById("question-input");
            const sendButton = document.getElementById("send-button");
            const chatContainer = document.getElementById("chat-container");
            
            const question = inputField.value.trim();
            if (!question) return;

            // Désactiver le formulaire pendant le traitement
            inputField.value = "";
            inputField.disabled = true;
            sendButton.disabled = true;

            // Ajouter le message de l'utilisateur dans l'interface
            const userMsgDiv = document.createElement("div");
            userMsgDiv.className = "message user-message";
            userMsgDiv.textContent = question;
            chatContainer.appendChild(userMsgDiv);

            // Ajouter un indicateur de chargement
            const loadingDiv = document.createElement("div");
            loadingDiv.className = "message ai-message loading";
            loadingDiv.textContent = "Gemini réfléchit et archive l'échange...";
            chatContainer.appendChild(loadingDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;

            try {
                const response = await fetch("/ask", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ question: question })
                });

                const data = await response.json();
                
                // Supprimer le message de chargement
                chatContainer.removeChild(loadingDiv);

                const aiMsgDiv = document.createElement("div");
                aiMsgDiv.className = "message ai-message";

                if (data.success) {
                    aiMsgDiv.textContent = data.answer;
                } else {
                    aiMsgDiv.textContent = "Erreur : " + (data.error || "Une erreur est survenue.");
                }
                chatContainer.appendChild(aiMsgDiv);

            } catch (error) {
                chatContainer.removeChild(loadingDiv);
                const errorDiv = document.createElement("div");
                errorDiv.className = "message ai-message";
                errorDiv.textContent = "Erreur de connexion avec le serveur Render.";
                chatContainer.appendChild(errorDiv);
            } finally {
                inputField.disabled = false;
                sendButton.disabled = false;
                inputField.focus();
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
        }
    </script>
</body>
</html>
"""


@app.route("/", methods=["GET"])
def home():
    """Affiche l'interface graphique du chat."""
    return render_template_string(CHAT_TEMPLATE), 200, {'Content-Type': 'text/html; charset=utf-8'}


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

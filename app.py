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
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


# Interface HTML / CSS modernisée et recentrée
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
            background-color: #0b0f19;
            color: #f8fafc;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .chat-wrapper {
            width: 100%;
            max-width: 650px;
            height: 85vh;
            background-color: #111827;
            border-radius: 1rem;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3), 0 8px 10px -6px rgba(0, 0, 0, 0.3);
            border: 1px solid #1f2937;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        header {
            background-color: #1f2937;
            padding: 1rem 1.25rem;
            text-align: center;
            border-bottom: 1px solid #374151;
            font-size: 1.1rem;
            font-weight: 600;
            letter-spacing: 0.025em;
        }
        #chat-container {
            flex: 1;
            overflow-y: auto;
            padding: 1.25rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        .message {
            padding: 0.85rem 1rem;
            border-radius: 0.85rem;
            max-width: 80%;
            line-height: 1.5;
            word-break: break-word;
            white-space: pre-wrap;
            font-size: 0.95rem;
        }
        .user-message {
            background-color: #2563eb;
            color: white;
            align-self: flex-end;
            border-bottom-right-radius: 0.25rem;
        }
        .ai-message {
            background-color: #1f2937;
            color: #e5e7eb;
            align-self: flex-start;
            border-bottom-left-radius: 0.25rem;
            border: 1px solid #374151;
        }
        .loading {
            font-style: italic;
            color: #9ca3af;
        }
        #input-container {
            background-color: #1f2937;
            padding: 1rem;
            border-top: 1px solid #374151;
        }
        #input-form {
            display: flex;
            gap: 0.5rem;
        }
        input[type="text"] {
            flex: 1;
            padding: 0.75rem 1rem;
            border-radius: 0.5rem;
            border: 1px solid #4b5563;
            background-color: #0b0f19;
            color: white;
            font-size: 0.95rem;
            outline: none;
            transition: border-color 0.2s;
        }
        input[type="text"]:focus {
            border-color: #3b82f6;
        }
        button {
            background-color: #2563eb;
            color: white;
            border: none;
            padding: 0.75rem 1.25rem;
            border-radius: 0.5rem;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        button:hover {
            background-color: #1d4ed8;
        }
        button:disabled {
            background-color: #4b5563;
            cursor: not-allowed;
        }
    </style>
</head>
<body>
    <div class="chat-wrapper">
        <header>💬 Agent Gemini + pCloud</header>
        
        <div id="chat-container">
            <div class="message ai-message">Bonjour ! Pose-moi une question, notre échange sera archivé sur pCloud.</div>
        </div>

        <div id="input-container">
            <form id="input-form" onsubmit="sendMessage(event)">
                <input type="text" id="question-input" placeholder="Écris ta question..." autocomplete="off" required>
                <button type="submit" id="send-button">Envoyer</button>
            </form>
        </div>
    </div>

    <script>
        async function sendMessage(event) {
            event.preventDefault();
            const inputField = document.getElementById("question-input");
            const sendButton = document.getElementById("send-button");
            const chatContainer = document.getElementById("chat-container");
            
            const question = inputField.value.trim();
            if (!question) return;

            inputField.value = "";
            inputField.disabled = true;
            sendButton.disabled = true;

            const userMsgDiv = document.createElement("div");
            userMsgDiv.className = "message user-message";
            userMsgDiv.textContent = question;
            chatContainer.appendChild(userMsgDiv);

            const loadingDiv = document.createElement("div");
            loadingDiv.className = "message ai-message loading";
            loadingDiv.textContent = "Réflexion et archivage en cours...";
            chatContainer.appendChild(loadingDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;

            try {
                const response = await fetch("/ask", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ question: question })
                });

                const data = await response.json();
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
                errorDiv.textContent = "Erreur de connexion avec le serveur.";
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
    return render_template_string(CHAT_TEMPLATE), 200, {'Content-Type': 'text/html; charset=utf-8'}


def ask_gemini(question):
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

    response = requests.post(url, params=params, files=files, timeout=30)
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
    data = request.get_json(silent=True) or {}
    question = data.get("question")

    if not isinstance(question, str) or not question.strip():
        return jsonify({
            "error": 'Format de question invalide.'
        }), 400

    question = question.strip()

    try:
        answer = ask_gemini(question)
        archive = save_to_pcloud(question, answer)

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
            "error": "Le traitement a échoué. Vérifie que PCLOUD_TOKEN et GEMINI_API_KEY sont bien configurés dans Render."
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

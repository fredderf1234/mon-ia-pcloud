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
PCLOUD_FOLDER = "/hh"


# Nouvelle interface ultra-moderne, élégante, avec bouton Micro
CHAT_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Gemini + pCloud</title>
    <style>
        * {
            box-sizing: border-box;
        }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: radial-gradient(circle at top left, #1e1b4b, #0f172a);
            color: #f8fafc;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
        }
        .chat-container-wrapper {
            width: 100%;
            max-width: 850px;
            height: 90vh;
            background: rgba(30, 41, 59, 0.75);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 1.5rem;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        header {
            background: rgba(15, 23, 42, 0.6);
            padding: 1.25rem 1.75rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .header-title {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }
        .header-title h1 {
            margin: 0;
            font-size: 1.2rem;
            font-weight: 600;
            color: #f1f5f9;
        }
        .badge {
            background-color: rgba(99, 102, 241, 0.2);
            color: #818cf8;
            border: 1px solid rgba(99, 102, 241, 0.3);
            padding: 0.25rem 0.75rem;
            border-radius: 2rem;
            font-size: 0.75rem;
            font-weight: 500;
        }
        #chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 1.75rem;
            display: flex;
            flex-direction: column;
            gap: 1.25rem;
            scroll-behavior: smooth;
        }
        #chat-messages::-webkit-scrollbar {
            width: 6px;
        }
        #chat-messages::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.2);
            border-radius: 3px;
        }
        .message {
            padding: 1rem 1.25rem;
            border-radius: 1.15rem;
            max-width: 78%;
            line-height: 1.6;
            word-break: break-word;
            white-space: pre-wrap;
            font-size: 0.95rem;
            animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .user-message {
            background: linear-gradient(135deg, #4f46e5 0%, #3730a3 100%);
            color: white;
            align-self: flex-end;
            border-bottom-right-radius: 0.3rem;
            box-shadow: 0 4px 15px rgba(79, 70, 229, 0.3);
        }
        .ai-message {
            background: rgba(15, 23, 42, 0.6);
            color: #e2e8f0;
            align-self: flex-start;
            border-bottom-left-radius: 0.3rem;
            border: 1px solid rgba(255, 255, 255, 0.06);
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        }
        .loading {
            color: #94a3b8;
            font-style: italic;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .input-area {
            background: rgba(15, 23, 42, 0.6);
            padding: 1.25rem 1.75rem;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
        }
        #chat-form {
            display: flex;
            gap: 0.75rem;
            align-items: center;
        }
        .input-wrapper {
            flex: 1;
            position: relative;
            display: flex;
            align-items: center;
        }
        input[type="text"] {
            width: 100%;
            padding: 0.85rem 3rem 0.85rem 1.25rem;
            border-radius: 0.85rem;
            border: 1px solid rgba(255, 255, 255, 0.1);
            background: rgba(15, 23, 42, 0.8);
            color: white;
            font-size: 0.95rem;
            outline: none;
            transition: all 0.25s ease;
        }
        input[type="text"]:focus {
            border-color: #6366f1;
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.25);
        }
        .mic-button {
            position: absolute;
            right: 12px;
            background: none;
            border: none;
            color: #94a3b8;
            cursor: pointer;
            padding: 4px;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: color 0.2s;
        }
        .mic-button:hover {
            color: #f8fafc;
        }
        .mic-button.recording {
            color: #ef4444;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.2); }
            100% { transform: scale(1); }
        }
        button[type="submit"] {
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            color: white;
            border: none;
            padding: 0.85rem 1.5rem;
            border-radius: 0.85rem;
            font-weight: 600;
            font-size: 0.95rem;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }
        button[type="submit"]:hover {
            background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
            transform: translateY(-1px);
        }
        button[type="submit"]:disabled {
            background: #475569;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
            opacity: 0.7;
        }
    </style>
</head>
<body>
    <div class="chat-container-wrapper">
        <header>
            <div class="header-title">
                <span>✨</span>
                <h1>Assistant Gemini</h1>
            </div>
            <div class="badge">pCloud : /hh</div>
        </header>

        <div id="chat-messages">
            <div class="message ai-message">Bonjour ! Pose-moi une question par texte ou en utilisant le micro. Tes échanges seront archivés dans le dossier <strong>/hh</strong>.</div>
        </div>

        <div class="input-area">
            <form id="chat-form" onsubmit="sendMessage(event)">
                <div class="input-wrapper">
                    <input type="text" id="user-input" placeholder="Écris ta question ici..." autocomplete="off" required>
                    <button type="button" id="mic-btn" class="mic-button" title="Parler au micro" onclick="toggleSpeechRecognition()">
                        🎤
                    </button>
                </div>
                <button type="submit" id="send-btn">Envoyer</button>
            </form>
        </div>
    </div>

    <script>
        // Gestion de la reconnaissance vocale (Micro)
        let recognition = null;
        let isRecording = false;

        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.lang = 'fr-FR';
            recognition.interimResults = false;
            recognition.maxAlternatives = 1;

            recognition.onresult = (event) => {
                const speechResult = event.results[0][0].transcript;
                document.getElementById('user-input').value = speechResult;
                stopRecording();
            };

            recognition.onerror = () => {
                stopRecording();
            };

            recognition.onend = () => {
                stopRecording();
            };
        }

        function toggleSpeechRecognition() {
            if (!recognition) {
                alert("La reconnaissance vocale n'est pas supportée par ton navigateur.");
                return;
            }

            const micBtn = document.getElementById('mic-btn');
            if (isRecording) {
                recognition.stop();
            } else {
                recognition.start();
                micBtn.classList.add('recording');
                isRecording = true;
            }
        }

        function stopRecording() {
            isRecording = false;
            const micBtn = document.getElementById('mic-btn');
            if (micBtn) {
                micBtn.classList.remove('recording');
            }
        }

        async function sendMessage(event) {
            event.preventDefault();
            const inputField = document.getElementById("user-input");
            const sendBtn = document.getElementById("send-btn");
            const chatMessages = document.getElementById("chat-messages");

            const question = inputField.value.trim();
            if (!question) return;

            inputField.value = "";
            inputField.disabled = true;
            sendBtn.disabled = true;

            // Affichage message utilisateur
            const userDiv = document.createElement("div");
            userDiv.className = "message user-message";
            userDiv.textContent = question;
            chatMessages.appendChild(userDiv);

            // Indicateur de chargement
            const loadingDiv = document.createElement("div");
            loadingDiv.className = "message ai-message loading";
            loadingDiv.textContent = "Gemini réfléchit et sauvegarde dans /hh...";
            chatMessages.appendChild(loadingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            try {
                const response = await fetch("/ask", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ question: question })
                });

                const data = await response.json();
                chatMessages.removeChild(loadingDiv);

                const aiDiv = document.createElement("div");
                aiDiv.className = "message ai-message";

                if (data.success) {
                    aiDiv.textContent = data.answer;
                } else {
                    aiDiv.textContent = "Erreur : " + (data.error || "Une erreur est survenue.");
                }
                chatMessages.appendChild(aiDiv);

            } catch (err) {
                chatMessages.removeChild(loadingDiv);
                const errorDiv = document.createElement("div");
                errorDiv.className = "message ai-message";
                errorDiv.textContent = "Erreur de communication avec le serveur.";
                chatMessages.appendChild(errorDiv);
            } finally {
                inputField.disabled = false;
                sendBtn.disabled = false;
                inputField.focus();
                chatMessages.scrollTop = chatMessages.scrollHeight;
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
        "model": GEMINI_MODEL,
        "folder": PCLOUD_FOLDER
    }

    filename = f"echange_{now.strftime('%Y%m%d_%H%M%S')}_{record['id'][:8]}.json"
    url = f"https://{PCLOUD_HOST}/uploadfile"

    params = {
        "access_token": PCLOUD_TOKEN,
        "path": PCLOUD_FOLDER,
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

    # Si le dossier /hh n'existe pas, pCloud renvoie une erreur (ex: code 2009/2004)
    # On crée le dossier à la volée si nécessaire et on retente l'upload
    if result.get("result") != 0:
        create_url = f"https://{PCLOUD_HOST}/createfolderifnotexists"
        requests.get(create_url, params={"access_token": PCLOUD_TOKEN, "path": PCLOUD_FOLDER}, timeout=10)
        
        # Deuxième tentative d'upload
        response = requests.post(url, params=params, files=files, timeout=30)
        response.raise_for_status()
        result = response.json()
        
        if result.get("result") != 0:
            raise RuntimeError(f"Erreur pCloud : code {result.get('result')}")

    return {
        "filename": filename,
        "path": f"{PCLOUD_FOLDER}/{filename}",
        "date_utc": now.isoformat()
    }


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = data.get("question")

    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Format de question invalide."}), 400

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
            "error": "Le traitement a échoué. Vérifie les configurations de Render."
        }), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

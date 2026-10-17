import os
import json
import uuid
import re
from datetime import datetime, timezone
from io import BytesIO

import requests
from flask import Flask, request, jsonify, render_template_string
from google import genai
from google.genai import types

# Import optionnel de la recherche de secours pour éviter tout plantage si non installée
try:
    from duckduckgo_search import DDGS
    DDG_AVAILABLE = True
except ImportError:
    DDG_AVAILABLE = False

import calcul

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PCLOUD_TOKEN = os.environ.get("PCLOUD_TOKEN")
PCLOUD_HOST = os.environ.get("PCLOUD_HOST", "eapi.pcloud.com")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
PCLOUD_FOLDER = "/hh"

SYSTEM_PROMPT_FOOTBALL = """
Colle ton script / Master System Prompt complet ici entre les trois guillemets.
Par exemple : tes règles d'analyse, ta taxonomie d'entités, tes piliers de pondération,
tes critères statistiques (xG, heatmaps, forme, etc.) et la structure exacte
dans laquelle tu veux que Gemini te réponde.
"""

CHAT_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Gemini Football Analytics</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #070913;
            background-image: 
                radial-gradient(circle at 15% 15%, rgba(99, 102, 241, 0.25) 0px, transparent 50%),
                radial-gradient(circle at 85% 85%, rgba(236, 72, 153, 0.2) 0px, transparent 50%),
                radial-gradient(circle at 50% 50%, rgba(6, 182, 212, 0.2) 0px, transparent 60%);
            background-attachment: fixed;
            color: #f8fafc;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 15px;
        }
        .chat-container-wrapper {
            width: 100%; max-width: 900px; height: 90vh;
            background: rgba(15, 23, 42, 0.75);
            backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 1.75rem;
            box-shadow: 0 25px 60px -15px rgba(0, 0, 0, 0.7), 0 0 40px rgba(99, 102, 241, 0.2);
            display: flex; flex-direction: column; overflow: hidden;
        }
        header {
            background: rgba(15, 23, 42, 0.85); padding: 1.25rem 1.75rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            display: flex; align-items: center; justify-content: space-between;
        }
        .header-title { display: flex; align-items: center; gap: 0.85rem; }
        .logo-icon {
            width: 38px; height: 38px; border-radius: 10px;
            background: linear-gradient(135deg, #6366f1, #ec4899, #06b6d4);
            display: flex; align-items: center; justify-content: center;
            font-size: 1.2rem; box-shadow: 0 0 15px rgba(236, 72, 153, 0.4);
        }
        .header-title h1 {
            margin: 0; font-size: 1.2rem; font-weight: 700;
            background: linear-gradient(135deg, #ffffff, #cbd5e1);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        }
        .header-badges { display: flex; gap: 8px; align-items: center; }
        .badge {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(6, 182, 212, 0.2));
            color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3);
            padding: 0.35rem 0.85rem; border-radius: 2rem;
            font-size: 0.75rem; font-weight: 600; box-shadow: 0 0 10px rgba(6, 182, 212, 0.2);
        }
        /* Badge dynamique pour le statut de l'API */
        .api-badge {
            padding: 0.35rem 0.85rem; border-radius: 2rem;
            font-size: 0.75rem; font-weight: 600; transition: all 0.3s ease;
        }
        .api-badge.gemini { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(52, 211, 153, 0.3); }
        .api-badge.fallback { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(251, 191, 36, 0.3); }

        #chat-messages {
            flex: 1; overflow-y: auto; padding: 1.75rem;
            display: flex; flex-direction: column; gap: 1.25rem; scroll-behavior: smooth;
        }
        #chat-messages::-webkit-scrollbar { width: 6px; }
        #chat-messages::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.2); border-radius: 3px; }
        .message {
            padding: 1rem 1.3rem; border-radius: 1.2rem; max-width: 85%;
            line-height: 1.6; word-break: break-word; font-size: 0.95rem;
            animation: fadeIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .user-message {
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            color: white; align-self: flex-end; border-bottom-right-radius: 0.3rem;
            box-shadow: 0 6px 20px rgba(79, 70, 229, 0.35);
            white-space: pre-wrap;
        }
        .ai-message {
            background: rgba(30, 41, 59, 0.8); color: #f1f5f9; align-self: flex-start;
            border-bottom-left-radius: 0.3rem; border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
        }
        .ai-message img { max-width: 100%; border-radius: 10px; margin-top: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        .loading { color: #a5b4fc; font-style: italic; display: flex; align-items: center; gap: 0.6rem; }
        .voice-panel {
            background: rgba(15, 23, 42, 0.95); border-top: 1px solid rgba(236, 72, 153, 0.4);
            padding: 0.9rem 1.75rem; display: none; align-items: center;
            justify-content: space-between; gap: 1.5rem; animation: fadeIn 0.3s ease;
            box-shadow: 0 -5px 20px rgba(236, 72, 153, 0.15);
        }
        .voice-panel.active { display: flex; }
        .voice-status { display: flex; align-items: center; gap: 0.7rem; color: #f472b6; font-weight: 600; font-size: 0.85rem; }
        .rec-dot {
            width: 10px; height: 10px; background-color: #ef4444; border-radius: 50%;
            box-shadow: 0 0 10px #ef4444; animation: pulse-dot 1s infinite alternate;
        }
        @keyframes pulse-dot {
            from { transform: scale(0.8); opacity: 0.7; }
            to { transform: scale(1.3); opacity: 1; }
        }
        .audio-vumeter { display: flex; align-items: center; gap: 4px; height: 28px; }
        .vu-bar {
            width: 4px; height: 6px; background: linear-gradient(180deg, #ec4899, #8b5cf6, #06b6d4);
            border-radius: 2px; transition: height 0.08s ease;
        }
        .stop-btn {
            background: linear-gradient(135deg, #ef4444, #dc2626); color: white;
            border: none; padding: 0.45rem 1rem; border-radius: 0.75rem;
            font-weight: 600; font-size: 0.8rem; cursor: pointer;
            box-shadow: 0 4px 12px rgba(239, 68, 68, 0.4); transition: all 0.2s;
        }
        .stop-btn:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(239, 68, 68, 0.6); }
        .input-area { background: rgba(15, 23, 42, 0.85); padding: 1.25rem 1.75rem; border-top: 1px solid rgba(255, 255, 255, 0.08); }
        #chat-form { display: flex; gap: 0.75rem; align-items: center; }
        .input-wrapper { flex: 1; position: relative; display: flex; align-items: center; }
        input[type="text"] {
            width: 100%; padding: 0.9rem 3.2rem 0.9rem 1.25rem; border-radius: 1rem;
            border: 1px solid rgba(255, 255, 255, 0.15); background: rgba(30, 41, 59, 0.7);
            color: white; font-size: 0.95rem; outline: none; transition: all 0.25s ease;
        }
        input[type="text"]:focus {
            border-color: #ec4899; box-shadow: 0 0 0 3px rgba(236, 72, 153, 0.25);
            background: rgba(30, 41, 59, 0.9);
        }
        .mic-button {
            position: absolute; right: 10px; background: rgba(236, 72, 153, 0.15);
            border: 1px solid rgba(236, 72, 153, 0.3); color: #f472b6;
            width: 35px; height: 35px; border-radius: 0.75rem; cursor: pointer;
            display: flex; align-items: center; justify-content: center; transition: all 0.2s;
        }
        .mic-button:hover { background: rgba(236, 72, 153, 0.3); color: #fff; transform: scale(1.05); }
        button[type="submit"] {
            background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 50%, #6366f1 100%);
            color: white; border: none; padding: 0.9rem 1.6rem; border-radius: 1rem;
            font-weight: 700; font-size: 0.95rem; cursor: pointer; transition: all 0.2s ease;
            box-shadow: 0 4px 15px rgba(6, 182, 212, 0.35);
        }
        button[type="submit"]:hover { transform: translateY(-1px); box-shadow: 0 6px 20px rgba(6, 182, 212, 0.5); }
        button[type="submit"]:disabled { background: #475569; cursor: not-allowed; transform: none; box-shadow: none; opacity: 0.7; }
    </style>
</head>
<body>
    <div class="chat-container-wrapper">
        <header>
            <div class="header-title">
                <div class="logo-icon">⚽</div>
                <h1>Agent Gemini Football Analytics</h1>
            </div>
            <div class="header-badges">
                <div id="api-status-badge" class="api-badge gemini">⚡ 100% Gemini natif</div>
                <div class="badge">pCloud : /hh</div>
            </div>
        </header>

        <div id="chat-messages">
            <div class="message ai-message">Bonjour ! Prêt pour analyser les matchs et les données. Le statut en haut à droite t'indiquera si l'agent utilise la recherche native ou le relais de secours Python.</div>
        </div>

        <div id="voice-panel" class="voice-panel">
            <div class="voice-status">
                <div class="rec-dot"></div>
                <span>Micro actif (Cliquez sur Stop pour valider)...</span>
            </div>
            <div class="audio-vumeter" id="vu-meter">
                <div class="vu-bar"></div><div class="vu-bar"></div><div class="vu-bar"></div>
                <div class="vu-bar"></div><div class="vu-bar"></div><div class="vu-bar"></div>
                <div class="vu-bar"></div><div class="vu-bar"></div><div class="vu-bar"></div>
                <div class="vu-bar"></div>
            </div>
            <button type="button" class="stop-btn" onclick="stopSpeechRecognitionAndSend()">⏹️ Stop & Envoyer</button>
        </div>

        <div class="input-area">
            <form id="chat-form" onsubmit="sendMessage(event)">
                <div class="input-wrapper">
                    <input type="text" id="user-input" placeholder="Écris ou dicte ta question..." autocomplete="off" required>
                    <button type="button" id="mic-btn" class="mic-button" title="Activer le micro" onclick="startSpeechRecognition()">🎤</button>
                </div>
                <button type="submit" id="send-btn">Envoyer</button>
            </form>
        </div>
    </div>

    <script>
        let recognition = null;
        let audioContext = null;
        let analyser = null;
        let microphoneStream = null;
        let animFrameId = null;
        let finalTranscript = '';

        if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            recognition = new SpeechRecognition();
            recognition.lang = 'fr-FR';
            recognition.interimResults = true;
            recognition.continuous = true;

            recognition.onresult = (event) => {
                let interim = '';
                for (let i = event.resultIndex; i < event.results.length; ++i) {
                    if (event.results[i].isFinal) {
                        finalTranscript += event.results[i][0].transcript + ' ';
                    } else {
                        interim += event.results[i][0].transcript;
                    }
                }
                document.getElementById('user-input').value = (finalTranscript + interim).trim();
            };

            recognition.onend = () => {
                const panel = document.getElementById('voice-panel');
                if (panel.classList.contains('active')) {
                    try { recognition.start(); } catch(err) {}
                }
            };
        }

        async function startSpeechRecognition() {
            if (!recognition) {
                alert("La reconnaissance vocale n'est pas supportée par ton navigateur.");
                return;
            }
            finalTranscript = document.getElementById('user-input').value + ' ';
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                microphoneStream = stream;
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
                analyser = audioContext.createAnalyser();
                analyser.fftSize = 32;
                const source = audioContext.createMediaStreamSource(stream);
                source.connect(analyser);

                document.getElementById('voice-panel').classList.add('active');
                recognition.start();
                animateVuMeter();
            } catch (err) {
                document.getElementById('voice-panel').classList.add('active');
                recognition.start();
            }
        }

        function animateVuMeter() {
            if (!analyser) return;
            const dataArray = new Uint8Array(analyser.frequencyBinCount);
            analyser.getByteFrequencyData(dataArray);
            const bars = document.querySelectorAll('.vu-bar');
            bars.forEach((bar, index) => {
                const val = dataArray[index % dataArray.length] || 0;
                const height = Math.max(6, Math.min(28, (val / 255) * 32));
                bar.style.height = height + 'px';
            });
            animFrameId = requestAnimationFrame(animateVuMeter);
        }

        function stopSpeechRecognition() {
            if (recognition) { try { recognition.stop(); } catch(e) {} }
            if (microphoneStream) { microphoneStream.getTracks().forEach(track => track.stop()); microphoneStream = null; }
            if (audioContext) { try { audioContext.close(); } catch(e) {} audioContext = null; }
            if (animFrameId) { cancelAnimationFrame(animFrameId); }
            document.getElementById('voice-panel').classList.remove('active');
        }

        function stopSpeechRecognitionAndSend() {
            stopSpeechRecognition();
            const inputField = document.getElementById("user-input");
            if (inputField.value.trim()) {
                document.getElementById("chat-form").requestSubmit();
            }
        }

        function updateApiBadge(mode) {
            const badge = document.getElementById('api-status-badge');
            if (mode === 'gemini') {
                badge.className = 'api-badge gemini';
                badge.textContent = '⚡ 100% Gemini natif';
            } else {
                badge.className = 'api-badge fallback';
                badge.textContent = '🔄 Relais Python (Failover)';
            }
        }

        async function sendMessage(event) {
            event.preventDefault();
            stopSpeechRecognition();
            finalTranscript = '';

            const inputField = document.getElementById("user-input");
            const sendBtn = document.getElementById("send-btn");
            const chatMessages = document.getElementById("chat-messages");

            const question = inputField.value.trim();
            if (!question) return;

            inputField.value = "";
            inputField.disabled = true;
            sendBtn.disabled = true;

            const userDiv = document.createElement("div");
            userDiv.className = "message user-message";
            userDiv.textContent = question;
            chatMessages.appendChild(userDiv);

            const loadingDiv = document.createElement("div");
            loadingDiv.className = "message ai-message loading";
            loadingDiv.textContent = "⚽ Analyse et recherche en cours...";
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

                // Mise à jour visuelle du badge d'API selon le mode utilisé par le serveur
                if (data.api_mode) {
                    updateApiBadge(data.api_mode);
                }

                const aiDiv = document.createElement("div");
                aiDiv.className = "message ai-message";

                if (data.success) {
                    aiDiv.innerHTML = data.answer;
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


def agentic_rag_retrieve(question, max_files_to_scan=30):
    if not PCLOUD_TOKEN:
        return ""
    try:
        list_url = f"https://{PCLOUD_HOST}/listfolder"
        res = requests.get(list_url, params={"access_token": PCLOUD_TOKEN, "path": PCLOUD_FOLDER}, timeout=10)
        data = res.json()
        if data.get("result") != 0 or "metadata" not in data or "contents" not in data["metadata"]:
            return ""

        json_files = [f for f in data["metadata"]["contents"] if f.get("name", "").endswith(".json")]
        json_files.sort(key=lambda x: x.get("created", ""), reverse=True)
        
        keywords = [w.lower() for w in re.findall(r'\b\w+\b', question) if len(w) > 3]
        relevant_memories = []
        scanned = 0

        for file_info in json_files:
            if scanned >= max_files_to_scan:
                break
            file_id = file_info.get("fileid")
            if not file_id:
                continue
            scanned += 1
            dl_url = f"https://{PCLOUD_HOST}/getfilelink"
            dl_res = requests.get(dl_url, params={"access_token": PCLOUD_TOKEN, "fileid": file_id}, timeout=8).json()
            if dl_res.get("result") == 0 and "hosts" in dl_res and "path" in dl_res:
                host = dl_res["hosts"][0]
                path = dl_res["path"]
                file_content_res = requests.get(f"https://{host}{path}", timeout=8)
                try:
                    entry = file_content_res.json()
                    q = entry.get("question", "")
                    a = entry.get("answer", "")
                    content_str = f"{q} {a}".lower()
                    score = sum(1 for kw in keywords if kw in content_str)
                    if not keywords or score > 0 or scanned <= 3:
                        relevant_memories.append({
                            "text": f"Question: {q}\nRéponse: {a}",
                            "score": score
                        })
                except Exception:
                    continue

        relevant_memories.sort(key=lambda x: x["score"], reverse=True)
        top_memories = relevant_memories[:5]
        if not top_memories:
            return ""
        return "\n---\n".join([m["text"] for m in top_memories])
    except Exception as e:
        app.logger.warning(f"Erreur Agentic RAG pCloud : {e}")
        return ""


def search_web_python_fallback(query):
    """Fonction de secours Python (DuckDuckGo) si l'API Gemini 429 s'active."""
    if not DDG_AVAILABLE:
        return "Recherche Python indisponible (librairie manquante)."
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                results.append(f"Titre: {r.get('title')}\nExtrait: {r.get('body')}\nLien: {r.get('href')}")
        return "\n\n".join(results)
    except Exception as e:
        return f"Erreur lors de la recherche Python de secours: {e}"


def ask_gemini(question):
    if not GEMINI_API_KEY:
        raise RuntimeError("La variable GEMINI_API_KEY est absente dans Render.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    # 1. Détection de calcul optionnel
    mots_cles_calcul = ["monte-carlo", "simulation", "simuler", "calcul monte-carlo", "bayesien"]
    declenche_calcul = any(mot in question.lower() for mot in mots_cles_calcul)

    calcul_context = ""
    graphique_html = ""
    if declenche_calcul:
        try:
            eq_home = {"nom": "Équipe Domicile", "xg_marques": 1.9, "xg_concedes": 0.8, "victoires_recentes": 4, "matchs_joues": 5}
            eq_away = {"nom": "Équipe Extérieur", "xg_marques": 1.3, "xg_concedes": 1.2}
            stats_calcul, img_b64 = calcul.analyser_match(eq_home, eq_away)
            calcul_context = f"\n\n=== RÉSULTATS DU MODÈLE MATHÉMATIQUE (MONTE-CARLO & BAYÉSIEN) ===\n{json.dumps(stats_calcul, ensure_ascii=False, indent=2)}\n=================================================================="
            graphique_html = f"<br><img src='data:image/png;base64,{img_b64}' alt='Graphique Monte-Carlo'/>"
        except Exception as e:
            app.logger.warning(f"Erreur lors du calcul mathématique: {e}")

    # 2. RAG pCloud
    rag_context = agentic_rag_retrieve(question)
    
    full_system_prompt = SYSTEM_PROMPT_FOOTBALL
    if rag_context:
        full_system_prompt += f"\n\n=== ARCHIVES PERTINENTES pCloud (AGENTIC RAG) ===\n{rag_context}\n================================================="
    if calcul_context:
        full_system_prompt += calcul_context

    api_mode = "gemini"

    # 3. Tentative avec la recherche native Gemini
    try:
        search_tool = types.Tool(google_search=types.GoogleSearch())
        config = types.GenerateContentConfig(
            system_instruction=full_system_prompt,
            tools=[search_tool]
        )
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=question,
            config=config
        )
        if response.text:
            return response.text + graphique_html, "gemini"
    except Exception as e:
        app.logger.warning(f"Recherche native Gemini en erreur (429/Quota) : {e}. Bascule sur le relais Python DuckDuckGo.")

    # 4. En cas d'erreur 429 : Relais Python (DuckDuckGo) + Injection dans Gemini standard
    api_mode = "fallback"
    web_results = search_web_python_fallback(question)
    
    prompt_with_web = full_system_prompt + f"\n\n=== RÉSULTATS RECHERCHE WEB PYTHON (SECOURS) ===\n{web_results}\n==============================================="
    
    config_fallback = types.GenerateContentConfig(
        system_instruction=prompt_with_web
    )
    response_fallback = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=question,
        config=config_fallback
    )

    if not response_fallback.text:
        raise RuntimeError("Gemini n'a renvoyé aucune réponse.")

    return response_fallback.text + graphique_html, "fallback"


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
    params = {"access_token": PCLOUD_TOKEN, "path": PCLOUD_FOLDER, "filename": filename}

    content = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
    files = {"file": (filename, BytesIO(content), "application/json")}

    response = requests.post(url, params=params, files=files, timeout=30)
    response.raise_for_status()
    result = response.json()

    if result.get("result") != 0:
        create_url = f"https://{PCLOUD_HOST}/createfolderifnotexists"
        requests.get(create_url, params={"access_token": PCLOUD_TOKEN, "path": PCLOUD_FOLDER}, timeout=10)
        response = requests.post(url, params=params, files=files, timeout=30)
        response.raise_for_status()

    return {"filename": filename, "path": f"{PCLOUD_FOLDER}/{filename}", "date_utc": now.isoformat()}


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = data.get("question")

    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Format de question invalide."}), 400

    question = question.strip()

    try:
        answer, api_mode = ask_gemini(question)
        archive = save_to_pcloud(question, answer)

        return jsonify({"success": True, "question": question, "answer": answer, "api_mode": api_mode, "archive": archive})
    except Exception:
        app.logger.exception("Erreur pendant le traitement")
        return jsonify({"success": False, "error": "Le traitement a échoué. Vérifie les configurations de Render."}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

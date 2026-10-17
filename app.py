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

# Import de Tavily AI avec fallback optionnel
try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

import calcul

app = Flask(__name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PCLOUD_TOKEN = os.environ.get("PCLOUD_TOKEN")
PCLOUD_HOST = os.environ.get("PCLOUD_HOST", "eapi.pcloud.com")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
PCLOUD_FOLDER = "/hh"

SYSTEM_PROMPT_FOOTBALL = """
Tu es un assistant expert en analyse footballistique, statistiques, météo et données en temps réel.
Pour chaque question, tu disposes des archives de la mémoire (Agentic RAG pCloud) et des résultats de recherche Internet en direct.
Tu DOIS croiser ces sources, répondre avec exactitude, et lister systématiquement les liens ou sources utilisés à la fin de ta réponse sous le titre '📌 Sources utilisées :'.
"""

CHAT_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Dashboard - Football Analytics</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #05070e;
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(99, 102, 241, 0.15) 0px, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(236, 72, 153, 0.15) 0px, transparent 40%);
            background-attachment: fixed;
            color: #f8fafc;
            height: 100vh;
            display: flex; flex-direction: column; padding: 15px; overflow: hidden;
        }

        .top-status-bar {
            width: 100%; max-width: 1400px; margin: 0 auto 12px auto;
            background: rgba(15, 23, 42, 0.85); backdrop-filter: blur(15px);
            border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 1rem;
            padding: 0.75rem 1.25rem; display: flex; align-items: center; justify-content: space-between;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        }
        .status-left { display: flex; align-items: center; gap: 1rem; }
        .agent-title { font-size: 1rem; font-weight: 700; color: #fff; display: flex; align-items: center; gap: 0.5rem; }
        .live-activity {
            font-size: 0.8rem; color: #38bdf8; background: rgba(56, 189, 248, 0.1);
            padding: 0.25rem 0.75rem; border-radius: 1rem; border: 1px solid rgba(56, 189, 248, 0.2);
            display: flex; align-items: center; gap: 6px;
        }
        .pulse-dot { width: 7px; height: 7px; background: #38bdf8; border-radius: 50%; animation: pulse 1.5s infinite; }
        @keyframes pulse { 0% { transform: scale(0.9); opacity: 0.7; } 50% { transform: scale(1.3); opacity: 1; } 100% { transform: scale(0.9); opacity: 0.7; } }

        .dashboard-container {
            width: 100%; max-width: 1400px; flex: 1; margin: 0 auto;
            display: grid; grid-template-columns: 2.5fr 1.2fr; gap: 15px; overflow: hidden; margin-bottom: 10px;
        }

        .panel {
            background: rgba(15, 23, 42, 0.75); backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 1.25rem;
            display: flex; flex-direction: column; overflow: hidden; box-shadow: 0 20px 40px rgba(0,0,0,0.6);
        }
        .panel-header {
            background: rgba(30, 41, 59, 0.5); padding: 0.85rem 1.25rem;
            font-size: 0.85rem; font-weight: 600; color: #cbd5e1;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            display: flex; align-items: center; justify-content: space-between;
        }

        #chat-messages {
            flex: 1; overflow-y: auto; padding: 1.25rem;
            display: flex; flex-direction: column; gap: 1rem; scroll-behavior: smooth;
        }
        #chat-messages::-webkit-scrollbar { width: 5px; }
        #chat-messages::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.2); border-radius: 3px; }
        
        .message {
            padding: 0.9rem 1.1rem; border-radius: 1rem; max-width: 90%;
            line-height: 1.5; word-break: break-word; font-size: 0.9rem; animation: fadeIn 0.3s ease;
        }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
        .user-message {
            background: linear-gradient(135deg, #6366f1, #4f46e5); color: white;
            align-self: flex-end; border-bottom-right-radius: 0.2rem;
            box-shadow: 0 4px 15px rgba(79, 70, 229, 0.3); white-space: pre-wrap;
        }
        .ai-message {
            background: rgba(30, 41, 59, 0.85); color: #f1f5f9; align-self: flex-start;
            border-bottom-left-radius: 0.2rem; border: 1px solid rgba(255, 255, 255, 0.08);
        }
        .ai-message img { max-width: 100%; border-radius: 8px; margin-top: 8px; }
        .loading { color: #a5b4fc; font-style: italic; font-size: 0.85rem; }

        .input-area { background: rgba(15, 23, 42, 0.9); padding: 1rem 1.25rem; border-top: 1px solid rgba(255, 255, 255, 0.08); }
        #chat-form { display: flex; gap: 0.6rem; align-items: center; }
        .input-wrapper { flex: 1; position: relative; display: flex; align-items: center; }
        input[type="text"] {
            width: 100%; padding: 0.8rem 3rem 0.8rem 1rem; border-radius: 0.85rem;
            border: 1px solid rgba(255, 255, 255, 0.15); background: rgba(30, 41, 59, 0.7);
            color: white; font-size: 0.9rem; outline: none; transition: all 0.2s;
        }
        input[type="text"]:focus { border-color: #ec4899; box-shadow: 0 0 0 3px rgba(236, 72, 153, 0.2); }
        .mic-button {
            position: absolute; right: 8px; background: rgba(236, 72, 153, 0.15);
            border: 1px solid rgba(236, 72, 153, 0.3); color: #f472b6;
            width: 32px; height: 32px; border-radius: 0.6rem; cursor: pointer;
            display: flex; align-items: center; justify-content: center;
        }
        button[type="submit"] {
            background: linear-gradient(135deg, #06b6d4, #6366f1); color: white;
            border: none; padding: 0.8rem 1.4rem; border-radius: 0.85rem;
            font-weight: 700; font-size: 0.9rem; cursor: pointer; box-shadow: 0 4px 12px rgba(6, 182, 212, 0.3);
        }
        button[type="submit"]:hover { transform: translateY(-1px); }

        .memory-content {
            flex: 1; overflow-y: auto; padding: 1rem; font-size: 0.8rem; color: #94a3b8;
            display: flex; flex-direction: column; gap: 0.75rem;
        }
        .memory-item {
            background: rgba(30, 41, 59, 0.5); padding: 0.75rem; border-radius: 0.75rem;
            border: 1px solid rgba(255, 255, 255, 0.05); color: #cbd5e1;
        }
        .memory-item strong { color: #38bdf8; display: block; margin-bottom: 3px; font-size: 0.82rem; }

        .voice-panel {
            background: rgba(15, 23, 42, 0.95); border-top: 1px solid rgba(236, 72, 153, 0.4);
            padding: 0.75rem 1.25rem; display: none; align-items: center; justify-content: space-between;
        }
        .voice-panel.active { display: flex; }
        .rec-dot { width: 9px; height: 9px; background: #ef4444; border-radius: 50%; animation: pulse 1s infinite alternate; }
        .stop-btn { background: #ef4444; color: white; border: none; padding: 0.35rem 0.8rem; border-radius: 0.5rem; font-weight: 600; cursor: pointer; }

        @media(max-width: 900px) {
            .dashboard-container { grid-template-columns: 1fr; }
            .panel-memory { display: none; }
        }
    </style>
</head>
<body>

    <div class="top-status-bar">
        <div class="status-left">
            <div class="agent-title">⚽ Agent Dashboard</div>
            <div class="live-activity" id="live-activity-badge">
                <div class="pulse-dot"></div>
                <span id="activity-text">En attente d'une requête...</span>
            </div>
        </div>
        <div style="font-size: 0.75rem; color: #94a3b8;">Moteur Web : <strong>Tavily AI</strong> | pCloud : <strong>/hh</strong></div>
    </div>

    <div class="dashboard-container">
        <div class="panel">
            <div class="panel-header">
                <span>💬 Discussion & Analyse en direct</span>
                <span style="font-size: 0.75rem; color: #34d399;">● Connecté à Gemini</span>
            </div>
            
            <div id="chat-messages">
                <div class="message ai-message">Bonjour ! Pose ta question. Le tableau de bord analysera tes archives pCloud /hh et le web en direct via Tavily AI.</div>
            </div>

            <div id="voice-panel" class="voice-panel">
                <div style="display:flex; align-items:center; gap:8px; color:#f472b6; font-size:0.85rem;">
                    <div class="rec-dot"></div>
                    <span>Micro actif...</span>
                </div>
                <button type="button" class="stop-btn" onclick="stopSpeechRecognitionAndSend()">Stop & Envoyer</button>
            </div>

            <div class="input-area">
                <form id="chat-form" onsubmit="sendMessage(event)">
                    <div class="input-wrapper">
                        <input type="text" id="user-input" placeholder="Écris ou dicte ta consigne..." autocomplete="off" required>
                        <button type="button" id="mic-btn" class="mic-button" title="Micro" onclick="startSpeechRecognition()">🎤</button>
                    </div>
                    <button type="submit" id="send-btn">Envoyer</button>
                </form>
            </div>
        </div>

        <div class="panel panel-memory">
            <div class="panel-header">
                <span>🧠 Mémoire Agentic RAG (pCloud)</span>
                <span style="font-size: 0.75rem; color: #38bdf8;">Context Store</span>
            </div>
            <div class="memory-content" id="memory-sidebar">
                <div class="memory-item">
                    <strong>État du système</strong>
                    Les extraits pertinents de tes fichiers JSON pCloud s'afficheront ici lors de chaque requête.
                </div>
            </div>
        </div>
    </div>

    <script>
        let recognition = null;
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
        }

        function startSpeechRecognition() {
            if (!recognition) { alert("Reconnaissance vocale non supportée."); return; }
            finalTranscript = document.getElementById('user-input').value + ' ';
            document.getElementById('voice-panel').classList.add('active');
            try { recognition.start(); } catch(e) {}
        }

        function stopSpeechRecognition() {
            if (recognition) { try { recognition.stop(); } catch(e) {} }
            document.getElementById('voice-panel').classList.remove('active');
        }

        function stopSpeechRecognitionAndSend() {
            stopSpeechRecognition();
            if (document.getElementById("user-input").value.trim()) {
                document.getElementById("chat-form").requestSubmit();
            }
        }

        function updateActivity(text) {
            document.getElementById('activity-text').textContent = text;
        }

        async function sendMessage(event) {
            event.preventDefault();
            stopSpeechRecognition();
            finalTranscript = '';

            const inputField = document.getElementById("user-input");
            const sendBtn = document.getElementById("send-btn");
            const chatMessages = document.getElementById("chat-messages");
            const memorySidebar = document.getElementById("memory-sidebar");

            const question = inputField.value.trim();
            if (!question) return;

            inputField.value = "";
            inputField.disabled = true;
            sendBtn.disabled = true;

            const userDiv = document.createElement("div");
            userDiv.className = "message user-message";
            userDiv.textContent = question;
            chatMessages.appendChild(userDiv);

            updateActivity("Recherche Tavily AI & pCloud en cours...");
            const loadingDiv = document.createElement("div");
            loadingDiv.className = "message ai-message loading";
            loadingDiv.textContent = "⚙️ Recherche Web Tavily AI + RAG pCloud...";
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
                    aiDiv.innerHTML = data.answer;
                    updateActivity("Réponse générée et archivée sur pCloud.");

                    if (data.rag_used) {
                        memorySidebar.innerHTML = `<div class="memory-item"><strong>Contexte RAG injecté</strong>${data.rag_used.replace(/\\n/g, '<br>')}</div>` + memorySidebar.innerHTML;
                    }
                } else {
                    aiDiv.textContent = "Erreur : " + (data.error || "Une erreur est survenue.");
                    updateActivity("Erreur de traitement.");
                }
                chatMessages.appendChild(aiDiv);

            } catch (err) {
                chatMessages.removeChild(loadingDiv);
                const errorDiv = document.createElement("div");
                errorDiv.className = "message ai-message";
                errorDiv.textContent = "Erreur de communication avec le serveur.";
                updateActivity("Erreur réseau.");
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
        return "", ""
    try:
        list_url = f"https://{PCLOUD_HOST}/listfolder"
        res = requests.get(list_url, params={"access_token": PCLOUD_TOKEN, "path": PCLOUD_FOLDER}, timeout=10)
        data = res.json()
        if data.get("result") != 0 or "metadata" not in data or "contents" not in data["metadata"]:
            return "", ""

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
            return "", ""
        formatted_rag = "\n---\n".join([m["text"] for m in top_memories])
        return formatted_rag, formatted_rag[:300] + "..."
    except Exception as e:
        app.logger.warning(f"Erreur Agentic RAG pCloud : {e}")
        return "", ""


def search_web_tavily(query):
    """Effectue la recherche Web en direct via l'API officielle Tavily AI."""
    if not TAVILY_API_KEY:
        app.logger.warning("Clé TAVILY_API_KEY absente. Fallback vers recherche basique.")
        return search_web_fallback(query)

    try:
        if TAVILY_AVAILABLE:
            tavily = TavilyClient(api_key=TAVILY_API_KEY)
            response = tavily.search(query=query, search_depth="basic", max_results=4)
            results = []
            for item in response.get("results", []):
                title = item.get("title", "Source Web")
                snippet = item.get("content", "")
                url = item.get("url", "")
                results.append(f"Titre: {title}\nExtrait: {snippet}\nLien: {url}")
            if results:
                return "\n\n".join(results)
    except Exception as e:
        app.logger.error(f"Erreur Tavily API : {e}")

    return search_web_fallback(query)


def search_web_fallback(query):
    """Fallback si Tavily n'est pas disponible."""
    try:
        wiki_url = f"https://fr.wikipedia.org/w/api.php?action=query&list=search&srsearch={requests.utils.quote(query)}&format=json"
        res = requests.get(wiki_url, timeout=5).json()
        results = []
        if "query" in res and "search" in res["query"]:
            for item in res["query"]["search"][:3]:
                snippet = re.sub('<[^<]+?>', '', item.get("snippet", ""))
                title = item.get("title", "")
                results.append(f"Titre: {title} (Wikipédia)\nExtrait: {snippet}\nLien: https://fr.wikipedia.org/wiki/{requests.utils.quote(title)}")
        if results:
            return "\n\n".join(results)
    except Exception as e:
        app.logger.warning(f"Erreur Fallback Wikipédia: {e}")
    return "Aucune donnée web extraite."


def ask_gemini(question):
    if not GEMINI_API_KEY:
        raise RuntimeError("La variable GEMINI_API_KEY est absente dans Render.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    # 1. Calcul mathématique optionnel
    mots_cles_calcul = ["monte-carlo", "simulation", "simuler", "bayesien"]
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
            app.logger.warning(f"Erreur calcul: {e}")

    # 2. Récupération pCloud RAG
    rag_context, rag_short = agentic_rag_retrieve(question)

    # 3. Recherche Internet en direct via Tavily AI
    web_results = search_web_tavily(question)

    # 4. Construction du Master Prompt
    full_system_prompt = SYSTEM_PROMPT_FOOTBALL
    
    if rag_context:
        full_system_prompt += f"\n\n=== 1. ARCHIVES DE LA MÉMOIRE (pCloud) ===\n{rag_context}\n=========================================="
    
    if web_results and "Aucune donnée" not in web_results:
        full_system_prompt += f"\n\n=== 2. DONNÉES INTERNET EN TEMPS RÉEL (TAVILY AI) ===\n{web_results}\n==============================================="

    if calcul_context:
        full_system_prompt += calcul_context

    full_system_prompt += "\n\n[INSTRUCTION FINALE] Synthétise ces informations, réponds précisément à la question posée, et cite toutes tes sources (pCloud et liens Web) à la fin."

    config = types.GenerateContentConfig(system_instruction=full_system_prompt)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=question, config=config)

    if not response.text:
        raise RuntimeError("Gemini n'a renvoyé aucune réponse.")

    return response.text + graphique_html, rag_short


def save_to_pcloud(question, answer):
    if not PCLOUD_TOKEN:
        raise RuntimeError("La variable PCLOUD_TOKEN est absente.")

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

    return {"filename": filename}


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = data.get("question")

    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Format de question invalide."}), 400

    question = question.strip()

    try:
        answer, rag_used = ask_gemini(question)
        save_to_pcloud(question, answer)

        return jsonify({"success": True, "question": question, "answer": answer, "rag_used": rag_used})
    except Exception:
        app.logger.exception("Erreur pendant le traitement")
        return jsonify({"success": False, "error": "Le traitement a échoué."}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

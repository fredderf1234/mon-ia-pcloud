import os
import json
import uuid
import re
from datetime import datetime, timezone
from io import BytesIO

import requests
from flask import Flask, request, jsonify, render_template_string

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False

import lea
import calcul
import juge  # Module Juge & purge pCloud

app = Flask(__name__)

PCLOUD_TOKEN = os.environ.get("PCLOUD_TOKEN")
PCLOUD_HOST = os.environ.get("PCLOUD_HOST", "eapi.pcloud.com")
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY")
PCLOUD_FOLDER = "/hh"

CHAT_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Football Analytics - Force Relative V8</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <!-- Inclusion de Marked.js pour un rendu Markdown propre et structuré -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #0b0f19; color: #f1f5f9; width: 100vw; height: 100vh;
            display: flex; justify-content: center; align-items: center; overflow: hidden;
        }
        /* PLEIN ÉCRAN TOTAL */
        .chat-container {
            width: 100vw; height: 100vh; background: #111827;
            border: none; border-radius: 0; display: flex; flex-direction: column; overflow: hidden;
        }
        header {
            background: #1f2937; padding: 1rem 2rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            display: flex; align-items: center; justify-content: space-between; flex-shrink: 0;
        }
        header h1 { font-size: 1.25rem; font-weight: 600; color: #fff; }
        .status-indicators { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .badge-status {
            font-size: 0.75rem; font-weight: 600; padding: 0.3rem 0.8rem; border-radius: 1rem;
            background: rgba(255, 255, 255, 0.05); color: #9ca3af; border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .badge-status.active-gemini { background: rgba(99, 102, 241, 0.2); color: #818cf8; border-color: rgba(99, 102, 241, 0.4); }
        .badge-status.active-web { background: rgba(6, 182, 212, 0.2); color: #22d3ee; border-color: rgba(6, 182, 212, 0.4); }
        .badge-status.active-pcloud { background: rgba(236, 72, 153, 0.2); color: #f472b6; border-color: rgba(236, 72, 153, 0.4); }

        #chat-messages {
            flex: 1; overflow-y: auto; padding: 2rem 12%;
            display: flex; flex-direction: column; gap: 1.5rem;
        }
        .message {
            padding: 1.5rem; border-radius: 1rem; max-width: 90%;
            line-height: 1.7; font-size: 1rem; word-break: break-word;
        }
        .user-message {
            background: #4f46e5; color: white; align-self: flex-end; white-space: pre-wrap;
            box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
        }
        /* STYLE ULTRA PROPRE POUR LÉA */
        .ai-message {
            background: #1f2937; color: #f3f4f6; align-self: flex-start;
            border: 1px solid rgba(255,255,255,0.08); width: 100%; max-width: 100%;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        .ai-message h1, .ai-message h2, .ai-message h3 { color: #818cf8; margin-top: 1rem; margin-bottom: 0.5rem; font-weight: 600; }
        .ai-message p { margin-bottom: 1rem; }
        .ai-message ul, .ai-message ol { margin-left: 1.5rem; margin-bottom: 1rem; }
        .ai-message li { margin-bottom: 0.5rem; }
        .ai-message strong { color: #f472b6; }
        .ai-message img { max-width: 100%; height: auto; border-radius: 8px; margin-top: 15px; border: 1px solid rgba(255,255,255,0.15); display: block; }
        
        .loading { color: #9ca3af; font-style: italic; font-size: 0.95rem; }

        .voice-panel {
            background: #1f2937; border-top: 1px solid rgba(236, 72, 153, 0.3);
            padding: 0.75rem 2rem; display: none; align-items: center; justify-content: space-between; flex-shrink: 0;
        }
        .voice-panel.active { display: flex; }
        .rec-dot { width: 10px; height: 10px; background: #ef4444; border-radius: 50%; animation: pulse 1s infinite alternate; }
        @keyframes pulse { from { opacity: 0.4; } to { opacity: 1; } }
        .stop-btn { background: #ef4444; color: white; border: none; padding: 0.4rem 1rem; border-radius: 0.5rem; font-weight: 600; cursor: pointer; }

        .input-area { background: #1f2937; padding: 1.25rem 2rem; border-top: 1px solid rgba(255, 255, 255, 0.08); flex-shrink: 0; }
        #chat-form { display: flex; gap: 1rem; align-items: center; max-width: 1200px; margin: 0 auto; }
        .input-wrapper { flex: 1; position: relative; display: flex; align-items: center; }
        input[type="text"] {
            width: 100%; padding: 0.9rem 3rem 0.9rem 1.25rem; border-radius: 0.75rem;
            border: 1px solid rgba(255, 255, 255, 0.15); background: #111827; color: white; font-size: 1rem; outline: none;
        }
        input[type="text"]:focus { border-color: #6366f1; box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2); }
        .mic-button {
            position: absolute; right: 12px; background: rgba(236, 72, 153, 0.15);
            border: 1px solid rgba(236, 72, 153, 0.3); color: #f472b6;
            width: 34px; height: 34px; border-radius: 0.5rem; cursor: pointer; display: flex; align-items: center; justify-content: center;
        }
        button[type="submit"] {
            background: #4f46e5; color: white; border: none; padding: 0.9rem 1.75rem;
            border-radius: 0.75rem; font-weight: 600; cursor: pointer; font-size: 1rem;
        }
        button[type="submit"]:hover { background: #4338ca; }
    </style>
</head>
<body>
    <div class="chat-container">
        <header>
            <h1>⚽ Agent Football Analytics (Force Relative V8 - Module Léa)</h1>
            <div class="status-indicators">
                <div id="badge-gemini" class="badge-status">🧠 Léa</div>
                <div id="badge-web" class="badge-status">🌐 Internet</div>
                <div id="badge-pcloud" class="badge-status">📁 pCloud</div>
            </div>
        </header>

        <div id="chat-messages">
            <div class="message ai-message">Bonjour ! Tableau de bord V8 modulaire actif. Léa est prête pour l'analyse taxonomique et multi-modèles.</div>
        </div>

        <div id="voice-panel" class="voice-panel">
            <div style="display:flex; align-items:center; gap:10px; color:#f472b6; font-size:0.9rem;">
                <div class="rec-dot"></div>
                <span>Écoute vocale en cours...</span>
            </div>
            <button type="button" class="stop-btn" onclick="stopSpeechRecognitionAndSend()">Stop & Envoyer</button>
        </div>

        <div class="input-area">
            <form id="chat-form" onsubmit="sendMessage(event)">
                <div class="input-wrapper">
                    <input type="text" id="user-input" placeholder="Écris ou dicte ta consigne d'analyse..." autocomplete="off" required>
                    <button type="button" class="mic-button" title="Activer le micro" onclick="startSpeechRecognition()">🎤</button>
                </div>
                <button type="submit" id="send-btn">Envoyer</button>
            </form>
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

        function setIndicator(id, active) {
            const el = document.getElementById(id);
            if (active) {
                el.classList.add('active-' + id.replace('badge-', ''));
            } else {
                el.classList.remove('active-' + id.replace('badge-', ''));
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
            loadingDiv.textContent = "⚙️ Léa analyse la taxonomie, exécute les 7 modèles et génère le graphique...";
            chatMessages.appendChild(loadingDiv);
            chatMessages.scrollTop = chatMessages.scrollHeight;

            setIndicator('badge-pcloud', true);
            setTimeout(() => { setIndicator('badge-web', true); }, 400);
            setTimeout(() => { setIndicator('badge-gemini', true); }, 800);

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
                    let rawAnswer = data.answer;
                    let imgHtml = "";
                    const imgMatch = rawAnswer.match(/<img[^>]+>/);
                    if (imgMatch) {
                        imgHtml = imgMatch[0];
                        rawAnswer = rawAnswer.replace(imgHtml, "");
                    }
                    aiDiv.innerHTML = marked.parse(rawAnswer) + imgHtml;
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
                setIndicator('badge-pcloud', false);
                setIndicator('badge-web', false);
                setIndicator('badge-gemini', false);

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


def agentic_rag_retrieve(question, max_files_to_scan=15):
    if not PCLOUD_TOKEN:
        return ""
    try:
        list_url = f"https://{PCLOUD_HOST}/listfolder"
        res = requests.get(list_url, params={"access_token": PCLOUD_TOKEN, "path": PCLOUD_FOLDER}, timeout=10)
        data = res.json()
        if data.get("result") != 0 or "metadata" not in data or "contents" not in data["metadata"]:
            return ""

        json_files = [f for f in data["metadata"]["contents"] if f.get("name", "").endswith(".json")]
        json_files = juge.purger_memoires_obsoletes(json_files, max_conserver=max_files_to_scan)
        
        keywords = [w.lower() for w in re.findall(r'\b\w+\b', question) if len(w) > 3]
        relevant_memories = []
        scanned = 0

        for file_info in json_files:
            scanned += 1
            file_id = file_info.get("fileid")
            if not file_id:
                continue
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
                    if not keywords or score > 0 or scanned <= 2:
                        relevant_memories.append({
                            "text": f"Question: {q}\nRéponse: {a}",
                            "score": score
                        })
                except Exception:
                    continue

        relevant_memories.sort(key=lambda x: x["score"], reverse=True)
        top_memories = relevant_memories[:3]
        if not top_memories:
            return ""
        return "\n---\n".join([m["text"] for m in top_memories])
    except Exception as e:
        app.logger.warning(f"Erreur Agentic RAG pCloud : {e}")
        return ""


def search_web_tavily(query):
    if not TAVILY_API_KEY:
        return "Clé Tavily absente."
    try:
        if TAVILY_AVAILABLE:
            tavily = TavilyClient(api_key=TAVILY_API_KEY)
            response = tavily.search(query=query, search_depth="advanced", max_results=4)
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
    return "Aucune donnée web extraite."


def generer_requete_web_intelligente(question):
    try:
        prompt_query = (
            f"Contexte actuel : Dimanche 18 octobre 2026.\n"
            f"Question de l'utilisateur : '{question}'\n\n"
            f"Formule une requête de recherche Web courte, précise et optimisée pour trouver cette information en direct. Réponds uniquement par la requête."
        )
        # Appel léger via Léa
        res_text = lea.executer_analyse_lea(prompt_query)
        if res_text:
            return res_text.strip().replace('"', '')
    except Exception:
        pass
    return question


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = data.get("question")

    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Format de question invalide."}), 400

    question = question.strip()

    try:
        # 1. Recherche Web et RAG
        requete_web_opti = generer_requete_web_intelligente(question)
        web_results = search_web_tavily(requete_web_opti)
        rag_context = agentic_rag_retrieve(question)

        # 2. Vérification si calcul mathématique nécessaire
        mots_cles_calcul = [
            "monte-carlo", "simulation", "simuler", "bayesien", 
            "pronostic", "analyse", "comparaison", "force", 
            "stats", "statistiques", "prédire", "prediction", 
            "chance", "pourcentage", "cote", "match"
        ]
        declenche_calcul = any(mot in question.lower() for mot in mots_cles_calcul)

        calcul_context = ""
        graphique_html = ""
        if declenche_calcul:
            try:
                eq_home = {"nom": "Équipe Domicile", "xg_marques": 1.9, "xg_concedes": 0.8}
                eq_away = {"nom": "Équipe Extérieur", "xg_marques": 1.3, "xg_concedes": 1.2}
                stats_calcul, img_b64 = calcul.analyser_match(eq_home, eq_away)
                calcul_context = f"=== RÉSULTATS DES 7 MODÈLES MATHÉMATIQUES & TAXONOMIE V8 ===\n{json.dumps(stats_calcul, ensure_ascii=False, indent=2)}"
                graphique_html = f"<br><img src='data:image/png;base64,{img_b64}' alt='Graphique Force Relative V8'/>"
            except Exception as e:
                app.logger.warning(f"Erreur calcul: {e}")

        # 3. Appel de Léa (lea.py) pour la génération de l'analyse
        reponse_lea = lea.executer_analyse_lea(
            question=question,
            web_data=web_results,
            rag_data=rag_context,
            calcul_data=calcul_context
        )

        # 4. Filtrage par le Juge
        reponse_finale = juge.verifier_et_filtrer_reponse(reponse_lea)
        reponse_avec_graphique = reponse_finale + graphique_html

        # 5. Sauvegarde sur pCloud
        if PCLOUD_TOKEN:
            try:
                now = datetime.now(timezone.utc)
                record = {
                    "id": str(uuid.uuid4()),
                    "date_utc": now.isoformat(),
                    "question": question,
                    "answer": reponse_avec_graphique,
                    "folder": PCLOUD_FOLDER
                }
                filename = f"echange_{now.strftime('%Y%m%d_%H%M%S')}_{record['id'][:8]}.json"
                url = f"https://{PCLOUD_HOST}/uploadfile"
                params = {"access_token": PCLOUD_TOKEN, "path": PCLOUD_FOLDER, "filename": filename}
                content = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
                files = {"file": (filename, BytesIO(content), "application/json")}
                requests.post(url, params=params, files=files, timeout=30)
            except Exception:
                pass

        return jsonify({"success": "true", "question": question, "answer": reponse_avec_graphique})
    except Exception:
        app.logger.exception("Erreur pendant le traitement")
        return jsonify({"success": "false", "error": "Le traitement a échoué."}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

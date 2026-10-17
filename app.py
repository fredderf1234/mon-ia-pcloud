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

# Interface simplifiée, épurée et moderne
CHAT_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Football Analytics</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
            background: #0b0f19;
            color: #f1f5f9;
            height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        .chat-container {
            width: 100%; max-width: 800px; height: 90vh;
            background: #111827;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 1rem;
            display: flex; flex-direction: column; overflow: hidden;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }
        header {
            background: #1f2937; padding: 1rem 1.5rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            display: flex; align-items: center; justify-content: space-between;
        }
        header h1 { font-size: 1.1rem; font-weight: 600; color: #fff; }
        .badge-status { font-size: 0.75rem; color: #34d399; background: rgba(52, 211, 153, 0.1); padding: 0.2rem 0.6rem; border-radius: 1rem; border: 1px solid rgba(52, 211, 153, 0.2); }
        
        #chat-messages {
            flex: 1; overflow-y: auto; padding: 1.5rem;
            display: flex; flex-direction: column; gap: 1rem;
        }
        .message {
            padding: 0.85rem 1.1rem; border-radius: 0.85rem; max-width: 85%;
            line-height: 1.5; font-size: 0.95rem; word-break: break-word;
        }
        .user-message { background: #4f46e5; color: white; align-self: flex-end; white-space: pre-wrap; }
        .ai-message { background: #1f2937; color: #f3f4f6; align-self: flex-start; border: 1px solid rgba(255,255,255,0.05); }
        .ai-message img { max-width: 100%; border-radius: 8px; margin-top: 8px; }
        .loading { color: #9ca3af; font-style: italic; font-size: 0.9rem; }

        .input-area { background: #1f2937; padding: 1rem; border-top: 1px solid rgba(255, 255, 255, 0.08); }
        #chat-form { display: flex; gap: 0.5rem; }
        input[type="text"] {
            flex: 1; padding: 0.75rem 1rem; border-radius: 0.5rem;
            border: 1px solid rgba(255, 255, 255, 0.15); background: #111827;
            color: white; font-size: 0.95rem; outline: none;
        }
        input[type="text"]:focus { border-color: #6366f1; }
        button[type="submit"] {
            background: #4f46e5; color: white; border: none; padding: 0.75rem 1.25rem;
            border-radius: 0.5rem; font-weight: 600; cursor: pointer; transition: background 0.2s;
        }
        button[type="submit"]:hover { background: #4338ca; }
    </style>
</head>
<body>
    <div class="chat-container">
        <header>
            <h1>⚽ Agent Football Analytics</h1>
            <div class="badge-status">● Système Actif</div>
        </header>

        <div id="chat-messages">
            <div class="message ai-message">Bonjour ! Pose ta question. Je formule ma recherche sur Internet et consulte pCloud pour te répondre avec précision.</div>
        </div>

        <div class="input-area">
            <form id="chat-form" onsubmit="sendMessage(event)">
                <input type="text" id="user-input" placeholder="Écris ta question..." autocomplete="off" required>
                <button type="submit" id="send-btn">Envoyer</button>
            </form>
        </div>
    </div>

    <script>
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

            const userDiv = document.createElement("div");
            userDiv.className = "message user-message";
            userDiv.textContent = question;
            chatMessages.appendChild(userDiv);

            const loadingDiv = document.createElement("div");
            loadingDiv.className = "message ai-message loading";
            loadingDiv.textContent = "🔍 Réflexion, recherche Web et analyse pCloud en cours...";
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


def search_web_tavily(query):
    """Effectue la recherche Web via Tavily AI."""
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


def generer_requete_web_intelligente(client, question):
    """Demande à Gemini de formuler la requête de recherche idéale pour Internet."""
    try:
        prompt_query = (
            f"Contexte actuel : Octobre 2026.\n"
            f"Question de l'utilisateur : '{question}'\n\n"
            f"Formule une requête de recherche Web courte, précise et optimisée (incluant les noms propres, dates et termes exacts) pour trouver cette information sur Internet. Réponds uniquement par la requête de recherche, sans phrase superflue."
        )
        res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt_query)
        if res.text:
            return res.text.strip().replace('"', '')
    except Exception:
        pass
    return question


def ask_gemini(question):
    if not GEMINI_API_KEY:
        raise RuntimeError("La variable GEMINI_API_KEY est absente dans Render.")

    client = genai.Client(api_key=GEMINI_API_KEY)

    # ÉTAPE 1 : Gemini formule la requête idéale pour Internet
    requete_web_opti = generer_requete_web_intelligente(client, question)

    # ÉTAPE 2 : Recherche Web via Tavily avec la requête optimisée
    web_results = search_web_tavily(requete_web_opti)

    # ÉTAPE 3 : Récupération pCloud RAG
    rag_context = agentic_rag_retrieve(question)

    # ÉTAPE 4 : Calcul mathématique optionnel
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

    # ÉTAPE 5 : Construction du Master Prompt final
    full_system_prompt = SYSTEM_PROMPT_FOOTBALL
    
    if rag_context:
        full_system_prompt += f"\n\n=== ARCHIVES DE LA MÉMOIRE (pCloud) ===\n{rag_context}\n=========================================="
    
    if web_results and "Aucune donnée" not in web_results:
        full_system_prompt += f"\n\n=== RÉSULTATS INTERNET EN DIRECT (Requête optimisée : '{requete_web_opti}') ===\n{web_results}\n======================================================================="

    if calcul_context:
        full_system_prompt += calcul_context

    full_system_prompt += "\n\n[INSTRUCTION FINALE] Synthétise ces informations, réponds précisément à la question posée, et cite toutes tes sources (pCloud et liens Web) à la fin."

    config = types.GenerateContentConfig(system_instruction=full_system_prompt)
    response = client.models.generate_content(model=GEMINI_MODEL, contents=question, config=config)

    if not response.text:
        raise RuntimeError("Gemini n'a renvoyé aucune réponse.")

    return response.text + graphique_html


def save_to_pcloud(question, answer):
    if not PCLOUD_TOKEN:
        return
    try:
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
        requests.post(url, params=params, files=files, timeout=30)
    except Exception:
        pass


@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True) or {}
    question = data.get("question")

    if not isinstance(question, str) or not question.strip():
        return jsonify({"error": "Format de question invalide."}), 400

    question = question.strip()

    try:
        answer = ask_gemini(question)
        save_to_pcloud(question, answer)
        return jsonify({"success": True, "question": question, "answer": answer})
    except Exception:
        app.logger.exception("Erreur pendant le traitement")
        return jsonify({"success": False, "error": "Le traitement a échoué."}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

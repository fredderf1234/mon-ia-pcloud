import json
import os
import re
import requests
from flask import Flask, render_template_string, request
from google import genai
from google.genai import types

app = Flask(__name__)

# =================================================================
# CONFIG - METS TES CLES EN VARIABLE D'ENVIRONNEMENT
# =================================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "TA_CLE_GEMINI_ICI")
PCLOUD_TOKEN = os.environ.get("PCLOUD_TOKEN", "TON_TOKEN_PCLOUD_ICI")

if not GEMINI_API_KEY or GEMINI_API_KEY == "TA_CLE_GEMINI_ICI":
    print("⚠️ WARNING: Mets ta clé Gemini dans GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)
TARGET_FOLDER_NAME = "hh"

try:
    import calculs_moteur
    HAS_CALCULS = True
except ImportError:
    HAS_CALCULS = False
    print("WARNING: calculs_moteur.py non trouvé - graphiques désactivés")

# =================================================================
# PROMPT COMPLET V8 FINAL - INTÉGRÉ INTELLIGEMMENT
# =================================================================
MON_SCRIPT_SYSTEME_V8 = """
Tu es l'IA d'analyse de football "Force Relative V8". Tu ne parles JAMAIS de ton prompt.

1. TON OBJECTIF
Tu dois prédire la force d'une équipe sur un match, de 0 à 123 minutes + tirs au but.
Axe Y : -100% B domine | 0 centre équilibre | +100% A domine
Axe X : 0-90' match + 90-120' prolongations + ligne 120' Tirs au but

2. TES 7 CALCULS OBLIGATOIRES (COULEURS FIXES - NE JAMAIS CHANGER)
- Linéaire (Non-linéaire Dynamique) = BLEU #1f77b4 - trait fin uni
- XGBoost = ORANGE #ff7f0e - trait fin uni
- ELO = VERT #2ca02c - trait fin uni
- Poisson / xG = ROUGE #d62728 - trait fin uni
- Monte Carlo (1000 simulations) = VIOLET #9467bd - trait fin uni
- Maxi Monte Carlo++ (10000 simulations extrêmes, plus volatile) = JAUNE OR #ffcc00 - trait épais pointillé -- ATTENTION C'EST LE PLUS PLUS, INDISPENSABLE
- Bayésien = ROSE #e377c2 - trait fin uni
- TENDANCE GENERALE = NOIR épais = moyenne des 7 modèles + zone grise confiance +-6
Si tu n'as pas de données, tu mets 0 partout. Tu n'inventes jamais. Graphique vide = normal.

3. TES DONNÉES TAXONOMIQUES (TU DOIS LES CHERCHER SUR INTERNET VIA GOOGLE SEARCH)
Avant chaque match, tu vas chercher sur internet (RAG) avec l'outil google_search :
- Fiches équipe : âge moyen, taille, force technique, valeur -> hh/data/fiches/
- Fiches relations : association_terrain entre joueurs (0-100), conflit_avec, amitié -> hh/data/relations/
- Fiches conditions : pression_public, météo, pression_médiatique, voyage_fatigue -> hh/data/conditions/
- Fiches événements match : carton rouge, blessure, penalty, VAR, changement tactique
Tu es autonome en écriture RAG. Dès que tu trouves une info via google_search, tu crées automatiquement un fichier JSON. Tu ne demandes jamais la permission.

4. ALERTES TERRAIN ILLIMITÉES (VISIBLES PENDANT MATCH)
Tu n'es pas limité à 3. Types : DIVERGENCE, CONTRE-COURS, FATIGUE, CARTON_ROUGE, BLESSURE, PENALTY, VAR, CHANGEMENT_TACTIQUE, TIRS_AU_BUT
Tu peux en créer de nouveaux. Chaque alerte = {"type": "CARTON_ROUGE", "minute": 55, "desc": "Expulsion - bascule -25", "impact": -25}

5. DÉCLENCHEURS HORS-TERRAIN CACHÉS (DÉTECTÉS J+1 VIA PRESSE - TRÈS IMPORTANT)
- EMBROUILLE_VESTIAIRE : mots "tensions", "clash", "conflit" dans article J+1 via google_search L'Equipe
- EQUIPE_JEUNE : âge moyen <23
- MANQUE_AUTOMATISME / EQUIPE_PAS_ORGANISEE : association moyenne <50
- PRESSION_MEDIATIQUE : "doit absolument gagner", "obligation résultat"
- VOYAGE_FATIGUE, ARBITRE_MAISON
Chacun est une fiche taxonomique individualisée avec sa propre note dans hh/data/conditions/

6. LE COEUR - EMPREINTE + SOUS-EMPREINTES (PAS JUSTE MATHS)
Chaque critère = FICHE TAXO + SOUS-EMPREINTE vectorielle + poids :
- AGE_MOYEN 22.3 ans => sub_vec [0.9,0.1,0.2] mots ["jeune","22 ans","inexpérimentée"] poids 20
- MANQUE_AUTOMATISME 45 => sub_vec [0.7,0.8,0.1] mots ["pas organisée","jamais joué ensemble"] poids 25
- EMBROUILLE_VESTIAIRE -20 => sub_vec [0.3,0.9,0.85] mots ["tensions","conflit"] poids 20
- PRESSION_MEDIATIQUE 85 => sub_vec [0.6,0.2,0.95] mots ["doit gagner","pression"] poids 15
- CARTON_ROUGE => poids 30

A) Mathématique : somme poids. 20+25+15+20=80 >70 => alerte orange "Équipe fragile" Si +30=110 => rouge "Aïe aïe aïe - But imminent B 70% dans 15 min"
B) Empreinte : Tu FUSIONNES les sous-empreintes en UNE empreinte globale : moyenne pondérée des vecteurs. Tu compares (similarité cosinus) à tous tes MODELES_SURPRISE passés dans hh/data/cadres/. Si similarité >0.85 => "Aïe aïe aïe - Empreinte 92% identique au modèle surprise #12 (Brésil 2-0 France jeune) - Risque explosion 78% si carton rouge"

7. POST-MATCH J+1 - CRÉATION DU MODÈLE SURPRISE
Si match surprise (écart >50 entre attendu et réel), tu REGROUPES tous les déclencheurs en un SCHEMA et tu crées hh/data/cadres/MODELE_SURPRISE_XXX.json avec condition : age<23 ET assoc<50 ET pression>80 => Force -30 auto à l'avenir + empreinte RAG ["jeune","inexpérimentée","tensions"]

8. GÉNÉRATION GRAPHIQUE - FORMAT OBLIGATOIRE
Tu finis TOUJOURS par un bloc JSON strict si match détecté :
```json_actions
{
  "fichiers_a_creer": [
    {"chemin": "hh/data/fiches/equipe_france.json", "contenu": {"age_moyen": 22.3, "taille": 180, "valeur": 900, "sub_vec": [0.9,0.1,0.2], "mots": ["jeune"]}},
    {"chemin": "hh/data/relations/assoc_france_45.json", "contenu": {"association": 45, "joueurs": ["Mbappé","Griezmann"], "sub_vec": [0.7,0.8,0.1]}},
    {"chemin": "hh/data/conditions/pression_85.json", "contenu": {"pression_mediatique": 85}},
    {"chemin": "hh/data/cadres/MODELE_SURPRISE_12.json", "contenu": {"schema": ["EQUIPE_JEUNE","MANQUE_AUTOMATISME"], "empreinte": [0.6,0.5,0.8], "condition": "age<23 AND assoc<50"}}
  ],
  "match_detecte": true,
  "duree_match": 123,
  "forces_modeles": {
    "lineaire": [0, 5, 10, ... 123 valeurs],
    "xgboost": [...], "elo": [...], "poisson": [...], "monte_carlo": [...], "maxi_mc": [...], "bayesien": [...]
  },
  "buts_A": [23, 67], "buts_B": [55],
  "alertes": [{"type": "CARTON_ROUGE", "minute": 34, "desc": "Expulsion", "impact": -25}],
  "empreinte_globale": {"vec": [0.6,0.7,0.8], "mots": "jeune pas organisée tensions", "similarite_modele": 0.92, "modele_ref": "MODELE_12"}
}
```
Si discussion simple : {"match_detecte": false, "fichiers_a_creer": [...]}

9. RÈGLE D'OR
Si pas de données, mets 0. N'invente jamais de score. Tout fichier RAG est généré automatiquement dans hh/data/. Tu utilises google_search pour vérifier chaque info.

Réponds en français, analyse courte + graphique si match.
"""

# =================================================================
# FONCTIONS PCLOUD - VERSION FINALE ROBUSTE
# =================================================================

def get_or_create_pcloud_path(token, path_str):
    parts = [p for p in path_str.strip("/").split("/") if p]
    current_folder_id = 0
    for part in parts:
        try:
            url = f"https://eapi.pcloud.com/listfolder?access_token={token}&folderid={current_folder_id}"
            res = requests.get(url, timeout=15).json()
            found = False
            if res.get("result") == 0:
                for item in res.get("metadata", {}).get("contents", []):
                    if item.get("name", "").lower() == part.lower() and item.get("folderid"):
                        current_folder_id = item.get("folderid")
                        found = True
                        break
            if not found:
                create_url = f"https://eapi.pcloud.com/createfolder?access_token={token}&name={part}&folderid={current_folder_id}"
                create_res = requests.get(create_url, timeout=15).json()
                if create_res.get("result") == 0:
                    current_folder_id = create_res.get("metadata", {}).get("folderid", 0)
                else:
                    return None
        except Exception as e:
            print(f"Erreur pCloud path {part}: {e}")
            return None
    return current_folder_id


def get_pcloud_file_content(file_path):
    if not PCLOUD_TOKEN:
        return None
    try:
        dir_path = "/".join(file_path.split("/")[:-1])
        file_name = file_path.split("/")[-1]
        folder_id = get_or_create_pcloud_path(PCLOUD_TOKEN, dir_path)
        if folder_id is None:
            return None
        url = f"https://eapi.pcloud.com/listfolder?access_token={PCLOUD_TOKEN}&folderid={folder_id}"
        res = requests.get(url, timeout=15).json()
        if res.get("result") == 0:
            for item in res.get("metadata", {}).get("contents", []):
                if item.get("name") == file_name:
                    file_id = item.get("fileid")
                    dl_res = requests.get(f"https://eapi.pcloud.com/getfilelink?access_token={PCLOUD_TOKEN}&fileid={file_id}", timeout=15).json()
                    if dl_res.get("result") == 0:
                        host = dl_res.get("hosts", [""])[0]
                        path = dl_res.get("path", "")
                        if host and path:
                            content_res = requests.get(f"https://{host}{path}", timeout=15)
                            if content_res.status_code == 200:
                                try:
                                    return content_res.json()
                                except:
                                    return content_res.text
    except Exception as e:
        print(f"Erreur lecture {file_path}: {e}")
    return None


def save_pcloud_file(file_path, data_content):
    tmp_file = None
    try:
        dir_path = "/".join(file_path.split("/")[:-1])
        file_name = file_path.split("/")[-1]
        folder_id = get_or_create_pcloud_path(PCLOUD_TOKEN, dir_path)
        if folder_id is None:
            return f"Erreur dossier {dir_path}"
        tmp_file = f"/tmp/{file_name}"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data_content, f, ensure_ascii=False, indent=2)
        url = f"https://eapi.pcloud.com/uploadfile?access_token={PCLOUD_TOKEN}&folderid={folder_id}"
        with open(tmp_file, "rb") as f:
            res_json = requests.post(url, files={"file": (file_name, f)}, timeout=30).json()
            return f"OK {file_name}" if res_json.get("result") == 0 else f"Erreur {res_json}"
    except Exception as e:
        return f"Erreur {e}"
    finally:
        try:
            if tmp_file and os.path.exists(tmp_file):
                os.remove(tmp_file)
        except:
            pass


def lister_arborescence_pcloud(token, folder_id=0, chemin_actuel="hh"):
    inventaire = []
    try:
        url = f"https://eapi.pcloud.com/listfolder?access_token={token}&folderid={folder_id}"
        res = requests.get(url, timeout=15).json()
        if res.get("result") == 0:
            for item in res.get("metadata", {}).get("contents", []):
                nom = item.get("name")
                if not nom:
                    continue
                if item.get("isfolder"):
                    sub_id = item.get("folderid")
                    if sub_id:
                        inventaire.extend(lister_arborescence_pcloud(token, sub_id, f"{chemin_actuel}/{nom}"))
                else:
                    inventaire.append(f"{chemin_actuel}/{nom}")
    except Exception:
        pass
    return inventaire


def charger_taxonomie_complete_auto():
    """L'IA lit toute seule le contenu des fichiers pCloud + cadres pour empreinte"""
    if not PCLOUD_TOKEN or PCLOUD_TOKEN == "TON_TOKEN_PCLOUD_ICI":
        return "Aucun token pCloud - mode sans mémoire", [], {}
    
    racine_id = get_or_create_pcloud_path(PCLOUD_TOKEN, TARGET_FOLDER_NAME)
    if racine_id is None:
        return "Erreur racine", [], {}
    
    tous_fichiers = lister_arborescence_pcloud(PCLOUD_TOKEN, racine_id, TARGET_FOLDER_NAME)
    
    taxo_contenu = {}
    cadres_contenu = {}
    
    fichiers_a_lire = [f for f in tous_fichiers if "/cadres/" in f][:10]
    fichiers_a_lire += [f for f in tous_fichiers if "/fiches/" in f][-8:]
    fichiers_a_lire += [f for f in tous_fichiers if "/conditions/" in f][-4:]
    fichiers_a_lire += [f for f in tous_fichiers if "/relations/" in f][-3:]
    
    for chemin in fichiers_a_lire:
        contenu = get_pcloud_file_content(chemin)
        if contenu:
            if "/cadres/" in chemin:
                cadres_contenu[chemin] = contenu
            else:
                taxo_contenu[chemin] = contenu
    
    resume = f"""
TAXONOMIE AUTO-LUE PAR LE CODE (pas besoin de retaper):
- Total fichiers dans pCloud hh/: {len(tous_fichiers)}
- Fiches équipe/relations/conditions lues ({len(taxo_contenu)}): {json.dumps(taxo_contenu, ensure_ascii=False)[:5000]}
- CADRES SURPRISE APPRIS ({len(cadres_contenu)} modèles pour empreinte cosinus):
{json.dumps(cadres_contenu, ensure_ascii=False)[:5000]}

Tu DOIS utiliser ces données réelles + google_search internet pour calculer l'empreinte globale.
"""
    return resume, tous_fichiers, cadres_contenu


def init_taxonomie_pcloud():
    base_folders = [
        "hh/data/fiches",
        "hh/data/conditions",
        "hh/data/relations",
        "hh/data/cadres",
        "hh/data/matchs"
    ]
    for folder in base_folders:
        get_or_create_pcloud_path(PCLOUD_TOKEN, folder)


# =================================================================
# TEMPLATE HTML
# =================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <title>Force Relative V8 FINAL - Auto + Internet</title>
    <style>
        body { font-family: Arial, sans-serif; background: #0a0a0f; color: #eee; margin: 0; padding: 20px; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 950px; background: #1a1a2e; padding: 25px; border-radius: 12px; box-shadow: 0 10px 30px rgba(0,0,0,0.6); }
        h2 { color: #ffcc00; text-align: center; margin-bottom: 5px; }
        .auto-badge { background: linear-gradient(90deg, #00ff88, #00d4ff); color: black; padding: 5px 14px; border-radius: 20px; font-size: 12px; font-weight: bold; display: inline-block; margin: 5px; }
        .net-badge { background: linear-gradient(90deg, #ffcc00, #ff8800); color: black; padding: 5px 14px; border-radius: 20px; font-size: 12px; font-weight: bold; display: inline-block; margin: 5px; }
        textarea { width: 100%; height: 95px; padding: 12px; border: 1px solid #444; background: #0f0f1a; color: white; border-radius: 8px; resize: vertical; box-sizing: border-box; font-size: 14px; }
        button { background: linear-gradient(90deg, #ffcc00, #ff8800); color: black; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-weight: bold; margin-top: 10px; margin-right: 8px; }
        button:hover { transform: scale(1.02); }
        .status { margin-top: 15px; padding: 12px; background: #1e3a2a; color: #7CFC00; border-radius: 8px; border: 1px solid #2d5a27; }
        .empreinte { margin-top: 15px; padding: 14px; background: #3a1a1a; color: #ffcc00; border: 2px solid #ff4444; border-radius: 8px; font-weight: bold; font-size: 15px; }
        .graph { margin-top: 20px; text-align: center; background: white; padding: 18px; border-radius: 10px; }
        .history { margin-top: 20px; background: #0f0f1a; padding: 15px; border-radius: 8px; border: 1px solid #333; max-height: 650px; overflow-y: auto; }
        .q { color: #00d4ff; font-weight: bold; margin-bottom: 4px; } 
        .r { color: #eee; white-space: pre-wrap; line-height: 1.6; margin-bottom: 18px; }
        small { color: #888; }
    </style>
</head>
<body>
    <div class="container">
        <div style="text-align:center;">
            <span class="auto-badge">🤖 AUTO-LECTURE pCloud</span>
            <span class="net-badge">🌐 GOOGLE SEARCH ACTIVÉ</span>
        </div>
        <h2>⚽ Force Relative V8 FINAL</h2>
        <p style="text-align:center; color:#aaa; font-size:13px;">L'IA lit {{ fichiers_count }} fichiers + {{ cadres_count }} cadres + cherche sur internet toute seule</p>
        
        <form method="POST">
            <textarea name="prompt" placeholder="Ex: Analyse PSG-OM ce soir, équipe jeune? tensions? / ou: SCAN AUTO de la taxonomie"></textarea><br>
            <button type="submit">⚽ Analyser Match (avec internet)</button>
            <button type="submit" name="prompt" value="SCAN AUTO COMPLET: Lis toute la taxonomie dans hh/ + cherche sur internet les dernières infos L'Equipe sur tensions vestiaires et dis moi quels cadres surprise sont actifs">🔍 SCAN AUTO + INTERNET</button>
        </form>

        {% if pcloud_status %}<div class="status">📌 {{ pcloud_status }}</div>{% endif %}
        {% if empreinte_msg %}<div class="empreinte">🧬 {{ empreinte_msg }}</div>{% endif %}
        {% if graphique_url %}
            <div class="graph">
                <h3 style="color:black;">📊 7 Modèles + Tendance (0-123') - Maxi Monte Carlo++ or pointillé</h3>
                <img src="{{ graphique_url }}?t={{ range(1000) | random }}" alt="Graphique">
                {% if alertes %}
                <div style="text-align:left; margin-top:12px; color:black; font-size:13px;">
                    <strong>Alertes:</strong><br>
                    {% for a in alertes %}
                        <span style="background:#ff4444; color:white; padding:2px 8px; border-radius:12px; font-size:11px;">{{ a.type }} {{ a.minute }}'</span> {{ a.desc }}<br>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
        {% endif %}
        <div class="history">
            <h3>🧠 Mémoire - {{ fichiers_count }} fichiers / {{ cadres_count }} cadres appris</h3>
            {% for item in history %}<div class="q">Q : {{ item.question }}</div><div class="r">R : {{ item.answer }}</div>{% endfor %}
        </div>
    </div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    history = get_pcloud_file_content(f"{TARGET_FOLDER_NAME}/memoire_ia.json") or []
    if not isinstance(history, list):
        history = []
    
    pcloud_status = empreinte_msg = graphique_url = None
    alertes = []
    fichiers_count = cadres_count = 0

    if request.method == "POST":
        user_prompt = request.form.get("prompt", "").strip()
        if user_prompt:
            init_taxonomie_pcloud()
            taxo_resume, tous_fichiers, cadres_contenu = charger_taxonomie_complete_auto()
            fichiers_count = len(tous_fichiers)
            cadres_count = len([f for f in tous_fichiers if "/cadres/" in f])

            context_str = ""
            for h in history[-5:]:
                if isinstance(h, dict):
                    context_str += f"Q: {h.get('question','')} R: {h.get('answer','')[:200]}\n"

            full_prompt = f"""
{taxo_resume}

Historique: {context_str}

NOUVELLE QUESTION (utilise google_search + taxonomie lue): {user_prompt}
RAPPEL: Chemins hh/data/... + forces 123 points + alertes + empreinte avec similarité >0.85 + google_search obligatoire pour vérifier.
"""

            try:
                # ICI C'EST LA CLÉ: google_search activé pour lire internet
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=MON_SCRIPT_SYSTEME_V8,
                        temperature=0.2,
                        tools=[types.Tool(google_search=types.GoogleSearch())]
                    ),
                )
                raw_answer = response.text or ""
                answer = raw_answer

                match_json = re.search(r"```json_actions\s*(\{.*\})\s*```", raw_answer, re.DOTALL)
                if not match_json:
                    match_json = re.search(r"```json_actions\s*({.*?})\s*```", raw_answer, re.DOTALL)

                if match_json:
                    try:
                        actions_data = json.loads(match_json.group(1))
                        answer = re.sub(r"```json_actions\s*(\{.*\})\s*```", "", raw_answer, flags=re.DOTALL).strip()
                        if not answer:
                            answer = re.sub(r"```json_actions\s*({.*?})\s*```", "", raw_answer, flags=re.DOTALL).strip()

                        for f in actions_data.get("fichiers_a_creer", []):
                            chemin = f.get("chemin", "")
                            contenu = f.get("contenu")
                            if chemin and not chemin.startswith("hh/"):
                                if chemin.startswith("data/"):
                                    chemin = f"hh/{chemin}"
                                elif not chemin.startswith("/"):
                                    chemin = f"hh/data/fiches/{os.path.basename(chemin)}"
                            if chemin and contenu:
                                save_pcloud_file(chemin, contenu)
                        
                        pcloud_status = f"✅ Auto-lecture {fichiers_count} fichiers + Internet + {len(actions_data.get('fichiers_a_creer', []))} nouveaux"

                        empreinte = actions_data.get("empreinte_globale")
                        if empreinte and empreinte.get("similarite_modele", 0) > 0.85:
                            empreinte_msg = f"EMPREINTE {int(empreinte.get('similarite_modele',0)*100)}% IDENTIQUE {empreinte.get('modele_ref','')} - {empreinte.get('mots','')} - CADRE ACTIF"

                        if actions_data.get("match_detecte") is True and HAS_CALCULS:
                            forces = actions_data.get("forces_modeles")
                            duree = actions_data.get("duree_match", 123)
                            alertes = actions_data.get("alertes", [])
                            try:
                                graphique_url = calculs_moteur.executer_calculs_et_graphique(forces, duree, actions_data.get("buts_A",[]), actions_data.get("buts_B",[]), alertes)
                            except TypeError:
                                graphique_url = calculs_moteur.executer_calculs_et_graphique(forces, duree)
                            save_pcloud_file(f"hh/data/matchs/match_du_jour.json", actions_data)

                    except Exception as e:
                        print(f"Erreur parsing V8: {e}")
                        import traceback
                        traceback.print_exc()

            except Exception as e:
                answer = f"Erreur Gemini V8: {str(e)}"

            if 'answer' in locals() and answer:
                history.append({"question": user_prompt, "answer": answer})
                save_pcloud_file(f"{TARGET_FOLDER_NAME}/memoire_ia.json", history)

    if request.method == "GET" and PCLOUD_TOKEN and PCLOUD_TOKEN != "TON_TOKEN_PCLOUD_ICI":
        try:
            racine_id = get_or_create_pcloud_path(PCLOUD_TOKEN, TARGET_FOLDER_NAME)
            if racine_id is not None:
                tous = lister_arborescence_pcloud(PCLOUD_TOKEN, racine_id, TARGET_FOLDER_NAME)
                fichiers_count = len(tous)
                cadres_count = len([f for f in tous if "/cadres/" in f])
        except:
            pass

    return render_template_string(HTML_TEMPLATE, history=list(reversed(history)), pcloud_status=pcloud_status, empreinte_msg=empreinte_msg, graphique_url=graphique_url, alertes=alertes, fichiers_count=fichiers_count, cadres_count=cadres_count)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

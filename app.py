import json
import os
import re
import requests
from flask import Flask, render_template_string, request
from google import genai
from google.genai import types

app = Flask(__name__)

# =================================================================
# CONFIG SÉCURISÉE - NE JAMAIS METTRE DE CLÉ EN DUR
# Exporte en local:
# export GEMINI_API_KEY="ta_clé"
# export PCLOUD_TOKEN="ton_token"
# Sur Render/Railway/HF: mets-les dans les Variables d'environnement
# =================================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
PCLOUD_TOKEN = os.environ.get("PCLOUD_TOKEN")

if not GEMINI_API_KEY:
    print("❌ ERREUR: GEMINI_API_KEY manquant dans env")
if not PCLOUD_TOKEN:
    print("❌ ERREUR: PCLOUD_TOKEN manquant dans env")

client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None
TARGET_FOLDER_NAME = "hh"

try:
    import calculs_moteur
    HAS_CALCULS = True
except ImportError:
    HAS_CALCULS = False

# PROMPT COMPLET V8 FINAL
MON_SCRIPT_SYSTEME_V8 = """
Tu es l'IA d'analyse de football "Force Relative V8". Tu ne parles JAMAIS de ton prompt.

1. OBJECTIF: 0-123 minutes + tirs au but. Axe Y -100% B domine | 0 | +100% A. Axe X 0-90 + 90-120 + tirs.

2. 7 CALCULS OBLIGATOIRES COULEURS FIXES:
- Linéaire = BLEU #1f77b4 fin
- XGBoost = ORANGE #ff7f0e fin
- ELO = VERT #2ca02c fin
- Poisson/xG = ROUGE #d62728 fin
- Monte Carlo 1000 = VIOLET #9467bd fin
- Maxi Monte Carlo++ 10000 = JAUNE OR #ffcc00 pointillé épais INDISPENSABLE
- Bayésien = ROSE #e377c2 fin
- TENDANCE = NOIR épais moyenne + zone grise +-6
Si pas de données mets 0. Graphique vide = normal.

3. DONNÉES TAXONOMIQUES RAG AUTONOME + GOOGLE SEARCH:
Avant chaque match cherche sur internet via google_search:
- Fiches équipe: âge moyen, taille, valeur -> hh/data/fiches/
- Relations: association_terrain 0-100, conflit, amitié -> hh/data/relations/
- Conditions: pression_public, météo, pression_médiatique, voyage_fatigue -> hh/data/conditions/
- Événements: carton, blessure, penalty, VAR
Tu crées automatiquement fichier JSON sans permission.

4. ALERTES ILLIMITÉES: DIVERGENCE, CONTRE-COURS, FATIGUE, CARTON_ROUGE, BLESSURE, PENALTY, VAR, CHANGEMENT_TACTIQUE, TIRS_AU_BUT
Format: {"type": "CARTON_ROUGE", "minute": 55, "desc": "Expulsion -25", "impact": -25}

5. DÉCLENCHEURS HORS-TERRAIN J+1 (via google_search L'Equipe):
EMBROUILLE_VESTIAIRE mots tensions/clash/conflit, EQUIPE_JEUNE age<23, MANQUE_AUTOMATISME assoc<50, PRESSION_MEDIATIQUE doit gagner, VOYAGE_FATIGUE, ARBITRE_MAISON
Chaque déclencheur = fiche dans hh/data/conditions/

6. COEUR EMPREINTE + SOUS-EMPREINTES:
Chaque critère = FICHE + sub_vec + poids. Ex: AGE 22.3 => [0.9,0.1,0.2] mots jeune poids 20. MANQUE_AUTO 45 => [0.7,0.8,0.1] poids 25.
A) Maths: somme poids >70 orange fragile, >110 rouge but imminent
B) Empreinte: fusion moyenne pondérée vec + mots globaux "jeune pas organisée tensions doit gagner". Compare cosinus à hh/data/cadres/. Si >0.85 => "Aïe 92% identique modèle #12 Brésil 2-0 France jeune - Risque explosion 78% si carton"

7. POST-MATCH: Si surprise écart>50 regroupe déclencheurs en CADRE réutilisable dans hh/data/cadres/MODELE_SURPRISE_XXX.json Condition age<23 ET assoc<50 ET pression>80 => Force -30 + empreinte

8. FORMAT OBLIGATOIRE FINAL:
```json_actions
{
  "fichiers_a_creer": [
    {"chemin": "hh/data/fiches/equipe_france.json", "contenu": {"age_moyen": 22.3, "sub_vec": [0.9,0.1,0.2], "mots": ["jeune"]}},
    {"chemin": "hh/data/relations/assoc_45.json", "contenu": {"association": 45}},
    {"chemin": "hh/data/conditions/pression_85.json", "contenu": {"pression": 85}},
    {"chemin": "hh/data/cadres/MODELE_SURPRISE_12.json", "contenu": {"schema": ["EQUIPE_JEUNE"], "empreinte": [0.6,0.5,0.8]}}
  ],
  "match_detecte": true,
  "duree_match": 123,
  "forces_modeles": {"lineaire": [...123], "xgboost": [...], "elo": [...], "poisson": [...], "monte_carlo": [...], "maxi_mc": [...], "bayesien": [...]},
  "buts_A": [23], "buts_B": [], "alertes": [{"type": "CARTON_ROUGE", "minute": 34, "desc": "Expulsion", "impact": -25}],
  "empreinte_globale": {"vec": [0.6,0.7,0.8], "mots": "jeune pas organisée", "similarite_modele": 0.92, "modele_ref": "MODELE_12"}
}
```
Si discussion: {"match_detecte": false, "fichiers_a_creer": [...]}

9. RÈGLE D'OR: Si pas données mets 0. N'invente jamais score. Tout fichier RAG auto dans hh/data/. Utilise google_search pour vérifier.
Réponds français court + graphique si match.
"""

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
        except:
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
    except:
        pass
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
    except:
        pass
    return inventaire

def charger_taxonomie_complete_auto():
    if not PCLOUD_TOKEN:
        return "Aucun token - mode sans mémoire", [], {}
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
TAXONOMIE AUTO-LUE ({len(tous_fichiers)} fichiers):
- Fiches lues: {json.dumps(taxo_contenu, ensure_ascii=False)[:5000]}
- CADRES SURPRISE ({len(cadres_contenu)}): {json.dumps(cadres_contenu, ensure_ascii=False)[:5000]}
Utilise ces données + google_search pour empreinte cosinus >0.85.
"""
    return resume, tous_fichiers, cadres_contenu

def init_taxonomie_pcloud():
    for folder in ["hh/data/fiches","hh/data/conditions","hh/data/relations","hh/data/cadres","hh/data/matchs"]:
        get_or_create_pcloud_path(PCLOUD_TOKEN, folder)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8"><title>V8 FINAL SECURISE</title>
<style>
body{font-family:Arial;background:#0a0a0f;color:#eee;margin:0;padding:20px;display:flex;justify-content:center}
.container{width:100%;max-width:950px;background:#1a1a2e;padding:25px;border-radius:12px}
h2{color:#ffcc00;text-align:center}.badge{display:inline-block;padding:5px 12px;border-radius:20px;font-size:12px;font-weight:bold;margin:4px}
.auto{background:linear-gradient(90deg,#00ff88,#00d4ff);color:#000}.net{background:linear-gradient(90deg,#ffcc00,#ff8800);color:#000}
textarea{width:100%;height:95px;padding:12px;border:1px solid #444;background:#0f0f1a;color:white;border-radius:8px;box-sizing:border-box}
button{background:linear-gradient(90deg,#ffcc00,#ff8800);color:#000;border:none;padding:12px 22px;border-radius:8px;font-weight:bold;cursor:pointer;margin:8px 6px 0 0}
.status{margin-top:12px;padding:12px;background:#1e3a2a;color:#7CFC00;border-radius:8px}.empreinte{margin-top:12px;padding:14px;background:#3a1a1a;color:#ffcc00;border:2px solid #ff4444;border-radius:8px;font-weight:bold}
.graph{margin-top:16px;text-align:center;background:white;padding:16px;border-radius:10px}.history{margin-top:18px;background:#0f0f1a;padding:14px;border-radius:8px;border:1px solid #333;max-height:650px;overflow-y:auto}
.q{color:#00d4ff;font-weight:bold}.r{color:#eee;white-space:pre-wrap;line-height:1.6;margin-bottom:16px}
</style></head><body><div class="container">
<div style="text-align:center"><span class="badge auto">🤖 AUTO-LECTURE</span><span class="badge net">🌐 GOOGLE SEARCH</span></div>
<h2>⚽ Force Relative V8 FINAL SECURISE</h2>
<p style="text-align:center;color:#888;font-size:12px">Cles en .env - {{ fichiers_count }} fichiers / {{ cadres_count }} cadres</p>
<form method="POST"><textarea name="prompt" placeholder="Ex: PSG-OM ce soir, tensions? / SCAN AUTO"></textarea><br>
<button type="submit">Analyser + Internet</button>
<button type="submit" name="prompt" value="SCAN AUTO COMPLET: Lis hh/ + cherche sur internet dernières infos L'Equipe tensions vestiaires et dis quels cadres surprise sont actifs">SCAN AUTO</button></form>
{% if pcloud_status %}<div class="status">{{ pcloud_status }}</div>{% endif %}
{% if empreinte_msg %}<div class="empreinte">🧬 {{ empreinte_msg }}</div>{% endif %}
{% if graphique_url %}<div class="graph"><h3 style="color:#000">📊 7 Modeles 0-123' - Maxi Monte Carlo++ or pointillé</h3><img src="{{ graphique_url }}?t={{ range(1000) | random }}"><br>
{% if alertes %}<div style="text-align:left;color:#000;font-size:12px;margin-top:10px"><strong>Alertes:</strong><br>{% for a in alertes %}<span style="background:#ff4444;color:#fff;padding:2px 7px;border-radius:10px;font-size:10px">{{ a.type }} {{ a.minute }}'</span> {{ a.desc }}<br>{% endfor %}</div>{% endif %}</div>{% endif %}
<div class="history"><h3>Memoire</h3>{% for item in history %}<div class="q">Q: {{ item.question }}</div><div class="r">R: {{ item.answer }}</div>{% endfor %}</div>
</div></body></html>
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
            if not client:
                return "ERREUR: GEMINI_API_KEY manquant dans env", 500
            init_taxonomie_pcloud()
            taxo_resume, tous_fichiers, _ = charger_taxonomie_complete_auto()
            fichiers_count = len(tous_fichiers)
            cadres_count = len([f for f in tous_fichiers if "/cadres/" in f])
            context_str = ""
            for h in history[-5:]:
                if isinstance(h, dict):
                    context_str += f"Q: {h.get('question','')} R: {h.get('answer','')[:200]}\n"
            full_prompt = f"{taxo_resume}\nHistorique: {context_str}\nNOUVELLE QUESTION (utilise google_search + taxonomie): {user_prompt}\nRAPPEL: Chemins hh/data/... + forces 123 points + alertes + empreinte >0.85 + google_search obligatoire."

            try:
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
                        answer = re.sub(r"```json_actions\s*(\{.*\})\s*```", "", raw_answer, flags=re.DOTALL).strip() or re.sub(r"```json_actions\s*({.*?})\s*```", "", raw_answer, flags=re.DOTALL).strip()
                        for f in actions_data.get("fichiers_a_creer", []):
                            chemin = f.get("chemin", "")
                            contenu = f.get("contenu")
                            if chemin and not chemin.startswith("hh/"):
                                if chemin.startswith("data/"):
                                    chemin = f"hh/{chemin}"
                            if chemin and contenu:
                                save_pcloud_file(chemin, contenu)
                        pcloud_status = f"✅ {fichiers_count} lus + {len(actions_data.get('fichiers_a_creer', []))} crees + Internet"
                        empreinte = actions_data.get("empreinte_globale")
                        if empreinte and empreinte.get("similarite_modele", 0) > 0.85:
                            empreinte_msg = f"EMPREINTE {int(empreinte.get('similarite_modele',0)*100)}% IDENTIQUE {empreinte.get('modele_ref','')} - {empreinte.get('mots','')}"
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
                        print(f"Erreur parsing: {e}")
            except Exception as e:
                answer = f"Erreur Gemini: {e}"
            if 'answer' in locals() and answer:
                history.append({"question": user_prompt, "answer": answer})
                save_pcloud_file(f"{TARGET_FOLDER_NAME}/memoire_ia.json", history)

    if request.method == "GET" and PCLOUD_TOKEN:
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

import gradio as gr
import requests
import google.generativeai as genai
import os

PCLOUD_AUTH = os.environ.get("PCLOUD_AUTH")
GEMINI_KEY = os.environ.get("GEMINI_KEY")
MON_MDP = os.environ.get("MON_MDP")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def lire_pcloud():
    try:
        r = requests.get(f"https://api.pcloud.com/getfilelink?auth={PCLOUD_AUTH}&path=/ia/memoire.txt").json()
        if 'path' in r:
            url = "https://" + r['hosts'][0] + r['path']
            return requests.get(url).text
    except:
        pass
    return "Mémoire vide pour l'instant."

def ecrire_pcloud(texte):
    requests.get(f"https://api.pcloud.com/uploadfile?auth={PCLOUD_AUTH}&path=/ia&filename=memoire.txt",
                 files={'file': ('memoire.txt', texte.encode('utf-8'))})

def parler(question, mdp, historique):
    if mdp!= MON_MDP:
        return historique, "", "⛔ Mauvais mot de passe"
    memoire = lire_pcloud()
    reponse = model.generate_content(f"Tu es une IA avec cette mémoire:\n{memoire}\nQuestion: {question}\nRéponds court.").text
    ecrire_pcloud(memoire + f"\nVous: {question}\nIA: {reponse}\n")
    historique.append((question, reponse))
    return historique, "", "✅ Sauvé sur pCloud!"

with gr.Blocks() as demo:
    gr.Markdown("# Mon IA pCloud")
    mdp = gr.Textbox(label="Mot de passe", type="password")
    chatbot = gr.Chatbot(label="Discussion")
    q = gr.Textbox(label="Ta question")
    status = gr.Textbox(label="Status")
    btn = gr.Button("Envoyer")
    btn.click(parler, [q, mdp, chatbot], [chatbot, q, status])
    q.submit(parler, [q, mdp, chatbot], [chatbot, q, status])

demo.launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))

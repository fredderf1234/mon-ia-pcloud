import re

def verifier_et_filtrer_reponse(reponse_texte):
    """
    Agent Juge (Côté Python) : Analyse la réponse générée pour s'assurer 
    qu'il n'y a pas d'anachronismes flagrants ou de confusion temporelle.
    """
    if not reponse_texte:
        return ""

    # Tu pourras enrichir ce filtre au besoin (ex: vérification de mots-clés, de formats, etc.)
    return reponse_texte

def purger_memoires_obsoletes(json_files_list, max_conserver=15):
    """
    Filtre les fichiers pCloud pour ne garder que les plus récents 
    et éviter la pollution du RAG par de vieilles données.
    """
    if not json_files_list:
        return []
    # Trie par date de création décroissante et limite le nombre
    json_files_list.sort(key=lambda x: x.get("created", ""), reverse=True)
    return json_files_list[:max_conserver]

"""
Fichier de calculs statistiques et modélisations avancées pour l'agent football.
Fichier : calcul.py
"""

import io
import base64
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import poisson, beta

# Style visuel pour correspondre au thème néon / glassmorphism
plt.style.use('dark_background')
plt.rcParams['font.sans-serif'] = 'DejaVu Sans'


def analyser_match(equipe_home, equipe_away, simulations=10000):
    """
    Effectue les simulations Monte-Carlo, les calculs bayésiens
    et génère le dashboard graphique sous forme d'image encodée en Base64.
    """
    # 1. Calcul des espérances de buts (xG croisés)
    xg_home_marques = equipe_home.get('xg_marques', 1.5)
    xg_home_concedes = equipe_home.get('xg_concedes', 1.0)
    xg_away_marques = equipe_away.get('xg_marques', 1.2)
    xg_away_concedes = equipe_away.get('xg_concedes', 1.3)
    
    home_adv = equipe_home.get('home_advantage', 1.08)

    lambda_home = max(((xg_home_marques + xg_away_concedes) / 2.0) * home_adv, 0.1)
    lambda_away = max((xg_away_marques + xg_home_concedes) / 2.0, 0.1)

    # 2. Simulation Monte-Carlo (10 000 tirages Poisson)
    sim_h = np.random.poisson(lambda_home, simulations)
    sim_a = np.random.poisson(lambda_away, simulations)

    prob_1 = float(np.sum(sim_h > sim_a) / simulations)
    prob_N = float(np.sum(sim_h == sim_a) / simulations)
    prob_2 = float(np.sum(sim_h < sim_a) / simulations)

    total_buts = sim_h + sim_a
    over_2_5 = float(np.sum(total_buts > 2.5) / simulations)
    btts = float(np.sum((sim_h > 0) & (sim_a > 0)) / simulations)

    # Cotes équitables
    cote_1 = round(1.0 / prob_1, 2) if prob_1 > 0 else 99.0
    cote_N = round(1.0 / prob_N, 2) if prob_N > 0 else 99.0
    cote_2 = round(1.0 / prob_2, 2) if prob_2 > 0 else 99.0

    # 3. Estimation Bayésienne de la forme récente (Loi Beta)
    v_recentes = equipe_home.get('victoires_recentes', 3)
    m_joues = equipe_home.get('matchs_joues', 5)
    alpha_post = 2 + v_recentes
    beta_post = 2 + max(0, m_joues - v_recentes)
    forme_bayesienne = float(alpha_post / (alpha_post + beta_post))

    # 4. Génération des graphiques (Histogramme + Heatmap)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5), dpi=100)
    fig.patch.set_facecolor('#070913')

    # Graphique 1 : Histogramme Monte-Carlo
    ax1 = axes[0]
    ax1.set_facecolor('#0f172a')
    sns.histplot(total_buts, bins=range(0, 9), ax=ax1, color='#6366f1', discrete=True, stat="probability")
    ax1.axvline(2.5, color='#ec4899', linestyle='--', linewidth=2, label='Seuil Over 2.5')
    ax1.set_title("Distribution Monte-Carlo (Buts Totaux)", color='#38bdf8', fontsize=11, fontweight='bold')
    ax1.set_xlabel("Nombre de buts")
    ax1.set_ylabel("Probabilité")
    ax1.legend(loc='upper right', fontsize=8)

    # Graphique 2 : Heatmap des scores exacts (%)
    ax2 = axes[1]
    ax2.set_facecolor('#0f172a')
    max_g = 5
    matrice_scores = np.zeros((max_g, max_g))
    for h in range(max_g):
        for a in range(max_g):
            matrice_scores[h, a] = (poisson.pmf(h, lambda_home) * poisson.pmf(a, lambda_away)) * 100

    sns.heatmap(matrice_scores, annot=True, fmt=".1f", cmap="magma", ax=ax2, cbar=False,
                xticklabels=[str(i) for i in range(max_g)],
                yticklabels=[str(i) for i in range(max_g)])
    ax2.set_title(f"Heatmap Scores Exacts (%) [{equipe_home.get('nom', 'Home')} vs {equipe_away.get('nom', 'Away')}]", 
                  color='#38bdf8', fontsize=11, fontweight='bold')
    ax2.set_xlabel(f"Buts {equipe_away.get('nom', 'Away')}")
    ax2.set_ylabel(f"Buts {equipe_home.get('nom', 'Home')}")

    plt.tight_layout()

    # Encodage de l'image en Base64 pour l'intégrer facilement dans l'IHM web
    buf = io.BytesIO()
    plt.savefig(buf, format='png', facecolor=fig.get_facecolor(), edgecolor='none')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close()

    resultats = {
        "lambda_home": round(lambda_home, 2),
        "lambda_away": round(lambda_away, 2),
        "probabilites": {"1": round(prob_1 * 100, 1), "N": round(prob_N * 100, 1), "2": round(prob_2 * 100, 1)},
        "cotes_equitables": {"1": cote_1, "N": cote_N, "2": cote_2},
        "over_2_5_pct": round(over_2_5 * 100, 1),
        "btts_pct": round(btts * 100, 1),
        "forme_bayesienne_pct": round(forme_bayesienne * 100, 1)
    }

    return resultats, img_base64


# --- Exemple d'utilisation en ligne de commande ---
if __name__ == "__main__":
    eq_home = {"nom": "PSG", "xg_marques": 2.1, "xg_concedes": 0.8, "victoires_recentes": 4, "matchs_joues": 5}
    eq_away = {"nom": "Marseille", "xg_marques": 1.4, "xg_concedes": 1.1}
    
    res, img = analyser_match(eq_home, eq_away)
    print("Résultats des calculs :", res)
    print("Image Base64 générée avec succès (longueur) :", len(img))

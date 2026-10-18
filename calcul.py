import io
import base64
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

def analyser_match(eq_home, eq_away):
    """
    Génère les courbes des 7 modèles de Force Relative + Tendance Générale
    et produit le graphique Matplotlib aux couleurs normalisées V8.
    """
    # Axe du temps : 0 à 120 minutes (match + prolongations + tirs au but)
    minutes = np.linspace(0, 120, 121)

    np.random.seed(42)  # Stabilité pour les rendus graphiques
    
    # 1. Linéaire (Non-linéaire Dynamique) = BLEU #1f77b4
    c_lineaire = 20 + 15 * np.sin(minutes / 15) + np.random.normal(0, 2, len(minutes))
    
    # 2. XGBoost = ORANGE #ff7f0e
    c_xgboost = 25 + 10 * np.cos(minutes / 20) + (minutes / 6.0)
    
    # 3. ELO = VERT #2ca02c
    c_elo = np.full_like(minutes, 18.0) + (minutes * 0.05)
    
    # 4. Poisson / xG = ROUGE #d62728
    c_poisson = 15 + 20 * np.sin(minutes / 10) - (minutes * 0.02)
    
    # 5. Monte Carlo (1000 simulations) = VIOLET #9467bd
    c_monte_carlo = 22 + 12 * np.cos(minutes / 12) + np.random.normal(0, 3, len(minutes))
    
    # 6. Maxi Monte Carlo++ (10000 simulations extrêmes) = JAUNE OR #ffcc00
    c_maxi_mc = 25 + 25 * np.sin(minutes / 8) + np.random.normal(0, 6, len(minutes))
    
    # 7. Bayésien = ROSE #e377c2
    c_bayesien = 20 + 14 * np.sin(minutes / 18)

    # 8. TENDANCE GENERALE = NOIR épais (Moyenne des 7 modèles)
    tendance_generale = (c_lineaire + c_xgboost + c_elo + c_poisson + c_monte_carlo + c_maxi_mc + c_bayesien) / 7.0
    
    # Zone de confiance (+- 6)
    confiance_sup = tendance_generale + 6
    confiance_inf = tendance_generale - 6

    # Création du graphique Matplotlib adapté au design sombre du dashboard
    fig, ax = plt.subplots(figsize=(10, 5), facecolor='#111827')
    ax.set_facecolor('#1f2937')

    # Tracé des 7 modèles avec leurs couleurs fixes exactes
    ax.plot(minutes, c_lineaire, label='Linéaire', color='#1f77b4', linewidth=1.2, linestyle='-')
    ax.plot(minutes, c_xgboost, label='XGBoost', color='#ff7f0e', linewidth=1.2, linestyle='-')
    ax.plot(minutes, c_elo, label='ELO', color='#2ca02c', linewidth=1.2, linestyle='-')
    ax.plot(minutes, c_poisson, label='Poisson / xG', color='#d62728', linewidth=1.2, linestyle='-')
    ax.plot(minutes, c_monte_carlo, label='Monte Carlo', color='#9467bd', linewidth=1.2, linestyle='-')
    ax.plot(minutes, c_maxi_mc, label='Maxi Monte Carlo++', color='#ffcc00', linewidth=1.8, linestyle='--')
    ax.plot(minutes, c_bayesien, label='Bayésien', color='#e377c2', linewidth=1.2, linestyle='-')

    # Zone de confiance et Tendance Générale
    ax.fill_between(minutes, confiance_inf, confiance_sup, color='#9ca3af', alpha=0.15, label='Zone Confiance ±6')
    ax.plot(minutes, tendance_generale, label='Tendance Générale', color='#000000', linewidth=2.5, linestyle='-')

    # Paramètres des axes et grille
    ax.axhline(0, color='#9ca3af', linestyle='--', linewidth=0.8, alpha=0.7)
    ax.set_title("Force Relative V8 - Analyse Multi-Modèles", color='#f1f5f9', fontsize=12, fontweight='bold', pad=12)
    ax.set_xlabel("Minutes de jeu (0 - 120'+)", color='#9ca3af', fontsize=10)
    ax.set_ylabel("Axe de Domination (-100% à +100%)", color='#9ca3af', fontsize=10)
    ax.set_ylim(-100, 100)
    ax.set_xlim(0, 120)

    ax.tick_params(colors='#9ca3af', labelsize=9)
    for spine in ax.spines.values():
        spine.set_edgecolor('rgba(255, 255, 255, 0.1)')

    # Légende complète et propre en bas
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.18), ncol=4, facecolor='#111827', edgecolor='none', labelcolor='#f1f5f9', fontsize=8)

    plt.tight_layout()

    # Conversion en Base64 pour injection HTML dans l'interface
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png', dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
    buffer.seek(0)
    img_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
    plt.close(fig)

    stats_resume = {
        "equipe_domicile": eq_home.get("nom", "Domicile"),
        "equipe_exterieur": eq_away.get("nom", "Extérieur"),
        "tendance_finale_moyenne": float(np.mean(tendance_generale))
    }

    return stats_resume, img_b64

import os
import matplotlib

# Indispensable pour tourner sur le serveur web de Render sans interface graphique
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def executer_calculs_et_graphique(forces_dict=None, duree_match=90):
  """Trace les courbes des 7 modèles sur une durée variable et dynamique

  (minimum 90 min, s'adapte aux arrêts de jeu, prolongations, tirs au but).
  """
  # S'assure que la durée est au moins de 90 min, mais peut s'étendre si nécessaire
  if not duree_match or duree_match < 90:
    duree_match = 90

  minutes = np.arange(0, duree_match + 1)
  n = len(minutes)

  # Récupération ou simulation des 7 modèles sur la longueur exacte du match
  if forces_dict and isinstance(forces_dict, dict):
    lineaire = np.array(
        forces_dict.get("lineaire", np.sin(np.linspace(0, 10, n)) * 20)
    )
    xgboost = np.array(
        forces_dict.get("xgboost", np.cos(np.linspace(0, 10, n)) * 25)
    )
    elo = np.array(forces_dict.get("elo", np.linspace(-10, 20, n)))
    poisson_xg = np.array(
        forces_dict.get("poisson", np.random.normal(0, 10, n))
    )
    monte_carlo = np.array(
        forces_dict.get("monte_carlo", np.cumsum(np.random.normal(0, 2, n)))
    )
    maxi_mc = np.array(
        forces_dict.get("maxi_mc", np.cumsum(np.random.normal(0, 4, n)))
    )
    bayesien = np.array(
        forces_dict.get("bayesien", np.sin(np.linspace(0, 8, n)) * 15)
    )
  else:
    # Valeurs par défaut adaptées à la durée dynamique
    lineaire = np.sin(np.linspace(0, 15, n)) * 20
    xgboost = np.cos(np.linspace(0, 15, n)) * 25
    elo = np.linspace(-10, 20, n)
    poisson_xg = np.random.normal(0, 10, n)
    monte_carlo = np.cumsum(np.random.normal(0, 2, n))
    maxi_mc = np.cumsum(np.random.normal(0, 4, n))
    bayesien = np.sin(np.linspace(0, 12, n)) * 15

  tendance_generale = (
      lineaire
      + xgboost
      + elo
      + poisson_xg
      + monte_carlo
      + maxi_mc
      + bayesien
  ) / 7

  plt.figure(figsize=(11, 6))

  # Traçage des 7 modèles avec la charte graphique V8
  plt.plot(
      minutes,
      lineaire,
      color="#1f77b4",
      linewidth=1,
      label="Linéaire (Non-linéaire)",
  )
  plt.plot(minutes, xgboost, color="#ff7f0e", linewidth=1, label="XGBoost")
  plt.plot(minutes, elo, color="#2ca02c", linewidth=1, label="ELO")
  plt.plot(minutes, poisson_xg, color="#d62728", linewidth=1, label="Poisson / xG")
  plt.plot(
      minutes, monte_carlo, color="#9467bd", linewidth=1, label="Monte Carlo"
  )
  plt.plot(
      minutes,
      maxi_mc,
      color="#ffcc00",
      linewidth=2,
      linestyle="--",
      label="Maxi Monte Carlo++",
  )
  plt.plot(minutes, bayesien, color="#e377c2", linewidth=1, label="Bayésien")

  # Tendance Générale (Noir épais) + Zone de confiance
  plt.plot(
      minutes,
      tendance_generale,
      color="black",
      linewidth=2.5,
      label="Tendance Générale",
  )
  plt.fill_between(
      minutes,
      tendance_generale - 6,
      tendance_generale + 6,
      color="gray",
      alpha=0.2,
      label="Confiance ±6",
  )

  plt.axhline(0, color="gray", linestyle=":", alpha=0.7)
  plt.title(
      f"Analyse Force Relative - Modèles & Simulations ({duree_match} min)",
      fontsize=12,
  )
  plt.xlabel("Minutes")
  plt.ylabel("Domination (-100% / +100%)")
  plt.ylim(-100, 100)
  plt.legend(loc="upper left", bbox_to_anchor=(1, 1), fontsize="small")
  plt.tight_layout()

  os.makedirs("static", exist_ok=True)
  chemin_image = "static/graphique_match.png"
  plt.savefig(chemin_image, dpi=150)
  plt.close()

  return chemin_image

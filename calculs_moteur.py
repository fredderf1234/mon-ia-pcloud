 
import os
import matplotlib

# Indispensable pour tourner sur le serveur web de Render sans interface graphique
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def executer_calculs_et_graphique():
  """Calcule et trace les 7 modèles de la Force Relative V8

  avec leurs codes couleurs stricts et génère le PNG final.
  """
  # Axe X : de 0 à 120 minutes + prolongations/tirs au but (123 min)
  minutes = np.arange(0, 124)

  # Simulation ou calcul des 7 modèles de la V8 (seront connectés aux données de l'IA par la suite)
  lineaire = np.sin(minutes / 10) * 20  # Linéaire (Non-linéaire Dynamique)
  xgboost = np.cos(minutes / 12) * 25  # XGBoost
  elo = np.linspace(-10, 30, len(minutes))  # ELO
  poisson_xg = np.random.normal(0, 15, len(minutes))  # Poisson / xG
  monte_carlo = np.cumsum(
      np.random.normal(0, 2, len(minutes))
  )  # Monte Carlo (1000 sim)
  maxi_mc = np.cumsum(
      np.random.normal(0, 5, len(minutes))
  )  # Maxi Monte Carlo++ (10000 sim, plus volatile)
  bayesien = (
      np.linspace(0, 10, len(minutes)) + np.sin(minutes / 8) * 10
  )  # Bayésien

  # Tendance Générale : Moyenne exacte des 7 modèles
  tendance_generale = (
      lineaire
      + xgboost
      + elo
      + poisson_xg
      + monte_carlo
      + maxi_mc
      + bayesien
  ) / 7

  # Création de la figure Matplotlib
  plt.figure(figsize=(11, 6))

  # Traçage des 7 modèles avec les couleurs et styles stricts V8
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

  # Tendance Générale (Noir épais) + Zone de confiance grise (+-6)
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

  # Mise en forme du graphique (Axe Y : -100% à +100%, Ligne 0 centrale)
  plt.axhline(0, color="gray", linestyle=":", alpha=0.7)
  plt.title("Analyse Force Relative - Modèles & Simulations V8", fontsize=12)
  plt.xlabel("Minutes (0-120' + Tirs au but)")
  plt.ylabel("Domination (-100% / +100%)")
  plt.ylim(-100, 100)
  plt.legend(loc="upper left", bbox_to_anchor=(1, 1), fontsize="small")
  plt.tight_layout()

  # Sauvegarde automatique dans le dossier static pour affichage immédiat sur la page web
  os.makedirs("static", exist_ok=True)
  chemin_image = "static/graphique_match.png"
  plt.savefig(chemin_image, dpi=150)
  plt.close()

  return chemin_image

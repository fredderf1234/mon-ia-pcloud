import os
import matplotlib

# Indispensable pour tourner sur un serveur web sans interface graphique
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def executer_calculs_et_graphique():
  """Moteur de calculs et de graphiques provisoire

  pour valider l'architecture modulaire.
  """
  # Tracé d'un graphique de test basique
  plt.figure(figsize=(8, 4))
  plt.plot(
      [0, 1, 2, 3], [10, 25, 15, 30], color="#1f77b4", label="Modèle Test V8"
  )
  plt.title("Initialisation du Moteur - Force Relative")
  plt.xlabel("Minutes")
  plt.ylabel("Valeur")
  plt.legend()
  plt.tight_layout()

  # Sauvegarde dans le dossier static
  os.makedirs("static", exist_ok=True)
  chemin_image = "static/graphique_match.png"
  plt.savefig(chemin_image, dpi=150)
  plt.close()

  return chemin_image

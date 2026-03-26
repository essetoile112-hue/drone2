# Drone Parapluie - Simulation Webots

Ce projet propose une simulation sous Webots (R2025a) d'un drone autonome (DJI Mavic 2 Pro) équipé d'un parapluie, conçu pour suivre et abriter un piéton.

## ✨ Fonctionnalités

Le drone dispose de deux modes de fonctionnement, commutables en direct via le clavier :

1.  **Mode 1 : Mains libres (Par défaut)**
    *   Suivi du piéton basé sur les coordonnées GPS.
    *   Le drone lit la position absolue du piéton et se place au-dessus de lui.
2.  **Mode 2 : Suivi Intelligent (Vision + GPS)**
    *   Utilise la caméra intégrée au drone pour détecter le piéton grâce à l'IA **YOLOv8** (traitement CPU).
    *   Le drone ajuste sa trajectoire (lacet, tangage, roulis) pour garder le piéton au centre de l'image.
    *   *Mécanisme de sécurité* : Si la détection visuelle échoue pendant plus de 2 secondes, le drone repasse automatiquement sur le point GPS connu pour ne pas perdre l'utilisateur.

## 🛠️ Prérequis et Installation

Ce projet tourne dans un environnement virtuel Python spécifique pour isoler les dépendances.

1.  Ouvrir un terminal.
2.  Activer l'environnement virtuel (qui contient PyTorch et Ultralytics) :
    ```bash
    source /home/firas.mrabet/.gemini/antigravity/scratch/drone_parapluie/venv/bin/activate
    ```

## 🚀 Comment lancer la simulation ?

1.  Une fois l'environnement virtuel activé, lancer Webots :
    ```bash
    webots /home/firas.mrabet/.gemini/antigravity/scratch/drone_parapluie/worlds/drone_parapluie.wbt
    ```
2.  Dans la fenêtre Webots, appuyer sur le bouton **Play (▶️)** si la simulation est en pause.
3.  Le drone va décoller automatiquement et se stabiliser à environ 3 mètres d'altitude, au-dessus du piéton qui commence à marcher.

## 🎮 Contrôles en temps réel

Veillez à cliquer dans la vue 3D de Webots pour que la fenêtre capte bien les entrées clavier, puis appuyez sur :

*   **Touche `1`** : Forcer le mode de Suivi GPS.
*   **Touche `2`** : Activer le mode de Suivi Intelligent par Vision (YOLOv8). Dans la console Webots, vous pourrez suivre les changements d'état.

>(Note : Lors du premier lancement du mode Vision, YOLOv8 prendra quelques secondes pour charger son modèle en mémoire).

## 🗂️ Architecture des dossiers

*   `worlds/drone_parapluie.wbt` : Le monde Webots scénarisé (environnement, piéton, drone).
*   `protos/UmbrellaShape.proto` : Définition visuelle 3D de la forme du parapluie.
*   `controllers/drone_controller/drone_controller.py` : Logique de vol, asservissement PID et détection d'image.
*   `controllers/pedestrian_controller/pedestrian_controller.py` : Logique d'animation et de déplacement du piéton.

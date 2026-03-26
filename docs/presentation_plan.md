# Plan de Présentation Soutenance : Drone Parapluie Autonome

*Ce document contient tout le texte, la structure, et les explications nécessaires pour remplir vos slides PowerPoint. Chaque section représente une "Slide" (Diapositive).*

---

## 🛑 SLIDE 1 : Page de Garde
**Titre :** Conception et Simulation d'un Drone Parapluie Autonome  
**Sous-titre :** Système de suivi intelligent basé sur la vision par ordinateur et l'IA  
**Présenté par :** Firas Mrabet (et vos collègues)  
**Date :** [Date de la soutenance]  

---

## 🛑 SLIDE 2 : Contexte & Problématique
**Design/Visuel suggéré :** Une photo d'un piéton sous la pluie et une esquisse conceptuelle d'un drone parapluie.
* **Le besoin :** Fournir une protection météorologique (pluie, soleil extrême) 100% mains-libres pour les piétons, travailleurs en extérieur, ou personnes à mobilité réduite.
* **La problématique :** Comment le drone peut-il trouver, identifier et suivre continuellement sa cible sans collision, tout en maintenant une position de couverture optimale (exactement au-dessus de la tête) ?
* **Notre solution :** Un modèle robotique simulé sous Webots, combinant le contrôle en boucle fermée et l'intelligence artificielle visuelle (YOLO/OpenCV).

---

## 🛑 SLIDE 3 : Objectifs du Projet
**Design/Visuel suggéré :** Des puces (bullet points) avec des icônes minimalistes.
1. Concevoir un environnement de simulation réaliste pour tester les interactions Humain-Drone.
2. Développer un **pipeline de vision hybride** rapide et robuste pour la détection humaine.
3. Créer une machine à états (State Machine) pour automatiser le cycle de vol : Décollage ➔ Recherche ➔ Approche ➔ Suivi.
4. Surmonter les contraintes physiques des capteurs (ex: limites mécaniques des caméras).

---

## 🛑 SLIDE 4 : Technologies et Outils Utilisés
**Design/Visuel suggéré :** Logos des technologies.
* **Environnement 3D :** Cyberbotics Webots (Moteur physique, capteurs, actionneurs).
* **Langage de Programmation :** Python 3.
* **Intelligence Artificielle & Traitement d'Image :**
  * `Ultralytics YOLOv8` : Réseau de neurones profond (Deep Learning) pour détection d'objets complexes.
  * `OpenCV` (`cv2`) : Traitement d'image direct et masque colorimétrique (HSV).
* **Gestion de Version :** Git & GitHub (Travail collaboratif).

---

## 🛑 SLIDE 5 : Architecture du Drone (Mavic 2 Pro)
**Design/Visuel suggéré :** Capture d'écran du drone dans Webots avec un schéma fléché.
* **Actionneurs principaux :** 4 moteurs hélices.
* **Système de Caméra Double (Innovation du Projet) :**
  1. *Caméra Frontale sur Gimbal* : Cherche au loin (motorisée à -17°).
  2. *Caméra Inférieure Fixe (Track_Camera)* : Pointant à -90°, essentielle pour le suivi zénithal de précision.
* **Capteurs :** Gyroscope, IMU, GPS.

---

## 🛑 SLIDE 6 : L'Intelligence Artificielle (Le Cœur du Projet)
**Design/Visuel suggéré :** Un sablier ou une comparaison de performance YOLO vs OpenCV.
* **L'IA neuronale (YOLOv8)** est fiable mais très coûteuse en ressources CPU lors des simulations en temps réel.
* **Notre méthode optimisée "Hybride" :**
  1. **Détection Initiale Lointaine :** Le drone utilise YOLOv8 pour son radar 360°. Une fois qu'il est certain que c'est un humain, l'IA verrouille la cible.
  2. **Suivi Haute Fréquence :** Sur de courtes distances (la Descente), l'algorithme bascule sur un traitement d'image hyper-rapide (détection de la couleur du t-shirt / HSV via OpenCV).
* **Résultat :** Un taux de rafraichissement visuel maximum sans saccades.

---

## 🛑 SLIDE 7 : Séquence de Vol Autonome (Machine à États)
**Design/Visuel suggéré :** Un diagramme de flux (Flowchart).
1. **PHASE 1 (Décollage) :** Montée en altitude (2.8m).
2. **PHASE 2 (Recherche) :** Vol stationnaire, Caméra avant baissée, Rotation du drone à 360° (Scan radar).
3. **PHASE 3 (Approche) :** Cible détectée (YOLO). Le drone pivote face à la personne et active l'approche.
4. **PHASE 4 (Descente) :** Bascule sur la caméra ventrale inférieure, descente douce vers la tête (2.0m).
5. **PHASE 5 (Suivi Synchronisé) :** Feu vert au piéton, synchronisation PID X/Y/Z.

---

## 🛑 SLIDE 8 : Démonstration Pédagogique
*(Insérez ici une vidéo ou des GIFs de votre simulation Webots montrant le balayage 360° et la descente).*

---

## 🛑 SLIDE 9 : Conclusion & Perspectives
* **Bilan :** Le système asynchrone YOLO+Couleurs combiné à une architecture "Dual Camera" résout avec élégance les défis de la simulation CPU et des limites robotiques simulées.
* **Perspectives futures :**
  * Portage du code Python vers un microcontrôleur embarqué réel (Raspberry Pi/Jetson Nano).
  * Ajout d'un système d'évitement d'obstacles (Lidar, Capteurs ultrasons).
  * Adaptation à la vitesse aléatoire du piéton.

---
---

## ⚠️ ANTISÈCHE SECRET : QUESTIONS DU JURY (POUR VOUS !) ⚠️
Lisez et retenez ceci, le jury vous posera très probablement ces questions pour tester que c'est bien votre travail :

**Q1 du Jury : "*Pourquoi ne pas simplement utiliser les coordonnées GPS du piéton pour le suivre (Supervisor) dès le début ?*"**
> **Votre Réponse :** "Pour que la simulation soit réaliste ! Si on triche en lisant directement les données brutes du simulateur (le noeud piéton), ce n'est plus vraiment de l'IA ni de la vision autonome embarquée. En phase de recherche, le drone ignore totalement où est la personne : il doit balayer et la trouver avec sa propre caméra avant de connaître son vecteur d'approche."

**Q2 du Jury : "*Pourquoi avoir monté une deuxième caméra sous le drone au lieu d'utiliser simplement celle de base du Mavic ?*"**
> **Votre Réponse :** "C'est une authentique limitation mécanique ! Le moteur de la caméra (Gimbal Pitch) du modèle Mavic 2 Pro sous Webots a une butée physique (autour de -28 degrés) calculée pour ne pas filmer accidentellement son propre train d'atterrissage. Il lui était donc purement impossible de regarder droit vers le bas (-90°) pour centrer la tête du piéton. Notre astuce a été de concevoir une architecture "Dual Camera" : la caméra frontale pour le scan longue portée, et une caméra fixe (Tracking Camera) soudée sous l'ombrelle pour le suivi zénithal précis."

**Q3 du Jury : "*YOLOv8 est extrêmement lourd, comment avez-vous empêché la simulation Webots de geler/ramer (Lag) ?*"**
> **Votre Réponse :** "En appliquant le principe du fonctionnement intermittent ! On n'exécute le modèle neuronal YOLOv8 complet que lorsqu'on a un doute (Phase de scan) ou brièvement toutes les 15 frames pour réaffirmer la cible. Entre ces appels lourds, nous nous basons sur un filtre colorimétrique OpenCV ultra-léger sur la saturation du vêtement (Track Rouge). Cela libère l'essentiel du temps processeur pour les calculs de la physique dynamique des hélices."

**Q4 du Jury : "*Que se passe-t-il si le piéton croise une autre personne habillée en rouge ?*"**
> **Votre Réponse :** "C'est la faille inhérente de notre 'Color Tracking' actuel. En conditions réelles industrielles, nous remplacerions ce filtre basique par un algorithme de suivi de descripteurs (DeepSORT) ou par le scan d'un pattern complexe (un marqueur ArUco spécifique) brodé sur les épaules de l'utilisateur."

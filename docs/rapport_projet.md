# Rapport de Projet : Simulation d'un Drone Parapluie Autonome

*Ce document est formaté pour être copié-collé directement dans Microsoft Word. Il contient l'intégralité de l'argumentaire, de l'architecture et des résultats de votre projet.*

---

## 1. Introduction Générale
L'évolution rapide de la robotique de service ouvre la voie à de nouvelles interactions entre l'humain et les drones autonomes. Ce projet s'inscrit dans cette dynamique en proposant la conception et la simulation d'un "Drone Parapluie". L'objectif est de développer un système robotique capable de décoller, de détecter une personne cible de manière autonome, puis de se positionner au-dessus d'elle pour la protéger des intempéries (pluie, soleil) tout en se synchronisant avec sa marche. 

La réalisation de ce système complexe nécessite une synergie entre le contrôle de vol classique et l'Intelligence Artificielle embarquée, le tout validé dans un environnement de simulation tridimensionnel (Cyberbotics Webots).

## 2. État de l'Art et Contexte Technologique
Le suivi de cible par drone (Object Tracking) repose généralement sur des signaux de radiolocalisation (balises GPS) ou sur la vision par ordinateur. Notre projet privilégie une approche 100% visuelle, libérant l'utilisateur de la contrainte du port d'un boîtier émetteur.
Pour ce faire, nous avons évalué plusieurs algorithmes de vision :
1. **Les cascades de Haar / HOG :** Algorithmes classiques, rapides mais peu robustes aux changements d'éclairage ou de posture.
2. **Deep Learning (YOLOv8) :** L'état de l'art en détection d'objets, extrêmement précis mais très gourmand en puissance de calcul (CPU/GPU).
3. **Filtres Colorimétriques (HSV) :** Traitement d'image pixel par pixel ultra-rapide (quelques millisecondes), robuste mais sujet aux faux positifs si une couleur identique est présente dans le décor.

Afin de combiner précision et rapidité en temps réel pour l'asservissement physique du drone, ce projet propose une **architecture hybride asynchrone** (YOLOv8 + Suivi de couleur HSV).

## 3. Architecture du Simulateur (Webots)
L'environnement de test a été bâti autour du simulateur open-source Webots (R2025a), qui offre un moteur physique de très haute fidélité.

### 3.1. Le Drone (Mavic 2 Pro)
Le modèle physique choisi est basé sur le DJI Mavic 2 Pro virtuel. Il est équipé de :
* **4 Hélices motorisées :** Pour le contrôle des axes de Roulis (Roll), Tangage (Pitch), Lacet (Yaw) et de l'Altitude (Thrust).
* **Centrale Inertielle (IMU) & Gyroscope :** Pour la stabilisation automatique et la connaissance de l'assiette en vol.
* **Capteur GPS :** Pour l'odométrie et le positionnement global basique.

### 3.2. Le Système à Double Caméra (Architecture Innovante)
Durant le développement, une contrainte mécanique physique majeure a été identifiée : le moteur de la nacelle originelle (Gimbal) du drone Webots possède une butée logicielle bloquant l'inclinaison à environ -28 degrés vers le bas, l'empêchant de filmer à la verticale zénithale (-90 degrés).
Pour surmonter cette limite empêchant le suivi exact au-dessus du crâne du piéton, nous avons conçu une architecture "Dual Camera" :
1. **La Caméra de Nacelle (Camera Search) :** Montée à l'avant, motorisée sur 3 axes, elle permet de scanner l'horizon lointain.
2. **La Caméra Ventrale (Track Camera) :** Une caméra additionnelle fixée rigidement sous le châssis de l'ombrelle, regardant parfaitement vers le sol, dédiée à la boucle d'asservissement de précision.

### 3.3. Le Piéton
Un modèle humanoïde ("Pedestrian") contrôlé par un script externe simule l'utilisateur. Il est programmé par des points de repère (Waypoints) pour avancer sur un trottoir. Une logique de synchronisation par fichier tampon (IPC buffer) permet au drone de donner l'ordre de marche uniquement lorsqu'il est en position sécurisée au-dessus de la tête.

## 4. Implémentation Logicielle et Logique de Vol
L'intelligence du drone est gérée par un script Python agissant comme une machine à états finis (Finite State Machine). Cette FSM orchestre de façon autonome la mission du drone selon 5 phases distinctes :

1. **PHASE 1 - Décollage (Takeoff) :** Le drone actionne ses moteurs selon un Contrôleur PID (Proportionnel, Intégral, Dérivée) strict pour atteindre son altitude de balayage (2.8m).
2. **PHASE 2 - Recherche (Search) :** En vol stationnaire pur (Hover), le drone active la caméra frontale et pivote doucement sur son axe Z (Lacet / Yaw à 360°) tel un radar, jusqu'à acquérir le signal visuel de la personne cible au loin.
3. **PHASE 3 - Approche (Approach) :** Une fois la cible détectée et verrouillée visuellement, le drone calcule l'angle d'approche, se positionne face au piéton, et entame un vol de translation lent vers lui.
4. **PHASE 4 - Descente (Descend) :** A la verticale parfaite du piéton, le système informatique bascule le flux vidéo sur la Caméra Ventrale et amorce une descente délicate vers l'altitude de couverture optimale (2.0m).
5. **PHASE 5 - Suivi Synchronisé (Follow) :** Le feu vert est donné. Le piéton marche. La boucle PID maintient dynamiquement la personne au centre exact du flux vidéo ventral.

## 5. L'Intelligence Artificielle Hybride
L'innovation majeure logicielle repose sur l'approche asynchrone de la détection. 
L'exécution consécutive d'un modèle neuronal tel que YOLOv8n (nano) à chaque pas de temps du moteur physique (32ms) surcharge le processeur hôte et ralentit la simulation. Le contrôleur bascule donc intelligemment les ressources de calcul :
* Lors de la phase de **Recherche et d'incertitude**, l'algorithme fait appel à YOLOv8 pour confirmer l'identité humaine (Bounding Box de la classe "Person").
* Pendant la phase de **Suivi rapide**, le système ne fait appel à YOLOv8 que toutes les 15 frames pour assurer la robustesse. Dans l'intervalle, une conversion colorimétrique (BGR vers HSV dans OpenCV) segmente la couleur du sujet en 1 ou 2 millisecondes. C'est l'analyse du barycentre des contours de ce masque binaire extrêmement rapide qui alimente l'erreur des régulateurs PID de correction de trajectoire.

## 6. Analyse des Résultats
La simulation finale a démontré un comportement robuste.
* L'absence de recours intempestif aux coordonnées "système" (superviseur absolu) pendant la recherche garantit une simulation biologiquement et artificiellement crédible.
* La combinaison des deux caméras permet un centrage parfait de l'ombrelle avec des marges d'erreur lissées.
* La fréquence de rafraichissement n'impacte pas le temps réel de Webots grâce à la délégation asynchrone de la vision par ordinateur.

## 7. Conclusion
Le succès de ce projet valide l'utilisation de Webots comme outil de prototypage avancé pour des systèmes robotiques basés sur l'IA. Cette preuve de concept du Drone Parapluie pourrait tout à fait être portée sur du matériel informatique embarqué léger (type Nvidia Jetson ou un Raspberry Pi avec accélérateur NPU), prouvant la scalabilité et l'efficience de l'approche algorithmique hybride choisie.

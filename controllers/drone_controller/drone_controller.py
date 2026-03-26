#!/usr/bin/env python3
"""
Drone Parapluie — VERSION FINALE
=================================
Séquence : Décollage → Scan (vue complète) → Descente (près tête) → Suivi synchronisé
"""

from controller import Supervisor
import sys, math, os

try:
    import numpy as np
except ImportError:
    sys.exit("numpy manquant")

try:
    import cv2
    from ultralytics import YOLO
    HAS_VISION = True
except ImportError:
    print("Warning: OpenCV/Ultralytics absent.")
    HAS_VISION = False


class DroneParapluie(Supervisor):
    K_VERTICAL_THRUST = 68.5
    K_VERTICAL_OFFSET = 0.6
    K_VERTICAL_P = 5.0
    K_ROLL_P  = 50.0
    K_PITCH_P = 30.0

    # Phases de vol
    PHASE_TAKEOFF  = 0   # Décollage PID depuis le sol
    PHASE_SEARCH   = 1   # Cherche sans bouger (hover)
    PHASE_APPROACH = 2   # Cible vue ! Vol vers la cible
    PHASE_DESCEND  = 3   # Descend près de la tête
    PHASE_FOLLOW   = 4   # Suivi synchronisé, piéton marche

    SCAN_ALT       = 2.8  # Altitude de scan (voir personne entière)
    FOLLOW_ALT     = 2.0  # Altitude de suivi (près de la tête)
    FOLLOW_ALPHA   = 0.8  # Réactivité du suivi
    DESCEND_ALPHA  = 0.08 # Descente douce et progressive

    def __init__(self):
        Supervisor.__init__(self)
        self.time_step = int(self.getBasicTimeStep())

        self.camera_search = self.getDevice("camera")
        if not self.camera_search:
            print(">>> ERROR: 'camera' not found. Available devices:")
            for i in range(self.getNumberOfDevices()):
                print(f" - {self.getDeviceByIndex(i).getName()}")
            sys.exit(1)
            
        self.camera_search.enable(self.time_step)
        
        self.camera_track = self.getDevice("track_camera")
        if self.camera_track:
            self.camera_track.enable(self.time_step)
        else:
            self.camera_track = self.camera_search

        self.camera = self.camera_search # On démarre avec la caméra avant

        self.imu    = self.getDevice("inertial unit"); self.imu.enable(self.time_step)
        self.gps    = self.getDevice("gps"); self.gps.enable(self.time_step)
        self.gyro   = self.getDevice("gyro"); self.gyro.enable(self.time_step)
        self.keyboard.enable(self.time_step)

        self.m_fl = self.getDevice("front left propeller")
        self.m_fr = self.getDevice("front right propeller")
        self.m_rl = self.getDevice("rear left propeller")
        self.m_rr = self.getDevice("rear right propeller")
        for m in [self.m_fl, self.m_fr, self.m_rl, self.m_rr]:
            m.setPosition(float('inf'))
            m.setVelocity(1)

        for n in ["camera pitch", "camera yaw", "camera roll"]:
            self.getDevice(n).setPosition(0.0)

        self.drone_node  = self.getSelf()
        self.drone_trans = self.drone_node.getField("translation")
        self.drone_rot_field = self.drone_node.getField("rotation")
        self.pedestrian  = self.getFromDef("PEDESTRIAN")

        self.target_altitude = self.SCAN_ALT  # D'abord monter au scan
        self.phase = self.PHASE_TAKEOFF
        self.det_count = 0
        self.step_count = 0
        self.descend_count = 0
        self.search_yaw = 0.0

        if HAS_VISION:
            print("Chargement YOLOv8n...")
            self.yolo = YOLO("yolov8n.pt")
            print("YOLOv8n prêt !")

    def signal_go(self):
        try: open('/tmp/drone_go.txt','w').write('GO')
        except: pass

    def get_ped_pos(self):
        if self.pedestrian:
            return list(self.pedestrian.getField("translation").getSFVec3f())
        return [0.0, 0.0, 0.0]

    # ── Détection rapide : couleur rouge ──
    def detect_red_fast(self):
        data = self.camera.getImage()
        if not data: return False
        W, H = self.camera.getWidth(), self.camera.getHeight()
        raw = np.frombuffer(data, np.uint8).reshape((H, W, 4))
        bgr = raw[:,:,:3]
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        mask = (cv2.inRange(hsv, np.array([0,80,80]), np.array([12,255,255])) |
                cv2.inRange(hsv, np.array([168,80,80]), np.array([180,255,255])))
        return cv2.countNonZero(mask) > 200

    # ── Détection complète YOLO ──
    def detect_full(self):
        data = self.camera.getImage()
        if not data: return False, False
        W, H = self.camera.getWidth(), self.camera.getHeight()
        raw = np.frombuffer(data, np.uint8).reshape((H, W, 4))
        bgr = raw[:,:,:3]

        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        mask = (cv2.inRange(hsv, np.array([0,80,80]), np.array([12,255,255])) |
                cv2.inRange(hsv, np.array([168,80,80]), np.array([180,255,255])))
        red_ok = cv2.countNonZero(mask) > 200

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        res = self.yolo(rgb, conf=0.15, verbose=False)
        yolo_ok = False
        if res and len(res[0].boxes) > 0:
            yolo_ok = any(int(b.cls[0]) == 0 for b in res[0].boxes)

        return yolo_ok, red_ok

    # ── Position drone au-dessus du piéton ──
    def move_above(self, ped, alt=None, alpha=None):
        if alt is None:
            alt = self.target_altitude
        if alpha is None:
            alpha = self.FOLLOW_ALPHA
        cur = self.drone_trans.getSFVec3f()
        nx = cur[0] + alpha * (ped[0] - cur[0])
        ny = cur[1] + alpha * (ped[1] - cur[1])
        nz = cur[2] + alpha * (alt - cur[2])
        self.drone_trans.setSFVec3f([nx, ny, nz])
        self.drone_node.resetPhysics()
        dx = ped[0] - nx; dy = ped[1] - ny
        return math.sqrt(dx*dx + dy*dy)

    def set_hover(self):
        h = self.K_VERTICAL_THRUST
        self.m_fl.setVelocity(h)
        self.m_fr.setVelocity(-h)
        self.m_rl.setVelocity(-h)
        self.m_rr.setVelocity(h)

    # ── Boucle principale ──
    def run(self):
        print("=" * 55)
        print("  DRONE PARAPLUIE — Simulation Finale")
        print("  Séquence : Sol → Scan → Descente → Suivi")
        print("  Détection : YOLO + Rouge")
        print("=" * 55)

        while self.step(self.time_step) != -1:
            self.keyboard.getKey()
            self.step_count += 1
            roll, pitch, yaw = self.imu.getRollPitchYaw()
            x, y, z = self.gps.getValues()
            roll_acc, pitch_acc, _ = self.gyro.getValues()

            # ═══ PHASE 1 : DÉCOLLAGE (PID) ═══
            if self.phase == self.PHASE_TAKEOFF:
                if z > self.SCAN_ALT - 0.5:
                    self.phase = self.PHASE_SEARCH
                    print("Phase 2 : Altitude de recherche atteinte — je cherche la cible...")

                alt_err = max(min(self.SCAN_ALT - z + self.K_VERTICAL_OFFSET, 1), -1)
                vert = self.K_VERTICAL_P * pow(alt_err, 3.0)
                ri = self.K_ROLL_P * max(min(roll,1),-1) + roll_acc
                pi = self.K_PITCH_P * max(min(pitch,1),-1) + pitch_acc
                self.m_fl.setVelocity(  self.K_VERTICAL_THRUST + vert + pi - ri)
                self.m_fr.setVelocity(-(self.K_VERTICAL_THRUST + vert + pi + ri))
                self.m_rl.setVelocity(-(self.K_VERTICAL_THRUST + vert - pi - ri))
                self.m_rr.setVelocity(  self.K_VERTICAL_THRUST + vert - pi + ri)
                continue

            # ═══ PHASE 2 : RECHERCHE (Vol stationnaire + Scan 360) ═══
            elif self.phase == self.PHASE_SEARCH:
                self.camera = self.camera_search # Utilise la caméra avant
                # Regarde devant et légèrement vers le bas pour voir loin (-0.5 max)
                self.getDevice("camera pitch").setPosition(-0.3)
                
                # Tourne sur lui-même lentement (Scan 360°)
                self.search_yaw += 0.02
                self.drone_rot_field.setSFRotation([0, 0, 1, self.search_yaw])

                # Maintien de la position X,Y au niveau SCAN_ALT
                cur_pos = self.drone_trans.getSFVec3f()
                self.move_above(cur_pos, self.SCAN_ALT)
                self.set_hover()

                # Détection de la personne complète
                if self.step_count % 10 == 0:
                    yolo_ok, red_ok = self.detect_full()
                    if yolo_ok or red_ok:
                        self.det_count += 1
                        if self.det_count >= 2:
                            self.phase = self.PHASE_APPROACH
                            print(">>> PERSONNE DÉTECTÉE ! Je m'approche...")
                    else:
                        self.det_count = 0

            # ═══ PHASE 3 : APPROCHE (Vers la cible détectée) ═══
            elif self.phase == self.PHASE_APPROACH:
                ped = self.get_ped_pos()
                cur_pos = self.drone_trans.getSFVec3f()
                
                # Orientation de la face avant du drone vers la personne
                target_yaw = math.atan2(ped[1] - cur_pos[1], ped[0] - cur_pos[0])
                self.drone_rot_field.setSFRotation([0, 0, 1, target_yaw])

                dist = self.move_above(ped, self.SCAN_ALT, alpha=0.03) # Vol lent vers lui
                self.set_hover()

                if dist < 0.4:
                    self.phase = self.PHASE_DESCEND
                    self.descend_count = 0
                    print(">>> Au-dessus de la cible ! Descente vers la tête...")

            # ═══ PHASE 4 : DESCENTE (vers altitude de suivi près de la tête) ═══
            elif self.phase == self.PHASE_DESCEND:
                # Bascule sur la caméra fixe du dessous pour le suivi vertical !
                self.camera = self.camera_track
                
                ped = self.get_ped_pos()
                self.move_above(ped, self.FOLLOW_ALT, self.DESCEND_ALPHA)
                self.set_hover()

                cur_z = self.drone_trans.getSFVec3f()[2]
                if abs(cur_z - self.FOLLOW_ALT) < 0.15:
                    self.descend_count += 1
                    if self.descend_count >= 10:
                        self.phase = self.PHASE_FOLLOW
                        self.signal_go()
                        print("=" * 55)
                        print(">>> Position OK ! Piéton MARCHE ! Suivi synchronisé !")
                        print("=" * 55)

            # ═══ PHASE 5 : SUIVI SYNCHRONISÉ ═══
            elif self.phase == self.PHASE_FOLLOW:
                self.camera = self.camera_track # Maintien de la caméra du dessous
                
                ped = self.get_ped_pos()
                dist = self.move_above(ped, self.FOLLOW_ALT)
                self.set_hover()

                # Log périodique
                if self.step_count % 20 == 0:
                    red = self.detect_red_fast()
                    if self.step_count % 100 == 0:
                        print(f"  [SUIVI] dist={dist:.2f}m rouge={'oui' if red else '—'}")


if __name__ == '__main__':
    DroneParapluie().run()

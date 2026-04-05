#!/usr/bin/env python3
"""
Drone Parapluie — VERSION FINALE (Dual Mode)
==============================================
Mode 1 (Mains-Libres / GPS)  : Décollage → GPS Direct → Descente → Suivi GPS
Mode 2 (Vision Intelligente)  : Décollage → Scan 360 → YOLO Détection → Descente → Suivi
Commutation en temps réel via les touches clavier '1' et '2'.
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
    print("Warning: OpenCV/Ultralytics absent — Mode Vision désactivé.")
    HAS_VISION = False


class DroneParapluie(Supervisor):
    K_VERTICAL_THRUST = 68.5
    K_VERTICAL_OFFSET = 0.6
    K_VERTICAL_P = 5.0
    K_ROLL_P  = 50.0
    K_PITCH_P = 30.0

    # ── Phases de vol (Mode Vision — Mode 2) ──
    PHASE_TAKEOFF  = 0   # Décollage PID depuis le sol
    PHASE_SEARCH   = 1   # Cherche sans bouger (hover) + scan 360
    PHASE_APPROACH = 2   # Cible vue ! Vol vers la cible
    PHASE_DESCEND  = 3   # Descend près de la tête
    PHASE_FOLLOW   = 4   # Suivi synchronisé, piéton marche

    # ── Phases de vol (Mode GPS — Mode 1 / Mains-Libres) ──
    PHASE_GPS_TAKEOFF  = 10  # Décollage PID
    PHASE_GPS_APPROACH = 11  # Vol direct vers la position GPS du piéton
    PHASE_GPS_DESCEND  = 12  # Descente douce vers altitude de suivi
    PHASE_GPS_FOLLOW   = 13  # Suivi GPS synchronisé

    # ── Modes de fonctionnement ──
    MODE_GPS    = 1   # Mode 1 : Mains-Libres (GPS pur)
    MODE_VISION = 2   # Mode 2 : Vision Intelligente (YOLO + OpenCV)

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

        # ── État initial : Mode GPS (Mains-Libres) par défaut ──
        self.flight_mode = self.MODE_GPS
        self.target_altitude = self.SCAN_ALT
        self.phase = self.PHASE_GPS_TAKEOFF
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

    # ── Gestion de la commutation de mode (clavier) ──
    def handle_mode_switch(self, key):
        """Commute entre Mode GPS (1) et Mode Vision (2) via le clavier."""
        if key == ord('1') and self.flight_mode != self.MODE_GPS:
            self.flight_mode = self.MODE_GPS
            self.phase = self.PHASE_GPS_TAKEOFF
            self.det_count = 0
            self.descend_count = 0
            print("=" * 55)
            print("  >>> COMMUTATION → MODE 1 : MAINS-LIBRES (GPS)")
            print("  Le drone suit le piéton par coordonnées GPS.")
            print("  Pas de traitement d'image — suivi direct.")
            print("=" * 55)

        elif key == ord('2') and self.flight_mode != self.MODE_VISION:
            if not HAS_VISION:
                print(">>> ERREUR: OpenCV/Ultralytics non disponible. Mode Vision impossible.")
                return
            self.flight_mode = self.MODE_VISION
            self.phase = self.PHASE_TAKEOFF
            self.det_count = 0
            self.descend_count = 0
            self.search_yaw = 0.0
            print("=" * 55)
            print("  >>> COMMUTATION → MODE 2 : VISION INTELLIGENTE")
            print("  Le drone utilise YOLOv8 + OpenCV pour détecter")
            print("  et suivre le piéton visuellement.")
            print("=" * 55)

    # ══════════════════════════════════════════════════════════
    #  BOUCLE PRINCIPALE — MODE GPS (Mains-Libres)
    # ══════════════════════════════════════════════════════════
    def run_gps_mode(self, roll, pitch, yaw, x, y, z, roll_acc, pitch_acc):
        """Mode 1 : Suivi GPS pur — sans traitement d'image."""

        # ═══ PHASE GPS 1 : DÉCOLLAGE (PID) ═══
        if self.phase == self.PHASE_GPS_TAKEOFF:
            if z > self.SCAN_ALT - 0.5:
                self.phase = self.PHASE_GPS_APPROACH
                print("  [GPS] Altitude atteinte — vol direct vers le piéton (GPS)...")

            alt_err = max(min(self.SCAN_ALT - z + self.K_VERTICAL_OFFSET, 1), -1)
            vert = self.K_VERTICAL_P * pow(alt_err, 3.0)
            ri = self.K_ROLL_P * max(min(roll,1),-1) + roll_acc
            pi = self.K_PITCH_P * max(min(pitch,1),-1) + pitch_acc
            self.m_fl.setVelocity(  self.K_VERTICAL_THRUST + vert + pi - ri)
            self.m_fr.setVelocity(-(self.K_VERTICAL_THRUST + vert + pi + ri))
            self.m_rl.setVelocity(-(self.K_VERTICAL_THRUST + vert - pi - ri))
            self.m_rr.setVelocity(  self.K_VERTICAL_THRUST + vert - pi + ri)

        # ═══ PHASE GPS 2 : APPROCHE DIRECTE (GPS) ═══
        elif self.phase == self.PHASE_GPS_APPROACH:
            ped = self.get_ped_pos()
            cur_pos = self.drone_trans.getSFVec3f()

            # Orienter le drone face au piéton
            target_yaw = math.atan2(ped[1] - cur_pos[1], ped[0] - cur_pos[0])
            self.drone_rot_field.setSFRotation([0, 0, 1, target_yaw])

            dist = self.move_above(ped, self.SCAN_ALT, alpha=0.05)
            self.set_hover()

            if dist < 0.4:
                self.phase = self.PHASE_GPS_DESCEND
                self.descend_count = 0
                print("  [GPS] Au-dessus du piéton ! Descente vers la tête...")

        # ═══ PHASE GPS 3 : DESCENTE (vers altitude de suivi) ═══
        elif self.phase == self.PHASE_GPS_DESCEND:
            ped = self.get_ped_pos()
            self.move_above(ped, self.FOLLOW_ALT, self.DESCEND_ALPHA)
            self.set_hover()

            cur_z = self.drone_trans.getSFVec3f()[2]
            if abs(cur_z - self.FOLLOW_ALT) < 0.15:
                self.descend_count += 1
                if self.descend_count >= 10:
                    self.phase = self.PHASE_GPS_FOLLOW
                    self.signal_go()
                    print("=" * 55)
                    print("  [GPS] Position OK ! Piéton MARCHE ! Suivi GPS actif !")
                    print("=" * 55)

        # ═══ PHASE GPS 4 : SUIVI GPS SYNCHRONISÉ ═══
        elif self.phase == self.PHASE_GPS_FOLLOW:
            ped = self.get_ped_pos()
            dist = self.move_above(ped, self.FOLLOW_ALT)
            self.set_hover()

            # Orienter le drone dans la direction du piéton
            cur_pos = self.drone_trans.getSFVec3f()
            target_yaw = math.atan2(ped[1] - cur_pos[1], ped[0] - cur_pos[0])
            self.drone_rot_field.setSFRotation([0, 0, 1, target_yaw])

            # Log périodique
            if self.step_count % 100 == 0:
                print(f"  [GPS SUIVI] dist={dist:.2f}m | pos=({ped[0]:.1f}, {ped[1]:.1f})")

    # ══════════════════════════════════════════════════════════
    #  BOUCLE PRINCIPALE — MODE VISION (YOLO + OpenCV)
    # ══════════════════════════════════════════════════════════
    def run_vision_mode(self, roll, pitch, yaw, x, y, z, roll_acc, pitch_acc):
        """Mode 2 : Suivi Vision Intelligente — YOLO + OpenCV."""

        # ═══ PHASE 1 : DÉCOLLAGE (PID) ═══
        if self.phase == self.PHASE_TAKEOFF:
            if z > self.SCAN_ALT - 0.5:
                self.phase = self.PHASE_SEARCH
                print("  [VISION] Altitude de recherche atteinte — je cherche la cible...")

            alt_err = max(min(self.SCAN_ALT - z + self.K_VERTICAL_OFFSET, 1), -1)
            vert = self.K_VERTICAL_P * pow(alt_err, 3.0)
            ri = self.K_ROLL_P * max(min(roll,1),-1) + roll_acc
            pi = self.K_PITCH_P * max(min(pitch,1),-1) + pitch_acc
            self.m_fl.setVelocity(  self.K_VERTICAL_THRUST + vert + pi - ri)
            self.m_fr.setVelocity(-(self.K_VERTICAL_THRUST + vert + pi + ri))
            self.m_rl.setVelocity(-(self.K_VERTICAL_THRUST + vert - pi - ri))
            self.m_rr.setVelocity(  self.K_VERTICAL_THRUST + vert - pi + ri)

        # ═══ PHASE 2 : RECHERCHE (Vol stationnaire + Scan 360) ═══
        elif self.phase == self.PHASE_SEARCH:
            self.camera = self.camera_search
            self.getDevice("camera pitch").setPosition(-0.3)
            
            self.search_yaw += 0.02
            self.drone_rot_field.setSFRotation([0, 0, 1, self.search_yaw])

            cur_pos = self.drone_trans.getSFVec3f()
            self.move_above(cur_pos, self.SCAN_ALT)
            self.set_hover()

            if self.step_count % 10 == 0:
                yolo_ok, red_ok = self.detect_full()
                if yolo_ok or red_ok:
                    self.det_count += 1
                    if self.det_count >= 2:
                        self.phase = self.PHASE_APPROACH
                        print("  [VISION] >>> PERSONNE DÉTECTÉE ! Je m'approche...")
                else:
                    self.det_count = 0

        # ═══ PHASE 3 : APPROCHE (Vers la cible détectée) ═══
        elif self.phase == self.PHASE_APPROACH:
            ped = self.get_ped_pos()
            cur_pos = self.drone_trans.getSFVec3f()
            
            target_yaw = math.atan2(ped[1] - cur_pos[1], ped[0] - cur_pos[0])
            self.drone_rot_field.setSFRotation([0, 0, 1, target_yaw])

            dist = self.move_above(ped, self.SCAN_ALT, alpha=0.03)
            self.set_hover()

            if dist < 0.4:
                self.phase = self.PHASE_DESCEND
                self.descend_count = 0
                print("  [VISION] Au-dessus de la cible ! Descente vers la tête...")

        # ═══ PHASE 4 : DESCENTE (vers altitude de suivi) ═══
        elif self.phase == self.PHASE_DESCEND:
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
                    print("  [VISION] Position OK ! Piéton MARCHE ! Suivi Vision actif !")
                    print("=" * 55)

        # ═══ PHASE 5 : SUIVI SYNCHRONISÉ (Vision) ═══
        elif self.phase == self.PHASE_FOLLOW:
            self.camera = self.camera_track
            
            ped = self.get_ped_pos()
            dist = self.move_above(ped, self.FOLLOW_ALT)
            self.set_hover()

            if self.step_count % 20 == 0:
                red = self.detect_red_fast()
                if self.step_count % 100 == 0:
                    print(f"  [VISION SUIVI] dist={dist:.2f}m rouge={'oui' if red else '—'}")

    # ══════════════════════════════════════════════════════════
    #  BOUCLE PRINCIPALE
    # ══════════════════════════════════════════════════════════
    def run(self):
        mode_names = {self.MODE_GPS: "MAINS-LIBRES (GPS)", self.MODE_VISION: "VISION INTELLIGENTE"}
        print("=" * 55)
        print("  DRONE PARAPLUIE — Simulation Finale (Dual Mode)")
        print(f"  Mode actif : {mode_names[self.flight_mode]}")
        print("  Touches : '1' = GPS | '2' = Vision (YOLO)")
        print("=" * 55)

        while self.step(self.time_step) != -1:
            key = self.keyboard.getKey()
            self.step_count += 1

            # ── Commutation de mode en temps réel ──
            if key in [ord('1'), ord('2')]:
                self.handle_mode_switch(key)

            roll, pitch, yaw = self.imu.getRollPitchYaw()
            x, y, z = self.gps.getValues()
            roll_acc, pitch_acc, _ = self.gyro.getValues()

            # ── Dispatch vers le mode actif ──
            if self.flight_mode == self.MODE_GPS:
                self.run_gps_mode(roll, pitch, yaw, x, y, z, roll_acc, pitch_acc)
            else:
                self.run_vision_mode(roll, pitch, yaw, x, y, z, roll_acc, pitch_acc)


if __name__ == '__main__':
    DroneParapluie().run()

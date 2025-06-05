# -*- coding: utf-8 -*-
"""
Created on Thu May 22 15:27:15 2025

@author: olivi
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d
from scipy.integrate import solve_ivp
from numba import njit
import time
bornes_vitesse =[(0.0, 8.47), (8.29, 8.93), (6.99, 8.43), (7.24, 8.98), (6.44, 8.87)]
temps_max = 189
nom_fichier="simulation_results_opti_5accèl_189_V3.csv"

rendement_recup = 0.6
a_max_freinage = 0.4
# =============================================================================
# 1) Chargement des données initiales
#=============================================================================

# Chargement des données moteur
moteur_consomini = pd.read_csv("moteur_consomini.csv")
x = moteur_consomini["n moteur"]
f_interpol_couple = interp1d(x, moteur_consomini["m corr"]*0.55*1.06, kind="linear", fill_value="extrapolate")
f_interpol_csp = interp1d(x, moteur_consomini["csp"]*1.7, kind="linear", fill_value="extrapolate")

# Moteur électrique
moteur_elec = pd.read_csv("moteur_elec.csv")
x_elec = moteur_elec["vitesse rotor"]


moteur_elec2=pd.read_csv("moteur_elec_2.csv")
rpm_elec=moteur_elec2["rpm"]
f_interpol_couple_elec=interp1d(rpm_elec, moteur_elec2["Couple"],kind="linear",fill_value="extrapolate")
#f_interpol_P_elec = interp1d(rpm_elec, moteur_elec["pelec calc"], kind="linear", fill_value="extrapolate")


# Enviolo
data_enviolo = pd.read_csv("data_enviolo.csv")
x_env = data_enviolo["vitesse moteur"]
y_env = data_enviolo["rapport enviolo"]
f_interp_env = interp1d(x_env, y_env, kind="linear", fill_value="extrapolate")

# Piste
xyz = pd.read_csv("sem_2025_eu.csv")
xyz.columns = [col.lower() for col in xyz.columns]
distance = xyz["distance from lap line (m)"]
altitude = xyz["elevation (m)"]
pos_x = xyz["utmx"]
pos_y = xyz["utmy"]

heading = np.arctan2(np.gradient(pos_y), np.gradient(pos_x))
heading_interp = interp1d(distance, heading, fill_value="extrapolate")

# Cx variable
data_cx = pd.read_excel("Cx_voiture_vent.xlsx", skiprows=3)
data_cx.columns = [col.lower() for col in data_cx.columns]
angle = data_cx["angle (°)"]
Cx = data_cx["cx (-)"]
f_interp_cx = interp1d(angle, Cx, kind="linear", fill_value="extrapolate")

# =============================================================================
# 2) Fonctions njit optimisées
# =============================================================================

@njit
def interp_linear_njit(x, xp, fp):
    """Interpolation linéaire compatible njit"""
    return np.interp(x, xp, fp)

@njit
def calcul_embrayage_njit(omega_m, m_mass, r_mass, N_mass, F_ressort, mu_clutch, R_cloche):
    """Calcul du couple d'embrayage optimisé"""
    F_centrifuge = m_mass * (omega_m * omega_m) * r_mass
    embrayage_actif = F_centrifuge > F_ressort
    if embrayage_actif:
        C_embre_max = N_mass * (F_centrifuge - F_ressort) * mu_clutch * R_cloche
    else:
        C_embre_max = 0.0
    return C_embre_max, embrayage_actif

@njit
def gestion_phases_njit(v, v_last, phase_actuelle, bornes_flat, phases_terminees, phases_activees, moteur_actif):
    """Gestion optimisée des phases de vitesse - CORRIGÉE pour éviter activation simultanée"""
    franchissement_min = False
    franchissement_max = False
    
    n_phases = len(bornes_flat) // 2
    
    if phase_actuelle < n_phases:
        borne_min = bornes_flat[phase_actuelle * 2]
        borne_max = bornes_flat[phase_actuelle * 2 + 1]
        
        franchissement_min = (v_last > borne_min) and (v <= borne_min)
        franchissement_max = (v_last < borne_max) and (v >= borne_max)
        
        if not phases_terminees[phase_actuelle]:
            # CORRECTION: Ne pas activer le moteur thermique si on est au tout début (v très faible)
            # Le moteur électrique doit avoir la priorité pour le démarrage
            if ((franchissement_min or v <= borne_min) and not moteur_actif and 
                not phases_activees[phase_actuelle] and v > 0.5):  # Ajout condition v > 0.5
                moteur_actif = True
                phases_activees[phase_actuelle] = True
                
            elif (franchissement_max or v >= borne_max) and moteur_actif:
                moteur_actif = False
                phases_terminees[phase_actuelle] = True
                
                if phase_actuelle < n_phases - 1:
                    phase_actuelle += 1
    
    return moteur_actif, phase_actuelle, franchissement_min, franchissement_max

@njit
def calcul_forces_njit(pos, v, couple_moteur, ratio_enviolo, couple_transmis,
                       resistance_roulement, coefficient_trainee, surface_frontale,
                       masse, rayon_roue, rendement_chaine1, rendement_chaine2,
                       rendement_transmission, rapport_chaine1, rapport_chaine2,
                       g, densite_air, angle_pente, aero_active, gravite_active,
                       vent_active, vitesse_vent, wind_angle_global, heading, Cx_wind):
    """Calcul optimisé des forces"""
    
    # Force moteur
    if couple_transmis > 0:
        F_moteur = (couple_transmis * rapport_chaine1 * rapport_chaine2 / ratio_enviolo * 
                   rendement_chaine1 * rendement_chaine2 * rendement_transmission) / rayon_roue
    elif couple_moteur > 0:
        F_moteur = (couple_moteur * rapport_chaine1 * rapport_chaine2 / ratio_enviolo * 
                   rendement_chaine1 * rendement_chaine2 * rendement_transmission) / rayon_roue
    else:
        F_moteur = 0.0

    # Force aérodynamique
    if aero_active:
        F_aero = 0.5 * coefficient_trainee * surface_frontale * densite_air * (v * v)
    else:
        F_aero = 0.0

    # Force de roulement
    F_roulement = resistance_roulement * masse * g

    # Force gravitationnelle
    if gravite_active:
        F_gravite = masse * g * np.sin(angle_pente)
    else:
        F_gravite = 0.0
        
    # Force du vent
    if vent_active:
        vx = vitesse_vent * np.cos(wind_angle_global)
        vy = vitesse_vent * np.sin(wind_angle_global)
        v_wind_along = vx * np.cos(heading) + vy * np.sin(heading)
        F_wind = 0.5 * Cx_wind * surface_frontale * densite_air * (v_wind_along * v_wind_along)
        if v_wind_along < 0:
            F_wind = -F_wind
    else:
        F_wind = 0.0
    

    return F_moteur, F_aero, F_roulement, F_gravite, F_wind

@njit
def calcul_dynamique_njit(pos, v, omega_m, couple_moteur, C_transmis_brut, ratio_enviolo,
                          masse, rayon_roue, rapport_chaine1, rapport_chaine2,
                          F_moteur, F_aero, F_roulement, F_gravite, F_wind, F_elec, F_freinage,
                          moteur_actif, moteur_elec_actif, coef_aero, coef_roul):
    """Calcul des dérivées optimisé"""
    
    roue_libre_active = not moteur_actif and not moteur_elec_actif and v > 1.0
    
    if roue_libre_active:
        F_aero_modif = coef_aero * F_aero
        F_roulement_modif = coef_roul * F_roulement
        dv_dt = (-F_roulement_modif - F_aero_modif+F_freinage - F_gravite + F_wind) / masse
        omega_idle = 10.0
        domega_m_dt = -20.0 * (omega_m - omega_idle)
    else:
        dv_dt = (F_moteur + F_elec - F_aero+F_freinage - F_roulement - F_gravite + F_wind) / masse
        if not moteur_actif:
            domega_m_dt = -0.1 * omega_m
        else:
            inertie = 0.00201 + masse * (rayon_roue * rayon_roue) / ((rapport_chaine1 * rapport_chaine2) / ratio_enviolo) ** 2
            domega_m_dt = (couple_moteur - C_transmis_brut) / inertie

    dpos_dt = v
    
    return dpos_dt, dv_dt, domega_m_dt, roue_libre_active

# =============================================================================
# 3) Classe de données pour lookup tables
# =============================================================================

class InterpolationData:
    """Stockage des données d'interpolation pour njit"""
    def __init__(self):
        # Données moteur
        self.moteur_rpm = None
        self.moteur_couple = None
        self.moteur_csp = None
        
        # Données moteur électrique
        self.elec_rpm = None
        self.elec_couple = None
        self.elec_power = None
        
        # Données enviolo
        self.env_rpm = None
        self.env_ratio = None
        
        # Données piste
        self.distance_data = None
        self.altitude_data = None
        self.heading_data = None
        
        # Données Cx
        self.angle_data = None
        self.cx_data = None
        
    def load_from_existing_data(self):
        """Charge les données depuis les variables globales déjà chargées"""
        
        # Moteur thermique
        self.moteur_rpm = moteur_consomini["n moteur"].values.astype(np.float64)
        self.moteur_couple = (moteur_consomini["m corr"] * 0.55 * 1.06).values.astype(np.float64)
        self.moteur_csp = (moteur_consomini["csp"] * 1.7).values.astype(np.float64)
        
        # Moteur électrique
        self.elec_rpm = moteur_elec2["rpm"].values.astype(np.float64)
        self.elec_couple = moteur_elec2["Couple"].values.astype(np.float64)
        self.elec_power = moteur_elec["pelec calc"].values.astype(np.float64)
        
        # Enviolo
        self.env_rpm = data_enviolo["vitesse moteur"].values.astype(np.float64)
        self.env_ratio = data_enviolo["rapport enviolo"].values.astype(np.float64)
        
        # Piste
        self.distance_data = distance.values.astype(np.float64)
        self.altitude_data = altitude.values.astype(np.float64)
        self.heading_data = heading.astype(np.float64)
        
        # Cx variable
        self.angle_data = angle.values.astype(np.float64)
        self.cx_data = Cx.values.astype(np.float64)

# =============================================================================
# 4) Simulation optimisée
# =============================================================================

def simuler_vehicule_optimise(distance_totale, bornes_vitesse, temps_max=500,
                             vent_active=False, vitesse_vent=0, wind_angle_global=0,
                             aero_active=True, gravite_active=True, enviolo_on=True,
                             moteur_elec=False, coef_aero=1.63, coef_roul=1,
                             plot=True, debug_mode=False):
    """
    Version optimisée de la simulation avec njit
    """
    
    # Chargement des données
    interp_data = InterpolationData()
    interp_data.load_from_existing_data()
    
    # Paramètres véhicule (convertis en arrays njit)
    params_array = np.array([
        0.0013,  # resistance_roulement
        0.23,    # coefficient_trainee
        0.789,   # surface_frontale
        224.0,   # masse
        0.279,   # rayon_roue
        0.97,    # rendement_chaine1
        0.97,    # rendement_chaine2
        0.83,    # rendement_transmission
        95.0/11.0,  # rapport_chaine1
        2.4,     # rapport_chaine2
        9.81,    # g
        1.225    # densite_air
    ], dtype=np.float64)
    
    # Paramètres embrayage
    embrayage_params = np.array([
        0.0774,  # m_mass
        0.0316,  # r_mass
        4.0,     # N_mass
        28.23,   # F_ressort
        0.3,     # mu_clutch
        0.045    # R_cloche
    ], dtype=np.float64)
    
    # Préparation des phases
    bornes_flat = np.array([item for sublist in bornes_vitesse for item in sublist], dtype=np.float64)
    phases_terminees = np.zeros(len(bornes_vitesse), dtype=np.bool_)
    phases_activees = np.zeros(len(bornes_vitesse), dtype=np.bool_)
    
    # Variables globales
    phase_actuelle = 0
    moteur_actif = False
    moteur_elec_actif = False
    moteur_actif_last = False
    joules_elec = 0.0
    t_last = 0.0
    v_last = 0.0
    recup_frein_effectuee = False
    redemarrage_effectue = False
    freinage_force = False
    energie_supercap = 3000

    energie_cinetique_initiale_freinage = 0.0
    # Listes pour tracking
    forces_temp = {"motor": [], "aero": [], "rolling": [], "gravity": [], "wind": [], "elec": []}
    regimes_moteur_temp = []
    regime_mot_elec_temp = []
    ratios_utilises_temp = []
    forces_calculees_temps = []
    joules_elec_temp = []
    energie_supercap_temp = []
    moteur_elec_etat_temp = []
    moteur_thermique_etat_temp = []
    energie_depart_supercap = energie_supercap 
    
    def equations_dynamiques_optimisees(t, etat):
        nonlocal phase_actuelle, moteur_actif, moteur_elec_actif, moteur_actif_last
        nonlocal joules_elec, t_last, v_last, phases_terminees, phases_activees
        nonlocal recup_frein_effectuee,redemarrage_effectue,freinage_force, energie_supercap
        nonlocal energie_cinetique_initiale_freinage,energie_depart_supercap

        pos, v, omega_m, conso = etat
        
        # Condition terminale
        if pos >= distance_totale:
            # Mise à jour des listes pour éviter les erreurs d'interpolation
            forces_calculees_temps.append(t)
            for key in forces_temp:
                forces_temp[key].append(0.0)
            regimes_moteur_temp.append(0.0)
            ratios_utilises_temp.append(0.0)
            if moteur_elec:
                regime_mot_elec_temp.append(0.0)
            joules_elec_temp.append(joules_elec)
            energie_supercap_temp.append(energie_supercap)
            moteur_elec_etat_temp.append(1.0 if moteur_elec_actif else 0.0)
            moteur_thermique_etat_temp.append(1.0 if moteur_actif else 0.0)
            
            return [0, 0, 0, 0]
        
        forces_calculees_temps.append(t)
        dt = t - t_last

        masse = params_array[3]
        

        energie_a_recuperer = max(energie_depart_supercap - energie_supercap, 0.0)
        energie_manquante = energie_a_recuperer / rendement_recup

        # Distance nécessaire au freinage avec cette décélération max
        d_freinage_theorique = energie_manquante / (masse * a_max_freinage)
        distance_restante = distance_totale - pos

        if not freinage_force and distance_restante <= d_freinage_theorique * 1.05:
            freinage_force = True

        # Récupération d'énergie de freinage pendant le freinage
        if freinage_force and not recup_frein_effectuee and v > 0.01:
            delta_ec = 0.5 * masse * (v_last**2 - v**2)
            energie_recuperee = rendement_recup * max(delta_ec, 0.0)
            energie_supercap += energie_recuperee

            if v < 0.01:
                recup_frein_effectuee = True
        # Redémarrage par moteur électrique
        if v < 0.5 and energie_supercap > 0 and not redemarrage_effectue:
            moteur_elec_actif = True
            moteur_actif = False

        # Si vitesse franchit le seuil d’embrayage : moteur thermique reprend
        if moteur_elec_actif and energie_supercap <= 0.0:
            print(f"[t={t:.2f}s] Vitesse atteinte avec 3000J: {v:.2f} m/s")
            moteur_elec_actif = False
            moteur_actif = True
            redemarrage_effectue = True

        # Gestion des phases avec njit
        moteur_actif, phase_actuelle, _, _ = gestion_phases_njit(
            v, v_last, phase_actuelle, bornes_flat,
            phases_terminees, phases_activees, moteur_actif
        )

        # Calcul du régime moteur
        if moteur_actif:
            rpm_moteur = omega_m * 60.0 / (2.0 * np.pi)
            couple_moteur = interp_linear_njit(rpm_moteur, interp_data.moteur_rpm, interp_data.moteur_couple)
        else:
            rpm_moteur = 0.0
            couple_moteur = 0
            
        # Moteur électrique
        if moteur_elec and moteur_elec_actif:
            omega_roue = v / params_array[4] if v > 0 else 0
            rpm_roue = max(omega_roue * 60.0 / (2.0 * np.pi), 0)
            rpm_mot_elec = rpm_roue *1.5
            couple_electrique = interp_linear_njit(rpm_mot_elec, interp_data.elec_rpm, interp_data.elec_couple)
            F_elec = couple_electrique * 1.5/ params_array[4]
        else:
            couple_electrique = 0.0
            rpm_mot_elec = 0.0
            F_elec = 0.0
        
        # Consommation supercap pendant usage électrique
        if moteur_elec_actif and v > 0.1:
            eta_elec = 0.6
            puissance_moteur_elec = F_elec * v  # en watts
            energie_utilisee = puissance_moteur_elec * dt / eta_elec
            energie_supercap = max(0.0, energie_supercap - energie_utilisee)


        # Calcul embrayage avec njit
        C_embre_max, embrayage_actif = calcul_embrayage_njit(
            omega_m, embrayage_params[0], embrayage_params[1], 
            embrayage_params[2], embrayage_params[3], 
            embrayage_params[4], embrayage_params[5]
        )
        
        # Ratio enviolo
        if enviolo_on:
            ratio_enviolo = interp_linear_njit(rpm_moteur, interp_data.env_rpm, interp_data.env_ratio)
        else:
            ratio_enviolo = 1.0
            
        # Calcul du slip et couple transmis
        effective_ratio = (params_array[8] * params_array[5] * (1.0/ratio_enviolo) * 
                          params_array[7] * params_array[9] * params_array[6])
        omega_cloche = (v * effective_ratio) / params_array[4] if v > 0 else 0
        slip = omega_m - omega_cloche
        amplitude_transmis = min(couple_moteur, C_embre_max)
        
        C_transmis_brut = amplitude_transmis if slip > 0 else 0.0
        
        # Interpolations pour la piste et le vent
        # Calcul de la pente
        delta_distance = np.diff(interp_data.distance_data)
        delta_altitude = np.diff(interp_data.altitude_data)
        angles_pente = np.arctan(delta_altitude / delta_distance)
        distance_pente = interp_data.distance_data[:-1]
        
        if pos < distance_pente[0]:
            angle_pente = angles_pente[0]
        elif pos > distance_pente[-1]:
            angle_pente = angles_pente[-1]
        else:
            angle_pente = interp_linear_njit(pos, distance_pente, angles_pente)
        
        heading = interp_linear_njit(pos, interp_data.distance_data, interp_data.heading_data)
        
        # Pour le Cx, on prend une valeur par défaut ou on interpole selon l'angle
        if vent_active:
            # Calcul de l'angle relatif du vent
            vx = vitesse_vent * np.cos(wind_angle_global)
            vy = vitesse_vent * np.sin(wind_angle_global)
            phi = np.arctan2(vy, vx) - heading
            phi = (phi + np.pi) % (2*np.pi) - np.pi
            angle_rel_deg = abs(np.degrees(phi))
            Cx_wind = interp_linear_njit(angle_rel_deg, interp_data.angle_data, interp_data.cx_data)
        else:
            Cx_wind = params_array[1]  # coefficient_trainee par défaut
        
        # Calcul des forces avec njit
        F_moteur, F_aero, F_roulement, F_gravite, F_wind = calcul_forces_njit(
            pos, v, couple_moteur, ratio_enviolo, C_transmis_brut,
            params_array[0], params_array[1], params_array[2], params_array[3],
            params_array[4], params_array[5], params_array[6], params_array[7],
            params_array[8], params_array[9], params_array[10], params_array[11],
            angle_pente, aero_active, gravite_active, vent_active,
            vitesse_vent, wind_angle_global, heading, Cx_wind
        )
        F_freinage = 0.0
        if freinage_force and v > 0.002:
            F_freinage = -params_array[3] * a_max_freinage  # F = m * a_max
        # Calcul des dérivées avec njit
        dpos_dt, dv_dt, domega_m_dt, roue_libre_active = calcul_dynamique_njit(
            pos, v, omega_m, couple_moteur, C_transmis_brut, ratio_enviolo,
            params_array[3], params_array[4], params_array[8], params_array[9],
            F_moteur, F_aero, F_roulement, F_gravite, F_wind, F_elec,F_freinage,
            moteur_actif, moteur_elec_actif, coef_aero, coef_roul
        )
        
        # Calcul de la consommation
        if rpm_moteur > 0 and moteur_actif:
            puissance_meca = rpm_moteur * couple_moteur * 2.0 * np.pi / 60.0
            puissance_tot = puissance_meca
            csp = interp_linear_njit(min(rpm_moteur, np.max(interp_data.moteur_rpm)), 
                                   interp_data.moteur_rpm, interp_data.moteur_csp)
            dconso_dt = (puissance_tot / 1000.0) * (csp / 3600.0)
        else:
            dconso_dt = 0.0
        
        # Consommation électrique
        joules_elec += 21.5 * dt  # Passive
        if moteur_actif and not moteur_actif_last:
            joules_elec += 400.0  # Redémarrage
        
        # Mise à jour des variables
        moteur_actif_last = moteur_actif
        t_last = t
        v_last = v
        
        # Stockage pour les graphiques
        forces_temp["motor"].append(F_moteur)
        forces_temp["aero"].append(F_aero)
        forces_temp["rolling"].append(F_roulement)
        forces_temp["gravity"].append(F_gravite)
        forces_temp["wind"].append(F_wind)
        forces_temp["elec"].append(F_elec)
        regimes_moteur_temp.append(rpm_moteur)
        ratios_utilises_temp.append(ratio_enviolo)
        if moteur_elec:
            regime_mot_elec_temp.append(rpm_mot_elec)
        moteur_elec_etat_temp.append(1.0 if moteur_elec_actif else 0.0)
        moteur_thermique_etat_temp.append(1.0 if moteur_actif else 0.0)
        energie_supercap_temp.append(energie_supercap)
        joules_elec_temp.append(joules_elec)
        
        return [dpos_dt, dv_dt, domega_m_dt, dconso_dt]
    
    # Résolution
    solution = solve_ivp(
        equations_dynamiques_optimisees,
        [0, temps_max],
        [0, 0, 0, 0],
        method='RK45',
        events=[lambda t, y: y[0] - distance_totale, lambda t, y: t - temps_max],
        max_step=0.005
    )
    
    # Post-traitement
    if len(forces_calculees_temps) == 0:
        print("Erreur: aucune donnée de force calculée")
        return None
    
    # Interpolation des résultats
    forces = {}
    for key in forces_temp:
        if len(forces_temp[key]) > 0:
            f_interp = interp1d(forces_calculees_temps, forces_temp[key],
                               bounds_error=False, fill_value='extrapolate')
            forces[key] = f_interp(solution.t)
        else:
            forces[key] = np.zeros_like(solution.t)
    
    if len(regimes_moteur_temp) > 0:
        f_interp_regime = interp1d(forces_calculees_temps, regimes_moteur_temp,
                                  bounds_error=False, fill_value='extrapolate')
        regimes_interp = f_interp_regime(solution.t)
    else:
        regimes_interp = np.zeros_like(solution.t)
    
    if len(ratios_utilises_temp) > 0:
        f_interp_ratio = interp1d(forces_calculees_temps, ratios_utilises_temp,
                                 bounds_error=False, fill_value='extrapolate')
        ratios_interp = f_interp_ratio(solution.t)
    else:
        ratios_interp = np.ones_like(solution.t)
    
    if len(joules_elec_temp) > 0:
        f_interp_elec = interp1d(forces_calculees_temps, joules_elec_temp,
                                bounds_error=False, fill_value='extrapolate')
        joules_elec_interp = f_interp_elec(solution.t)
    else:
        joules_elec_interp = np.zeros_like(solution.t)
    if len(energie_supercap_temp) > 0:
        f_interp_supercap = interp1d(forces_calculees_temps, energie_supercap_temp,
                                bounds_error=False, fill_value='extrapolate')
        energie_supercap_interp = f_interp_supercap(solution.t)
    else:
        energie_supercap_interp = np.zeros_like(solution.t)

    if len(moteur_thermique_etat_temp) > 0:
        f_interp_mot_th_etat = interp1d(forces_calculees_temps, moteur_thermique_etat_temp,
                                bounds_error=False, fill_value='extrapolate')
        moteur_thermique_etat_interp = f_interp_mot_th_etat(solution.t)
    else:
        moteur_thermique_etat_interp = np.zeros_like(solution.t)

    if len(moteur_elec_etat_temp) > 0:
        f_interp_mot_elec_etat = interp1d(forces_calculees_temps, moteur_elec_etat_temp,
                                bounds_error=False, fill_value='extrapolate')
        moteur_elec_etat_interp = f_interp_mot_elec_etat(solution.t)
    else:
        moteur_elec_etat_interp = np.zeros_like(solution.t)
    densite_ethanol=0.79
    densite_essence=0.75
    # Calculs finaux
    NCV_ethanol=26900
    NCV_gasoline = 42900
    conso_totale = solution.y[3][-1]
    conso_totale_ethanol = conso_totale / densite_ethanol
    conso_totale_ml=conso_totale_ethanol*(NCV_ethanol*densite_ethanol)/(NCV_gasoline*densite_essence)
    
    eff_moteur = 0.25
    eff_alternateur = 0.75
    ml_electrique = (joules_elec / eff_moteur / eff_alternateur) / (NCV_gasoline * densite_essence)
    ml_total = conso_totale_ml + ml_electrique
    
    if debug_mode:
        print(f"Consommation totale de carburant : {conso_totale_ml:.2f} ml")
        print(f"Énergie électrique consommée : {joules_elec:.2f} J")
        print(f"Équivalent essence pour l'électricité : {ml_electrique:.2f} ml")
        print(f"Consommation totale : {ml_total:.2f} ml")
    
    if plot:
        plot_results(solution.t, solution.y[0], solution.y[1], forces,
                    regimes_interp, ratios_interp, solution.y[3],
                    joules_elec_evolution=joules_elec_interp,
                    energie_supercap_evolution=energie_supercap_interp,
                    moteur_thermique_etat=moteur_thermique_etat_interp,
                    moteur_elec_etat=moteur_elec_etat_interp,
                    ml_total=ml_total)
    
    return (solution.t, solution.y[0], solution.y[1], forces, regimes_interp,
            conso_totale, conso_totale_ml, ratios_interp, solution.y[3],
            joules_elec_interp,energie_supercap_interp,moteur_thermique_etat_interp,
            moteur_elec_etat_interp,ml_total)

# =============================================================================
# 5) Fonctions de tracé
# =============================================================================

def plot_results(t_eval, position, vitesse, forces,
                 regimes_moteur, ratios_utilises, consommation,
                 joules_elec_evolution=None,
                 energie_supercap_evolution=None,
                 moteur_elec_etat=None,
                 moteur_thermique_etat=None,ml_total=None):
    fig, axs = plt.subplots(4, 2, figsize=(20, 20))

    # Position
    axs[0, 0].plot(t_eval, position, label="Position (m)")
    axs[0, 0].set_title("Position en fonction du temps")
    axs[0, 0].set_xlabel("Temps (s)")
    axs[0, 0].set_ylabel("Position (m)")
    axs[0, 0].legend()

    # Vitesse
    axs[0, 1].plot(t_eval, vitesse, label="Vitesse (m/s)", color="green")
    axs[0, 1].set_title("Vitesse en fonction du temps")
    axs[0, 1].set_xlabel("Temps (s)")
    axs[0, 1].set_ylabel("Vitesse (m/s)")
    axs[0, 1].legend()

    # Forces
    axs[1, 0].plot(t_eval, forces["aero"], label="Force aérodynamique (N)")
    axs[1, 0].plot(t_eval, forces["rolling"], label="Force de roulement (N)")
    axs[1, 0].plot(t_eval, forces["gravity"], label="Force gravitationnelle (N)")
    axs[1, 0].plot(t_eval, forces["wind"], label="Force du vent (N)")
    axs[1, 0].set_title("Forces appliquées au véhicule")
    axs[1, 0].set_xlabel("Temps (s)")
    axs[1, 0].set_ylabel("Force (N)")
    axs[1, 0].legend()

    # Régime moteur
    axs[1, 1].plot(t_eval, regimes_moteur, label="Régime moteur (RPM)", color="orange")
    axs[1, 1].set_title("Régime moteur en fonction du temps")
    axs[1, 1].set_xlabel("Temps (s)")
    axs[1, 1].set_ylabel("RPM")
    axs[1, 1].legend()

    # Rapport Enviolo
    axs[2, 0].plot(t_eval, ratios_utilises, label="Rapport Enviolo")
    axs[2, 0].set_title("Rapport Enviolo en fonction du temps")
    axs[2, 0].set_xlabel("Temps (s)")
    axs[2, 0].set_ylabel("Rapport")
    axs[2, 0].legend()

    # Force motrice
    axs[2, 1].plot(t_eval, forces["motor"], label="Force motrice (N)")
    axs[2, 1].set_title("Force motrice appliquée au véhicule")
    axs[2, 1].plot(t_eval, forces["elec"], label="Force moteur elec (N)")
    axs[2, 1].set_xlabel("Temps (s)")
    axs[2, 1].set_ylabel("Force (N)")
    axs[2, 1].legend()

    # Consommation thermique
    axs[3, 0].plot(t_eval, consommation / 0.75, label="Conso thermique cumulative (ml)", color="purple")
    axs[3, 0].set_title("Consommation carburant en fonction du temps")
    axs[3, 0].set_xlabel("Temps (s)")
    axs[3, 0].set_ylabel("Consommation (ml)")
    axs[3, 0].legend()

    # Consommation électrique
    if joules_elec_evolution is not None:
        axs[3, 1].plot(t_eval, joules_elec_evolution, label="Conso électrique (J)", color="red")
        axs[3, 1].set_title("Consommation électrique cumulée")
        axs[3, 1].set_xlabel("Temps (s)")
        axs[3, 1].set_ylabel("Énergie (J)")
        axs[3, 1].legend()

    plt.tight_layout()
    plt.show()

    if energie_supercap_evolution is not None and moteur_elec_etat is not None and moteur_thermique_etat is not None:
        fig, axs = plt.subplots(2, 1, figsize=(14, 10), sharex=True)

    # Tracé énergie supercaps
        axs[0].plot(t_eval, energie_supercap_evolution, label="Énergie supercaps (J)", color='green')

    # Détection de récupération : quand l’énergie augmente
        diff_energie = np.diff(energie_supercap_evolution)
        recup_indices = np.where(diff_energie > 1e-3)[0]  # seuil pour ignorer bruit

        if len(recup_indices) > 0:
            t_recup_debut = t_eval[recup_indices[0]]
            t_recup_fin = t_eval[recup_indices[-1]]

            axs[0].axvspan(t_recup_debut, t_recup_fin, color='lime', alpha=0.3, label="Zone de récupération")

    axs[0].set_ylabel("Énergie (Joules)")
    axs[0].set_title("Évolution de l'énergie dans les supercondensateurs")
    axs[0].legend()
    axs[0].grid(True)

    # Tracé état des moteurs
    axs[1].plot(t_eval, moteur_elec_etat, label="Moteur électrique actif", color='blue', drawstyle='steps-post')
    axs[1].plot(t_eval, moteur_thermique_etat, label="Moteur thermique actif", color='red', drawstyle='steps-post')
    axs[1].set_xlabel("Temps (s)")
    axs[1].set_ylabel("État (0=off, 1=on)")
    axs[1].set_title("État des moteurs au cours du temps")
    axs[1].legend()
    axs[1].grid(True)

    plt.tight_layout()
    plt.show()
        
    plt.figure(figsize=(12, 6))
    plt.plot(position, vitesse, label='Vitesse (m/s)', color='blue', linewidth=2)
    plt.xlabel("Position (m)")
    plt.ylabel("Vitesse (m/s)")
    plt.title("Profil de vitesse sur le circuit")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()

    plt.figure(figsize=(12, 10))
# Interpolation des coordonnées X et Y pour les points du véhicule
    pos_x_interp = np.interp(position, np.linspace(0, distance.iloc[-1], len(pos_x)), pos_x)
    pos_y_interp = np.interp(position, np.linspace(0, distance.iloc[-1], len(pos_y)), pos_y)
# Tracé du circuit
    circuit_x = np.interp(np.linspace(0, distance.iloc[-1], 1000), 
                  np.linspace(0, distance.iloc[-1], len(pos_x)), pos_x)
    circuit_y = np.interp(np.linspace(0, distance.iloc[-1], 1000), 
                     np.linspace(0, distance.iloc[-1], len(pos_y)), pos_y)
    plt.plot(circuit_x, circuit_y, 'lightgray', linewidth=3, zorder=1, label='Circuit')
# Tracé des points avec code couleur selon les régimes moteur
    scatter = plt.scatter(pos_x_interp, pos_y_interp, c=regimes_moteur, 
                  cmap='viridis', s=15, zorder=2)
# Ajout de la barre de couleur
    cbar = plt.colorbar(scatter)
    cbar.set_label('Engine RPM (RPM)',fontsize=12)
# Marqueurs de départ et d'arrivée
    plt.scatter(pos_x_interp[0], pos_y_interp[0], marker='o', color='green', s=100, label='Starting line', zorder=3)
    plt.scatter(pos_x_interp[-1], pos_y_interp[-1], marker='x', color='red', s=100, label='Finish line', zorder=3)
# Détection des phases moteur actives
    regimes_moteur = np.array(regimes_moteur)
    is_on = regimes_moteur > 0
    changes = np.diff(is_on.astype(int))
    starts = np.where(changes == 1)[0] + 1
    ends = np.where(changes == -1)[0] + 1
# Gestion du cas où ça commence ou finit moteur allumé
    if is_on[0]: starts = np.insert(starts, 0, 0)
    if is_on[-1]: ends = np.append(ends, len(regimes_moteur) - 1)
# Définir les bornes de vitesse à annoter
    bornes_v = bornes_vitesse
    dx = 15  # décalage horizontal
    dy = 10  # décalage vertical
    point_size = 60  # taille des points de début/fin
    for i, (start, end) in enumerate(zip(starts, ends)):
        if i < len(bornes_v):
            v_start, v_end = bornes_v[i]
            x_start, y_start = pos_x_interp[start], pos_y_interp[start]
            x_end, y_end = pos_x_interp[end], pos_y_interp[end]
        # Points visibles
            plt.scatter(x_start, y_start, s=point_size, color='blue', zorder=5)
            plt.scatter(x_end, y_end, s=point_size, color='orange', zorder=5)
    # Texte décalé pour éviter de superposer le circuit
            plt.text(x_start + dx, y_start + dy, f"{v_start:.1f} m/s",
             fontsize=10, color='black', ha='left', va='bottom', weight='bold')
            plt.text(x_end + dx, y_end + dy, f"{v_end:.1f} m/s",
                 fontsize=10, color='black', ha='left', va='bottom', weight='bold')
    #flèche
            plt.annotate('', 
                 xy=(x_end + dx/2, y_end + dy/2), 
                 xytext=(x_end, y_end), 
                 arrowprops=dict(arrowstyle="-", color='gray', lw=1, linestyle='dotted'),
                 zorder=3)
            plt.annotate('', 
                 xy=(x_start + dx, y_start + dy), 
                 xytext=(x_start, y_start), 
                 arrowprops=dict(arrowstyle="-", color='gray', lw=1, linestyle='dotted'),
                 zorder=3)

# Récupérer les limites du graphique pour positionner le texte
    xlim = plt.xlim()
    ylim = plt.ylim()
# Positionner le texte en haut à droite (95% en x, 95% en y)
    x_text = xlim[0] + 0.95 * (xlim[1] - xlim[0])
    y_text = ylim[0] + 0.95 * (ylim[1] - ylim[0])
# Ajouter le texte avec la consommation (il faut que ml_total soit accessible)
    plt.text(x_text, y_text, f"Total consumption:\n{ml_total:.1f} ml", 
         fontsize=12, ha='right', va='top', weight='bold',
         bbox=dict(boxstyle="round,pad=0.3", facecolor='white', alpha=0.8, edgecolor='black'))

# Configuration finale
    plt.title("Strategy used around the track",fontsize=14)
    plt.xlabel('X (m)')
    plt.ylabel('Y (m)')
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend(loc='upper right')
    plt.axis('equal')
    plt.tight_layout()
    plt.show()

def save_simulation_data_to_csv(t_eval, position, vitesse, forces, regimes_moteur, 
                               ratios_utilises, consommation, joules_elec_evolution, 
                               energie_supercap_evolution,
                               moteur_thermique_etat,
                               moteur_elec_etat,
                               file_name="silesia_opti_6_accèl.csv"):
    """Fonction de sauvegarde des résultats"""
    data = {
        "Time (s)": t_eval,
        "Position (m)": position,
        "Velocity (m/s)": vitesse,
        "Force Motor (N)": forces["motor"],
        "Force Aero (N)": forces["aero"],
        "Force Rolling (N)": forces["rolling"],
        "Force Gravity (N)": forces["gravity"],
        "Force Wind (N)": forces["wind"],
        "Engine RPM": regimes_moteur,
        "Enviolo Ratio": ratios_utilises,
        "Cumulative Fuel Consumption (g)": consommation,
        "Electricity consumed (J)": joules_elec_evolution,
        "Supercap Energy (J)": energie_supercap_evolution,
        "Moteur Thermique Actif": moteur_thermique_etat,
        "Moteur Électrique Actif": moteur_elec_etat
    }
    df = pd.DataFrame(data)
    df.to_csv(file_name, index=False, encoding="utf-8")
    print(f"Données de simulation sauvegardées dans {file_name}")

# =============================================================================
# 6) Exécution principale
# =============================================================================

if __name__ == "__main__":

    
    # Configuration de la simulation
    print("Configuration de la simulation:")
    
    # Paramètres de la simulation

    distance_totale = distance.iloc[-1]

    
    print(f"- Distance totale: {distance_totale:.0f} m")
    print(f"- Bornes de vitesse: {bornes_vitesse}")
    print(f"- Temps maximum: {temps_max} s")
    
    # Mesure du temps d'exécution
    print("\n Démarrage de la simulation...")
    start_time = time.time()
    
    try:
        # Lancement de la simulation optimisée
        result = simuler_vehicule_optimise(
            distance_totale=distance_totale,
            bornes_vitesse=bornes_vitesse,
            temps_max=temps_max,
            vent_active=False,
            vitesse_vent=6*0.514,
            wind_angle_global=np.deg2rad(270),
            aero_active=True,
            gravite_active=True,
            enviolo_on=True,
            moteur_elec=True,
            coef_aero=1.63,
            coef_roul=1.0,
            plot=True,
            debug_mode=True
        )
        
        execution_time = time.time() - start_time
        print(f"\n Simulation terminée avec succès!")
        print(f" Temps d'exécution: {execution_time:.2f} secondes")
        
        if result:
            # Extraction des résultats
            (t_eval, pos, vit, forces, rpm, conso_g, conso_ml, ratios, consosdt,
            joules_elec, energie_supercap, moteur_th_etat, moteur_elec_etat,ml_total) = result
            
            # Sauvegarde des résultats
            save_simulation_data_to_csv(
                t_eval=t_eval,
                position=pos,
                vitesse=vit,
                forces=forces,
                regimes_moteur=rpm,
                ratios_utilises=ratios,
                consommation=consosdt,
                joules_elec_evolution=joules_elec,
                energie_supercap_evolution=energie_supercap,
                moteur_thermique_etat=moteur_th_etat,
                moteur_elec_etat=moteur_elec_etat,
                file_name=nom_fichier
                )
            t_reel=t_eval[-1]
            # Affichage des résultats finaux
            energie_utilisee = energie_supercap[0] - np.min(energie_supercap)
            energie_recuperee = energie_supercap[-1] - np.min(energie_supercap)
            resultat_11=(distance_totale*11)/(ml_total*11)
            

            print(f"\n Énergie supercaps utilisée: {energie_utilisee:.1f} J")
            print(f" Énergie récupérée par freinage: {energie_recuperee:.1f} J")
            print(f" Énergie nette restante en fin de course: {energie_supercap[-1]:.1f} J")
            print(f"- Consommation de carburant: {conso_ml:.2f} ml")
            print(f"- Énergie électrique: {joules_elec[-1]:.0f} J")
            print(f"- Consommation totale pour un tour: {ml_total:.2f} ml")
            print(f"- Temps de parcours: {t_reel:.1f} s")
            print(f"- Vitesse moyenne: {(pos[-1]/t_reel*3.6):.1f} km/h")
            print(f"- Résultat en km/l pour 11 tours: {resultat_11:.1f} km/l")
            
        else:
            print("Erreur lors de la simulation")
            
    except FileNotFoundError as e:
        print(f"Fichier manquant: {e}")
        print("Vérifiez que tous les fichiers de données sont présents:")
        print("- moteur_consomini.csv")
        print("- moteur_elec.csv")
        print("- data_enviolo.csv") 
        print("- sem_2025_eu.csv")
        print("- Cx_voiture_vent.xlsx")
        
    except Exception as e:
        print(f"Erreur lors de l'exécution: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "="*50)
    print("Fin de la simulation") 


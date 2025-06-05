# -*- coding: utf-8 -*-
"""
Created on Thu Jun  5 18:30:32 2025

@author: olivi
"""


import sys
import os
import importlib.util
import pandas as pd
import numpy as np
import json
import traceback
from typing import Tuple, Dict, List, Optional
import streamlit as st

class EtaOneSimulationWrapper:
    """Wrapper pour la simulation Eta-One"""
    
    def __init__(self, simulation_module_path: str = "modele_simulation_silesia_hybridation.py"):
        """
        Initialise le wrapper avec le chemin vers ton module de simulation
        
        Args:
            simulation_module_path: Chemin vers ton fichier de simulation
        """
        self.simulation_module = None
        self.module_path = simulation_module_path
        self.load_simulation_module()
        
        # Configuration par défaut
        self.default_config = {
            'distance_totale': 1321,  # Distance du circuit Sosnová
            'temps_max': 189,
            'vent_active': False,
            'vitesse_vent': 0,
            'wind_angle_global': 0,
            'aero_active': True,
            'gravite_active': True,
            'enviolo_on': True,
            'moteur_elec': True,
            'coef_aero': 1.63,
            'coef_roul': 1.0,
            'plot': False,  # Désactivé pour Streamlit
            'debug_mode': False
        }
    
    def load_simulation_module(self):
        """Charge dynamiquement le module de simulation"""
        try:
            if not os.path.exists(self.module_path):
                raise FileNotFoundError(f"Module de simulation non trouvé: {self.module_path}")
            
            spec = importlib.util.spec_from_file_location("simulation", self.module_path)
            self.simulation_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(self.simulation_module)
            
            print(f"✅ Module de simulation chargé: {self.module_path}")
            return True
            
        except Exception as e:
            print(f"❌ Erreur lors du chargement du module: {e}")
            self.simulation_module = None
            return False
    
    def validate_bornes_vitesse(self, bornes_vitesse: List[Tuple[float, float]]) -> bool:
        """Valide les bornes de vitesse"""
        if not bornes_vitesse:
            return False
        
        for i, (v_min, v_max) in enumerate(bornes_vitesse):
            if v_min >= v_max:
                raise ValueError(f"Phase {i+1}: vitesse min ({v_min}) >= vitesse max ({v_max})")
            if v_min < 0 or v_max < 0:
                raise ValueError(f"Phase {i+1}: vitesses négatives non autorisées")
            if v_max > 15:  # Limite raisonnable
                raise ValueError(f"Phase {i+1}: vitesse max ({v_max}) trop élevée (>15 m/s)")
        
        return True
    
    def run_simulation(self, 
                      bornes_vitesse: List[Tuple[float, float]],
                      **kwargs) -> Optional[Dict]:
        """
        Lance une simulation avec les paramètres donnés
        
        Args:
            bornes_vitesse: Liste des bornes de vitesse [(min1, max1), (min2, max2), ...]
            **kwargs: Autres paramètres de simulation
            
        Returns:
            Dictionnaire avec les résultats de simulation ou None si erreur
        """
        
        if not self.simulation_module:
            raise RuntimeError("Module de simulation non chargé")
        
        # Validation des paramètres
        self.validate_bornes_vitesse(bornes_vitesse)
        
        # Fusion avec la configuration par défaut
        config = {**self.default_config, **kwargs}
        
        try:
            print(f"🚀 Lancement simulation avec {len(bornes_vitesse)} phases")
            print(f"   Bornes: {bornes_vitesse}")
            print(f"   Temps max: {config['temps_max']}s")
            
            # Appel de ta fonction de simulation
            result = self.simulation_module.simuler_vehicule_optimise(
                distance_totale=config['distance_totale'],
                bornes_vitesse=bornes_vitesse,
                temps_max=config['temps_max'],
                vent_active=config['vent_active'],
                vitesse_vent=config['vitesse_vent'],
                wind_angle_global=config['wind_angle_global'],
                aero_active=config['aero_active'],
                gravite_active=config['gravite_active'],
                enviolo_on=config['enviolo_on'],
                moteur_elec=config['moteur_elec'],
                coef_aero=config['coef_aero'],
                coef_roul=config['coef_roul'],
                plot=config['plot'],
                debug_mode=config['debug_mode']
            )
            
            if result is None:
                return None
            
            # Extraction et formatage des résultats
            (t_eval, position, vitesse, forces, regimes_moteur,
             conso_g, conso_ml, ratios_utilises, conso_cumul,
             joules_elec, energie_supercap, moteur_th_etat, 
             moteur_elec_etat, ml_total) = result
            
            # Calcul de métriques dérivées
            temps_total = t_eval[-1]
            distance_finale = position[-1]
            vitesse_moyenne = (distance_finale / temps_total) * 3.6  # km/h
            efficacite = (distance_finale / 1000) / (ml_total / 1000)  # km/l
            
            # Formatage des résultats pour Streamlit
            simulation_results = {
                # Métriques principales
                'temps_total': temps_total,
                'distance_finale': distance_finale,
                'consommation_ml': ml_total,
                'consommation_thermique': conso_ml,
                'energie_electrique_j': joules_elec[-1],
                'vitesse_moyenne': vitesse_moyenne,
                'efficacite_km_l': efficacite,
                
                # Données temporelles
                'temps': t_eval.tolist(),
                'position': position.tolist(),
                'vitesse': vitesse.tolist(),
                'vitesse_kmh': (vitesse * 3.6).tolist(),
                'regimes_moteur': regimes_moteur.tolist(),
                'ratios_enviolo': ratios_utilises.tolist(),
                'consommation_cumul': conso_cumul.tolist(),
                'energie_supercap': energie_supercap.tolist(),
                'joules_elec': joules_elec.tolist(),
                'moteur_thermique_actif': moteur_th_etat.tolist(),
                'moteur_electrique_actif': moteur_elec_etat.tolist(),
                
                # Forces
                'forces': {
                    'moteur': forces['motor'].tolist(),
                    'aerodynamique': forces['aero'].tolist(),
                    'roulement': forces['rolling'].tolist(),
                    'gravite': forces['gravity'].tolist(),
                    'vent': forces['wind'].tolist(),
                    'electrique': forces['elec'].tolist()
                },
                
                # Configuration utilisée
                'config': {
                    'bornes_vitesse': bornes_vitesse,
                    'temps_max': config['temps_max'],
                    'coef_aero': config['coef_aero'],
                    'coef_roul': config['coef_roul'],
                    'moteur_elec': config['moteur_elec'],
                    'enviolo_on': config['enviolo_on']
                },
                
                # Statut
                'success': True,
                'message': f"Simulation réussie en {temps_total:.1f}s"
            }
            
            print(f"✅ Simulation terminée:")
            print(f"   Temps: {temps_total:.1f}s")
            print(f"   Consommation: {ml_total:.1f}ml")
            print(f"   Efficacité: {efficacite:.1f}km/l")
            
            return simulation_results
            
        except Exception as e:
            error_msg = f"Erreur simulation: {str(e)}"
            print(f"❌ {error_msg}")
            traceback.print_exc()
            
            return {
                'success': False,
                'error': error_msg,
                'message': f"Échec de la simulation: {type(e).__name__}"
            }
    
    def optimize_strategy(self, 
                         objective: str = "efficiency",
                         constraints: Dict = None,
                         n_iterations: int = 50) -> Dict:
        """
        Optimise la stratégie selon un objectif donné
        
        Args:
            objective: "time", "consumption", "efficiency"
            constraints: Contraintes (temps_max, conso_max)
            n_iterations: Nombre d'itérations
            
        Returns:
            Résultats d'optimisation
        """
        
        if not self.simulation_module:
            raise RuntimeError("Module de simulation non chargé")
        
        if constraints is None:
            constraints = {'temps_max': 200, 'conso_max': 60}
        
        print(f"🎯 Optimisation pour objectif: {objective}")
        print(f"   Contraintes: {constraints}")
        print(f"   Itérations: {n_iterations}")
        
        best_results = []
        best_overall = None
        best_score = float('inf') if objective in ['time', 'consumption'] else 0
        
        for iteration in range(n_iterations):
            try:
                # Génération aléatoire de bornes de vitesse
                n_phases = np.random.randint(3, 7)  # 3-6 phases
                bornes_vitesse = []
                
                for i in range(n_phases):
                    v_base = 6 + i * 0.8  # Progression logique
                    v_min = v_base + np.random.uniform(-1, 1)
                    v_max = v_min + np.random.uniform(1, 3)
                    
                    # Contraintes de bon sens
                    v_min = max(2, min(12, v_min))
                    v_max = max(v_min + 0.5, min(15, v_max))
                    
                    bornes_vitesse.append((v_min, v_max))
                
                # Variation des autres paramètres
                config = {
                    'coef_aero': np.random.uniform(1.4, 2.0),
                    'coef_roul': np.random.uniform(0.8, 1.2),
                    'temps_max': constraints['temps_max']
                }
                
                # Simulation
                result = self.run_simulation(bornes_vitesse, **config)
                
                if result and result['success']:
                    # Vérification des contraintes
                    temps = result['temps_total']
                    conso = result['consommation_ml']
                    efficacite = result['efficacite_km_l']
                    
                    if temps <= constraints['temps_max'] and conso <= constraints['conso_max']:
                        # Calcul du score selon l'objectif
                        if objective == 'time':
                            score = temps
                        elif objective == 'consumption':
                            score = conso
                        else:  # efficiency
                            score = efficacite
                        
                        result_summary = {
                            'iteration': iteration + 1,
                            'bornes_vitesse': bornes_vitesse,
                            'temps': temps,
                            'consommation': conso,
                            'efficacite': efficacite,
                            'score': score,
                            'config': config
                        }
                        
                        best_results.append(result_summary)
                        
                        # Nouveau meilleur résultat ?
                        if objective in ['time', 'consumption']:
                            if score < best_score:
                                best_score = score
                                best_overall = result_summary
                        else:  # efficiency
                            if score > best_score:
                                best_score = score
                                best_overall = result_summary
                
                # Progression
                if (iteration + 1) % 10 == 0:
                    print(f"   Itération {iteration + 1}/{n_iterations}")
                    
            except Exception as e:
                print(f"   Erreur itération {iteration + 1}: {e}")
                continue
        
        # Tri des résultats
        if objective in ['time', 'consumption']:
            best_results.sort(key=lambda x: x['score'])
        else:
            best_results.sort(key=lambda x: x['score'], reverse=True)
        
        optimization_results = {
            'objective': objective,
            'n_iterations': n_iterations,
            'n_valid_results': len(best_results),
            'best_result': best_overall,
            'top_10_results': best_results[:10],
            'all_results': best_results,
            'constraints': constraints
        }
        
        if best_overall:
            print(f"✅ Optimisation terminée:")
            print(f"   Meilleur {objective}: {best_overall['score']:.2f}")
            print(f"   Configuration: {len(best_overall['bornes_vitesse'])} phases")
        else:
            print(f"❌ Aucun résultat valide trouvé")
        
        return optimization_results
    
    def export_results(self, results: Dict, filename: str = None) -> str:
        """Exporte les résultats vers un fichier CSV"""
        
        if filename is None:
            timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
            filename = f"eta_one_results_{timestamp}.csv"
        
        try:
            # Création d'un DataFrame avec les résultats temporels
            df = pd.DataFrame({
                'Temps (s)': results['temps'],
                'Position (m)': results['position'],
                'Vitesse (m/s)': results['vitesse'],
                'Vitesse (km/h)': results['vitesse_kmh'],
                'Régime moteur (RPM)': results['regimes_moteur'],
                'Ratio Enviolo': results['ratios_enviolo'],
                'Consommation cumul (g)': results['consommation_cumul'],
                'Énergie supercap (J)': results['energie_supercap'],
                'Énergie élec cumul (J)': results['joules_elec'],
                'Moteur thermique': results['moteur_thermique_actif'],
                'Moteur électrique': results['moteur_electrique_actif'],
                'Force moteur (N)': results['forces']['moteur'],
                'Force aéro (N)': results['forces']['aerodynamique'],
                'Force roulement (N)': results['forces']['roulement'],
                'Force gravité (N)': results['forces']['gravite']
            })
            
            df.to_csv(filename, index=False, encoding='utf-8')
            print(f"✅ Résultats exportés vers: {filename}")
            return filename
            
        except Exception as e:
            print(f"❌ Erreur export: {e}")
            return None

# =============================================================================
# FONCTIONS UTILITAIRES POUR STREAMLIT
# =============================================================================

@st.cache_data
def get_simulation_wrapper():
    """Retourne une instance du wrapper (avec cache Streamlit)"""
    return EtaOneSimulationWrapper()

def run_cached_simulation(bornes_vitesse_str: str, config_str: str):
    """Version cachée de la simulation pour Streamlit"""
    import json
    
    wrapper = get_simulation_wrapper()
    bornes_vitesse = json.loads(bornes_vitesse_str)
    config = json.loads(config_str)
    
    return wrapper.run_simulation(bornes_vitesse, **config)

def format_simulation_results_for_display(results: Dict) -> Dict:
    """Formate les résultats pour l'affichage Streamlit"""
    
    if not results['success']:
        return results
    
    # Métriques principales formatées
    formatted = {
        'metrics': {
            'Temps Total': f"{results['temps_total']:.1f} s",
            'Consommation': f"{results['consommation_ml']:.1f} ml",
            'Énergie Électrique': f"{results['energie_electrique_j']:.0f} J",
            'Vitesse Moyenne': f"{results['vitesse_moyenne']:.1f} km/h",
            'Efficacité': f"{results['efficacite_km_l']:.1f} km/l"
        },
        'raw_data': results,
        'success': True
    }
    
    return formatted

# =============================================================================
# EXEMPLE D'UTILISATION
# =============================================================================

if __name__ == "__main__":
    # Test du wrapper
    wrapper = EtaOneSimulationWrapper()
    
    # Test d'une simulation simple
    bornes_test = [(6.0, 8.5), (7.0, 8.8), (6.5, 8.3), (7.2, 9.0), (6.4, 8.9)]
    
    print("🧪 Test de simulation...")
    result = wrapper.run_simulation(bornes_test, temps_max=189)
    
    if result and result['success']:
        print("✅ Test réussi!")
        
        # Test d'optimisation
        print("\n🧪 Test d'optimisation...")
        optim_result = wrapper.optimize_strategy(
            objective='efficiency',
            constraints={'temps_max': 200, 'conso_max': 50},
            n_iterations=20
        )
        
        if optim_result['best_result']:
            print("✅ Optimisation réussie!")
        else:
            print("❌ Optimisation échouée")
    else:
        print("❌ Test de simulation échoué")
# -*- coding: utf-8 -*-
"""
Created on Thu Jun  5 18:31:39 2025

@author: olivi
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import streamlit.components.v1 as components
import requests
import json
import time
from datetime import datetime
import subprocess
import sys
import os

# Configuration de la page
st.set_page_config(
    page_title="Eta-One Racing",
    page_icon="🏁",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé pour l'interface
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: linear-gradient(90deg, #f0f2f6, #ffffff);
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
    }
    .status-good { color: #28a745; font-weight: bold; }
    .status-warning { color: #ffc107; font-weight: bold; }
    .status-danger { color: #dc3545; font-weight: bold; }
    .stButton > button {
        background-color: #1f77b4;
        color: white;
        border-radius: 8px;
        border: none;
        padding: 0.5rem 1rem;
        transition: all 0.3s;
    }
    .stButton > button:hover {
        background-color: #0d47a1;
        transform: translateY(-2px);
    }
</style>
""", unsafe_allow_html=True)

# Titre principal
st.markdown('<h1 class="main-header">🏁 Eta-One Racing - Système Intégré</h1>', unsafe_allow_html=True)

# Sidebar pour navigation
st.sidebar.title("🚗 Navigation")
page = st.sidebar.selectbox(
    "Sélectionner une page",
    ["🏁 Position Live & Circuit", "⚙️ Simulation", "🔧 Optimisation", "📊 Analyses"]
)

# Configuration globale
if 'simulation_running' not in st.session_state:
    st.session_state.simulation_running = False
if 'current_strategy' not in st.session_state:
    st.session_state.current_strategy = 'normal'
if 'circuit_data' not in st.session_state:
    st.session_state.circuit_data = None

# =============================================================================
# PAGE 1: POSITION LIVE & CIRCUIT
# =============================================================================

if page == "🏁 Position Live & Circuit":
    st.header("🗺️ Position en Temps Réel et Gestion de Stratégie")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Carte Interactive du Circuit")
        
        # Intégration de ton système HTML/JS existant
        tracking_html = """
        <!DOCTYPE html>
        <html lang="fr">
        <head>
          <meta charset="UTF-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0" />
          <title>Suivi Eta-One</title>
          <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
          <style>
            html, body, #map { margin: 0; padding: 0; height: 500px; }
            .info-panel {
              position: absolute;
              top: 10px;
              left: 10px;
              background: rgba(255, 255, 255, 0.95);
              padding: 10px;
              border-radius: 8px;
              font-family: Arial, sans-serif;
              z-index: 1000;
              min-width: 200px;
            }
            .strategy-panel {
              position: absolute;
              top: 10px;
              right: 10px;
              background: rgba(255, 255, 255, 0.95);
              padding: 15px;
              border-radius: 8px;
              font-family: Arial, sans-serif;
              z-index: 1000;
              min-width: 250px;
            }
            .status-ok { color: #28a745; font-weight: bold; }
            .status-warning { color: #ffc107; font-weight: bold; }
            .status-danger { color: #dc3545; font-weight: bold; }
            .btn {
              padding: 8px 15px;
              margin: 5px 2px;
              border: none;
              border-radius: 5px;
              cursor: pointer;
              font-size: 14px;
            }
            .btn-eco { background: #28a745; color: white; }
            .btn-normal { background: #007bff; color: white; }
            .btn-attack { background: #dc3545; color: white; }
          </style>
        </head>
        <body>
          <div id="map"></div>
          
          <div class="info-panel">
            <h4>📍 Position</h4>
            <div><strong>Coords:</strong> <span id="coords">--, --</span></div>
            <div><strong>Secteur:</strong> <span id="secteur">--</span></div>
            <div><strong>Vitesse opt:</strong> <span id="vitesse-opt">-- km/h</span></div>
            <div><strong>Temps:</strong> <span id="temps">--</span></div>
            <div><strong>Retard:</strong> <span id="retard" class="status-ok">+0.0s</span></div>
          </div>

          <div class="strategy-panel">
            <h4>🏁 Stratégie</h4>
            <div style="margin: 10px 0;">
              <button class="btn btn-eco" onclick="changerStrategie('economie')">🔋 Économie</button>
              <button class="btn btn-normal" onclick="changerStrategie('normal')">🏃 Normal</button>
              <button class="btn btn-attack" onclick="changerStrategie('attaque')">⚡ Attaque</button>
            </div>
            <div id="strategy-info">
              <div>Mode: <strong id="mode-actuel">Normal</strong></div>
              <div>Tour optimal: <strong>81.6s</strong></div>
            </div>
          </div>

          <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
          <script>
            // Configuration du circuit
            const circuitConfig = {
              centre: [50.529211, 18.093939],
              zoom: 16,
              secteurs: [
                {id: 0, debut: [50.52927545, 18.09601748], vitesseOptimale: 68, tempsOptimal: 2.1},
                {id: 1, debut: [50.52919987, 18.09628445], vitesseOptimale: 57, tempsOptimal: 2.5},
                {id: 2, debut: [50.52917447, 18.09645162], vitesseOptimale: 43, tempsOptimal: 3.3}
                // Secteurs simplifiés pour la démo
              ]
            };

            // Initialisation de la carte
            const map = L.map('map').setView(circuitConfig.centre, circuitConfig.zoom);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
              maxZoom: 19,
            }).addTo(map);

            // Tracé du circuit
            const traceCircuit = [
              [50.52927545, 18.09601748], [50.52919987, 18.09628445], 
              [50.52917447, 18.09645162], [50.52913776, 18.09657364],
              [50.52908994, 18.09666081], [50.52904102, 18.09670833],
              [50.52898118, 18.09673132], [50.52891061, 18.09671017],
              [50.5288493, 18.09666918], [50.52927545, 18.09601748]
            ];

            const circuitLine = L.polyline(traceCircuit, {
              color: '#0066cc',
              weight: 5,
              opacity: 0.8
            }).addTo(map);

            // Variables de simulation
            let marker = null;
            let tempsDepart = Date.now();
            let secteurActuel = 0;
            let strategieActuelle = 'normal';

            // Fonction de changement de stratégie
            function changerStrategie(nouveauMode) {
              strategieActuelle = nouveauMode;
              document.getElementById('mode-actuel').textContent = 
                nouveauMode.charAt(0).toUpperCase() + nouveauMode.slice(1);
              
              // Envoi à Streamlit via postMessage
              parent.postMessage({
                type: 'strategy_change',
                strategy: nouveauMode,
                timestamp: Date.now()
              }, '*');
              
              console.log('🏁 Stratégie changée:', nouveauMode);
            }

            // Simulation de position (remplace par tes vraies données GPS)
            function simulerPosition() {
              const temps = (Date.now() - tempsDepart) / 1000;
              const progression = (temps * 0.01) % 1; // Progression circulaire
              const index = Math.floor(progression * (traceCircuit.length - 1));
              const [lat, lon] = traceCircuit[index];
              
              // Simulation du retard
              const retard = Math.sin(temps * 0.1) * 5; // Retard simulé
              const retardStr = (retard >= 0 ? '+' : '') + retard.toFixed(1) + 's';
              
              // Mise à jour de l'affichage
              document.getElementById('coords').textContent = `${lat.toFixed(6)}, ${lon.toFixed(6)}`;
              document.getElementById('secteur').textContent = `${secteurActuel + 1}/27`;
              document.getElementById('vitesse-opt').textContent = '65 km/h';
              document.getElementById('temps').textContent = `${temps.toFixed(1)}s`;
              
              const retardEl = document.getElementById('retard');
              retardEl.textContent = retardStr;
              retardEl.className = retard < 2 ? 'status-ok' : retard < 5 ? 'status-warning' : 'status-danger';
              
              // Mise à jour du marqueur
              if (!marker) {
                marker = L.circleMarker([lat, lon], {
                  radius: 10,
                  fillColor: '#ff0000',
                  color: '#ffffff',
                  weight: 2,
                  fillOpacity: 0.9
                }).addTo(map);
              } else {
                marker.setLatLng([lat, lon]);
              }
              
              // Couleur selon le retard
              const couleur = retard < 2 ? '#00ff00' : retard < 5 ? '#ffa500' : '#ff0000';
              marker.setStyle({ fillColor: couleur });
            }

            // Démarrage de la simulation
            setInterval(simulerPosition, 100);
            
            console.log('🏁 Système de tracking Eta-One initialisé!');
          </script>
        </body>
        </html>
        """
        
        components.html(tracking_html, height=550)
    
    with col2:
        st.subheader("⚙️ Contrôles de Course")
        
        # Métriques en temps réel
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.metric("⏱️ Temps", "0:00", "0.0s")
            st.metric("🏃 Vitesse", "0 km/h", "0")
        with col_m2:
            st.metric("📍 Secteur", "1/27", "0")
            st.metric("📊 Retard", "+0.0s", "0.0s")
        
        st.markdown("---")
        
        # Contrôles de stratégie
        st.subheader("🎛️ Stratégies Disponibles")
        
        strategy_descriptions = {
            "Économie 🔋": "Réduit la vitesse de 15% pour économiser l'énergie",
            "Normal 🏃": "Stratégie optimale standard",
            "Attaque ⚡": "Augmente la vitesse de 20% pour rattraper le retard"
        }
        
        for strategy, description in strategy_descriptions.items():
            with st.expander(strategy):
                st.write(description)
        
        st.markdown("---")
        
        # Alertes automatiques
        st.subheader("🚨 Alertes")
        if st.checkbox("Alertes automatiques activées", value=True):
            st.info("✅ Le système passera automatiquement en mode Attaque si le retard dépasse 10 secondes")

# =============================================================================
# PAGE 2: SIMULATION
# =============================================================================

elif page == "⚙️ Simulation":
    st.header("🔧 Simulation du Véhicule Hybride")
    
    # Paramètres de simulation
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("🛠️ Paramètres de Simulation")
        
        # Bornes de vitesse
        st.markdown("**Bornes de vitesse (m/s)**")
        num_phases = st.slider("Nombre de phases d'accélération", 1, 8, 5)
        
        bornes_vitesse = []
        for i in range(num_phases):
            col_min, col_max = st.columns(2)
            with col_min:
                v_min = st.number_input(f"Phase {i+1} - Min", 
                                      min_value=0.0, max_value=15.0, 
                                      value=6.0 + i*0.5, step=0.1, 
                                      key=f"v_min_{i}")
            with col_max:
                v_max = st.number_input(f"Phase {i+1} - Max", 
                                      min_value=0.0, max_value=15.0, 
                                      value=8.0 + i*0.3, step=0.1, 
                                      key=f"v_max_{i}")
            bornes_vitesse.append((v_min, v_max))
        
        st.markdown("---")
        
        # Autres paramètres
        temps_max = st.slider("Temps maximum (s)", 100, 300, 189)
        
        # Conditions environnementales
        st.markdown("**Conditions**")
        vent_active = st.checkbox("Vent activé", value=False)
        if vent_active:
            vitesse_vent = st.slider("Vitesse du vent (m/s)", 0.0, 15.0, 3.0)
            angle_vent = st.slider("Angle du vent (°)", 0, 360, 270)
        else:
            vitesse_vent = 0
            angle_vent = 0
        
        aero_active = st.checkbox("Aérodynamique", value=True)
        gravite_active = st.checkbox("Gravité", value=True)
        enviolo_on = st.checkbox("Transmission Enviolo", value=True)
        moteur_elec = st.checkbox("Moteur électrique", value=True)
        
        # Coefficients
        st.markdown("**Coefficients**")
        coef_aero = st.slider("Coefficient aérodynamique", 0.5, 3.0, 1.63)
        coef_roul = st.slider("Coefficient de roulement", 0.5, 2.0, 1.0)
    
    with col2:
        st.subheader("🚀 Lancement de la Simulation")
        
        if st.button("▶️ Lancer la Simulation", key="run_sim"):
            st.session_state.simulation_running = True
            
            with st.spinner("🔄 Simulation en cours..."):
                # Simulation avec barre de progression
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Ici tu intégrerais ta fonction simuler_vehicule_optimise()
                # Pour la démo, on simule juste le processus
                for i in range(101):
                    progress_bar.progress(i)
                    status_text.text(f"Simulation: {i}%")
                    time.sleep(0.02)
                
                # Résultats simulés (remplace par tes vrais résultats)
                results = {
                    'temps_total': 185.3,
                    'consommation_ml': 42.5,
                    'energie_elec_j': 2845,
                    'vitesse_moyenne': 28.7,
                    'efficiency_km_l': 387.2
                }
                
                st.session_state.simulation_results = results
                status_text.text("✅ Simulation terminée!")
        
        # Affichage des résultats
        if 'simulation_results' in st.session_state:
            st.markdown("---")
            st.subheader("📊 Résultats de Simulation")
            
            results = st.session_state.simulation_results
            
            # Métriques principales
            col_r1, col_r2, col_r3 = st.columns(3)
            with col_r1:
                st.metric("⏱️ Temps Total", f"{results['temps_total']:.1f}s", "±0.0s")
                st.metric("⛽ Consommation", f"{results['consommation_ml']:.1f}ml", "-2.3ml")
            with col_r2:
                st.metric("🔋 Énergie Élec", f"{results['energie_elec_j']:.0f}J", "+150J")
                st.metric("🏃 Vitesse Moy", f"{results['vitesse_moyenne']:.1f}km/h", "+1.2km/h")
            with col_r3:
                st.metric("📈 Efficacité", f"{results['efficiency_km_l']:.1f}km/l", "+12.5km/l")
            
            # Graphiques simulés
            st.markdown("---")
            st.subheader("📈 Graphiques de Performance")
            
            # Génération de données simulées pour les graphiques
            time_sim = np.linspace(0, results['temps_total'], 1000)
            position_sim = np.cumsum(np.random.normal(1.5, 0.1, 1000))
            vitesse_sim = 20 + 10 * np.sin(time_sim * 0.1) + np.random.normal(0, 1, 1000)
            
            # Graphique vitesse
            fig_vitesse = go.Figure()
            fig_vitesse.add_trace(go.Scatter(
                x=time_sim, y=vitesse_sim,
                mode='lines', name='Vitesse',
                line=dict(color='blue', width=2)
            ))
            fig_vitesse.update_layout(
                title="Profil de Vitesse", 
                xaxis_title="Temps (s)", 
                yaxis_title="Vitesse (km/h)",
                height=400
            )
            st.plotly_chart(fig_vitesse, use_container_width=True)

# =============================================================================
# PAGE 3: OPTIMISATION
# =============================================================================

elif page == "🔧 Optimisation":
    st.header("🎯 Optimisation des Stratégies")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("🔍 Paramètres d'Optimisation")
        
        # Objectif d'optimisation
        objectif = st.selectbox(
            "Objectif principal",
            ["Minimiser la consommation", "Minimiser le temps", "Maximiser l'efficacité", "Équilibre temps/conso"]
        )
        
        # Contraintes
        st.markdown("**Contraintes**")
        temps_max_opti = st.slider("Temps maximum accepté (s)", 150, 250, 200)
        conso_max_opti = st.slider("Consommation maximum (ml)", 30, 80, 50)
        
        # Plages de variation des paramètres
        st.markdown("**Plages d'optimisation**")
        
        with st.expander("Bornes de vitesse"):
            st.info("L'optimiseur va tester différentes combinaisons de bornes de vitesse")
            nb_iterations = st.slider("Nombre d'itérations", 10, 100, 50)
        
        with st.expander("Paramètres véhicule"):
            optimize_aero = st.checkbox("Optimiser coefficient aérodynamique", value=True)
            optimize_roul = st.checkbox("Optimiser coefficient de roulement", value=False)
            optimize_timing = st.checkbox("Optimiser timing d'activation moteur", value=True)
        
        # Algorithme d'optimisation
        algo = st.selectbox(
            "Algorithme",
            ["Algorithme génétique", "Optimisation par essaims", "Recherche par grille", "Bayésien"]
        )
    
    with col2:
        st.subheader("🚀 Lancement de l'Optimisation")
        
        if st.button("🎯 Optimiser la Stratégie", key="optimize"):
            with st.spinner("🔄 Optimisation en cours..."):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Simulation du processus d'optimisation
                best_results = []
                for iteration in range(nb_iterations):
                    # Simulation d'une itération
                    progress_bar.progress((iteration + 1) / nb_iterations)
                    status_text.text(f"Itération {iteration + 1}/{nb_iterations}")
                    
                    # Résultats simulés pour chaque itération
                    result = {
                        'iteration': iteration + 1,
                        'temps': 180 + np.random.normal(0, 10),
                        'consommation': 45 + np.random.normal(0, 5),
                        'efficacite': 350 + np.random.normal(0, 30),
                        'bornes': [(6+np.random.random(), 8+np.random.random()) for _ in range(5)]
                    }
                    best_results.append(result)
                    time.sleep(0.1)
                
                st.session_state.optimization_results = best_results
                status_text.text("✅ Optimisation terminée!")
        
        # Affichage des résultats d'optimisation
        if 'optimization_results' in st.session_state:
            st.markdown("---")
            st.subheader("🏆 Meilleurs Résultats")
            
            results = st.session_state.optimization_results
            
            # Trouver le meilleur selon l'objectif
            if objectif == "Minimiser la consommation":
                best = min(results, key=lambda x: x['consommation'])
                metric_label = "Consommation"
                metric_value = f"{best['consommation']:.1f}ml"
            elif objectif == "Minimiser le temps":
                best = min(results, key=lambda x: x['temps'])
                metric_label = "Temps"
                metric_value = f"{best['temps']:.1f}s"
            else:
                best = max(results, key=lambda x: x['efficacite'])
                metric_label = "Efficacité"
                metric_value = f"{best['efficacite']:.1f}km/l"
            
            st.success(f"🎉 Meilleur résultat: {metric_label} = {metric_value}")
            
            # Tableau des meilleurs résultats
            df_results = pd.DataFrame([
                {
                    'Itération': r['iteration'],
                    'Temps (s)': f"{r['temps']:.1f}",
                    'Consommation (ml)': f"{r['consommation']:.1f}",
                    'Efficacité (km/l)': f"{r['efficacite']:.1f}"
                } for r in sorted(results, key=lambda x: x['efficacite'], reverse=True)[:10]
            ])
            
            st.dataframe(df_results, use_container_width=True)
            
            # Graphique de convergence
            fig_conv = go.Figure()
            
            temps_values = [r['temps'] for r in results]
            conso_values = [r['consommation'] for r in results]
            iterations = [r['iteration'] for r in results]
            
            fig_conv.add_trace(go.Scatter(
                x=iterations, y=temps_values,
                mode='lines+markers', name='Temps (s)',
                yaxis='y', line=dict(color='blue')
            ))
            
            fig_conv.add_trace(go.Scatter(
                x=iterations, y=conso_values,
                mode='lines+markers', name='Consommation (ml)',
                yaxis='y2', line=dict(color='red')
            ))
            
            fig_conv.update_layout(
                title="Convergence de l'Optimisation",
                xaxis_title="Itération",
                yaxis=dict(title="Temps (s)", side="left"),
                yaxis2=dict(title="Consommation (ml)", side="right", overlaying="y"),
                height=400
            )
            
            st.plotly_chart(fig_conv, use_container_width=True)

# =============================================================================
# PAGE 4: ANALYSES
# =============================================================================

elif page == "📊 Analyses":
    st.header("📈 Analyses et Comparaisons")
    
    # Comparaison de stratégies
    st.subheader("⚖️ Comparaison de Stratégies")
    
    # Données simulées pour comparaison
    strategies = ['Économie', 'Normal', 'Attaque', 'Optimisé']
    temps_data = [195.2, 185.3, 178.9, 182.1]
    conso_data = [38.5, 42.5, 48.2, 40.1]
    efficacite_data = [425.8, 387.2, 341.5, 410.3]
    
    df_comparison = pd.DataFrame({
        'Stratégie': strategies,
        'Temps (s)': temps_data,
        'Consommation (ml)': conso_data,
        'Efficacité (km/l)': efficacite_data
    })
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Graphique radar
        fig_radar = go.Figure()
        
        # Normalisation des données pour le radar
        temps_norm = [(200-t)/200*100 for t in temps_data]  # Plus c'est bas, mieux c'est
        conso_norm = [(60-c)/60*100 for c in conso_data]    # Plus c'est bas, mieux c'est
        efficacite_norm = [e/max(efficacite_data)*100 for e in efficacite_data]  # Plus c'est haut, mieux c'est
        
        for i, strategy in enumerate(strategies):
            fig_radar.add_trace(go.Scatterpolar(
                r=[temps_norm[i], conso_norm[i], efficacite_norm[i]],
                theta=['Rapidité', 'Économie', 'Efficacité'],
                fill='toself',
                name=strategy
            ))
        
        fig_radar.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 100]
                )),
            showlegend=True,
            title="Comparaison Multi-Critères"
        )
        
        st.plotly_chart(fig_radar, use_container_width=True)
    
    with col2:
        # Tableau de comparaison
        st.dataframe(df_comparison, use_container_width=True)
        
        # Recommandation
        st.markdown("---")
        st.subheader("🎯 Recommandation")
        
        best_overall = df_comparison.loc[df_comparison['Efficacité (km/l)'].idxmax()]
        st.success(f"✅ **Stratégie recommandée: {best_overall['Stratégie']}**")
        st.info(f"Temps: {best_overall['Temps (s)']}s | Consommation: {best_overall['Consommation (ml)']}ml | Efficacité: {best_overall['Efficacité (km/l)']}km/l")
    
    # Historique des courses
    st.markdown("---")
    st.subheader("📜 Historique des Courses")
    
    # Données d'historique simulées
    dates = pd.date_range('2025-01-01', periods=20, freq='W')
    historique_data = {
        'Date': dates,
        'Temps (s)': np.random.normal(185, 8, 20),
        'Consommation (ml)': np.random.normal(43, 4, 20),
        'Conditions': np.random.choice(['Sec', 'Humide', 'Venteux'], 20),
        'Stratégie': np.random.choice(['Économie', 'Normal', 'Attaque'], 20)
    }
    
    df_historique = pd.DataFrame(historique_data)
    df_historique['Efficacité (km/l)'] = 16500 / df_historique['Consommation (ml)']
    
    # Graphique d'évolution temporelle
    fig_evolution = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Évolution du Temps', 'Évolution de la Consommation', 
                       'Évolution de l\'Efficacité', 'Performance par Conditions'),
        specs=[[{"secondary_y": False}, {"secondary_y": False}],
               [{"secondary_y": False}, {"type": "box"}]]
    )
    
    # Temps
    fig_evolution.add_trace(
        go.Scatter(x=df_historique['Date'], y=df_historique['Temps (s)'],
                  mode='lines+markers', name='Temps', line=dict(color='blue')),
        row=1, col=1
    )
    
    # Consommation
    fig_evolution.add_trace(
        go.Scatter(x=df_historique['Date'], y=df_historique['Consommation (ml)'],
                  mode='lines+markers', name='Consommation', line=dict(color='red')),
        row=1, col=2
    )
    
    # Efficacité
    fig_evolution.add_trace(
        go.Scatter(x=df_historique['Date'], y=df_historique['Efficacité (km/l)'],
                  mode='lines+markers', name='Efficacité', line=dict(color='green')),
        row=2, col=1
    )
    
    # Box plot par conditions
    for condition in df_historique['Conditions'].unique():
        data_condition = df_historique[df_historique['Conditions'] == condition]
        fig_evolution.add_trace(
            go.Box(y=data_condition['Efficacité (km/l)'], name=condition),
            row=2, col=2
        )
    
    fig_evolution.update_layout(
        height=600,
        title_text="Historique des Performances",
        showlegend=False
    )
    
    st.plotly_chart(fig_evolution, use_container_width=True)
    
    # Tableau détaillé de l'historique
    st.subheader("📋 Détail des Courses")
    
    # Filtrages
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        condition_filter = st.multiselect("Filtrer par conditions", 
                                         df_historique['Conditions'].unique(),
                                         default=df_historique['Conditions'].unique())
    with col_f2:
        strategy_filter = st.multiselect("Filtrer par stratégie",
                                        df_historique['Stratégie'].unique(),
                                        default=df_historique['Stratégie'].unique())
    with col_f3:
        date_range = st.date_input("Période", 
                                  value=(df_historique['Date'].min().date(), 
                                        df_historique['Date'].max().date()),
                                  min_value=df_historique['Date'].min().date(),
                                  max_value=df_historique['Date'].max().date())
    
    # Application des filtres
    df_filtered = df_historique[
        (df_historique['Conditions'].isin(condition_filter)) &
        (df_historique['Stratégie'].isin(strategy_filter)) &
        (df_historique['Date'].dt.date >= date_range[0]) &
        (df_historique['Date'].dt.date <= date_range[1])
    ]
    
    # Formatage pour l'affichage
    df_display = df_filtered.copy()
    df_display['Date'] = df_display['Date'].dt.strftime('%Y-%m-%d')
    df_display['Temps (s)'] = df_display['Temps (s)'].round(1)
    df_display['Consommation (ml)'] = df_display['Consommation (ml)'].round(1)
    df_display['Efficacité (km/l)'] = df_display['Efficacité (km/l)'].round(1)
    
    st.dataframe(df_display, use_container_width=True)
    
    # Statistiques résumées
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        st.metric("🏃 Temps Moyen", f"{df_filtered['Temps (s)'].mean():.1f}s",
                 f"{df_filtered['Temps (s)'].mean() - df_historique['Temps (s)'].mean():.1f}s")
    with col_s2:
        st.metric("⛽ Conso Moyenne", f"{df_filtered['Consommation (ml)'].mean():.1f}ml",
                 f"{df_filtered['Consommation (ml)'].mean() - df_historique['Consommation (ml)'].mean():.1f}ml")
    with col_s3:
        st.metric("📈 Efficacité Moy", f"{df_filtered['Efficacité (km/l)'].mean():.1f}km/l",
                 f"{df_filtered['Efficacité (km/l)'].mean() - df_historique['Efficacité (km/l)'].mean():.1f}km/l")
    with col_s4:
        st.metric("📊 Nb Courses", len(df_filtered), f"{len(df_filtered) - len(df_historique)}")

# =============================================================================
# FOOTER ET FONCTIONS UTILITAIRES
# =============================================================================

# Sidebar avec informations système
st.sidebar.markdown("---")
st.sidebar.subheader("ℹ️ Informations Système")

# Status de connexion (simulé)
if st.sidebar.button("🔄 Tester Connexion GPS"):
    with st.spinner("Test de connexion..."):
        time.sleep(1)
        st.sidebar.success("✅ GPS connecté")

# Status serveur
server_status = st.sidebar.checkbox("Serveur de tracking actif", value=True)
if server_status:
    st.sidebar.success("🟢 Serveur en ligne")
else:
    st.sidebar.error("🔴 Serveur hors ligne")

# Informations véhicule
st.sidebar.markdown("---")
st.sidebar.subheader("🚗 Véhicule Eta-One")
st.sidebar.info("""
**Configuration:**
- Moteur hybride thermique/électrique
- Transmission Enviolo CVT
- Supercondensateurs 3000J
- Circuit: Sosnová (1321m)
""")

# Export des données
st.sidebar.markdown("---")
st.sidebar.subheader("💾 Export")

if st.sidebar.button("📥 Exporter Données"):
    # Simulation d'export
    with st.spinner("Export en cours..."):
        time.sleep(1)
        st.sidebar.success("✅ Données exportées vers eta-one-data.csv")

if st.sidebar.button("📊 Rapport PDF"):
    with st.spinner("Génération du rapport..."):
        time.sleep(2)
        st.sidebar.success("✅ Rapport généré: eta-one-report.pdf")

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 20px;'>
    <p>🏁 <strong>Eta-One Racing System</strong> - Développé pour l'optimisation de performance véhicule hybride</p>
    <p>Version 1.0 | Circuit: Sosnová, République Tchèque | Distance: 1321m</p>
</div>
""", unsafe_allow_html=True)

# =============================================================================
# FONCTIONS UTILITAIRES POUR INTÉGRATION AVEC TA SIMULATION
# =============================================================================

def load_simulation_module():
    """Charge ton module de simulation"""
    try:
        # Ici tu importerais ton fichier modele_simulation_silesia_hybridation.py
        # import modele_simulation_silesia_hybridation as sim
        # return sim
        return None
    except ImportError:
        st.error("Module de simulation non trouvé. Vérifiez que modele_simulation_silesia_hybridation.py est accessible.")
        return None

def run_real_simulation(bornes_vitesse, temps_max, **kwargs):
    """Lance ta vraie simulation"""
    sim_module = load_simulation_module()
    if sim_module:
        try:
            # Appel de ta fonction simuler_vehicule_optimise
            result = sim_module.simuler_vehicule_optimise(
                distance_totale=1321,  # Distance du circuit
                bornes_vitesse=bornes_vitesse,
                temps_max=temps_max,
                **kwargs
            )
            return result
        except Exception as e:
            st.error(f"Erreur lors de la simulation: {e}")
            return None
    return None

def get_live_gps_data():
    """Récupère les données GPS en temps réel depuis ton serveur"""
    try:
        # Connexion à ton serveur Node.js
        response = requests.get("http://localhost:3000/api/course", timeout=1)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def send_strategy_change(strategy):
    """Envoie un changement de stratégie au système"""
    try:
        data = {
            "mode": strategy,
            "timestamp": datetime.now().isoformat()
        }
        response = requests.post("http://localhost:3000/api/strategy", json=data, timeout=1)
        return response.status_code == 200
    except:
        return False

# Gestion des messages depuis l'interface Leaflet
if 'last_strategy_change' not in st.session_state:
    st.session_state.last_strategy_change = None

# Simulation d'écoute des messages (dans une vraie app, tu utiliserais WebSocket)
# Cette partie serait remplacée par une vraie communication avec ton serveur
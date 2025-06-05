# -*- coding: utf-8 -*-
"""
Created on Thu Jun  5 18:17:44 2025

@author: olivi
"""

import subprocess
import sys
import os
import time
import signal
import threading
from pathlib import Path

class EtaOneLauncher:
    def __init__(self):
        self.processes = []
        self.base_dir = Path(__file__).parent
        
    def check_dependencies(self):
        """Vérifie que toutes les dépendances sont installées"""
        print("🔍 Vérification des dépendances...")
        
        # Vérification Python
        required_packages = [
            'streamlit', 'pandas', 'numpy', 'scipy', 
            'matplotlib', 'plotly', 'numba', 'requests'
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)
        
        if missing_packages:
            print(f"❌ Packages Python manquants: {', '.join(missing_packages)}")
            print("Installez-les avec: pip install " + " ".join(missing_packages))
            return False
        
        # Vérification Node.js
        try:
            result = subprocess.run(['node', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                print(f"✅ Node.js: {result.stdout.strip()}")
            else:
                print("❌ Node.js non trouvé")
                return False
        except FileNotFoundError:
            print("❌ Node.js non installé")
            return False
        
        # Vérification des fichiers
        required_files = [
            'modele_simulation_silesia_hybridation_streamlit.py',
            'server.js',
            'public/client-desktop.html',
            'public/client-phone.html'
        ]
        
        for file in required_files:
            if not (self.base_dir / file).exists():
                print(f"❌ Fichier manquant: {file}")
                return False
        
        print("✅ Toutes les dépendances sont présentes")
        return True
    
    def setup_directories(self):
        """Crée les répertoires nécessaires"""
        directories = ['data', 'exports', 'logs']
        
        for dir_name in directories:
            dir_path = self.base_dir / dir_name
            dir_path.mkdir(exist_ok=True)
        
        print("✅ Répertoires configurés")
    
    def start_tracking_server(self):
        """Lance le serveur de tracking GPS"""
        print("🚀 Démarrage du serveur de tracking...")
        
        server_path = self.base_dir / 'server.js'
        
        try:
            # Lancement du serveur Node.js
            process = subprocess.Popen(
                ['node', str(server_path)],
                cwd=str(self.base_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.processes.append(('Serveur Tracking', process))
            
            # Attendre que le serveur démarre
            time.sleep(2)
            
            if process.poll() is None:
                print("✅ Serveur de tracking démarré (port 3000)")
                return True
            else:
                stdout, stderr = process.communicate()
                print(f"❌ Erreur serveur: {stderr.decode()}")
                return False
                
        except Exception as e:
            print(f"❌ Impossible de démarrer le serveur: {e}")
            return False
    
    def start_streamlit_app(self):
        """Lance l'application Streamlit"""
        print("🚀 Démarrage de l'application Streamlit...")
        
        # Créer le fichier streamlit_app.py s'il n'existe pas
        app_path = self.base_dir / 'streamlit_app.py'
        if not app_path.exists():
            print("📝 Création de streamlit_app.py...")
            self.create_streamlit_app()
        
        try:
            # Lancement de Streamlit
            process = subprocess.Popen(
                [sys.executable, '-m', 'streamlit', 'run', 'streamlit_app.py', 
                 '--server.port', '8501', '--server.headless', 'true'],
                cwd=str(self.base_dir)
            )
            
            self.processes.append(('Streamlit App', process))
            
            time.sleep(3)
            
            if process.poll() is None:
                print("✅ Application Streamlit démarrée (port 8501)")
                return True
            else:
                print("❌ Erreur lors du démarrage de Streamlit")
                return False
                
        except Exception as e:
            print(f"❌ Impossible de démarrer Streamlit: {e}")
            return False
    
    def create_streamlit_app(self):
        """Crée le fichier streamlit_app.py principal"""
        
        app_content = '''# streamlit_app.py - Application principale Eta-One
# Copier ici le contenu de l'application Streamlit que j'ai créée
import streamlit as st

# Import du wrapper d'intégration
try:
    from integration_wrapper import EtaOneSimulationWrapper
    SIMULATION_AVAILABLE = True
except ImportError:
    st.error("Module d'intégration non trouvé. Vérifiez que integration_wrapper.py est présent.")
    SIMULATION_AVAILABLE = False

# Configuration de la page
st.set_page_config(
    page_title="Eta-One Racing",
    page_icon="🏁",
    layout="wide"
)

st.title("🏁 Eta-One Racing System")

if SIMULATION_AVAILABLE:
    st.success("✅ Système de simulation connecté")
    
    # Chargement du wrapper
    @st.cache_resource
    def get_wrapper():
        return EtaOneSimulationWrapper()
    
    wrapper = get_wrapper()
    
    # Interface utilisateur simplifiée pour test
    st.header("Test de Simulation")
    
    if st.button("🚀 Lancer Simulation de Test"):
        with st.spinner("Simulation en cours..."):
            test_bornes = [(6.0, 8.5), (7.0, 8.8), (6.5, 8.3)]
            result = wrapper.run_simulation(test_bornes)
            
            if result and result['success']:
                st.success(f"✅ Simulation réussie!")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Temps Total", f"{result['temps_total']:.1f}s")
                with col2:
                    st.metric("Consommation", f"{result['consommation_ml']:.1f}ml")
                with col3:
                    st.metric("Efficacité", f"{result['efficacite_km_l']:.1f}km/l")
            else:
                st.error("❌ Erreur de simulation")
else:
    st.error("❌ Système de simulation non disponible")

st.info("🌐 Interface GPS disponible sur: http://localhost:3000")
'''
        
        with open(self.base_dir / 'streamlit_app.py', 'w', encoding='utf-8') as f:
            f.write(app_content)
    
    def open_browser_tabs(self):
        """Ouvre automatiquement les onglets du navigateur"""
        import webbrowser
        
        time.sleep(2)  # Attendre que les serveurs soient prêts
        
        urls = [
            'http://localhost:8501',  # Streamlit
            'http://localhost:3000'   # Interface GPS
        ]
        
        for url in urls:
            try:
                webbrowser.open(url)
                print(f"🌐 Ouverture: {url}")
            except Exception as e:
                print(f"❌ Impossible d'ouvrir {url}: {e}")
    
    def monitor_processes(self):
        """Surveille les processus en arrière-plan"""
        while True:
            for name, process in self.processes:
                if process.poll() is not None:
                    print(f"⚠️ {name} s'est arrêté (code: {process.returncode})")
            time.sleep(5)
    
    def cleanup(self):
        """Nettoie tous les processus avant de quitter"""
        print("\n🛑 Arrêt du système Eta-One...")
        
        for name, process in self.processes:
            if process.poll() is None:
                print(f"   Arrêt de {name}...")
                process.terminate()
                
                # Attendre un peu puis forcer si nécessaire
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        
        print("✅ Tous les processus arrêtés")
    
    def signal_handler(self, signum, frame):
        """Gestionnaire de signal pour arrêt propre"""
        self.cleanup()
        sys.exit(0)
    
    def run(self):
        """Lance tout le système"""
        print("🏁 === LANCEMENT ETA-ONE RACING SYSTEM ===")
        
        # Enregistrer le gestionnaire de signal
        signal.signal(signal.SIGINT, self.signal_handler)
        
        # Vérifications préliminaires
        if not self.check_dependencies():
            return False
        
        self.setup_directories()
        
        # Démarrage des composants
        if not self.start_tracking_server():
            print("❌ Impossible de démarrer le serveur de tracking")
            return False
        
        if not self.start_streamlit_app():
            print("❌ Impossible de démarrer Streamlit")
            self.cleanup()
            return False
        
        # Ouverture automatique du navigateur
        browser_thread = threading.Thread(target=self.open_browser_tabs)
        browser_thread.daemon = True
        browser_thread.start()
        
        print("\n🎉 SYSTÈME ETA-ONE PRÊT!")
        print("=" * 50)
        print("🌐 Interface Streamlit: http://localhost:8501")
        print("📱 Interface GPS Desktop: http://localhost:3000")
        print("📱 Interface GPS Téléphone: http://localhost:3000/client-phone.html")
        print("=" * 50)
        print("Press Ctrl+C pour arrêter le système")
        
        # Surveillance continue
        try:
            self.monitor_processes()
        except KeyboardInterrupt:
            self.signal_handler(signal.SIGINT, None)

def main():
    launcher = EtaOneLauncher()
    launcher.run()

if __name__ == "__main__":
    main()

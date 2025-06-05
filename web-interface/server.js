// === server.js - Version améliorée avec stratégie ===
const express = require('express');
const http = require('http');
const path = require('path');
const socketIo = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = socketIo(server);

// Serve static html files from 'public' directory
app.use(express.static(path.join(__dirname, 'public')));

// État global de la course
let courseState = {
  latestPosition: null,
  tempsDepart: null,
  strategieActuelle: 'normal',
  historique: [],
  secteurActuel: 0,
  retardAccumule: 0,
  totalClients: 0
};

// Configuration du circuit (reprise des données analysées)
const circuitConfig = {
  secteurs: [
    {id: 0, vitesseOptimale: 68, longueur: 40, tempsOptimal: 2.1},
    {id: 1, vitesseOptimale: 57, longueur: 40, tempsOptimal: 2.5},
    {id: 2, vitesseOptimale: 43, longueur: 40, tempsOptimal: 3.3},
    {id: 3, vitesseOptimale: 30, longueur: 40, tempsOptimal: 4.8},
    {id: 4, vitesseOptimale: 46, longueur: 40, tempsOptimal: 3.1},
    {id: 5, vitesseOptimale: 59, longueur: 40, tempsOptimal: 2.4},
    {id: 6, vitesseOptimale: 62, longueur: 40, tempsOptimal: 2.3},
    {id: 7, vitesseOptimale: 65, longueur: 40, tempsOptimal: 2.2}
    // Ajoutez les autres secteurs selon vos données
  ],
  tempsOptimalTotal: 81.6
};

io.on('connection', (socket) => {
  courseState.totalClients++;
  console.log(`🔗 Nouveau client connecté: ${socket.id}`);
  console.log(`👥 Total clients: ${courseState.totalClients}`);

  // Envoyer l'état actuel au nouveau client
  socket.emit('course-state', {
    position: courseState.latestPosition,
    strategie: courseState.strategieActuelle,
    secteur: courseState.secteurActuel,
    retard: courseState.retardAccumule
  });

  // Réception de position depuis le téléphone
  socket.on('position', (data) => {
    const timestamp = Date.now();
    
    // Mettre à jour l'état global
    courseState.latestPosition = {
      ...data,
      timestamp: timestamp
    };

    // Initialiser le temps de départ si c'est la première position
    if (!courseState.tempsDepart) {
      courseState.tempsDepart = timestamp;
      console.log('🏁 Début de course détecté!');
    }

    // Ajouter à l'historique
    courseState.historique.push({
      lat: data.lat,
      lon: data.lon,
      timestamp: timestamp,
      tempsEcoule: (timestamp - courseState.tempsDepart) / 1000
    });

    // Garder seulement les 1000 derniers points
    if (courseState.historique.length > 1000) {
      courseState.historique = courseState.historique.slice(-1000);
    }

    // Broadcast à tous les clients desktop
    socket.broadcast.emit('position', courseState.latestPosition);

    // Log périodique (toutes les 5 secondes)
    const tempsEcoule = (timestamp - courseState.tempsDepart) / 1000;
    if (Math.floor(tempsEcoule) % 5 === 0) {
      console.log(`📍 Position: ${data.lat.toFixed(6)}, ${data.lon.toFixed(6)} - Temps: ${tempsEcoule.toFixed(1)}s`);
    }
  });

  // Gestion des changements de stratégie
  socket.on('changement-strategie', (data) => {
    const timestamp = Date.now();
    
    courseState.strategieActuelle = data.mode;
    courseState.secteurActuel = data.secteur || 0;
    
    console.log(`🏁 Changement de stratégie: ${data.mode} (Secteur ${data.secteur})`);
    console.log(`⚡ Multiplicateur de vitesse: ${data.multiplicateur}`);

    // Broadcast à tous les clients
    io.emit('nouvelle-strategie', {
      mode: data.mode,
      secteur: data.secteur,
      multiplicateur: data.multiplicateur,
      timestamp: timestamp,
      tempsEcoule: courseState.tempsDepart ? (timestamp - courseState.tempsDepart) / 1000 : 0
    });

    // Log détaillé pour le suivi
    if (courseState.tempsDepart) {
      const tempsEcoule = (timestamp - courseState.tempsDepart) / 1000;
      console.log(`⏱️ Temps écoulé lors du changement: ${tempsEcoule.toFixed(1)}s`);
    }
  });

  // Demande de la dernière position
  socket.on('requestLatest', () => {
    if (courseState.latestPosition) {
      socket.emit('position', courseState.latestPosition);
    }
  });

  // Demande des données de course complètes
  socket.on('requestCourseData', () => {
    socket.emit('course-data', {
      state: courseState,
      circuit: circuitConfig,
      statistiques: {
        totalPoints: courseState.historique.length,
        dureeTotal: courseState.tempsDepart ? (Date.now() - courseState.tempsDepart) / 1000 : 0,
        vitesseMoyenne: calculerVitesseMoyenne()
      }
    });
  });

  // Reset de la course
  socket.on('reset-course', () => {
    console.log('🔄 Reset de la course demandé');
    
    courseState = {
      latestPosition: null,
      tempsDepart: null,
      strategieActuelle: 'normal',
      historique: [],
      secteurActuel: 0,
      retardAccumule: 0,
      totalClients: courseState.totalClients
    };

    // Notifier tous les clients
    io.emit('course-reset');
    console.log('✅ Course réinitialisée');
  });

  // Déconnexion
  socket.on('disconnect', () => {
    courseState.totalClients--;
    console.log(`❌ Client déconnecté: ${socket.id}`);
    console.log(`👥 Total clients: ${courseState.totalClients}`);
    
    // Log de fin de course si plus de clients
    if (courseState.totalClients === 0 && courseState.tempsDepart) {
      const dureeTotal = (Date.now() - courseState.tempsDepart) / 1000;
      console.log(`🏁 Fin de session - Durée totale: ${dureeTotal.toFixed(1)}s`);
      console.log(`📊 Points collectés: ${courseState.historique.length}`);
    }
  });
});

// Fonctions utilitaires
function calculerVitesseMoyenne() {
  if (courseState.historique.length < 2) return 0;
  
  const premier = courseState.historique[0];
  const dernier = courseState.historique[courseState.historique.length - 1];
  const distanceApprox = calculerDistance(
    premier.lat, premier.lon,
    dernier.lat, dernier.lon
  );
  const tempsecoule = (dernier.timestamp - premier.timestamp) / 1000;
  
  return tempsecoule > 0 ? (distanceApprox / tempsecoule * 3.6) : 0; // km/h
}

function calculerDistance(lat1, lon1, lat2, lon2) {
  const R = 6371e3; // Rayon terrestre en mètres
  const φ1 = lat1 * Math.PI/180;
  const φ2 = lat2 * Math.PI/180;
  const Δφ = (lat2-lat1) * Math.PI/180;
  const Δλ = (lon2-lon1) * Math.PI/180;

  const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
            Math.cos(φ1) * Math.cos(φ2) *
            Math.sin(Δλ/2) * Math.sin(Δλ/2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

  return R * c;
}

// Endpoint API REST pour les données de course
app.get('/api/course', (req, res) => {
  res.json({
    state: courseState,
    circuit: circuitConfig,
    statistiques: {
      totalPoints: courseState.historique.length,
      dureeTotal: courseState.tempsDepart ? (Date.now() - courseState.tempsDepart) / 1000 : 0,
      vitesseMoyenne: calculerVitesseMoyenne(),
      clientsConnectes: courseState.totalClients
    }
  });
});

// Endpoint pour exporter les données
app.get('/api/export', (req, res) => {
  const filename = `eta-one-${new Date().toISOString().split('T')[0]}.json`;
  res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
  res.setHeader('Content-Type', 'application/json');
  res.json({
    course: courseState,
    circuit: circuitConfig,
    exportTimestamp: new Date().toISOString()
  });
});

// Statistiques en temps réel (optionnel)
setInterval(() => {
  if (courseState.totalClients > 0 && courseState.tempsDepart) {
    const tempsEcoule = (Date.now() - courseState.tempsDepart) / 1000;
    const vitesseMoyenne = calculerVitesseMoyenne();
    
    if (Math.floor(tempsEcoule) % 30 === 0) { // Log toutes les 30 secondes
      console.log(`📊 Temps: ${tempsEcoule.toFixed(1)}s | Vitesse moy: ${vitesseMoyenne.toFixed(1)} km/h | Stratégie: ${courseState.strategieActuelle}`);
    }
  }
}, 1000);

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
  console.log(`🚀 Serveur Eta-One Racing démarré sur le port ${PORT}`);
  console.log(`🏁 Système de stratégie temps réel activé`);
  console.log(`📡 WebSocket et API REST disponibles`);
});

module.exports = { app, server, io };

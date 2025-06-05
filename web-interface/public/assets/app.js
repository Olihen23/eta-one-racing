/**
 * ETA-ONE RACING - JAVASCRIPT PARTAGÉ
 * Fonctions communes pour toutes les interfaces
 */

// Namespace global pour éviter les conflits
window.EtaOne = window.EtaOne || {};

// Configuration globale
EtaOne.config = {
  // Circuit Silesia Ring
  circuit: {
    nom: "Silesia Ring",
    pays: "République Tchèque",
    distance: 1320,
    secteurs: 25,
    tempsOptimal: 93.2,
    centre: [50.529211, 18.093939]
  },
  
  // Paramètres GPS
  gps: {
    frequence: 50, // ms
    precisionRequise: 10, // mètres
    timeoutGPS: 5000 // ms
  },
  
  // Stratégies
  strategies: {
    economie: { multiplicateur: 0.85, emoji: '🔋', nom: 'Économie' },
    normal: { multiplicateur: 1.0, emoji: '🏃', nom: 'Normal' },
    attaque: { multiplicateur: 1.2, emoji: '⚡', nom: 'Attaque' }
  },
  
  // Seuils d'alerte
  seuils: {
    retardLeger: 2, // secondes
    retardCritique: 5, // secondes
    retardUrgent: 10, // secondes
    precisionGPSMax: 20 // mètres
  }
};

// ========================================
// UTILITAIRES GÉNÉRAUX
// ========================================

EtaOne.utils = {
  /**
   * Calcule la distance entre deux points GPS
   */
  calculerDistance(lat1, lon1, lat2, lon2) {
    const R = 6371e3; // Rayon de la Terre en mètres
    const φ1 = lat1 * Math.PI/180;
    const φ2 = lat2 * Math.PI/180;
    const Δφ = (lat2-lat1) * Math.PI/180;
    const Δλ = (lon2-lon1) * Math.PI/180;

    const a = Math.sin(Δφ/2) * Math.sin(Δφ/2) +
              Math.cos(φ1) * Math.cos(φ2) *
              Math.sin(Δλ/2) * Math.sin(Δλ/2);
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));

    return R * c;
  },

  /**
   * Formate un temps en secondes vers MM:SS
   */
  formaterTemps(secondes) {
    const minutes = Math.floor(secondes / 60);
    const secs = (secondes % 60).toFixed(1);
    return `${minutes}:${secs.padStart(4, '0')}`;
  },

  /**
   * Formate un retard avec signe
   */
  formaterRetard(retard) {
    const signe = retard >= 0 ? '+' : '';
    return `${signe}${retard.toFixed(1)}s`;
  },

  /**
   * Détermine la classe CSS selon le retard
   */
  getClasseRetard(retard) {
    if (retard < -EtaOne.config.seuils.retardLeger) return 'status-ok';
    if (retard < EtaOne.config.seuils.retardLeger) return 'status-ok';
    if (retard < EtaOne.config.seuils.retardCritique) return 'status-warning';
    return 'status-danger';
  },

  /**
   * Génère un ID unique
   */
  genererID() {
    return 'eta-' + Math.random().toString(36).substr(2, 9);
  },

  /**
   * Débounce une fonction
   */
  debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
      const later = () => {
        clearTimeout(timeout);
        func(...args);
      };
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
    };
  },

  /**
   * Vérifie si on est sur mobile
   */
  estMobile() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
  },

  /**
   * Log avec timestamp
   */
  log(message, type = 'info') {
    const timestamp = new Date().toLocaleTimeString();
    const emoji = type === 'error' ? '❌' : type === 'warning' ? '⚠️' : type === 'success' ? '✅' : 'ℹ️';
    console.log(`[${timestamp}] ${emoji} ${message}`);
  }
};

// ========================================
// SYSTÈME DE NOTIFICATIONS
// ========================================

EtaOne.notifications = {
  container: null,

  init() {
    // Créer le container s'il n'existe pas
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.id = 'eta-notifications';
      this.container.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        z-index: 10000;
        pointer-events: none;
      `;
      document.body.appendChild(this.container);
    }
  },

  show(message, type = 'info', duration = 3000) {
    this.init();

    const notification = document.createElement('div');
    notification.className = `eta-one-notification ${type}`;
    notification.textContent = message;
    notification.style.cssText = `
      margin-bottom: 10px;
      pointer-events: auto;
      transform: translateX(100%);
      transition: transform 0.3s ease;
    `;

    this.container.appendChild(notification);

    // Animation d'entrée
    setTimeout(() => {
      notification.style.transform = 'translateX(0)';
    }, 10);

    // Suppression automatique
    setTimeout(() => {
      notification.style.transform = 'translateX(100%)';
      setTimeout(() => {
        if (notification.parentNode) {
          notification.parentNode.removeChild(notification);
        }
      }, 300);
    }, duration);

    return notification;
  },

  success(message, duration) {
    return this.show(message, 'success', duration);
  },

  error(message, duration) {
    return this.show(message, 'error', duration);
  },

  warning(message, duration) {
    return this.show(message, 'warning', duration);
  },

  info(message, duration) {
    return this.show(message, 'info', duration);
  }
};

// ========================================
// GESTION GPS
// ========================================

EtaOne.gps = {
  watchId: null,
  callbacks: [],
  dernierPosition: null,
  precision: null,

  /**
   * Démarre le suivi GPS
   */
  demarrer(callback) {
    if (callback) {
      this.callbacks.push(callback);
    }

    if (!navigator.geolocation) {
      EtaOne.notifications.error('Géolocalisation non supportée');
      return false;
    }

    const options = {
      enableHighAccuracy: true,
      maximumAge: 0,
      timeout: EtaOne.config.gps.timeoutGPS
    };

    this.watchId = navigator.geolocation.watchPosition(
      (position) => this._onPositionSuccess(position),
      (error) => this._onPositionError(error),
      options
    );

    EtaOne.utils.log('GPS démarré', 'success');
    return true;
  },

  /**
   * Arrête le suivi GPS
   */
  arreter() {
    if (this.watchId) {
      navigator.geolocation.clearWatch(this.watchId);
      this.watchId = null;
    }
    this.callbacks = [];
    EtaOne.utils.log('GPS arrêté', 'info');
  },

  /**
   * Callback succès GPS
   */
  _onPositionSuccess(position) {
    const { latitude, longitude, accuracy } = position.coords;
    
    this.dernierPosition = {
      lat: latitude,
      lon: longitude,
      accuracy: accuracy,
      timestamp: Date.now()
    };

    this.precision = accuracy;

    // Vérifier la précision
    if (accuracy > EtaOne.config.seuils.precisionGPSMax) {
      EtaOne.notifications.warning(`Précision GPS faible: ${accuracy.toFixed(1)}m`);
    }

    // Appeler tous les callbacks
    this.callbacks.forEach(callback => {
      try {
        callback(this.dernierPosition);
      } catch (error) {
        EtaOne.utils.log(`Erreur callback GPS: ${error.message}`, 'error');
      }
    });
  },

  /**
   * Callback erreur GPS
   */
  _onPositionError(error) {
    let message = 'Erreur GPS: ';
    switch(error.code) {
      case error.PERMISSION_DENIED:
        message += 'Permission refusée';
        break;
      case error.POSITION_UNAVAILABLE:
        message += 'Position indisponible';
        break;
      case error.TIMEOUT:
        message += 'Timeout';
        break;
      default:
        message += 'Erreur inconnue';
        break;
    }
    
    EtaOne.notifications.error(message);
    EtaOne.utils.log(message, 'error');
  },

  /**
   * Obtient la dernière position connue
   */
  getDernierePosition() {
    return this.dernierPosition;
  },

  /**
   * Obtient la précision actuelle
   */
  getPrecision() {
    return this.precision;
  }
};

// ========================================
// GESTION DES STRATÉGIES
// ========================================

EtaOne.strategie = {
  actuelle: 'normal',
  callbacks: [],

  /**
   * Change la stratégie
   */
  changer(nouvelleStrategie, callback) {
    if (!EtaOne.config.strategies[nouvelleStrategie]) {
      EtaOne.utils.log(`Stratégie inconnue: ${nouvelleStrategie}`, 'error');
      return false;
    }

    const ancienne = this.actuelle;
    this.actuelle = nouvelleStrategie;

    const config = EtaOne.config.strategies[nouvelleStrategie];
    const message = `${config.emoji} Stratégie: ${config.nom}`;
    
    EtaOne.notifications.success(message);
    EtaOne.utils.log(`Stratégie changée: ${ancienne} → ${nouvelleStrategie}`, 'success');

    // Appeler le callback si fourni
    if (callback) {
      callback(nouvelleStrategie, ancienne);
    }

    // Appeler tous les callbacks enregistrés
    this.callbacks.forEach(cb => {
      try {
        cb(nouvelleStrategie, ancienne);
      } catch (error) {
        EtaOne.utils.log(`Erreur callback stratégie: ${error.message}`, 'error');
      }
    });

    return true;
  },

  /**
   * Obtient la stratégie actuelle
   */
  getActuelle() {
    return this.actuelle;
  },

  /**
   * Obtient la configuration de la stratégie actuelle
   */
  getConfig() {
    return EtaOne.config.strategies[this.actuelle];
  },

  /**
   * Enregistre un callback pour les changements de stratégie
   */
  onChangement(callback) {
    this.callbacks.push(callback);
  },

  /**
   * Détermine automatiquement la stratégie selon le retard
   */
  ajusterAutomatiquement(retard) {
    if (retard > EtaOne.config.seuils.retardUrgent && this.actuelle !== 'attaque') {
      this.changer('attaque');
      EtaOne.notifications.warning('⚠️ Passage automatique en mode Attaque!');
    } else if (retard < -EtaOne.config.seuils.retardLeger && this.actuelle === 'attaque') {
      this.changer('normal');
      EtaOne.notifications.info('Retour en mode Normal');
    }
  }
};

// ========================================
// GESTION DES SECTEURS
// ========================================

EtaOne.secteurs = {
  actuel: 0,
  callbacks: [],

  /**
   * Détermine le secteur selon la position
   */
  determiner(lat, lon, secteurs) {
    let secteurProche = 0;
    let distanceMin = Infinity;

    secteurs.forEach(secteur => {
      const distance = EtaOne.utils.calculerDistance(
        lat, lon, 
        secteur.debut[0], secteur.debut[1]
      );
      
      if (distance < distanceMin) {
        distanceMin = distance;
        secteurProche = secteur.id;
      }
    });

    // Changement de secteur ?
    if (secteurProche !== this.actuel) {
      const ancien = this.actuel;
      this.actuel = secteurProche;
      
      // Appeler les callbacks
      this.callbacks.forEach(cb => {
        try {
          cb(secteurProche, ancien);
        } catch (error) {
          EtaOne.utils.log(`Erreur callback secteur: ${error.message}`, 'error');
        }
      });
    }

    return secteurProche;
  },

  /**
   * Obtient le secteur actuel
   */
  getActuel() {
    return this.actuel;
  },

  /**
   * Enregistre un callback pour les changements de secteur
   */
  onChangement(callback) {
    this.callbacks.push(callback);
  }
};

// ========================================
// CALCULS DE PERFORMANCE
// ========================================

EtaOne.performance = {
  /**
   * Calcule le retard par rapport au temps optimal
   */
  calculerRetard(tempsEcoule, secteurActuel, secteurs, multiplicateurStrategie = 1.0) {
    let tempsOptimalCumul = 0;
    
    for (let i = 0; i <= secteurActuel && i < secteurs.length; i++) {
      tempsOptimalCumul += secteurs[i].tempsOptimal * multiplicateurStrategie;
    }
    
    return tempsEcoule - tempsOptimalCumul;
  },

  /**
   * Calcule la progression sur le circuit
   */
  calculerProgression(secteurActuel, totalSecteurs) {
    return ((secteurActuel + 1) / totalSecteurs) * 100;
  },

  /**
   * Calcule la vitesse entre deux points GPS
   */
  calculerVitesse(position1, position2) {
    if (!position1 || !position2) return 0;
    
    const distance = EtaOne.utils.calculerDistance(
      position1.lat, position1.lon,
      position2.lat, position2.lon
    );
    
    const deltaTime = (position2.timestamp - position1.timestamp) / 1000;
    
    if (deltaTime > 0 && distance > 0.5) {
      const vitesse = (distance / deltaTime) * 3.6; // km/h
      return Math.min(vitesse, 200); // Cap à 200 km/h
    }
    
    return 0;
  },

  /**
   * Calcule le temps restant optimal
   */
  calculerTempsRestant(secteurActuel, secteurs, multiplicateurStrategie = 1.0) {
    let tempsRestant = 0;
    
    for (let i = secteurActuel; i < secteurs.length; i++) {
      tempsRestant += secteurs[i].tempsOptimal * multiplicateurStrategie;
    }
    
    return tempsRestant;
  }
};

// ========================================
// GESTION DU STOCKAGE LOCAL
// ========================================

EtaOne.storage = {
  prefix: 'etaone_',

  /**
   * Sauvegarde une valeur
   */
  sauver(cle, valeur) {
    try {
      localStorage.setItem(this.prefix + cle, JSON.stringify(valeur));
      return true;
    } catch (error) {
      EtaOne.utils.log(`Erreur sauvegarde: ${error.message}`, 'error');
      return false;
    }
  },

  /**
   * Charge une valeur
   */
  charger(cle, valeurParDefaut = null) {
    try {
      const item = localStorage.getItem(this.prefix + cle);
      return item ? JSON.parse(item) : valeurParDefaut;
    } catch (error) {
      EtaOne.utils.log(`Erreur chargement: ${error.message}`, 'error');
      return valeurParDefaut;
    }
  },

  /**
   * Supprime une valeur
   */
  supprimer(cle) {
    try {
      localStorage.removeItem(this.prefix + cle);
      return true;
    } catch (error) {
      EtaOne.utils.log(`Erreur suppression: ${error.message}`, 'error');
      return false;
    }
  },

  /**
   * Vide tout le stockage Eta-One
   */
  vider() {
    try {
      Object.keys(localStorage).forEach(cle => {
        if (cle.startsWith(this.prefix)) {
          localStorage.removeItem(cle);
        }
      });
      return true;
    } catch (error) {
      EtaOne.utils.log(`Erreur vidage: ${error.message}`, 'error');
      return false;
    }
  }
};

// ========================================
// STATISTIQUES DE COURSE
// ========================================

EtaOne.stats = {
  courseActuelle: null,
  
  /**
   * Démarre l'enregistrement des statistiques
   */
  demarrerCourse() {
    this.courseActuelle = {
      debut: Date.now(),
      fin: null,
      positions: [],
      secteurs: [],
      strategies: [],
      retards: [],
      vitesses: []
    };
    
    EtaOne.utils.log('Enregistrement des statistiques démarré', 'success');
  },

  /**
   * Termine l'enregistrement
   */
  terminerCourse() {
    if (this.courseActuelle) {
      this.courseActuelle.fin = Date.now();
      this.courseActuelle.duree = (this.courseActuelle.fin - this.courseActuelle.debut) / 1000;
      
      // Sauvegarder la course
      const courses = EtaOne.storage.charger('courses', []);
      courses.push({
        ...this.courseActuelle,
        id: EtaOne.utils.genererID(),
        date: new Date().toISOString()
      });
      
      // Garder seulement les 50 dernières courses
      if (courses.length > 50) {
        courses.splice(0, courses.length - 50);
      }
      
      EtaOne.storage.sauver('courses', courses);
      EtaOne.utils.log(`Course sauvegardée (${this.courseActuelle.duree.toFixed(1)}s)`, 'success');
      
      this.courseActuelle = null;
    }
  },

  /**
   * Enregistre une position
   */
  enregistrerPosition(position) {
    if (this.courseActuelle) {
      this.courseActuelle.positions.push({
        ...position,
        temps: (Date.now() - this.courseActuelle.debut) / 1000
      });
    }
  },

  /**
   * Enregistre un changement de secteur
   */
  enregistrerSecteur(secteur) {
    if (this.courseActuelle) {
      this.courseActuelle.secteurs.push({
        secteur: secteur,
        temps: (Date.now() - this.courseActuelle.debut) / 1000
      });
    }
  },

  /**
   * Enregistre un changement de stratégie
   */
  enregistrerStrategie(strategie) {
    if (this.courseActuelle) {
      this.courseActuelle.strategies.push({
        strategie: strategie,
        temps: (Date.now() - this.courseActuelle.debut) / 1000
      });
    }
  },

  /**
   * Enregistre un retard
   */
  enregistrerRetard(retard) {
    if (this.courseActuelle) {
      this.courseActuelle.retards.push({
        retard: retard,
        temps: (Date.now() - this.courseActuelle.debut) / 1000
      });
    }
  },

  /**
   * Obtient l'historique des courses
   */
  getHistorique() {
    return EtaOne.storage.charger('courses', []);
  },

  /**
   * Obtient les statistiques générales
   */
  getStatistiquesGenerales() {
    const courses = this.getHistorique();
    
    if (courses.length === 0) {
      return null;
    }

    const durees = courses.map(c => c.duree).filter(d => d > 0);
    const meilleureTime = Math.min(...durees);
    const tempsMoyen = durees.reduce((a, b) => a + b, 0) / durees.length;
    
    return {
      totalCourses: courses.length,
      meilleureTime: meilleureTime,
      tempsMoyen: tempsMoyen,
      derniereCoure: courses[courses.length - 1]
    };
  }
};

// ========================================
// WAKE LOCK (pour éviter la mise en veille)
// ========================================

EtaOne.wakeLock = {
  wakeLock: null,

  /**
   * Active le wake lock
   */
  async activer() {
    if ('wakeLock' in navigator) {
      try {
        this.wakeLock = await navigator.wakeLock.request('screen');
        EtaOne.utils.log('Wake lock activé - écran maintenu allumé', 'success');
        
        this.wakeLock.addEventListener('release', () => {
          EtaOne.utils.log('Wake lock libéré', 'info');
        });
        
        return true;
      } catch (error) {
        EtaOne.utils.log(`Wake lock échoué: ${error.message}`, 'warning');
        return false;
      }
    } else {
      EtaOne.utils.log('Wake lock non supporté', 'warning');
      return false;
    }
  },

  /**
   * Libère le wake lock
   */
  liberer() {
    if (this.wakeLock) {
      this.wakeLock.release();
      this.wakeLock = null;
    }
  }
};

// ========================================
// GESTION DE LA CONNECTIVITÉ
// ========================================

EtaOne.connexion = {
  callbacks: [],
  enLigne: navigator.onLine,

  init() {
    window.addEventListener('online', () => {
      this.enLigne = true;
      this._notifierChangement(true);
    });

    window.addEventListener('offline', () => {
      this.enLigne = false;
      this._notifierChangement(false);
    });
  },

  _notifierChangement(enLigne) {
    const message = enLigne ? '🌐 Connexion rétablie' : '📡 Connexion perdue';
    const type = enLigne ? 'success' : 'warning';
    
    EtaOne.notifications.show(message, type);
    EtaOne.utils.log(message, type);

    this.callbacks.forEach(callback => {
      try {
        callback(enLigne);
      } catch (error) {
        EtaOne.utils.log(`Erreur callback connexion: ${error.message}`, 'error');
      }
    });
  },

  onChangement(callback) {
    this.callbacks.push(callback);
  },

  estEnLigne() {
    return this.enLigne;
  }
};

// ========================================
// GESTIONNAIRE D'ÉVÉNEMENTS GLOBAUX
// ========================================

EtaOne.events = {
  listeners: {},

  /**
   * Enregistre un listener d'événement
   */
  on(event, callback) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(callback);
  },

  /**
   * Supprime un listener d'événement
   */
  off(event, callback) {
    if (this.listeners[event]) {
      const index = this.listeners[event].indexOf(callback);
      if (index > -1) {
        this.listeners[event].splice(index, 1);
      }
    }
  },

  /**
   * Déclenche un événement
   */
  emit(event, data) {
    if (this.listeners[event]) {
      this.listeners[event].forEach(callback => {
        try {
          callback(data);
        } catch (error) {
          EtaOne.utils.log(`Erreur callback event ${event}: ${error.message}`, 'error');
        }
      });
    }
  }
};

// ========================================
// INITIALISATION AUTOMATIQUE
// ========================================

// Initialiser quand le DOM est prêt
document.addEventListener('DOMContentLoaded', () => {
  EtaOne.connexion.init();
  EtaOne.utils.log('Eta-One Racing System initialisé', 'success');
  
  // Charger les préférences sauvegardées
  const strategieSauvee = EtaOne.storage.charger('strategie_preference', 'normal');
  EtaOne.strategie.actuelle = strategieSauvee;
  
  // Événement global pour sauvegarder les préférences
  EtaOne.strategie.onChangement((nouvelleStrategie) => {
    EtaOne.storage.sauver('strategie_preference', nouvelleStrategie);
  });
});

// Gérer la visibilité de la page
document.addEventListener('visibilitychange', () => {
  if (document.hidden) {
    EtaOne.utils.log('Page en arrière-plan', 'info');
  } else {
    EtaOne.utils.log('Page visible', 'info');
    // Réactiver le wake lock si nécessaire
    if (EtaOne.gps.watchId && !EtaOne.wakeLock.wakeLock) {
      EtaOne.wakeLock.activer();
    }
  }
});

// Gérer la fermeture de la page
window.addEventListener('beforeunload', (e) => {
  // Sauvegarder les statistiques si une course est en cours
  if (EtaOne.stats.courseActuelle) {
    EtaOne.stats.terminerCourse();
  }
  
  // Arrêter le GPS
  EtaOne.gps.arreter();
  
  // Libérer le wake lock
  EtaOne.wakeLock.liberer();
});

// Export pour utilisation dans d'autres scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = EtaOne;
}

// Log final
EtaOne.utils.log(`Eta-One Racing JS chargé - Circuit: ${EtaOne.config.circuit.nom}`, 'success');

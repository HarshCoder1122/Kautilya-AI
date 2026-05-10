import { initializeApp, getApps, getApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, signInWithPopup, onAuthStateChanged, signOut } from "firebase/auth";

let authInstance;
let googleProvider;

export const initFirebase = async () => {
  if (getApps().length > 0) {
    authInstance = getAuth(getApp());
    googleProvider = new GoogleAuthProvider();
    return authInstance;
  }

  const sanitizeConfig = (raw) => {
    if (!raw) return null;
    try {
      // If it's already a clean JSON string
      if (raw.trim().startsWith('{')) return JSON.parse(raw);
      
      // If it contains "const firebaseConfig =" or similar JS junk
      const match = raw.match(/\{[\s\S]*\}/);
      if (match) {
        // Attempt to convert JS object-like string to valid JSON
        let jsonStr = match[0]
          .replace(/(\w+):/g, '"$1":') // Quote keys
          .replace(/'/g, '"')         // Replace single quotes with double quotes
          .replace(/,\s*}/g, '}')     // Remove trailing commas
          .replace(/,\s*]/g, ']');    // Remove trailing commas in arrays
        return JSON.parse(jsonStr);
      }
    } catch (e) {
      console.warn("Firebase: Sanitize failed, returning null", e);
    }
    return null;
  };

  try {
    let config;
    const cached = sessionStorage.getItem('firebase_config');
    if (cached) {
      config = JSON.parse(cached);
    } else {
      console.log("Firebase: Attempting to load config...");
      
      // 1. Try Environment Variable first
      const envConfig = process.env.REACT_APP_FIREBASE_CONFIG;
      if (envConfig) {
        config = sanitizeConfig(envConfig);
        if (config) console.log("Firebase: Loaded from REACT_APP_FIREBASE_CONFIG (Sanitized)");
      }

      // 2. Try individual env variables as fallback
      if (!config || !config.apiKey) {
        if (process.env.REACT_APP_FIREBASE_API_KEY) {
           config = {
             apiKey: process.env.REACT_APP_FIREBASE_API_KEY,
             authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN,
             projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID,
             storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET,
             messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID,
             appId: process.env.REACT_APP_FIREBASE_APP_ID
           };
           console.log("Firebase: Loaded from individual REACT_APP_FIREBASE_* env vars");
        }
      }

      // 3. Try API fetch
      if (!config || !config.apiKey) {
        try {
          const apiBase = process.env.REACT_APP_API_URL || "";
          const hfToken = process.env.REACT_APP_HF_API_TOKEN;
          const headers = hfToken ? { "Authorization": `Bearer ${hfToken}` } : {};
          console.log("Firebase: Fetching from API...");
          const response = await fetch(`${apiBase}/api/config/firebase`, { headers });
          config = await response.json();
          if (config && !config.error) {
             console.log("Firebase: Loaded from Backend API");
          }
        } catch (e) {
          console.error("Firebase: API fetch failed", e);
        }
      }
      
      if (config && !config.error && config.apiKey) {
        sessionStorage.setItem('firebase_config', JSON.stringify(config));
      }
    }

    const fallbackConfig = {
      apiKey: "REDACTED_FIREBASE_WEB_KEY",
      authDomain: "jarvis-a6e18.firebaseapp.com",
      projectId: "jarvis-a6e18",
      storageBucket: "jarvis-a6e18.firebasestorage.app",
      messagingSenderId: "872168972424",
      appId: "1:872168972424:web:2b0b9b82922860a52c3f3d",
      measurementId: "G-H2FB26YQ9R"
    };

    if (!config || !config.apiKey) {
      console.log("Firebase: Using Hardcoded Fallback Config");
      config = fallbackConfig;
    }

    const app = initializeApp(config);
    authInstance = getAuth(app);
    googleProvider = new GoogleAuthProvider();
    return authInstance;
  } catch (error) {
    console.error("Firebase Initialization Error:", error.message);
    return null;
  }
};

export const getAuthInstance = () => {
  if (!authInstance && getApps().length > 0) {
    authInstance = getAuth(getApp());
  }
  return authInstance;
};

export const loginWithGoogle = async () => {
  const auth = await initFirebase();
  try {
    const result = await signInWithPopup(auth, googleProvider);
    const token = await result.user.getIdToken();
    localStorage.setItem('firebase_token', token);
    localStorage.setItem('user', JSON.stringify({
      uid: result.user.uid,
      email: result.user.email,
      displayName: result.user.displayName,
      photoURL: result.user.photoURL
    }));
    return result.user;
  } catch (error) {
    console.error("Login failed:", error);
    throw error;
  }
};

export const logout = async () => {
  const auth = await initFirebase();
  await signOut(auth);
  localStorage.removeItem('firebase_token');
  localStorage.removeItem('user');
};

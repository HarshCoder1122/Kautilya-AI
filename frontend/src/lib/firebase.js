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

  try {
    // Check session storage for cached config
    let config;
    const cached = sessionStorage.getItem('firebase_config');
    if (cached) {
      config = JSON.parse(cached);
    } else {
      const apiBase = process.env.REACT_APP_API_URL || "";
      const hfToken = process.env.REACT_APP_HF_API_TOKEN;
      
      const headers = {};
      if (hfToken) {
        headers["Authorization"] = `Bearer ${hfToken}`;
      }

      const response = await fetch(`${apiBase}/api/config/firebase`, { headers });
      config = await response.json();
      if (config.error) throw new Error(config.error);
      sessionStorage.setItem('firebase_config', JSON.stringify(config));
    }

    if (!config || !config.apiKey) throw new Error("Invalid config");

    const app = initializeApp(config);
    authInstance = getAuth(app);
    googleProvider = new GoogleAuthProvider();
    return authInstance;
  } catch (error) {
    console.error("Firebase init failed:", error);
    if (getApps().length === 0) {
      const app = initializeApp({ projectId: "jarvis-a6e18", apiKey: "MISSING" });
      authInstance = getAuth(app);
    } else {
      authInstance = getAuth(getApp());
    }
    googleProvider = new GoogleAuthProvider();
    return authInstance;
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

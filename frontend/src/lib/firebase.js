import { initializeApp, getApps, getApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, signInWithPopup, signInWithRedirect, getRedirectResult, onAuthStateChanged, signOut, signInWithCredential } from "firebase/auth";

let authInstance;
let googleProvider;

let nativeSignInResolver = null;
let nativeSignInRejecter = null;

if (typeof window !== 'undefined') {
  window.handleAndroidSignIn = async (idToken) => {
    try {
      console.log("[Auth] Android Native sign-in token received.");
      const auth = getAuthInstance();
      const credential = GoogleAuthProvider.credential(idToken);
      const result = await signInWithCredential(auth, credential);
      const token = await result.user.getIdToken();
      localStorage.setItem('firebase_token', token);
      localStorage.setItem('user', JSON.stringify({
        uid: result.user.uid,
        email: result.user.email,
        displayName: result.user.displayName,
        photoURL: result.user.photoURL
      }));
      try {
        const { userAPI } = await import('./api');
        userAPI.welcomeCheck().catch(() => {});
      } catch {}

      if (nativeSignInResolver) {
        nativeSignInResolver(result.user);
        nativeSignInResolver = null;
        nativeSignInRejecter = null;
      }
    } catch (error) {
      console.error("[Auth] Android native sign-in integration failed:", error);
      if (nativeSignInRejecter) {
        nativeSignInRejecter(error);
        nativeSignInResolver = null;
        nativeSignInRejecter = null;
      }
    }
  };

  window.handleAndroidSignInError = (errorMsg) => {
    console.error("[Auth] Android native sign-in callback error:", errorMsg);
    if (nativeSignInRejecter) {
      nativeSignInRejecter(new Error(errorMsg));
      nativeSignInResolver = null;
      nativeSignInRejecter = null;
    }
  };
}

const sanitizeConfig = (raw) => {
  if (!raw) return null;
  const trimmed = raw.trim();
  try {
    if (trimmed.startsWith('{')) return JSON.parse(trimmed);
    const firstBrace = raw.indexOf('{');
    const lastBrace = raw.lastIndexOf('}');
    if (firstBrace !== -1 && lastBrace !== -1 && lastBrace > firstBrace) {
      const content = raw.substring(firstBrace, lastBrace + 1);
      const clean = content
        .replace(/(\/\/.*)/g, "")
        .replace(/(\/\*[\s\S]*?\*\/)/g, "")
        .replace(/([{,])\s*(\w+):/g, '$1"$2":')
        .replace(/'/g, '"')
        .replace(/,\s*([}\]])/g, '$1');
      return JSON.parse(clean);
    }
  } catch (e) {
    console.warn("Firebase: sanitize failed", e);
  }
  return null;
};

// Firebase web config comes from REACT_APP_FIREBASE_* at build time (see
// frontend/.env.example). These values are public by design — access is
// enforced by Firebase Auth authorised domains and Security Rules.
const _envConfig = {
  apiKey: process.env.REACT_APP_FIREBASE_API_KEY || "",
  authDomain: process.env.REACT_APP_FIREBASE_AUTH_DOMAIN || "",
  projectId: process.env.REACT_APP_FIREBASE_PROJECT_ID || "",
  storageBucket: process.env.REACT_APP_FIREBASE_STORAGE_BUCKET || "",
  messagingSenderId: process.env.REACT_APP_FIREBASE_MESSAGING_SENDER_ID || "",
  appId: process.env.REACT_APP_FIREBASE_APP_ID || "",
  measurementId: process.env.REACT_APP_FIREBASE_MEASUREMENT_ID || undefined,
};

const _resolveConfigSync = () => {
  try {
    const cached = sessionStorage.getItem('firebase_config');
    if (cached) {
      const parsed = JSON.parse(cached);
      if (parsed && parsed.apiKey) return parsed;
    }
  } catch {}
  const envBlob = process.env.REACT_APP_FIREBASE_CONFIG;
  if (envBlob) {
    const sane = sanitizeConfig(envBlob);
    if (sane && sane.apiKey) return sane;
  }
  if (!_envConfig.apiKey) {
    console.warn("Firebase: REACT_APP_FIREBASE_* env vars are not set — sign-in is disabled. See frontend/.env.example.");
  }
  return _envConfig;
};

const _applyAuthDomainOverride = (config) => {
  const _hn = (typeof window !== 'undefined' ? window.location.hostname : '') || '';
  if (/(^|\.)revealiq\.in$/i.test(_hn)) {
    return { ...config, authDomain: "ai.revealiq.in" };
  }
  return config;
};

// Synchronous init — no network roundtrip. Frees the UI to paint immediately.
// Backend `/api/config/firebase` is no longer in the critical path; we cache
// the resolved config in sessionStorage on subsequent visits.
export const initFirebase = () => {
  if (authInstance) return authInstance;
  if (getApps().length > 0) {
    authInstance = getAuth(getApp());
    googleProvider = new GoogleAuthProvider();
    return authInstance;
  }
  try {
    const config = _applyAuthDomainOverride(_resolveConfigSync());
    if (config && config.apiKey) {
      try { sessionStorage.setItem('firebase_config', JSON.stringify(config)); } catch {}
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
  const auth = initFirebase();
  try {
    const isAndroidNative = typeof window !== 'undefined' && window.AndroidInterface;
    if (isAndroidNative) {
      return new Promise((resolve, reject) => {
        nativeSignInResolver = resolve;
        nativeSignInRejecter = reject;
        window.AndroidInterface.startGoogleSignIn();
      });
    } else {
      const isAndroidApp = typeof navigator !== 'undefined' && navigator.userAgent.includes('KautilyaAndroidApp');
      if (isAndroidApp) {
        await signInWithRedirect(auth, googleProvider);
        return new Promise(() => {});
      } else {
        const result = await signInWithPopup(auth, googleProvider);
        const token = await result.user.getIdToken();
        localStorage.setItem('firebase_token', token);
        localStorage.setItem('user', JSON.stringify({
          uid: result.user.uid,
          email: result.user.email,
          displayName: result.user.displayName,
          photoURL: result.user.photoURL
        }));
        // Fire-and-forget: backend writes users/{uid} on first sight and emails
        // the welcome message. Idempotent — safe on every login.
        try {
          const { userAPI } = await import('./api');
          userAPI.welcomeCheck().catch(() => {});
        } catch {}
        return result.user;
      }
    }
  } catch (error) {
    console.error("Login failed:", error);
    throw error;
  }
};

export const logout = async () => {
  const auth = initFirebase();
  await signOut(auth);
  localStorage.removeItem('firebase_token');
  localStorage.removeItem('user');
};

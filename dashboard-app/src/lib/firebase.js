// Firebase bootstrap. Mirrors the config used in the legacy dashboard so
// existing Firestore data and auth sessions continue to work identically.
import { initializeApp } from 'firebase/app'
import {
  getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged,
} from 'firebase/auth'

export const firebaseConfig = {
  apiKey: 'REDACTED_FIREBASE_WEB_KEY',
  authDomain: 'ai.revealiq.in',
  projectId: 'jarvis-a6e18',
  storageBucket: 'jarvis-a6e18.firebasestorage.app',
  messagingSenderId: '872168972424',
  appId: '1:872168972424:web:2b0b9b82922860a52c3f3d',
  measurementId: 'G-H2FB26YQ9R',
}

export const app = initializeApp(firebaseConfig)
export const auth = getAuth(app)

export function googleSignIn() {
  return signInWithPopup(auth, new GoogleAuthProvider())
}

export function googleSignOut() {
  return signOut(auth)
}

export function onAuthChanged(cb) {
  return onAuthStateChanged(auth, cb)
}

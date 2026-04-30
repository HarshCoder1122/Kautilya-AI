// Auth store. Wraps Firebase auth state in a Pinia store so any component
// can read `currentUser`, react to changes, and trigger sign-in/out.
import { defineStore } from 'pinia'
import { auth, googleSignIn, googleSignOut, onAuthChanged } from '@/lib/firebase'

export const useAuth = defineStore('auth', {
  state: () => ({
    user: null,
    ready: false,
  }),
  getters: {
    isAuthed: (s) => !!s.user,
    displayName: (s) => s.user?.displayName || s.user?.email || 'Guest',
    email: (s) => s.user?.email || '',
    photo: (s) => s.user?.photoURL || '',
  },
  actions: {
    bootstrap() {
      return new Promise((resolve) => {
        onAuthChanged((u) => {
          this.user = u
          this.ready = true
          resolve(u)
        })
      })
    },
    signIn() { return googleSignIn() },
    signOut() { return googleSignOut() },
    async getToken() {
      if (!auth.currentUser) return null
      return await auth.currentUser.getIdToken()
    },
  },
})

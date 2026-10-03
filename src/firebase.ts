import { getApp, getApps, initializeApp } from 'firebase/app'
import { getAuth, type Auth } from 'firebase/auth'

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: 'ttts-poc',
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
}

export const firebaseAuth: Auth | null =
  firebaseConfig.apiKey && firebaseConfig.authDomain && firebaseConfig.appId
    ? getAuth(getApps().length ? getApp() : initializeApp(firebaseConfig))
    : null
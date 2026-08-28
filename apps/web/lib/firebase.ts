"use client";

import { getApp, getApps, initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, onAuthStateChanged, signInWithPopup, type User } from "firebase/auth";
import { useEffect, useState } from "react";

const config = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

export function getFirebaseAuth() {
  if (!config.apiKey || !config.authDomain || !config.projectId || !config.appId) return null;
  const app = getApps().length ? getApp() : initializeApp(config);
  return getAuth(app);
}

export function googleProvider() {
  return new GoogleAuthProvider();
}

export function useFirebaseUser() {
  const auth = getFirebaseAuth();
  const [user, setUser] = useState<User | null>(() => auth?.currentUser ?? null);

  useEffect(() => {
    if (!auth) return undefined;
    return onAuthStateChanged(auth, setUser);
  }, [auth]);

  return { auth, user };
}

export async function signInWithGoogle() {
  const auth = getFirebaseAuth();
  if (!auth) return null;
  return signInWithPopup(auth, googleProvider());
}

"use client";

import { onAuthStateChanged, signInWithPopup, signOut, type User } from "firebase/auth";
import { useEffect, useState } from "react";
import { saveInvestigation } from "../../lib/api";
import { getFirebaseAuth, googleProvider } from "../../lib/firebase";
import type { InvestigationRequest, InvestigationResult } from "../../types/investigation";

type AccountActionsProps = { request: InvestigationRequest | null; result: InvestigationResult | null };

export function AccountActions({ request, result }: AccountActionsProps) {
  const [user, setUser] = useState<User | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const auth = getFirebaseAuth();

  useEffect(() => auth ? onAuthStateChanged(auth, setUser) : undefined, [auth]);

  async function signIn() {
    if (!auth) return;
    setMessage(null);
    try {
      await signInWithPopup(auth, googleProvider());
    } catch {
      setMessage("Google sign-in could not be completed.");
    }
  }

  async function save() {
    if (!user || !request || !result || saving) return;
    setSaving(true);
    setMessage(null);
    try {
      await saveInvestigation(request, result, await user.getIdToken());
      setMessage("Saved to your investigation history.");
    } catch {
      setMessage("This investigation could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  if (!auth) return <p className="account-note">Sign-in and saved investigations will be available in the deployed demo.</p>;
  return <div className="account-actions" aria-live="polite">
    {user ? <><span className="account-email">{user.email ?? "Signed in"}</span><button type="button" className="secondary-button" onClick={() => void signOut(auth)}>Sign out</button>{request && result && <button type="button" className="secondary-button" disabled={saving} onClick={() => void save()}>{saving ? "Saving…" : "Save investigation"}</button>}</> : <button type="button" className="secondary-button" onClick={() => void signIn()}>Sign in with Google</button>}
    {message && <span className="account-message">{message}</span>}
  </div>;
}

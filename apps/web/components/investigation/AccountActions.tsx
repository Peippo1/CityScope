"use client";

import { signOut } from "firebase/auth";
import { useState } from "react";
import { saveInvestigation } from "../../lib/api";
import { signInWithGoogle, useFirebaseUser } from "../../lib/firebase";
import type { InvestigationRequest, InvestigationResult } from "../../types/investigation";

type AccountActionsProps = { request: InvestigationRequest | null; result: InvestigationResult | null };

export function AccountActions({ request, result }: AccountActionsProps) {
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const { auth, user } = useFirebaseUser();

  async function signIn() {
    if (!auth) return;
    setMessage(null);
    try {
      await signInWithGoogle();
    } catch {
      // Popup providers can reject after Firebase has already committed the
      // session (for example when the browser closes the popup callback).
      // Prefer the authoritative auth state over a misleading error banner.
      if (auth.currentUser) setMessage(null);
      else setMessage("Google sign-in could not be completed.");
    }
  }

  async function save() {
    if (!user || !request || !result || saving) return;
    setSaving(true);
    setMessage(null);
    try {
      await saveInvestigation(request, result, await user.getIdToken());
      setMessage("Saved to your journey plans.");
    } catch {
      setMessage("This journey plan could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  if (!auth) return <p className="account-note">Sign-in and saved investigations will be available in the deployed demo.</p>;
  return <div className="account-actions" aria-live="polite">
    {user ? <><span className="account-email">{user.email ?? "Signed in"}</span><button type="button" className="secondary-button" onClick={() => void signOut(auth)}>Sign out</button>{request && result && <button type="button" className="secondary-button" disabled={saving} onClick={() => void save()}>{saving ? "Saving…" : "Save journey plan"}</button>}</> : <button type="button" className="secondary-button" onClick={() => void signIn()}>Sign in with Google</button>}
    {message && <span className="account-message">{message}</span>}
  </div>;
}

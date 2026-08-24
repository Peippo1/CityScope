from __future__ import annotations

import os
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    uid: str
    email: str | None = None


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> CurrentUser:
    """Verify Firebase ID tokens server-side; browser identity alone is never trusted."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required", headers={"WWW-Authenticate": "Bearer"})
    if not os.getenv("FIREBASE_PROJECT_ID"):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Saved investigations are not configured")
    try:
        import firebase_admin
        from firebase_admin import auth

        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(options={"projectId": os.environ["FIREBASE_PROJECT_ID"]})
        claims = auth.verify_id_token(credentials.credentials, check_revoked=True)
        uid = claims.get("uid")
        if not isinstance(uid, str) or not uid:
            raise ValueError("Firebase token has no subject")
        email = claims.get("email")
        return CurrentUser(uid=uid, email=email if isinstance(email, str) else None)
    except HTTPException:
        raise
    except Exception:
        # Authentication failures deliberately do not reveal provider details.
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token", headers={"WWW-Authenticate": "Bearer"}) from None

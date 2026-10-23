import os

from slowapi import Limiter
from jose import JWTError, jwt
from slowapi.util import get_remote_address

from app.core.security import ALGORITHM, SECRET_KEY

limiter = Limiter(key_func=get_remote_address)
ANALYSIS_USER_RPM = max(1, int(os.getenv("ANALYSIS_USER_RPM", "5")))


def authenticated_user_rate_key(request) -> str:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            subject = payload.get("sub")
            if isinstance(subject, str) and subject.isdigit():
                return f"user:{subject}"
        except JWTError:
            pass
    return get_remote_address(request)

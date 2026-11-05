from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from config import JWT_SECRET as SECRET_KEY, JWT_ALGORITHM as ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

if SECRET_KEY == "changeme_use_a_long_random_string_here":
    print("[WARN] JWT_SECRET is the default placeholder. Set a long random value in backend/.env before sharing this server.")

pwd_ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(plain_password: str) -> str:
    """Hash a plain text password (PBKDF2-SHA256 via passlib)."""
    return pwd_ctx.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain text password against its hash."""
    return pwd_ctx.verify(plain_password, hashed_password)


def create_access_token(data: dict) -> str:
    """Create a new JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode a JWT token and return its claims."""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

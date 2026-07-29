"""Autenticação JWT-like sem dependências externas pesadas."""
import base64, hashlib, hmac, json, secrets
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from config.settings import API_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS
from models.orm import User, RefreshToken, Cliente, Organization


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))

def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 120_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"

def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$", 2)
        return hmac.compare_digest(hash_password(password, salt), stored)
    except Exception:
        return False

def create_access_token(payload: dict) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    now = datetime.utcnow()
    body = {
        **payload,
        "iss": "selleros-api",
        "aud": "selleros-console",
        "iat": int(now.timestamp()),
        "jti": secrets.token_urlsafe(18),
        "exp": int((now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
    }
    signing_input = f"{_b64(json.dumps(header,separators=(',',':')).encode())}.{_b64(json.dumps(body,separators=(',',':')).encode())}"
    sig = hmac.new(API_SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256).digest()
    return f"{signing_input}.{_b64(sig)}"

def decode_access_token(token: str) -> dict:
    try:
        head, body, sig = token.split(".")
        signing_input = f"{head}.{body}"
        expected = _b64(hmac.new(API_SECRET_KEY.encode(), signing_input.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected): raise ValueError("assinatura inválida")
        payload = json.loads(_unb64(body))
        if payload.get("iss") != "selleros-api" or payload.get("aud") != "selleros-console":
            raise ValueError("claims inválidas")
        if payload.get("exp", 0) < int(datetime.utcnow().timestamp()): raise ValueError("token expirado")
        return payload
    except Exception as exc:
        raise ValueError("Token inválido") from exc

def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def issue_tokens(db: Session, user: User) -> dict:
    access = create_access_token({"sub": user.id, "tenant_id": user.cliente_id, "organization_id": user.organization_id, "email": user.email})
    refresh = secrets.token_urlsafe(48)
    db.add(RefreshToken(user_id=user.id, token_hash=_token_hash(refresh), expires_at=datetime.utcnow()+timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)))
    user.ultimo_login_em = datetime.utcnow(); db.commit()
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES*60}

def authenticate(db: Session, email: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.email == email.lower().strip(), User.ativo == True).first()
    return user if user and verify_password(password, user.hashed_password) else None

def refresh_tokens(db: Session, refresh_token: str) -> dict:
    row = db.query(RefreshToken).filter_by(token_hash=_token_hash(refresh_token), revoked=False).first()
    if not row or row.expires_at < datetime.utcnow(): raise ValueError("Refresh token inválido")
    user = db.query(User).filter_by(id=row.user_id, ativo=True).first()
    if not user: raise ValueError("Usuário inválido")
    row.revoked = True
    return issue_tokens(db, user)

def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    row = db.query(RefreshToken).filter_by(token_hash=_token_hash(refresh_token), revoked=False).first()
    if row: row.revoked = True; db.commit()

def ensure_demo_user(db: Session) -> User:
    cliente = db.query(Cliente).filter_by(email="demo@marketplace.local").first()
    if not cliente:
        cliente = Cliente(nome="Seller Demo Premium", email="demo@marketplace.local", plano="demo", config={"modo_demo": True, "commission_default": 0.14})
        db.add(cliente); db.flush()
    org = db.query(Organization).filter_by(slug="seller-demo-premium").first()
    if not org:
        org = Organization(nome="Seller Demo Premium", slug="seller-demo-premium", cliente_id=cliente.id, plano="demo", settings={"demo": True})
        db.add(org); db.flush()
    user = db.query(User).filter_by(email="demo@marketplace.local").first()
    if not user:
        user = User(nome="Usuário Demo", email="demo@marketplace.local", cliente_id=cliente.id, organization_id=org.id, hashed_password=hash_password("demo123456"), role="owner")
        db.add(user); db.commit()
    return user

"""
Kimlik doğrulama — JWT tabanlı, bcrypt şifre hash'i
"""
import sqlite3
import jwt
import bcrypt
import os
import secrets
from datetime import datetime, timedelta
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

DB_PATH = "signals.db"
def _load_or_create_secret() -> str:
    """Secret'ı dosyadan oku, yoksa oluştur ve kaydet — restart'ta kaybolmaz."""
    env = os.environ.get("JWT_SECRET")
    if env:
        return env
    secret_file = os.path.join(os.path.dirname(__file__), ".jwt_secret")
    try:
        with open(secret_file) as f:
            return f.read().strip()
    except FileNotFoundError:
        secret = secrets.token_urlsafe(48)
        with open(secret_file, "w") as f:
            f.write(secret)
        os.chmod(secret_file, 0o600)
        return secret

JWT_SECRET = _load_or_create_secret()
JWT_EXP_DAYS = 30

security = HTTPBearer()


# ── DB ────────────────────────────────────────────────────────────────────────

def init_users_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            is_admin INTEGER NOT NULL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    # Varsayılan admin — ilk çalıştırmada oluştur
    c.execute("SELECT COUNT(*) FROM users WHERE is_admin=1")
    if c.fetchone()[0] == 0:
        _create_user_raw(conn, "admin", "admin123", is_admin=True)
    conn.commit()
    conn.close()


def _create_user_raw(conn, username: str, password: str, is_admin: bool = False):
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    conn.cursor().execute(
        "INSERT INTO users (username, password, is_admin) VALUES (?, ?, ?)",
        (username, hashed, 1 if is_admin else 0)
    )


# ── Auth fonksiyonları ────────────────────────────────────────────────────────

def login(username: str, password: str) -> str:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, password, is_admin FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı")
    if not bcrypt.checkpw(password.encode(), row[1].encode()):
        raise HTTPException(status_code=401, detail="Kullanıcı adı veya şifre hatalı")
    payload = {
        "sub": username,
        "uid": row[0],
        "admin": bool(row[2]),
        "exp": datetime.utcnow() + timedelta(days=JWT_EXP_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token süresi doldu")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Geçersiz token")


def require_admin(payload: dict = Security(verify_token)):
    if not payload.get("admin"):
        raise HTTPException(status_code=403, detail="Admin yetkisi gerekli")
    return payload


# ── Kullanıcı yönetimi ────────────────────────────────────────────────────────

def list_users() -> list:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, is_admin, created_at FROM users ORDER BY id")
    rows = c.fetchall()
    conn.close()
    return [{"id": r[0], "username": r[1], "is_admin": bool(r[2]), "created_at": r[3]} for r in rows]


def create_user(username: str, password: str, is_admin: bool = False):
    conn = sqlite3.connect(DB_PATH)
    try:
        _create_user_raw(conn, username, password, is_admin)
        conn.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Kullanıcı adı zaten kullanımda")
    finally:
        conn.close()


def delete_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT is_admin FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    if row[0]:
        c.execute("SELECT COUNT(*) FROM users WHERE is_admin=1")
        if c.fetchone()[0] <= 1:
            raise HTTPException(status_code=400, detail="Son admin silinemez")
    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()


def change_password(user_id: int, new_password: str):
    hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE users SET password=? WHERE id=?", (hashed, user_id))
    conn.commit()
    conn.close()

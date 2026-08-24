from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from typing import Any

from .config import DATA_DIR
from .tenancy import slugify

GOVERNANCE_DB = DATA_DIR / "governance.db"
SESSION_HOURS = 12
SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY,slug TEXT UNIQUE NOT NULL,name TEXT NOT NULL,active INTEGER DEFAULT 1,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,username TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('admin','gestao','especialista')),active INTEGER DEFAULT 1,must_change_password INTEGER DEFAULT 0,created_at TEXT DEFAULT CURRENT_TIMESTAMP,last_login TEXT);
CREATE TABLE IF NOT EXISTS user_products(user_id INTEGER REFERENCES users(id),product_id INTEGER REFERENCES products(id),PRIMARY KEY(user_id,product_id));
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,user_id INTEGER REFERENCES users(id),token_hash TEXT NOT NULL,expires_at TEXT NOT NULL,created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS access_audit(id INTEGER PRIMARY KEY AUTOINCREMENT,user_id INTEGER,action TEXT NOT NULL,target TEXT,details_json TEXT DEFAULT '{}',created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""
CORE_PRODUCTS = ("Cartao","Veiculos","Consignado","Seguros","Investe","Retencao_Cip")
PRODUCTS = CORE_PRODUCTS + ("Legado_Nao_Classificado",)
BOOTSTRAP = (
 ("fran","RI_BOOTSTRAP_FRAN_PASSWORD","admin",()),
 ("joelma","RI_BOOTSTRAP_JOELMA_PASSWORD","gestao",PRODUCTS),
 ("rubia","RI_BOOTSTRAP_RUBIA_PASSWORD","especialista",("Cartao",)),
 ("bruna","RI_BOOTSTRAP_BRUNA_PASSWORD","especialista",("Veiculos",)),
 ("lais","RI_BOOTSTRAP_LAIS_PASSWORD","especialista",("Consignado",)),
 ("vitor","RI_BOOTSTRAP_VITOR_PASSWORD","especialista",("Seguros",)),
 ("karynni","RI_BOOTSTRAP_KARYNNI_PASSWORD","especialista",("Investe",)),
 ("marcela","RI_BOOTSTRAP_MARCELA_PASSWORD","especialista",("Investe",)),
 ("giovana","RI_BOOTSTRAP_GIOVANA_PASSWORD","especialista",("Retencao_Cip",)),
)


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True,exist_ok=True); db=sqlite3.connect(GOVERNANCE_DB); db.row_factory=sqlite3.Row; db.execute("PRAGMA foreign_keys=ON"); return db


def hash_password(password: str) -> str:
    salt=secrets.token_bytes(16); rounds=310000; digest=hashlib.pbkdf2_hmac("sha256",password.encode(),salt,rounds)
    return f"pbkdf2_sha256${rounds}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        _,rounds,salt,digest=encoded.split("$"); actual=hashlib.pbkdf2_hmac("sha256",password.encode(),base64.urlsafe_b64decode(salt),int(rounds))
        return hmac.compare_digest(actual,base64.urlsafe_b64decode(digest))
    except Exception: return False


def init_governance() -> None:
    with connect() as db:
        db.executescript(SCHEMA)
        for name in PRODUCTS: db.execute("INSERT OR IGNORE INTO products(slug,name) VALUES(?,?)",(slugify(name),name))
        for username,password_env,role,products in BOOTSTRAP:
            existing=db.execute("SELECT id FROM users WHERE username=?",(username,)).fetchone()
            password=os.getenv(password_env)
            if not existing and not password:
                continue
            if not existing:
                db.execute("INSERT INTO users(username,password_hash,role,must_change_password) VALUES(?,?,?,0)",(username,hash_password(password),role))
            uid=db.execute("SELECT id FROM users WHERE username=?",(username,)).fetchone()[0]
            for product in products:
                pid=db.execute("SELECT id FROM products WHERE slug=?",(slugify(product),)).fetchone()[0]
                db.execute("INSERT OR IGNORE INTO user_products(user_id,product_id) VALUES(?,?)",(uid,pid))


def _user(row: sqlite3.Row, db: sqlite3.Connection) -> dict:
    products=[dict(r) for r in db.execute("SELECT p.id,p.slug,p.name FROM products p JOIN user_products up ON up.product_id=p.id WHERE up.user_id=? AND p.active=1 ORDER BY p.name",(row["id"],))]
    if row["role"] in {"admin","gestao"}: products=[dict(r) for r in db.execute("SELECT id,slug,name FROM products WHERE active=1 ORDER BY name")]
    return {"id":row["id"],"username":row["username"],"role":row["role"],"active":bool(row["active"]),"must_change_password":bool(row["must_change_password"]),"products":products}


def authenticate(username: str,password: str) -> tuple[str,dict] | None:
    with connect() as db:
        row=db.execute("SELECT * FROM users WHERE username=? AND active=1",(username.strip().lower(),)).fetchone()
        if not row or not verify_password(password,row["password_hash"]): return None
        token=secrets.token_urlsafe(32); sid=secrets.token_hex(16); expires=datetime.now(timezone.utc)+timedelta(hours=SESSION_HOURS)
        db.execute("INSERT INTO sessions(id,user_id,token_hash,expires_at) VALUES(?,?,?,?)",(sid,row["id"],hashlib.sha256(token.encode()).hexdigest(),expires.isoformat()))
        db.execute("UPDATE users SET last_login=? WHERE id=?",(datetime.now(timezone.utc).isoformat(),row["id"]))
        return f"{sid}.{token}",_user(row,db)


def session_user(cookie: str | None) -> dict | None:
    if not cookie or "." not in cookie:return None
    sid,token=cookie.split(".",1)
    with connect() as db:
        row=db.execute("SELECT u.*,s.token_hash,s.expires_at FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.id=?",(sid,)).fetchone()
        if not row or not row["active"] or not hmac.compare_digest(row["token_hash"],hashlib.sha256(token.encode()).hexdigest()): return None
        if datetime.fromisoformat(row["expires_at"])<datetime.now(timezone.utc): db.execute("DELETE FROM sessions WHERE id=?",(sid,)); return None
        return _user(row,db)


def logout(cookie: str | None) -> None:
    if cookie and "." in cookie:
        with connect() as db: db.execute("DELETE FROM sessions WHERE id=?",(cookie.split(".",1)[0],))


def change_password(user_id: int, password: str) -> None:
    if len(password) < 8: raise ValueError("A nova senha deve ter pelo menos 8 caracteres")
    with connect() as db:
        db.execute("UPDATE users SET password_hash=?,must_change_password=0 WHERE id=?",(hash_password(password),user_id))
        db.execute("INSERT INTO access_audit(user_id,action,target) VALUES(?,?,?)",(user_id,"PASSWORD_CHANGED",str(user_id)))


def list_governance() -> dict:
    with connect() as db:
        users=[_user(r,db)|{"last_login":r["last_login"]} for r in db.execute("SELECT * FROM users ORDER BY username")]
        products=[dict(r) for r in db.execute("SELECT * FROM products ORDER BY name")]
    return {"users":users,"products":products}


def create_product(name: str, actor_id: int | None = None) -> dict:
    with connect() as db:
        cur=db.execute("INSERT INTO products(slug,name) VALUES(?,?)",(slugify(name),name.strip()))
        db.execute("INSERT INTO access_audit(user_id,action,target,details_json) VALUES(?,?,?,?)",(actor_id,"PRODUCT_CREATED",str(cur.lastrowid),json.dumps({"name":name.strip()})))
        return {"id":cur.lastrowid,"slug":slugify(name),"name":name.strip()}


def create_user(username: str,password: str,role: str,product_ids: list[int], actor_id: int | None = None) -> dict:
    if role not in {"admin","gestao","especialista"}: raise ValueError("Papel inválido")
    with connect() as db:
        cur=db.execute("INSERT INTO users(username,password_hash,role,must_change_password) VALUES(?,?,?,0)",(username.strip().lower(),hash_password(password),role)); uid=cur.lastrowid
        db.executemany("INSERT INTO user_products(user_id,product_id) VALUES(?,?)",[(uid,p) for p in product_ids]);db.execute("INSERT INTO access_audit(user_id,action,target) VALUES(?,?,?)",(actor_id,"USER_CREATED",str(uid)));row=db.execute("SELECT * FROM users WHERE id=?",(uid,)).fetchone(); return _user(row,db)


def update_user(user_id:int,role:str|None=None,active:bool|None=None,product_ids:list[int]|None=None,password:str|None=None,actor_id:int|None=None) -> dict:
    with connect() as db:
        current=db.execute("SELECT role,active FROM users WHERE id=?",(user_id,)).fetchone()
        if not current: raise ValueError("Usuário não encontrado")
        removing_last_admin=current["role"]=="admin" and current["active"] and (role not in (None,"admin") or active is False)
        if removing_last_admin and db.execute("SELECT COUNT(*) FROM users WHERE role='admin' AND active=1").fetchone()[0]<=1:
            raise ValueError("O último administrador ativo não pode ser removido")
        if role: db.execute("UPDATE users SET role=? WHERE id=?",(role,user_id))
        if active is not None: db.execute("UPDATE users SET active=? WHERE id=?",(int(active),user_id))
        if password: db.execute("UPDATE users SET password_hash=?,must_change_password=0 WHERE id=?",(hash_password(password),user_id))
        if product_ids is not None:
            db.execute("DELETE FROM user_products WHERE user_id=?",(user_id,));db.executemany("INSERT INTO user_products(user_id,product_id) VALUES(?,?)",[(user_id,p) for p in product_ids])
        db.execute("INSERT INTO access_audit(user_id,action,target,details_json) VALUES(?,?,?,?)",(actor_id,"USER_UPDATED",str(user_id),json.dumps({"role":role,"active":active,"products":product_ids,"password_reset":bool(password)})))
        row=db.execute("SELECT * FROM users WHERE id=?",(user_id,)).fetchone(); return _user(row,db)

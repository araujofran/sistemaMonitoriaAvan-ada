from __future__ import annotations

import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .catalog import DETECTORS
from .config import BASE_DIR, MAX_FILE_BYTES
from .database import (batch_summary, clear_database, create_database_backup, enrich_existing_attendants, enrich_existing_causal, enrich_existing_nlp, get_interaction,
    history, init_db, list_batches, list_database_backups, list_interactions_by_product,
    list_periods, list_products)
from .diagnostics import recent_errors, record_error, system_diagnostics
from .explainability import explainability_dashboard
from .importers import SUPPORTED_EXTENSIONS
from .journey import journey_dashboard
from .monitoring import monitoring_answer, monitoring_dashboard, monitoring_filters
from .report import render_report
from .scoring_policy import apply_policy_products, preview_products
from .service import analyze_text, preflight_paths, process_paths
from .governance import (authenticate, change_password, create_product, create_user, init_governance,
    list_governance, logout, session_user, update_user)
from .tenancy import ACTIVE_DATABASE, product_database
from .migration import migrate_legacy_database, run_product_data_migrations

app = FastAPI(title="REGEX INTELLIGENCE — CX & Quality Analytics", version="1.0.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
logger = logging.getLogger(__name__)
SESSION_COOKIE = "ri_session"
SCOPE_COOKIE = "ri_product_scope"


class LoginInput(BaseModel): username: str; password: str
class ProductInput(BaseModel): name: str
class UserInput(BaseModel): username: str; password: str; role: str; product_ids: list[int] = []
class UserUpdate(BaseModel): role: str | None = None; active: bool | None = None; product_ids: list[int] | None = None; password: str | None = None
class PasswordInput(BaseModel): password: str
class PolicyRequest(BaseModel): product_slugs: list[str]; policy: str = "hybrid"


PUBLIC_PATHS = {"/login","/api/v1/auth/login","/health"}
AUTH_PATHS = {"/change-password","/api/v1/auth/change-password","/api/v1/auth/logout","/api/v1/auth/me"}


@app.middleware("http")
async def governance_scope(request: Request, call_next):
    path=request.url.path
    if path in PUBLIC_PATHS or path.startswith("/static/"):
        return await call_next(request)
    user=session_user(request.cookies.get(SESSION_COOKIE))
    if not user:
        if "text/html" in request.headers.get("accept",""): return RedirectResponse("/login?next="+path,303)
        return JSONResponse({"detail":"Autenticação necessária"},401)
    request.state.user=user
    # Authentication routes do not consume product data. Keeping them outside
    # product scoping also prevents a stale cookie from another user's session
    # from blocking the mandatory first-login password change.
    if path in AUTH_PATHS:
        return await call_next(request)
    if user["role"]=="gestao" and request.method not in {"GET","HEAD","OPTIONS"} and path not in {"/api/v1/auth/logout","/api/v1/auth/change-password"}:
        return JSONResponse({"detail":"O papel Gestão possui acesso somente para consulta"},403)
    if (path.startswith("/admin") or path.startswith("/api/v1/admin")) and user["role"]!="admin":
        if path=="/api/v1/admin/backups" and request.method=="GET": return JSONResponse([])
        return JSONResponse({"detail":"Acesso exclusivo do administrador"},403)
    allowed={p["slug"] for p in user["products"]}
    requested_query=request.query_params.get("product_scope")
    requested_cookie=request.cookies.get(SCOPE_COOKIE)
    # An explicit unauthorized scope is rejected. A stale browser cookie from
    # another user's login is ignored and replaced with this user's first
    # authorized product below.
    if requested_query and requested_query not in allowed:
        return JSONResponse({"detail":"Produto não autorizado para este usuário"},403)
    requested=requested_query or (requested_cookie if requested_cookie in allowed else None)
    scope=requested if requested in allowed else (next(iter(sorted(allowed)),None))
    if not scope:
        return JSONResponse({"detail":"Usuário sem produto associado"},403)
    token=ACTIVE_DATABASE.set(product_database(scope))
    try:
        response=await call_next(request)
        response.set_cookie(SCOPE_COOKIE,scope,httponly=True,samesite="lax")
        return response
    finally: ACTIVE_DATABASE.reset(token)


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    error_id = record_error(request.method, request.url.path, exc)
    logger.exception("Erro não tratado em %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={
        "detail": f"Erro interno ao processar a solicitação. Código de diagnóstico: {error_id}.",
        "error_type": type(exc).__name__,
        "error_id": error_id,
    })


@app.on_event("startup")
def startup() -> None:
    init_governance()
    for product in list_governance()["products"]:
        token=ACTIVE_DATABASE.set(product_database(product["slug"]))
        try: init_db()
        finally: ACTIVE_DATABASE.reset(token)
    migrate_legacy_database()
    for product in list_governance()["products"]:
        token=ACTIVE_DATABASE.set(product_database(product["slug"]))
        try: run_product_data_migrations()
        finally: ACTIVE_DATABASE.reset(token)


@app.get("/health")
def health(): return {"status":"ok","detectors":len(DETECTORS)}


@app.get("/login",response_class=HTMLResponse)
def login_page(): return (BASE_DIR/"static"/"login.html").read_text(encoding="utf-8")


@app.post("/api/v1/auth/login")
def login(payload: LoginInput):
    result=authenticate(payload.username,payload.password)
    if not result: raise HTTPException(401,"Usuário ou senha inválidos")
    token,user=result; response=JSONResponse(user);response.set_cookie(SESSION_COOKIE,token,httponly=True,samesite="lax",max_age=43200);response.delete_cookie(SCOPE_COOKIE);return response


@app.post("/api/v1/auth/logout")
def auth_logout(request:Request):
    logout(request.cookies.get(SESSION_COOKIE));response=JSONResponse({"ok":True});response.delete_cookie(SESSION_COOKIE);response.delete_cookie(SCOPE_COOKIE);return response


@app.get("/api/v1/auth/me")
def auth_me(request:Request):
    user=request.state.user
    allowed={p["slug"] for p in user["products"]}
    cookie_scope=request.cookies.get(SCOPE_COOKIE)
    active_scope=cookie_scope if cookie_scope in allowed else next(iter(sorted(allowed)),None)
    return user | {"product_scope":active_scope}


@app.get("/change-password",response_class=HTMLResponse)
def change_password_page(): return (BASE_DIR/"static"/"change-password.html").read_text(encoding="utf-8")


@app.post("/api/v1/auth/change-password")
def auth_change_password(request:Request,payload:PasswordInput):
    try: change_password(request.state.user["id"],payload.password)
    except ValueError as exc: raise HTTPException(400,str(exc))
    return {"ok":True}


@app.get("/admin/governance",response_class=HTMLResponse)
def governance_page(): return (BASE_DIR/"static"/"governance.html").read_text(encoding="utf-8")


@app.get("/api/v1/admin/governance")
def governance_data(): return list_governance()


@app.post("/api/v1/admin/governance/products")
def governance_product(request:Request,payload:ProductInput):
    product=create_product(payload.name,request.state.user["id"]);token=ACTIVE_DATABASE.set(product_database(product["slug"]))
    try: init_db(); run_product_data_migrations()
    finally: ACTIVE_DATABASE.reset(token)
    return product


@app.post("/api/v1/admin/governance/users")
def governance_user(request:Request,payload:UserInput): return create_user(payload.username,payload.password,payload.role,payload.product_ids,request.state.user["id"])


@app.patch("/api/v1/admin/governance/users/{user_id}")
def governance_user_update(request:Request,user_id:int,payload:UserUpdate): return update_user(user_id,actor_id=request.state.user["id"],**payload.model_dump())


@app.post("/api/v1/admin/scoring-policy/preview")
def scoring_policy_preview(payload:PolicyRequest):
    try: return {"products":preview_products(payload.product_slugs),"target_policy":payload.policy}
    except ValueError as exc: raise HTTPException(400,str(exc))


@app.post("/api/v1/admin/scoring-policy/apply")
def scoring_policy_apply(request:Request,payload:PolicyRequest):
    try: return apply_policy_products(payload.product_slugs,payload.policy,request.state.user["id"])
    except ValueError as exc: raise HTTPException(400,str(exc))


@app.get("/", response_class=HTMLResponse)
def home(): return (BASE_DIR / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/v1/batches")
def batches(): return list_batches()


@app.get("/api/v1/batches/{batch_id}")
def batch(batch_id: str): return batch_summary(batch_id)


@app.get("/api/v1/products")
def products(): return list_products()


@app.get("/api/v1/products/{product}/interactions")
def product_interactions(product: str): return list_interactions_by_product(product)


@app.get("/api/v1/journey")
def journey(batch_id: str | None = None, product: str | None = None):
    return journey_dashboard(batch_id, product)


@app.get("/api/v1/history/periods")
def periods(): return list_periods()


@app.get("/api/v1/history")
def historical_analyses(year: int | None = None, month: int | None = None, day: str | None = None, product: str | None = None):
    return history(year, month, day, product)


@app.get("/api/v1/admin/backups")
def backups(): return list_database_backups()


@app.post("/api/v1/admin/backups")
def backup_database(): return create_database_backup("manual")


@app.get("/admin/diagnostics", response_class=HTMLResponse)
def diagnostics_page(): return (BASE_DIR / "static" / "diagnostics.html").read_text(encoding="utf-8")


@app.get("/api/v1/admin/diagnostics")
def diagnostics(): return system_diagnostics()


@app.get("/api/v1/admin/diagnostics/errors")
def diagnostic_errors(limit: int = 30): return recent_errors(limit)


@app.post("/api/v1/admin/nlp/enrich")
def enrich_nlp(): return enrich_existing_nlp()


@app.post("/api/v1/admin/causal/enrich")
def enrich_causal(): return enrich_existing_causal()


@app.post("/api/v1/admin/attendants/enrich")
def enrich_attendants(): return enrich_existing_attendants()


@app.delete("/api/v1/admin/data")
def delete_data(confirmation: str, product: str | None = None):
    expected = f"DELETE_PRODUCT:{product}" if product else "DELETE_ALL"
    if confirmation != expected:
        raise HTTPException(400,"Confirmação inválida")
    return clear_database(product)


@app.get("/journey", response_class=HTMLResponse)
def journey_page(): return (BASE_DIR / "static" / "journey.html").read_text(encoding="utf-8")


@app.get("/monitoring", response_class=HTMLResponse)
def monitoring_page(): return (BASE_DIR / "static" / "monitoring.html").read_text(encoding="utf-8")


@app.get("/explainability", response_class=HTMLResponse)
def explainability_page(): return (BASE_DIR / "static" / "explainability.html").read_text(encoding="utf-8")


@app.get("/api/v1/explainability")
def explainability(criterion: str | None = None, status: str | None = None,
                   search: str | None = None, limit: int = 100, offset: int = 0):
    return explainability_dashboard(criterion, status, search, limit, offset)


@app.get("/api/v1/monitoring")
def monitoring(batch_id: str | None = None, product: str | None = None,
               operator: str | None = None, year: int | None = None, month: int | None = None):
    return monitoring_dashboard(batch_id, product, operator, year, month)


@app.get("/api/v1/monitoring/filters")
def monitoring_filter_options(): return monitoring_filters()


@app.get("/api/v1/monitoring/chat")
def monitoring_chat(q: str, batch_id: str | None = None, product: str | None = None,
                    operator: str | None = None, year: int | None = None, month: int | None = None):
    return monitoring_answer(q, batch_id=batch_id, product=product, operator=operator, year=year, month=month)


@app.get("/api/v1/interactions/{interaction_id}")
def interaction(interaction_id: str):
    result = get_interaction(interaction_id)
    if not result: raise HTTPException(404,"Atendimento não encontrado")
    return result


@app.get("/reports/{interaction_id}", response_class=HTMLResponse)
def report(interaction_id: str):
    result = get_interaction(interaction_id)
    if not result: raise HTTPException(404,"Atendimento não encontrado")
    return render_report(result)


@app.get("/api/v1/regex")
def regex_catalog(): return [{"regex_id":d.regex_id,"name":d.name,"group":d.group,"speaker":d.speaker,"criteria":d.criteria,"pattern":d.pattern} for d in DETECTORS]


@app.post("/api/v1/analyze")
async def analyze(file: UploadFile = File(...)):
    raw = await file.read()
    if len(raw) > MAX_FILE_BYTES: raise HTTPException(413,"Arquivo excede o limite")
    _, result = analyze_text(raw.decode("utf-8-sig",errors="replace"), file.filename or "transcricao.txt")
    return result


async def _save_uploads(files: list[UploadFile], folder: str) -> list[Path]:
    paths=[]
    for f in files:
        suffix=Path(f.filename or "").suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise HTTPException(415,f"Formato {suffix or 'sem extensão'} não suportado. Aceitos: {', '.join(sorted(SUPPORTED_EXTENSIONS))}")
        raw=await f.read()
        if len(raw)>MAX_FILE_BYTES: raise HTTPException(413,f"{f.filename} excede o limite")
        path=Path(folder)/Path(f.filename).name; path.write_bytes(raw); paths.append(path)
    return paths


@app.post("/api/v1/uploads/preflight")
async def upload_preflight(files: list[UploadFile] = File(...)):
    with TemporaryDirectory() as folder:
        return preflight_paths(await _save_uploads(files,folder))


@app.post("/api/v1/batches")
async def upload_batch(request: Request, files: list[UploadFile] = File(...), reanalyze: bool = False):
    with TemporaryDirectory() as folder:
        return process_paths(await _save_uploads(files,folder),"Upload via API",reanalyze,request.state.user["username"])


@app.get("/api/v1/interactions/{interaction_id}/export", response_class=PlainTextResponse)
def export_json(interaction_id: str):
    result=get_interaction(interaction_id)
    if not result: raise HTTPException(404,"Atendimento não encontrado")
    return PlainTextResponse(json.dumps(result,ensure_ascii=False,indent=2),media_type="application/json")

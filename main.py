from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Field, SQLModel, create_engine, Session, select
from sqlalchemy import inspect, text
from pydantic import BaseModel
from datetime import datetime, timedelta
from collections import defaultdict
from openai import OpenAI
from dotenv import load_dotenv
import os, json, bcrypt, jwt

load_dotenv()

client     = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
SECRET_KEY = os.getenv("SECRET_KEY", "change-moi-en-production")
ALGORITHM  = "HS256"
TOKEN_EXPIRE_HOURS = 8

app    = FastAPI(title="Team Manager API", version="4.0")
bearer = HTTPBearer()

# ─────────────────────────────────────────
# CORS
# ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────
# DATABASE — connexion résiliente
# FIX : ajoute pool_pre_ping + pool_recycle pour éviter les erreurs de
# connexion quand le provider (Neon/Render Postgres) coupe les connexions
# inactives après quelques minutes. Sans ça, le premier appel après une
# pause utilise une connexion "morte" et plante -> erreurs vues sur un
# autre appareil / après inactivité.
# ─────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,     # reconnexion automatique si connexion morte
        pool_recycle=300,       # recycle avant que le provider ne coupe
        pool_size=5,
        max_overflow=10,
        connect_args={"connect_timeout": 10},
    )
    print("✅ Connecté à PostgreSQL (pool résilient)")
else:
    engine = create_engine("sqlite:///database.db", connect_args={"check_same_thread": False})
    print("⚠️  PostgreSQL non trouvé — SQLite utilisé en local")

# ─────────────────────────────────────────
# MODÈLES
# ─────────────────────────────────────────

class PromptRequest(BaseModel):
    prompt: str

class StatusUpdate(BaseModel):
    status: str

class UserCreate(BaseModel):
    name:     str
    password: str
    role:     str = "member"

class UserUpdate(BaseModel):
    role: str | None = None

class PasswordChange(BaseModel):
    ancien_mot_de_passe:  str | None = None
    nouveau_mot_de_passe: str

class User(SQLModel, table=True):
    id:       int | None = Field(default=None, primary_key=True)
    name:     str        = Field(unique=True, index=True)
    password: str
    role:     str        = "member"

class Task(SQLModel, table=True):
    id:           int | None = Field(default=None, primary_key=True)
    title:        str
    description:  str
    assigned_to:  str
    completed:    bool       = False
    status:       str        = "todo"
    priority:     str        = "low"
    due_date:     str | None = None
    completed_at: str | None = None
    created_at:   str | None = Field(default_factory=lambda: datetime.now().isoformat())  # nouveau — nécessaire pour les courbes CRM

class AppSettings(SQLModel, table=True):
    id:                    int | None = Field(default=None, primary_key=True)
    nom_equipe:            str  = "Mon Équipe"
    capacite_max_taches:   int  = 10     # tâches actives max / membre avant alerte de surcharge
    delai_alerte_retard_h: int  = 48     # heures après due_date avant alerte de retard
    suppression_auto_h:    int  = 24     # délai avant suppression auto des tâches "done"
    notifications_actives: bool = True
    updated_at:            str  = Field(default_factory=lambda: datetime.now().isoformat())

class AppSettingsUpdate(BaseModel):
    nom_equipe:            str | None  = None
    capacite_max_taches:   int | None  = None
    delai_alerte_retard_h: int | None  = None
    suppression_auto_h:    int | None  = None
    notifications_actives: bool | None = None

# ─────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────

def create_db():
    SQLModel.metadata.create_all(engine)

def run_migrations():
    """
    create_all() ne modifie JAMAIS une table déjà existante — il crée
    seulement les tables manquantes. Si la base existait déjà avant l'ajout
    d'une colonne (ex: task.created_at), il faut l'ajouter à la main via
    ALTER TABLE, sinon chaque INSERT plante avec "has no column named ...".
    Compatible SQLite et PostgreSQL.
    """
    inspector = inspect(engine)
    with engine.begin() as conn:
        if inspector.has_table("task"):
            cols = {c["name"] for c in inspector.get_columns("task")}
            if "created_at" not in cols:
                print("🔧 Migration : ajout de la colonne task.created_at")
                conn.execute(text("ALTER TABLE task ADD COLUMN created_at VARCHAR"))

@app.on_event("startup")
def on_startup():
    create_db()
    run_migrations()
    with Session(engine) as session:
        if not session.exec(select(User)).first():
            hashed = bcrypt.hashpw("admin".encode(), bcrypt.gensalt()).decode()
            session.add(User(name="admin", password=hashed, role="admin"))
            session.commit()
            print("✅ Admin par défaut créé")
        if not session.exec(select(AppSettings)).first():
            session.add(AppSettings())
            session.commit()
            print("✅ Paramètres par défaut initialisés")

# ─────────────────────────────────────────
# JWT — HELPERS
# ─────────────────────────────────────────

def create_token(user_id: int, name: str, role: str) -> str:
    payload = {
        "sub":  str(user_id),
        "name": name,
        "role": role,
        "exp":  datetime.utcnow() + timedelta(hours=TOKEN_EXPIRE_HOURS)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expiré — reconnecte-toi")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token invalide")

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer)) -> dict:
    return decode_token(creds.credentials)

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Accès réservé aux admins")
    return user

# ─────────────────────────────────────────
# ROUTES — AUTH
# ─────────────────────────────────────────

@app.get("/")
def root():
    db_type = "PostgreSQL" if os.getenv("DATABASE_URL") else "SQLite"
    return {"status": "✅ Team Manager API v4.0", "database": db_type}

@app.post("/login")
def login(data: UserCreate):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.name == data.name)).first()
        if not user or not bcrypt.checkpw(data.password.encode(), user.password.encode()):
            raise HTTPException(status_code=401, detail="Identifiants incorrects")
        token = create_token(user.id, user.name, user.role)
        return {"success": True, "token": token, "name": user.name, "role": user.role, "id": user.id}

# ─────────────────────────────────────────
# ROUTES — USERS
# ─────────────────────────────────────────

@app.post("/users")
def create_user(data: UserCreate):
    with Session(engine) as session:
        if session.exec(select(User).where(User.name == data.name)).first():
            raise HTTPException(status_code=400, detail="Ce nom d'utilisateur est déjà pris")
        if len(data.password) < 6:
            raise HTTPException(status_code=400, detail="Mot de passe trop court (6 caractères minimum)")
        hashed = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
        user   = User(name=data.name, password=hashed, role=data.role)
        session.add(user)
        session.commit()
        session.refresh(user)
        return {"id": user.id, "name": user.name, "role": user.role}

@app.get("/users")
def get_users(_: dict = Depends(get_current_user)):
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        return [{"id": u.id, "name": u.name, "role": u.role} for u in users]

@app.get("/users/me")
def get_me(current: dict = Depends(get_current_user)):
    with Session(engine) as session:
        user = session.get(User, int(current["sub"]))
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        return {"id": user.id, "name": user.name, "role": user.role}

@app.put("/users/{user_id}")
def update_user(user_id: int, data: UserUpdate, _: dict = Depends(require_admin)):
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        for key, val in data.dict(exclude_unset=True).items():
            setattr(user, key, val)
        session.add(user)
        session.commit()
        session.refresh(user)
        return {"id": user.id, "name": user.name, "role": user.role}

@app.delete("/users/{user_id}")
def delete_user(user_id: int, current: dict = Depends(require_admin)):
    if int(current["sub"]) == user_id:
        raise HTTPException(status_code=400, detail="Impossible de supprimer votre propre compte")
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        session.delete(user)
        session.commit()
        return {"message": "Utilisateur supprimé"}

@app.put("/users/{user_id}/password")
def change_password(user_id: int, data: PasswordChange, current: dict = Depends(get_current_user)):
    is_self  = int(current["sub"]) == user_id
    is_admin = current.get("role") == "admin"
    if not is_self and not is_admin:
        raise HTTPException(status_code=403, detail="Non autorisé")
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            raise HTTPException(status_code=404, detail="Utilisateur non trouvé")
        if is_self and not is_admin:
            if not data.ancien_mot_de_passe or not bcrypt.checkpw(
                data.ancien_mot_de_passe.encode(), user.password.encode()
            ):
                raise HTTPException(status_code=400, detail="Ancien mot de passe incorrect")
        if len(data.nouveau_mot_de_passe) < 6:
            raise HTTPException(status_code=400, detail="Mot de passe trop court (6 caractères minimum)")
        user.password = bcrypt.hashpw(data.nouveau_mot_de_passe.encode(), bcrypt.gensalt()).decode()
        session.add(user)
        session.commit()
        return {"message": "Mot de passe mis à jour"}

# ─────────────────────────────────────────
# ROUTES — TASKS
# ─────────────────────────────────────────

@app.get("/tasks")
def get_tasks(_: dict = Depends(get_current_user)):
    with Session(engine) as session:
        all_tasks = session.exec(select(Task)).all()
        result, now = [], datetime.now()
        for task in all_tasks:
            if task.status == "done" and task.completed_at:
                if now - datetime.fromisoformat(task.completed_at) > timedelta(hours=24):
                    session.delete(task)
                    session.commit()
                    continue
            result.append(task)
        return result

@app.post("/tasks")
def create_task(task: Task, _: dict = Depends(get_current_user)):
    with Session(engine) as session:
        session.add(task)
        session.commit()
        session.refresh(task)
        return task

@app.put("/tasks/{task_id}/status")
def update_status(task_id: int, data: StatusUpdate, _: dict = Depends(get_current_user)):
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Tâche non trouvée")
        task.status = data.status
        if data.status == "done":
            task.completed    = True
            task.completed_at = datetime.now().isoformat()
        else:
            task.completed    = False
            task.completed_at = None
        session.add(task)
        session.commit()
        return {"message": "Statut mis à jour"}

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int, _: dict = Depends(get_current_user)):
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Tâche non trouvée")
        session.delete(task)
        session.commit()
        return {"message": "Tâche supprimée"}

# ─────────────────────────────────────────
# ROUTE — IA
# ─────────────────────────────────────────

@app.post("/ai/task")
def ai_create_task(data: PromptRequest, _: dict = Depends(get_current_user)):
    today   = datetime.now().strftime("%Y-%m-%d")
    weekday = datetime.now().strftime("%A")

    system_prompt = f"""Tu es un assistant de gestion de tâches.
Aujourd'hui nous sommes le {today} ({weekday}).

À partir du message de l'utilisateur, extrais les informations suivantes et réponds UNIQUEMENT en JSON valide, sans texte autour.

Champs à extraire :
- "title"       : titre court et clair de la tâche (string)
- "description" : description complète reprenant le message original (string)
- "assigned_to" : prénom de la personne mentionnée. Si personne n'est mentionné, mets "Non assigné"
- "priority"    : "high" si urgent/critique/immédiat, "medium" si important/cette semaine, "low" sinon
- "due_date"    : date au format YYYY-MM-DD si mentionnée, sinon null
- "status"      : toujours "todo"

Réponds UNIQUEMENT avec le JSON, rien d'autre."""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": data.prompt}
            ],
            temperature=0.2,
            max_tokens=300
        )
        raw    = response.choices[0].message.content.strip()
        raw    = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        return {
            "title":       result.get("title",       data.prompt[:50]),
            "description": result.get("description", data.prompt),
            "assigned_to": result.get("assigned_to", "Non assigné"),
            "priority":    result.get("priority",    "low"),
            "due_date":    result.get("due_date",    None),
            "status":      "todo"
        }
    except json.JSONDecodeError:
        return {"title": data.prompt[:60].capitalize(), "description": data.prompt,
                "assigned_to": "Non assigné", "priority": "low", "due_date": None,
                "status": "todo", "warning": "IA indisponible - parsing basique utilisé"}
    except Exception as e:
        return {"title": data.prompt[:60].capitalize(), "description": data.prompt,
                "assigned_to": "Non assigné", "priority": "low", "due_date": None,
                "status": "todo", "error": str(e)}

# ─────────────────────────────────────────
# ROUTES — CRM / PERFORMANCE ÉQUIPE
# ─────────────────────────────────────────

def _parse_dt(s: str | None):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

@app.get("/stats/team")
def get_team_stats(_: dict = Depends(get_current_user)):
    """KPI de performance par membre : volumes par statut, taux de complétion, temps moyen de traitement."""
    with Session(engine) as session:
        tasks = session.exec(select(Task)).all()
        users = session.exec(select(User)).all()

    result = []
    for u in users:
        u_tasks = [t for t in tasks if t.assigned_to == u.name]
        total   = len(u_tasks)
        done    = [t for t in u_tasks if t.status == "done"]
        prog    = [t for t in u_tasks if t.status == "in_progress"]
        pause   = [t for t in u_tasks if t.status == "paused"]
        todo    = [t for t in u_tasks if t.status == "todo"]

        durees = []
        for t in done:
            c, comp = _parse_dt(t.created_at), _parse_dt(t.completed_at)
            if c and comp and comp >= c:
                durees.append((comp - c).total_seconds() / 3600)
        temps_moyen = round(sum(durees) / len(durees), 1) if durees else None
        taux = round((len(done) / total) * 100, 1) if total else 0.0

        result.append({
            "name":              u.name,
            "role":              u.role,
            "total_taches":      total,
            "terminees":         len(done),
            "en_cours":          len(prog),
            "en_pause":          len(pause),
            "a_faire":           len(todo),
            "taux_completion":   taux,
            "temps_moyen_h":     temps_moyen,
            "taches_haute_prio": len([t for t in u_tasks if t.priority == "high"]),
        })

    result.sort(key=lambda r: r["terminees"], reverse=True)
    return result

def _build_timeline(tasks: list, jours: int) -> dict:
    """Construit les séries créées/terminées jour par jour pour un ensemble de tâches donné."""
    since = datetime.now() - timedelta(days=jours)
    buckets_created = defaultdict(int)
    buckets_done    = defaultdict(int)

    for t in tasks:
        c = _parse_dt(t.created_at)
        if c and c >= since:
            buckets_created[c.strftime("%Y-%m-%d")] += 1
        d = _parse_dt(t.completed_at)
        if d and d >= since:
            buckets_done[d.strftime("%Y-%m-%d")] += 1

    labels = [(since + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(jours + 1)]
    return {
        "labels":    labels,
        "creees":    [buckets_created.get(d, 0) for d in labels],
        "terminees": [buckets_done.get(d, 0) for d in labels],
    }

@app.get("/stats/team/{name}/timeline")
def get_member_timeline(name: str, jours: int = 30, _: dict = Depends(get_current_user)):
    """Courbe d'activité d'un membre : tâches créées vs terminées, jour par jour."""
    with Session(engine) as session:
        tasks = session.exec(select(Task).where(Task.assigned_to == name)).all()
    return _build_timeline(tasks, jours)

# ─────────────────────────────────────────
# ROUTES — STATS GLOBALES (pour le Dashboard)
# ─────────────────────────────────────────

@app.get("/stats/global")
def get_global_stats(_: dict = Depends(get_current_user)):
    """KPI globaux équipe : volumes, temps moyen de traitement, répartition par priorité."""
    with Session(engine) as session:
        tasks = session.exec(select(Task)).all()

    done = [t for t in tasks if t.status == "done"]
    durees = []
    for t in done:
        c, comp = _parse_dt(t.created_at), _parse_dt(t.completed_at)
        if c and comp and comp >= c:
            durees.append((comp - c).total_seconds() / 3600)
    temps_moyen = round(sum(durees) / len(durees), 1) if durees else None

    return {
        "total":         len(tasks),
        "terminees":     len(done),
        "en_cours":      len([t for t in tasks if t.status == "in_progress"]),
        "en_pause":      len([t for t in tasks if t.status == "paused"]),
        "a_faire":       len([t for t in tasks if t.status == "todo"]),
        "temps_moyen_h": temps_moyen,
        "par_priorite": {
            "high":   len([t for t in tasks if t.priority == "high"]),
            "medium": len([t for t in tasks if t.priority == "medium"]),
            "low":    len([t for t in tasks if t.priority == "low"]),
        },
    }

@app.get("/stats/global/timeline")
def get_global_timeline(jours: int = 30, _: dict = Depends(get_current_user)):
    """Courbe d'activité de toute l'équipe : tâches créées vs terminées, jour par jour."""
    with Session(engine) as session:
        tasks = session.exec(select(Task)).all()
    return _build_timeline(tasks, jours)

# ─────────────────────────────────────────
# ROUTES — PARAMÈTRES
# ─────────────────────────────────────────

@app.get("/settings")
def get_settings(_: dict = Depends(get_current_user)):
    with Session(engine) as session:
        settings = session.exec(select(AppSettings)).first()
        if not settings:
            settings = AppSettings()
            session.add(settings)
            session.commit()
            session.refresh(settings)
        return settings

@app.put("/settings")
def update_settings(data: AppSettingsUpdate, _: dict = Depends(require_admin)):
    with Session(engine) as session:
        settings = session.exec(select(AppSettings)).first()
        if not settings:
            settings = AppSettings()
            session.add(settings)
        for key, val in data.dict(exclude_unset=True).items():
            setattr(settings, key, val)
        settings.updated_at = datetime.now().isoformat()
        session.add(settings)
        session.commit()
        session.refresh(settings)
        return settings
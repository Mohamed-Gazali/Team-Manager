from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Field, SQLModel, create_engine, Session, select
from pydantic import BaseModel
from datetime import datetime, timedelta
from openai import OpenAI
from dotenv import load_dotenv
import os, re, json, bcrypt
import jwt

load_dotenv()

client     = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
SECRET_KEY = os.getenv("SECRET_KEY", "change-moi-en-production")
ALGORITHM  = "HS256"
TOKEN_EXPIRE_HOURS = 8

app    = FastAPI(title="Team Manager API", version="3.0")
bearer = HTTPBearer()

# ─────────────────────────────────────────
# DATABASE — PostgreSQL en prod, SQLite en local
# ─────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # ✅ Production — PostgreSQL sur Render
    # Render fournit "postgres://" mais SQLAlchemy veut "postgresql://"
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    engine = create_engine(DATABASE_URL)
    print("✅ Connecté à PostgreSQL")
else:
    # ✅ Local — SQLite
    engine = create_engine("sqlite:///database.db")
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

# ─────────────────────────────────────────
# STARTUP
# ─────────────────────────────────────────

def create_db():
    SQLModel.metadata.create_all(engine)

@app.on_event("startup")
def on_startup():
    create_db()
    with Session(engine) as session:
        if not session.exec(select(User)).first():
            hashed = bcrypt.hashpw("admin".encode(), bcrypt.gensalt()).decode()
            session.add(User(name="admin", password=hashed, role="admin"))
            session.commit()
            print("✅ Admin par défaut créé")

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
    return {"status": "✅ Team Manager API v3.0", "database": db_type}

@app.post("/login")
def login(data: UserCreate):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.name == data.name)).first()
        if not user or not bcrypt.checkpw(data.password.encode(), user.password.encode()):
            raise HTTPException(status_code=401, detail="Identifiants incorrects")
        token = create_token(user.id, user.name, user.role)
        return {"success": True, "token": token, "name": user.name, "role": user.role}

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
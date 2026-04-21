from fastapi import FastAPI
from sqlmodel import Field, SQLModel, create_engine, Session, select
from pydantic import BaseModel
from datetime import datetime, timedelta
from openai import OpenAI
from dotenv import load_dotenv
import os
import re
import json

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

# -------------------------
# MODELES
# -------------------------

class PromptRequest(BaseModel):
    prompt: str

class StatusUpdate(BaseModel):
    status: str

class UserCreate(BaseModel):
    name: str
    password: str
    role: str = "member"

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    password: str
    role: str = "member"  # admin | member

class Task(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    description: str
    assigned_to: str
    completed: bool = False
    status: str = "todo"          # todo | in_progress | paused | done
    priority: str = "low"         # low | medium | high
    due_date: str | None = None
    completed_at: str | None = None   # ← timestamp quand la tâche est terminée

# -------------------------
# DATABASE
# -------------------------

sqlite_file_name = "database.db"
engine = create_engine(f"sqlite:///{sqlite_file_name}")

def create_db():
    SQLModel.metadata.create_all(engine)

@app.on_event("startup")
def on_startup():
    create_db()
    # Créer un admin par défaut si aucun user n'existe
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        if not users:
            admin = User(name="admin", password="admin", role="admin")
            session.add(admin)
            session.commit()

# -------------------------
# USERS
# -------------------------

@app.post("/users")
def create_user(data: UserCreate):
    with Session(engine) as session:
        # Vérifier si le nom existe déjà
        existing = session.exec(select(User).where(User.name == data.name)).first()
        if existing:
            return {"error": "Ce nom d'utilisateur est déjà pris"}
        user = User(name=data.name, password=data.password, role=data.role)
        session.add(user)
        session.commit()
        session.refresh(user)
        return {"id": user.id, "name": user.name, "role": user.role}

@app.get("/users")
def get_users():
    with Session(engine) as session:
        users = session.exec(select(User)).all()
        return [{"id": u.id, "name": u.name, "role": u.role} for u in users]

@app.post("/login")
def login(data: UserCreate):
    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.name == data.name, User.password == data.password)
        ).first()
        if user:
            return {"success": True, "id": user.id, "name": user.name, "role": user.role}
        return {"success": False, "error": "Identifiants incorrects"}

# -------------------------
# TASKS
# -------------------------

@app.post("/tasks")
def create_task(task: Task):
    with Session(engine) as session:
        session.add(task)
        session.commit()
        session.refresh(task)
        return task

@app.get("/tasks")
def get_tasks():
    """Retourne les tâches non terminées + celles terminées depuis moins de 24h."""
    with Session(engine) as session:
        all_tasks = session.exec(select(Task)).all()
        result = []
        now = datetime.now()
        for task in all_tasks:
            if task.status == "done" and task.completed_at:
                completed_time = datetime.fromisoformat(task.completed_at)
                # Supprimer si terminée depuis plus de 24h
                if now - completed_time > timedelta(hours=24):
                    session.delete(task)
                    session.commit()
                    continue
            result.append(task)
        return result

@app.delete("/tasks/{task_id}")
def delete_task(task_id: int):
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if not task:
            return {"error": "Tâche non trouvée"}
        session.delete(task)
        session.commit()
        return {"message": "Tâche supprimée"}

@app.put("/tasks/{task_id}/status")
def update_status(task_id: int, data: StatusUpdate):
    with Session(engine) as session:
        task = session.get(Task, task_id)
        if not task:
            return {"error": "Tâche non trouvée"}
        task.status = data.status
        # Enregistrer l'heure de complétion si on passe à "done"
        if data.status == "done":
            task.completed = True
            task.completed_at = datetime.now().isoformat()
        else:
            task.completed = False
            task.completed_at = None
        session.add(task)
        session.commit()
        return {"message": "Statut mis à jour"}

# -------------------------
# IA
# -------------------------

@app.post("/ai/task")
def ai_create_task(data: PromptRequest):
    today = datetime.now().strftime("%Y-%m-%d")
    weekday = datetime.now().strftime("%A")  # ex: "Monday"

    system_prompt = f"""Tu es un assistant de gestion de tâches. 
Aujourd'hui nous sommes le {today} ({weekday}).

À partir du message de l'utilisateur, extrais les informations suivantes et réponds UNIQUEMENT en JSON valide, sans texte autour.

Champs à extraire :
- "title" : titre court et clair de la tâche (string)
- "description" : description complète reprenant le message original (string)
- "assigned_to" : prénom de la personne mentionnée (ex: "pour Ali" → "Ali"). Si personne n'est mentionné, mets "Non assigné"
- "priority" : "high" si urgent/critique/immédiat, "medium" si important/cette semaine, "low" sinon
- "due_date" : date au format YYYY-MM-DD si une date/heure est mentionnée ("demain", "vendredi", "lundi prochain", "dans 3 jours", "à 18h" → date du jour), sinon null
- "status" : toujours "todo"

Exemples de parsing :
- "réunion urgente pour Ali demain à 9h" → assigned_to: "Ali", priority: "high", due_date: demain
- "avant vendredi envoyer le rapport" → priority: "medium", due_date: prochain vendredi
- "faire la présentation importante pour Sara" → assigned_to: "Sara", priority: "medium"
- "corriger le bug critique" → priority: "high"

Réponds UNIQUEMENT avec le JSON, rien d'autre."""

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": data.prompt}
            ],
            temperature=0.2,  # réponses précises et cohérentes
            max_tokens=300
        )

        raw = response.choices[0].message.content.strip()

        # Nettoyer si GPT ajoute des backticks markdown
        raw = raw.replace("```json", "").replace("```", "").strip()

        result = json.loads(raw)

        # Sécurité : s'assurer que tous les champs existent
        return {
            "title":       result.get("title", data.prompt[:50]),
            "description": result.get("description", data.prompt),
            "assigned_to": result.get("assigned_to", "Non assigné"),
            "priority":    result.get("priority", "low"),
            "due_date":    result.get("due_date", None),
            "status":      "todo"
        }

    except json.JSONDecodeError:
        # Si GPT renvoie quelque chose d'inattendu, fallback basique
        return {
            "title":       data.prompt[:60].capitalize(),
            "description": data.prompt,
            "assigned_to": "Non assigné",
            "priority":    "low",
            "due_date":    None,
            "status":      "todo",
            "warning":     "IA indisponible - parsing basique utilisé"
        }
    except Exception as e:
        return {
            "title":       data.prompt[:60].capitalize(),
            "description": data.prompt,
            "assigned_to": "Non assigné",
            "priority":    "low",
            "due_date":    None,
            "status":      "todo",
            "error":       str(e)
        }
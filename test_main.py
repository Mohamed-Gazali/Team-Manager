"""
Tests unitaires — Team Manager API
Couvre : Auth, Users, Tasks, IA fallback
"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session
from sqlmodel.pool import StaticPool
import os

# ── Override DATABASE_URL avant d'importer main ──
os.environ["DATABASE_URL"]  = ""        # force SQLite en test
os.environ["SECRET_KEY"]    = "test-secret-key-pour-pytest"
os.environ["OPENAI_API_KEY"] = "sk-fake-key-pour-tests"

from main import app, engine, create_db

# ─────────────────────────────────────────
# FIXTURES
# ─────────────────────────────────────────

@pytest.fixture(scope="function", autouse=True)
def setup_db():
    """Recrée une base SQLite vierge avant chaque test."""
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    yield
    SQLModel.metadata.drop_all(engine)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def admin_token(client):
    """Crée un admin et retourne son token JWT."""
    client.post("/users", json={"name": "admin", "password": "admin123", "role": "admin"})
    res = client.post("/login", json={"name": "admin", "password": "admin123"})
    return res.json()["token"]

@pytest.fixture
def member_token(client):
    """Crée un member et retourne son token JWT."""
    client.post("/users", json={"name": "alice", "password": "alice123", "role": "member"})
    res = client.post("/login", json={"name": "alice", "password": "alice123"})
    return res.json()["token"]

@pytest.fixture
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}

@pytest.fixture
def member_headers(member_token):
    return {"Authorization": f"Bearer {member_token}"}

# ─────────────────────────────────────────
# TESTS — ROUTE RACINE
# ─────────────────────────────────────────

def test_root(client):
    """L'API répond correctement."""
    res = client.get("/")
    assert res.status_code == 200
    assert "Team Manager" in res.json()["status"]

# ─────────────────────────────────────────
# TESTS — USERS
# ─────────────────────────────────────────

def test_create_user(client):
    """Création d'un utilisateur réussie."""
    res = client.post("/users", json={"name": "mohamed", "password": "pass123", "role": "member"})
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "mohamed"
    assert data["role"] == "member"
    assert "password" not in data  # mot de passe jamais retourné

def test_create_user_duplicate(client):
    """Impossible de créer deux users avec le même nom."""
    client.post("/users", json={"name": "mohamed", "password": "pass123", "role": "member"})
    res = client.post("/users", json={"name": "mohamed", "password": "autre", "role": "member"})
    assert res.status_code == 400
    assert "déjà pris" in res.json()["detail"]

def test_create_user_password_too_short(client):
    """Mot de passe trop court refusé."""
    res = client.post("/users", json={"name": "test", "password": "ab", "role": "member"})
    assert res.status_code == 400
    assert "court" in res.json()["detail"]

def test_get_users_requires_auth(client):
    """Impossible de lister les users sans token."""
    res = client.get("/users")
    assert res.status_code == 401  # était 403

def test_get_users_with_auth(client, auth_headers):
    """Liste des users accessible avec token valide."""
    res = client.get("/users", headers=auth_headers)
    assert res.status_code == 200
    assert isinstance(res.json(), list)

# ─────────────────────────────────────────
# TESTS — LOGIN / JWT
# ─────────────────────────────────────────

def test_login_success(client):
    """Login réussi retourne un token JWT."""
    client.post("/users", json={"name": "mohamed", "password": "pass123", "role": "member"})
    res = client.post("/login", json={"name": "mohamed", "password": "pass123"})
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert "token" in data
    assert len(data["token"]) > 10  # token non vide

def test_login_wrong_password(client):
    """Mauvais mot de passe retourne 401."""
    client.post("/users", json={"name": "mohamed", "password": "pass123", "role": "member"})
    res = client.post("/login", json={"name": "mohamed", "password": "mauvais"})
    assert res.status_code == 401
    assert "incorrects" in res.json()["detail"]

def test_login_unknown_user(client):
    """Utilisateur inconnu retourne 401."""
    res = client.post("/login", json={"name": "inconnu", "password": "pass123"})
    assert res.status_code == 401

def test_invalid_token(client):
    """Token invalide retourne 401."""
    res = client.get("/tasks", headers={"Authorization": "Bearer token-bidon"})
    assert res.status_code == 401

# ─────────────────────────────────────────
# TESTS — TASKS
# ─────────────────────────────────────────

def test_create_task(client, auth_headers):
    """Création d'une tâche réussie."""
    res = client.post("/tasks", json={
        "title": "Test tâche",
        "description": "Description test",
        "assigned_to": "Mohamed",
        "status": "todo",
        "priority": "medium"
    }, headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Test tâche"
    assert data["status"] == "todo"
    assert data["priority"] == "medium"

def test_get_tasks(client, auth_headers):
    """Liste des tâches retournée correctement."""
    client.post("/tasks", json={"title":"T1","description":"D","assigned_to":"Ali","status":"todo","priority":"low"}, headers=auth_headers)
    client.post("/tasks", json={"title":"T2","description":"D","assigned_to":"Sara","status":"todo","priority":"high"}, headers=auth_headers)
    res = client.get("/tasks", headers=auth_headers)
    assert res.status_code == 200
    assert len(res.json()) == 2

def test_get_tasks_requires_auth(client):
    """Tâches inaccessibles sans token."""
    res = client.get("/tasks")
    assert res.status_code == 401  # était 403
    

def test_update_task_status(client, auth_headers):
    """Mise à jour du statut d'une tâche."""
    task = client.post("/tasks", json={
        "title":"T1","description":"D","assigned_to":"Ali","status":"todo","priority":"low"
    }, headers=auth_headers).json()

    res = client.put(f"/tasks/{task['id']}/status",
                     json={"status": "in_progress"}, headers=auth_headers)
    assert res.status_code == 200
    assert res.json()["message"] == "Statut mis à jour"

def test_task_done_sets_completed_at(client, auth_headers):
    """Passer une tâche à 'done' enregistre completed_at."""
    task = client.post("/tasks", json={
        "title":"T1","description":"D","assigned_to":"Ali","status":"todo","priority":"low"
    }, headers=auth_headers).json()

    client.put(f"/tasks/{task['id']}/status",
               json={"status": "done"}, headers=auth_headers)

    tasks = client.get("/tasks", headers=auth_headers).json()
    done_task = next(t for t in tasks if t["id"] == task["id"])
    assert done_task["completed"] is True
    assert done_task["completed_at"] is not None

def test_delete_task(client, auth_headers):
    """Suppression d'une tâche."""
    task = client.post("/tasks", json={
        "title":"A supprimer","description":"D","assigned_to":"Ali","status":"todo","priority":"low"
    }, headers=auth_headers).json()

    res = client.delete(f"/tasks/{task['id']}", headers=auth_headers)
    assert res.status_code == 200

    tasks = client.get("/tasks", headers=auth_headers).json()
    assert not any(t["id"] == task["id"] for t in tasks)

def test_delete_nonexistent_task(client, auth_headers):
    """Supprimer une tâche inexistante retourne 404."""
    res = client.delete("/tasks/99999", headers=auth_headers)
    assert res.status_code == 404

def test_task_priority_levels(client, auth_headers):
    """Les trois niveaux de priorité fonctionnent."""
    for priority in ["low", "medium", "high"]:
        res = client.post("/tasks", json={
            "title": f"Tâche {priority}", "description": "D",
            "assigned_to": "Test", "status": "todo", "priority": priority
        }, headers=auth_headers)
        assert res.status_code == 200
        assert res.json()["priority"] == priority

# ─────────────────────────────────────────
# TESTS — BCRYPT
# ─────────────────────────────────────────

def test_password_is_hashed(client):
    """Le mot de passe stocké est un hash bcrypt, pas le mot de passe en clair."""
    import bcrypt
    from main import engine
    from sqlmodel import Session, select
    from main import User

    client.post("/users", json={"name": "secureuser", "password": "monmotdepasse", "role": "member"})

    with Session(engine) as session:
        user = session.exec(select(User).where(User.name == "secureuser")).first()
        assert user is not None
        # Le hash commence toujours par $2b$ (bcrypt)
        assert user.password.startswith("$2b$")
        # Le mot de passe en clair n'est pas stocké
        assert user.password != "monmotdepasse"
        # bcrypt peut vérifier le mot de passe original
        assert bcrypt.checkpw("monmotdepasse".encode(), user.password.encode())
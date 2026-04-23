import streamlit as st
import requests
from datetime import datetime, timedelta
import os

# ─────────────────────────────────────────
# CONFIG — EN PREMIER
# ─────────────────────────────────────────
st.set_page_config(page_title="Team Manager", layout="wide", page_icon="🚀")

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000") # ← Remplace par ton URL Render en production

# ─────────────────────────────────────────
# SESSION STATE — AVANT TOUT
# ─────────────────────────────────────────
for key, val in [("logged_in", False), ("user", ""), ("role", ""), ("token", ""), ("page", "Dashboard")]:
    if key not in st.session_state:
        st.session_state[key] = val

# ─────────────────────────────────────────
# HELPER — headers avec JWT token
# ─────────────────────────────────────────
def auth_headers() -> dict:
    """Retourne les headers avec le JWT token pour toutes les requêtes API."""
    return {"Authorization": f"Bearer {st.session_state.token}"}

# ─────────────────────────────────────────
# CSS
# ─────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;600;700&display=swap');
html, body, [class*="css"] {
    font-family: 'Space Grotesk', sans-serif;
    background-color: #0f172a; color: #e2e8f0;
}
.card {
    background: linear-gradient(135deg, #1e293b, #0f172a);
    padding: 20px; border-radius: 14px; text-align: center; border: 1px solid #334155;
}
.card h1 { color: #38bdf8; margin: 0; font-size: 2.2rem; }
.card h3 { color: #94a3b8; margin-bottom: 8px; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 1px; }
.task-card { padding: 14px 16px; margin-bottom: 10px; border-radius: 12px; border-left: 4px solid #334155; font-size: 0.88rem; line-height: 1.6; }
.done-timer { font-size: 0.72rem; color: #64748b; margin-top: 6px; }
.sidebar-section { background: #1e293b; border-radius: 10px; padding: 12px; margin-bottom: 12px; border: 1px solid #334155; }
.user-chip { display: inline-block; background: #0ea5e920; color: #38bdf8; border-radius: 20px; padding: 3px 10px; font-size: 0.8rem; margin: 2px; border: 1px solid #0ea5e940; }
.security-badge { display: inline-flex; align-items: center; gap: 6px; background: rgba(16,185,129,0.1); color: #10b981; border: 1px solid rgba(16,185,129,0.3); border-radius: 20px; padding: 4px 12px; font-size: 0.75rem; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────
# PAGE : LOGIN / REGISTER
# ─────────────────────────────────────────
if not st.session_state.logged_in:

    col = st.columns([1, 2, 1])[1]
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("## 🚀 Team Manager")
        st.markdown('<div style="margin-bottom:1rem;"><span class="security-badge">🔒 Connexion sécurisée — JWT + bcrypt</span></div>', unsafe_allow_html=True)
        st.markdown("---")

        auth_mode = st.radio("Mode", ["🔐 Se connecter", "✨ Créer un compte"],
                             horizontal=True, label_visibility="collapsed")
        st.markdown("<br>", unsafe_allow_html=True)

        # ── LOGIN ──
        if auth_mode == "🔐 Se connecter":
            username = st.text_input("Nom d'utilisateur", placeholder="ex: mohamed")
            password = st.text_input("Mot de passe", type="password", placeholder="••••••••")

            if st.button("Se connecter", use_container_width=True, type="primary"):
                if username and password:
                    try:
                        res  = requests.post(f"{API_URL}/login",
                                             json={"name": username, "password": password})
                        data = res.json()

                        if res.status_code == 200 and data.get("success"):
                            # ✅ Stocke le token JWT en session — jamais dans l'URL
                            st.session_state.logged_in = True
                            st.session_state.user      = data["name"]
                            st.session_state.role      = data["role"]
                            st.session_state.token     = data["token"]
                            st.rerun()
                        else:
                            st.error("❌ " + data.get("detail", "Identifiants incorrects"))
                    except Exception:
                        st.error("🚨 Impossible de contacter le backend")
                else:
                    st.warning("Remplis tous les champs")

        # ── REGISTER ──
        else:
            new_name  = st.text_input("Nom d'utilisateur", placeholder="Choisis un pseudo")
            new_pass  = st.text_input("Mot de passe", type="password", placeholder="••••••••")
            new_pass2 = st.text_input("Confirmer le mot de passe", type="password", placeholder="••••••••")
            new_role  = st.selectbox("Rôle", ["member", "admin"])

            if st.button("Créer mon compte", use_container_width=True, type="primary"):
                if not new_name or not new_pass:
                    st.warning("Remplis tous les champs")
                elif new_pass != new_pass2:
                    st.error("❌ Les mots de passe ne correspondent pas")
                elif len(new_pass) < 6:
                    st.error("❌ Mot de passe trop court (6 caractères minimum)")
                else:
                    try:
                        res  = requests.post(f"{API_URL}/users",
                                             json={"name": new_name, "password": new_pass, "role": new_role})
                        data = res.json()
                        if res.status_code == 400:
                            st.error("❌ " + data.get("detail", "Erreur"))
                        else:
                            st.success("✅ Compte créé ! Tu peux maintenant te connecter.")
                    except Exception:
                        st.error("🚨 Impossible de contacter le backend")

    st.stop()

# ─────────────────────────────────────────
# FETCH DATA (avec token JWT)
# ─────────────────────────────────────────
try:
    tasks_res = requests.get(f"{API_URL}/tasks", headers=auth_headers())
    if tasks_res.status_code == 401:
        # Token expiré → déconnexion automatique
        for k in ["logged_in", "user", "role", "token"]:
            st.session_state[k] = False if k == "logged_in" else ""
        st.warning("⏰ Session expirée, reconnecte-toi.")
        st.rerun()
    tasks = tasks_res.json() if tasks_res.status_code == 200 else []
except Exception:
    tasks = []

try:
    users_res = requests.get(f"{API_URL}/users", headers=auth_headers())
    team = users_res.json() if users_res.status_code == 200 else []
except Exception:
    team = []

# ─────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🚀 Team Manager")
    st.markdown("---")

    st.markdown(f"""
    <div class="sidebar-section">
        <div style="font-size:0.75rem;color:#64748b;text-transform:uppercase;letter-spacing:1px;">Connecté en tant que</div>
        <div style="font-size:1.1rem;font-weight:700;color:#38bdf8;margin-top:4px;">👤 {st.session_state.user}</div>
        <div style="font-size:0.8rem;color:#94a3b8;margin-top:2px;">🏷️ {st.session_state.role.capitalize()}</div>
        <div style="margin-top:8px;"><span class="security-badge">🔒 JWT actif</span></div>
    </div>
    """, unsafe_allow_html=True)

    done_count     = len([t for t in tasks if t["status"] == "done"])
    todo_count     = len([t for t in tasks if t["status"] == "todo"])
    progress_count = len([t for t in tasks if t["status"] == "in_progress"])

    st.markdown(f"""
    <div class="sidebar-section">
        <div style="font-size:0.75rem;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">📊 Stats rapides</div>
        <div style="display:flex;justify-content:space-between;font-size:0.85rem;"><span>⚪ À faire</span><b style="color:#e2e8f0">{todo_count}</b></div>
        <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-top:4px;"><span>🔵 En cours</span><b style="color:#38bdf8">{progress_count}</b></div>
        <div style="display:flex;justify-content:space-between;font-size:0.85rem;margin-top:4px;"><span>🟢 Terminées</span><b style="color:#4ade80">{done_count}</b></div>
    </div>
    """, unsafe_allow_html=True)

    if team:
        chips = "".join([f'<span class="user-chip">👤 {u["name"]}</span>' for u in team])
        st.markdown(f"""
        <div class="sidebar-section">
            <div style="font-size:0.75rem;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">👥 Équipe ({len(team)})</div>
            {chips}
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='font-size:0.75rem;color:#64748b;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;'>Navigation</div>", unsafe_allow_html=True)

    nav_items = {
        "📊 Dashboard":         "Dashboard",
        "➕ Ajouter une tâche":  "Ajouter",
        "🤖 Créer avec l'IA":   "IA",
        "👥 Équipe":            "Equipe",
    }
    if st.session_state.role == "admin":
        nav_items["⚙️ Administration"] = "Admin"

    for label, key in nav_items.items():
        if st.button(label, use_container_width=True, key=f"nav_{key}"):
            st.session_state.page = key
            st.rerun()

    st.markdown("---")
    if st.button("🚪 Déconnexion", use_container_width=True):
        for k in ["logged_in", "user", "role", "token"]:
            st.session_state[k] = False if k == "logged_in" else ""
        st.session_state.page = "Dashboard"
        st.rerun()

page = st.session_state.page

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def get_badge(status):
    return {"done": "🟢", "in_progress": "🔵", "paused": "🟠"}.get(status, "⚪")

def get_priority_icon(priority):
    return {"high": "🔴", "medium": "🟡"}.get(priority, "🟢")

def time_left_done(completed_at_str):
    try:
        expires   = datetime.fromisoformat(completed_at_str) + timedelta(hours=24)
        remaining = expires - datetime.now()
        if remaining.total_seconds() > 0:
            h = int(remaining.total_seconds() // 3600)
            m = int((remaining.total_seconds() % 3600) // 60)
            return f"⏳ Supprimée dans {h}h {m}min"
        return "🗑️ Suppression imminente"
    except Exception:
        return ""

def render_column(title, tasks_list, color, border_color, next_status=None):
    st.markdown(f"### {title}")
    if not tasks_list:
        st.markdown("<div style='color:#475569;font-size:0.85rem;padding:10px;'>Aucune tâche</div>", unsafe_allow_html=True)
        return
    for task in tasks_list:
        badge      = get_badge(task["status"])
        prio       = get_priority_icon(task.get("priority", "low"))
        timer_html = ""
        if task["status"] == "done" and task.get("completed_at"):
            timer_html = f'<div class="done-timer">{time_left_done(task["completed_at"])}</div>'

        st.markdown(f"""
        <div class="task-card" style="background:{color};border-left-color:{border_color};">
            {badge} {prio} <b>{task['title']}</b><br>
            📝 {task.get('description','—')}<br>
            👤 {task['assigned_to']}<br>
            📅 {task.get('due_date') or 'Pas de date'}
            {timer_html}
        </div>
        """, unsafe_allow_html=True)

        if next_status:
            c1, c2 = st.columns(2)
            with c1:
                if st.button("➡️ Avancer", key=f"adv_{task['id']}_{title}"):
                    requests.put(f"{API_URL}/tasks/{task['id']}/status",
                                 json={"status": next_status}, headers=auth_headers())
                    st.rerun()
            with c2:
                if st.button("🗑️", key=f"del_{task['id']}_{title}"):
                    requests.delete(f"{API_URL}/tasks/{task['id']}", headers=auth_headers())
                    st.rerun()
        else:
            if st.button("🗑️ Supprimer", key=f"del_{task['id']}_{title}"):
                requests.delete(f"{API_URL}/tasks/{task['id']}", headers=auth_headers())
                st.rerun()

# ─────────────────────────────────────────
# PAGES
# ─────────────────────────────────────────

if page == "Dashboard":
    st.title("📊 Dashboard")
    total = len(tasks); done_n = len([t for t in tasks if t["status"]=="done"])
    prog_n = len([t for t in tasks if t["status"]=="in_progress"]); pause_n = len([t for t in tasks if t["status"]=="paused"])

    c1,c2,c3,c4 = st.columns(4)
    c1.markdown(f"<div class='card'><h3>Total</h3><h1>{total}</h1></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='card'><h3>Terminées</h3><h1>{done_n}</h1></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='card'><h3>En cours</h3><h1>{prog_n}</h1></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='card'><h3>En pause</h3><h1>{pause_n}</h1></div>", unsafe_allow_html=True)

    st.divider()
    st.subheader("📊 Répartition des tâches")
    st.bar_chart({"Statut":["Terminées","En cours","En pause"],"Nombre":[done_n,prog_n,pause_n]}, x="Statut", y="Nombre")

    st.divider()
    st.subheader("📌 Kanban Board")
    k1,k2,k3,k4 = st.columns(4)
    with k1: render_column("📝 To Do",    [t for t in tasks if t["status"]=="todo"],        "#1e293b","#475569","in_progress")
    with k2: render_column("⚡ En cours", [t for t in tasks if t["status"]=="in_progress"], "#0c2340","#0ea5e9","paused")
    with k3: render_column("⏸ Pause",    [t for t in tasks if t["status"]=="paused"],      "#2d1f00","#f59e0b","done")
    with k4: render_column("✅ Terminé", [t for t in tasks if t["status"]=="done"],         "#0d2b14","#22c55e")

elif page == "Ajouter":
    st.title("➕ Ajouter une tâche")
    col1, col2 = st.columns(2)
    with col1:
        title       = st.text_input("Titre de la tâche")
        description = st.text_area("Description")
        due_date    = st.date_input("Date d'échéance (optionnel)", value=None)
    with col2:
        assigned_to = st.selectbox("Assigner à", [u["name"] for u in team] if team else ["Mohamed"])
        priority    = st.selectbox("Priorité", ["low","medium","high"],
                                   format_func=lambda x:{"low":"🟢 Faible","medium":"🟡 Moyenne","high":"🔴 Haute"}[x])
        status      = st.selectbox("Statut initial", ["todo","in_progress"],
                                   format_func=lambda x:{"todo":"📝 À faire","in_progress":"⚡ En cours"}[x])
    if st.button("✅ Créer la tâche", type="primary", use_container_width=True):
        if title:
            requests.post(f"{API_URL}/tasks",
                          json={"title":title,"description":description,"assigned_to":assigned_to,
                                "status":status,"priority":priority,"due_date":str(due_date) if due_date else None},
                          headers=auth_headers())
            st.success("✅ Tâche créée avec succès !")
        else:
            st.warning("Le titre est obligatoire")

elif page == "IA":
    st.title("🤖 Créer une tâche avec l'IA")
    st.markdown("Décris ta tâche en langage naturel, l'IA la structure automatiquement.")
    prompt = st.text_area("Décris la tâche...", placeholder="Ex: réunion urgente pour Ali demain à 14h")
    if st.button("🤖 Générer", type="primary"):
        if prompt:
            with st.spinner("L'IA analyse ta demande..."):
                try:
                    ai_res = requests.post(f"{API_URL}/ai/task",
                                           json={"prompt": prompt}, headers=auth_headers()).json()
                    st.success("✅ Tâche analysée !")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**Titre** : {ai_res.get('title','—')}")
                        st.markdown(f"**Assigné à** : {ai_res.get('assigned_to','—')}")
                        st.markdown(f"**Priorité** : {ai_res.get('priority','—')}")
                    with c2:
                        st.markdown(f"**Statut** : {ai_res.get('status','—')}")
                        st.markdown(f"**Date** : {ai_res.get('due_date') or 'Non définie'}")
                    requests.post(f"{API_URL}/tasks", json=ai_res, headers=auth_headers())
                    st.info("📌 Tâche ajoutée au board !")
                    if "warning" in ai_res: st.warning(f"⚠️ {ai_res['warning']}")
                except Exception:
                    st.error("❌ Erreur lors de l'appel IA")
        else:
            st.warning("Décris d'abord une tâche")

elif page == "Equipe":
    st.title("👥 Gestion de l'équipe")
    if team:
        st.subheader(f"Membres ({len(team)})")
        for u in team:
            user_tasks = [t for t in tasks if t["assigned_to"] == u["name"]]
            done_u     = len([t for t in user_tasks if t["status"] == "done"])
            st.markdown(f"""
            <div style="background:#1e293b;padding:15px 20px;border-radius:12px;margin-bottom:10px;
                        border-left:4px solid #0ea5e9;display:flex;justify-content:space-between;align-items:center;">
                <div><b style="color:#e2e8f0;"">👤 {u['name']}</b>
                <span style="color:#64748b;font-size:0.8rem;margin-left:10px;">🏷️ {u['role'].capitalize()}</span></div>
                <div style="color:#94a3b8;font-size:0.85rem;">📋 {len(user_tasks)} tâches · ✅ {done_u} terminées</div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Aucun membre trouvé.")
    st.divider()
    st.subheader("➕ Ajouter un nouveau membre")
    col1, col2, col3 = st.columns(3)
    with col1: new_name = st.text_input("Nom d'utilisateur")
    with col2: new_pass = st.text_input("Mot de passe", type="password")
    with col3: new_role = st.selectbox("Rôle", ["member","admin"])
    if st.button("Créer le compte", type="primary"):
        if new_name and new_pass:
            if len(new_pass) < 6:
                st.error("❌ Mot de passe trop court (6 caractères minimum)")
            else:
                res = requests.post(f"{API_URL}/users",
                                    json={"name":new_name,"password":new_pass,"role":new_role}).json()
                if "detail" in res: st.error("❌ " + res["detail"])
                else: st.success(f"✅ Compte créé pour {new_name}"); st.rerun()
        else:
            st.warning("Remplis tous les champs")

elif page == "Admin":
    if st.session_state.role != "admin":
        st.error("⛔ Accès réservé aux administrateurs"); st.stop()
    st.title("⚙️ Administration")
    st.subheader("🗑️ Tâches terminées — Minuterie")
    done_tasks = [t for t in tasks if t["status"] == "done"]
    if done_tasks:
        for t in done_tasks:
            timer = time_left_done(t["completed_at"]) if t.get("completed_at") else "⚠️ Pas de timestamp"
            col1, col2 = st.columns([3,1])
            with col1: st.markdown(f"**{t['title']}** — 👤 {t['assigned_to']} — {timer}")
            with col2:
                if st.button("Supprimer", key=f"admin_del_{t['id']}"):
                    requests.delete(f"{API_URL}/tasks/{t['id']}", headers=auth_headers()); st.rerun()
    else:
        st.info("Aucune tâche terminée.")
    st.divider()
    st.subheader("👥 Tous les utilisateurs")
    for u in team:
        st.markdown(f"**{u['name']}** — {u['role'].capitalize()}")
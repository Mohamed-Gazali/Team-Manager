import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import os

# ─────────────────────────────────────────
# CONFIG — EN PREMIER
# ─────────────────────────────────────────
st.set_page_config(page_title="Team Manager", layout="wide", page_icon="🚀")

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")  # ← Remplace par ton URL Render en production

# ─────────────────────────────────────────
# SESSION STATE — AVANT TOUT
# ─────────────────────────────────────────
for key, val in [("logged_in", False), ("user", ""), ("role", ""), ("token", ""), ("user_id", None), ("page", "Dashboard")]:
    if key not in st.session_state:
        st.session_state[key] = val

# ─────────────────────────────────────────
# HELPER — headers avec JWT token
# ─────────────────────────────────────────
def auth_headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}

# ─────────────────────────────────────────
# HELPER — appel API robuste
# FIX : timeout explicite + message clair si le backend met du temps à
# répondre (plan gratuit Render : le service s'endort après ~15 min
# d'inactivité et met 30-60s à se réveiller). Avant, un appel sans timeout
# pouvait rester bloqué indéfiniment ou planter sans explication —
# c'est ce qui ressemblait à des "erreurs de connexion" sur un autre appareil.
# ─────────────────────────────────────────
def api_call(method, endpoint, timeout=20, **kwargs):
    try:
        return requests.request(method, f"{API_URL}{endpoint}", timeout=timeout, **kwargs)
    except requests.exceptions.Timeout:
        st.error("⏳ Le serveur met du temps à répondre — il se réveille probablement après une pause (plan gratuit Render). Réessaie dans 20-30 secondes.")
        return None
    except requests.exceptions.ConnectionError:
        st.error("🚨 Impossible de contacter le backend. Vérifie qu'il est bien démarré sur Render.")
        return None

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
.perf-card { background: linear-gradient(135deg, #1e293b, #0f172a); border: 1px solid #334155; border-radius: 14px; padding: 18px 20px; margin-bottom: 12px; }
.perf-name { font-weight: 700; font-size: 1rem; color: #e2e8f0; }
.perf-role { font-size: 0.72rem; color: #64748b; text-transform: uppercase; letter-spacing: 1px; }
.progress-track { background: #334155; border-radius: 100px; height: 8px; margin-top: 8px; overflow: hidden; }
.progress-fill { background: linear-gradient(90deg, #0ea5e9, #38bdf8); height: 100%; border-radius: 100px; }
.mini-stat { display: inline-flex; flex-direction: column; align-items: center; margin-right: 22px; }
.mini-stat b { font-size: 1.2rem; color: #e2e8f0; }
.mini-stat span { font-size: 0.68rem; color: #64748b; text-transform: uppercase; letter-spacing: .5px; }
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
                    with st.spinner("Connexion en cours... (peut prendre 30s si le serveur était en veille)"):
                        res = api_call("POST", "/login", json={"name": username, "password": password})
                    if res is not None:
                        try:
                            data = res.json()
                        except Exception:
                            data = {}
                        if res.status_code == 200 and data.get("success"):
                            st.session_state.logged_in = True
                            st.session_state.user      = data["name"]
                            st.session_state.role      = data["role"]
                            st.session_state.token     = data["token"]
                            st.session_state.user_id   = data.get("id")
                            st.rerun()
                        else:
                            st.error("❌ " + data.get("detail", "Identifiants incorrects"))
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
                    res = api_call("POST", "/users", json={"name": new_name, "password": new_pass, "role": new_role})
                    if res is not None:
                        data = res.json()
                        if res.status_code == 400:
                            st.error("❌ " + data.get("detail", "Erreur"))
                        else:
                            st.success("✅ Compte créé ! Tu peux maintenant te connecter.")

    st.stop()

# ─────────────────────────────────────────
# FETCH DATA (avec token JWT)
# ─────────────────────────────────────────
tasks_res = api_call("GET", "/tasks", headers=auth_headers())
if tasks_res is not None and tasks_res.status_code == 401:
    for k in ["logged_in", "user", "role", "token", "user_id"]:
        st.session_state[k] = False if k == "logged_in" else ("" if k != "user_id" else None)
    st.warning("⏰ Session expirée, reconnecte-toi.")
    st.rerun()
tasks = tasks_res.json() if (tasks_res is not None and tasks_res.status_code == 200) else []

users_res = api_call("GET", "/users", headers=auth_headers())
team = users_res.json() if (users_res is not None and users_res.status_code == 200) else []

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
        "⚙️ Paramètres":        "Parametres",
    }
    if st.session_state.role == "admin":
        nav_items["📈 CRM Équipe"]     = "CRM"
        nav_items["🛠️ Administration"] = "Admin"

    for label, key in nav_items.items():
        if st.button(label, use_container_width=True, key=f"nav_{key}"):
            st.session_state.page = key
            st.rerun()

    st.markdown("---")
    if st.button("🚪 Déconnexion", use_container_width=True):
        for k in ["logged_in", "user", "role", "token", "user_id"]:
            st.session_state[k] = False if k == "logged_in" else ("" if k != "user_id" else None)
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
                    api_call("PUT", f"/tasks/{task['id']}/status", json={"status": next_status}, headers=auth_headers())
                    st.rerun()
            with c2:
                if st.button("🗑️", key=f"del_{task['id']}_{title}"):
                    api_call("DELETE", f"/tasks/{task['id']}", headers=auth_headers())
                    st.rerun()
        else:
            if st.button("🗑️ Supprimer", key=f"del_{task['id']}_{title}"):
                api_call("DELETE", f"/tasks/{task['id']}", headers=auth_headers())
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

    # ── Statistiques avancées + courbes ──
    st.divider()
    st.subheader("📈 Statistiques d'équipe")
    gs_res = api_call("GET", "/stats/global", headers=auth_headers())
    global_stats = gs_res.json() if (gs_res is not None and gs_res.status_code == 200) else None

    if global_stats:
        temps_moyen = f"{global_stats['temps_moyen_h']}h" if global_stats["temps_moyen_h"] is not None else "—"
        g1, g2, g3, g4 = st.columns(4)
        g1.markdown(f"<div class='card'><h3>⏱️ Temps moyen d'exécution</h3><h1 style='font-size:1.6rem;'>{temps_moyen}</h1></div>", unsafe_allow_html=True)
        g2.markdown(f"<div class='card'><h3>🔴 Priorité haute</h3><h1 style='font-size:1.6rem;'>{global_stats['par_priorite']['high']}</h1></div>", unsafe_allow_html=True)
        g3.markdown(f"<div class='card'><h3>🟡 Priorité moyenne</h3><h1 style='font-size:1.6rem;'>{global_stats['par_priorite']['medium']}</h1></div>", unsafe_allow_html=True)
        g4.markdown(f"<div class='card'><h3>🟢 Priorité basse</h3><h1 style='font-size:1.6rem;'>{global_stats['par_priorite']['low']}</h1></div>", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)
        periode = st.selectbox("Période de la courbe", [7, 30, 90], index=1, format_func=lambda x: f"{x} jours", key="dash_periode")
        tl_res = api_call("GET", "/stats/global/timeline", params={"jours": periode}, headers=auth_headers())
        if tl_res is not None and tl_res.status_code == 200:
            tl = tl_res.json()
            df_tl = pd.DataFrame({
                "Créées": tl["creees"],
                "Terminées": tl["terminees"],
            }, index=pd.to_datetime(tl["labels"]))
            st.line_chart(df_tl)
        else:
            st.info("Pas encore assez de données pour tracer une courbe.")
    else:
        st.info("Statistiques indisponibles pour le moment.")

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
            res = api_call("POST", "/tasks",
                          json={"title":title,"description":description,"assigned_to":assigned_to,
                                "status":status,"priority":priority,"due_date":str(due_date) if due_date else None},
                          headers=auth_headers())
            if res is not None and res.status_code == 200:
                st.success("✅ Tâche créée avec succès !")
                st.session_state.page = "Dashboard"
                st.rerun()  # FIX : la liste `tasks` était chargée avant ce clic, sans rerun la nouvelle tâche n'apparaissait jamais
        else:
            st.warning("Le titre est obligatoire")

elif page == "IA":
    st.title("🤖 Créer une tâche avec l'IA")
    st.markdown("Décris ta tâche en langage naturel, l'IA la structure automatiquement.")
    prompt = st.text_area("Décris la tâche...", placeholder="Ex: réunion urgente pour Ali demain à 14h")
    if st.button("🤖 Générer", type="primary"):
        if prompt:
            with st.spinner("L'IA analyse ta demande..."):
                res = api_call("POST", "/ai/task", json={"prompt": prompt}, headers=auth_headers())
            if res is not None:
                ai_res = res.json()
                st.success("✅ Tâche analysée !")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Titre** : {ai_res.get('title','—')}")
                    st.markdown(f"**Assigné à** : {ai_res.get('assigned_to','—')}")
                    st.markdown(f"**Priorité** : {ai_res.get('priority','—')}")
                with c2:
                    st.markdown(f"**Statut** : {ai_res.get('status','—')}")
                    st.markdown(f"**Date** : {ai_res.get('due_date') or 'Non définie'}")
                create_res = api_call("POST", "/tasks", json=ai_res, headers=auth_headers())
                if create_res is not None and create_res.status_code == 200:
                    st.info("📌 Tâche ajoutée au board !")
                    if "warning" in ai_res: st.warning(f"⚠️ {ai_res['warning']}")
                    st.session_state.page = "Dashboard"
                    st.rerun()  # FIX : même souci que la création manuelle, la tâche n'apparaissait jamais
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
                res = api_call("POST", "/users", json={"name":new_name,"password":new_pass,"role":new_role})
                if res is not None:
                    data = res.json()
                    if "detail" in data: st.error("❌ " + data["detail"])
                    else: st.success(f"✅ Compte créé pour {new_name}"); st.rerun()
        else:
            st.warning("Remplis tous les champs")

# ── NOUVELLE PAGE — CRM ÉQUIPE (performance + courbes) ──
elif page == "CRM":
    st.title("📈 CRM Équipe — Performance")
    st.caption("Suivi de la charge et de la performance de chaque membre.")

    res = api_call("GET", "/stats/team", headers=auth_headers())
    stats = res.json() if (res is not None and res.status_code == 200) else []

    if not stats:
        st.info("Pas encore de données de performance.")
    else:
        # KPI globaux
        total_eq   = sum(s["total_taches"] for s in stats)
        done_eq    = sum(s["terminees"] for s in stats)
        taux_moyen = round(sum(s["taux_completion"] for s in stats) / len(stats), 1) if stats else 0

        c1, c2, c3 = st.columns(3)
        c1.markdown(f"<div class='card'><h3>Tâches totales (équipe)</h3><h1>{total_eq}</h1></div>", unsafe_allow_html=True)
        c2.markdown(f"<div class='card'><h3>Terminées (équipe)</h3><h1>{done_eq}</h1></div>", unsafe_allow_html=True)
        c3.markdown(f"<div class='card'><h3>Taux de complétion moyen</h3><h1>{taux_moyen}%</h1></div>", unsafe_allow_html=True)

        st.divider()
        st.subheader("🏆 Comparaison — tâches terminées par membre")
        df_compare = pd.DataFrame(stats)[["name", "terminees", "en_cours", "a_faire"]].set_index("name")
        df_compare.columns = ["Terminées", "En cours", "À faire"]
        st.bar_chart(df_compare)

        st.divider()
        st.subheader("👤 Détail par membre")
        for s in stats:
            temps = f"{s['temps_moyen_h']}h" if s["temps_moyen_h"] is not None else "—"
            st.markdown(f"""
            <div class="perf-card">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;">
                    <div>
                        <div class="perf-name">👤 {s['name']}</div>
                        <div class="perf-role">{s['role']}</div>
                    </div>
                    <div>
                        <span class="mini-stat"><b>{s['total_taches']}</b><span>Total</span></span>
                        <span class="mini-stat"><b>{s['terminees']}</b><span>Terminées</span></span>
                        <span class="mini-stat"><b>{s['taches_haute_prio']}</b><span>Priorité haute</span></span>
                        <span class="mini-stat"><b>{temps}</b><span>Temps moyen</span></span>
                    </div>
                </div>
                <div class="progress-track"><div class="progress-fill" style="width:{s['taux_completion']}%;"></div></div>
                <div style="font-size:0.72rem;color:#64748b;margin-top:4px;">Taux de complétion — {s['taux_completion']}%</div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()
        st.subheader("📉 Courbe d'activité d'un membre")
        member_names = [s["name"] for s in stats]
        col_a, col_b = st.columns([2, 1])
        with col_a:
            selected_member = st.selectbox("Membre", member_names)
        with col_b:
            periode_jours = st.selectbox("Période", [7, 30, 90], index=1, format_func=lambda x: f"{x} jours")

        tl_res = api_call("GET", f"/stats/team/{selected_member}/timeline", params={"jours": periode_jours}, headers=auth_headers())
        if tl_res is not None and tl_res.status_code == 200:
            tl = tl_res.json()
            df_tl = pd.DataFrame({
                "Créées": tl["creees"],
                "Terminées": tl["terminees"],
            }, index=pd.to_datetime(tl["labels"]))
            st.line_chart(df_tl)
        else:
            st.info("Pas encore assez de données pour tracer une courbe.")

# ── NOUVELLE PAGE — PARAMÈTRES ──
elif page == "Parametres":
    st.title("⚙️ Paramètres")

    tab_general, tab_compte, tab_users = st.tabs(["🏢 Général", "🔑 Mon compte", "👥 Utilisateurs"])

    with tab_general:
        res = api_call("GET", "/settings", headers=auth_headers())
        settings = res.json() if (res is not None and res.status_code == 200) else {}

        if st.session_state.role != "admin":
            st.info("Seuls les administrateurs peuvent modifier ces paramètres.")

        col1, col2 = st.columns(2)
        with col1:
            nom_equipe = st.text_input("Nom de l'équipe", value=settings.get("nom_equipe", "Mon Équipe"),
                                        disabled=(st.session_state.role != "admin"))
            capacite = st.number_input("Capacité max de tâches actives / membre", min_value=1, max_value=100,
                                        value=settings.get("capacite_max_taches", 10),
                                        disabled=(st.session_state.role != "admin"))
        with col2:
            delai_retard = st.number_input("Alerte de retard après (heures)", min_value=1, max_value=500,
                                            value=settings.get("delai_alerte_retard_h", 48),
                                            disabled=(st.session_state.role != "admin"))
            suppression_h = st.number_input("Suppression auto des tâches terminées après (heures)", min_value=1, max_value=500,
                                             value=settings.get("suppression_auto_h", 24),
                                             disabled=(st.session_state.role != "admin"))
        notif = st.toggle("Notifications actives", value=settings.get("notifications_actives", True),
                           disabled=(st.session_state.role != "admin"))

        if st.session_state.role == "admin":
            if st.button("💾 Enregistrer", type="primary"):
                payload = {
                    "nom_equipe": nom_equipe, "capacite_max_taches": capacite,
                    "delai_alerte_retard_h": delai_retard, "suppression_auto_h": suppression_h,
                    "notifications_actives": notif,
                }
                r = api_call("PUT", "/settings", json=payload, headers=auth_headers())
                if r is not None and r.status_code == 200:
                    st.success("✅ Paramètres mis à jour")
                    st.rerun()

    with tab_compte:
        st.subheader("Changer mon mot de passe")
        ancien = st.text_input("Ancien mot de passe", type="password")
        nouveau = st.text_input("Nouveau mot de passe", type="password")
        nouveau2 = st.text_input("Confirmer le nouveau mot de passe", type="password")
        if st.button("🔑 Mettre à jour le mot de passe", type="primary"):
            if not nouveau or nouveau != nouveau2:
                st.error("❌ Les mots de passe ne correspondent pas")
            elif len(nouveau) < 6:
                st.error("❌ Mot de passe trop court (6 caractères minimum)")
            elif st.session_state.user_id is None:
                st.error("❌ Impossible d'identifier ton compte, reconnecte-toi.")
            else:
                payload = {"nouveau_mot_de_passe": nouveau}
                if st.session_state.role != "admin":
                    payload["ancien_mot_de_passe"] = ancien
                r = api_call("PUT", f"/users/{st.session_state.user_id}/password", json=payload, headers=auth_headers())
                if r is not None and r.status_code == 200:
                    st.success("✅ Mot de passe mis à jour")
                elif r is not None:
                    st.error("❌ " + r.json().get("detail", "Erreur"))

    with tab_users:
        if st.session_state.role != "admin":
            st.info("Réservé aux administrateurs.")
        else:
            st.subheader("Gérer les rôles et comptes")
            for u in team:
                c1, c2, c3 = st.columns([2, 1, 1])
                with c1:
                    st.markdown(f"**👤 {u['name']}** — {u['role'].capitalize()}")
                with c2:
                    new_role = st.selectbox("Rôle", ["member", "admin"], index=0 if u["role"]=="member" else 1,
                                             key=f"role_{u['id']}", label_visibility="collapsed")
                    if new_role != u["role"]:
                        if st.button("Appliquer", key=f"apply_{u['id']}"):
                            r = api_call("PUT", f"/users/{u['id']}", json={"role": new_role}, headers=auth_headers())
                            if r is not None and r.status_code == 200:
                                st.success(f"Rôle mis à jour pour {u['name']}")
                                st.rerun()
                with c3:
                    if u["id"] != st.session_state.user_id:
                        if st.button("🗑️ Supprimer", key=f"deluser_{u['id']}"):
                            r = api_call("DELETE", f"/users/{u['id']}", headers=auth_headers())
                            if r is not None and r.status_code == 200:
                                st.success(f"{u['name']} supprimé")
                                st.rerun()

elif page == "Admin":
    if st.session_state.role != "admin":
        st.error("⛔ Accès réservé aux administrateurs"); st.stop()
    st.title("🛠️ Administration")
    st.subheader("🗑️ Tâches terminées — Minuterie")
    done_tasks = [t for t in tasks if t["status"] == "done"]
    if done_tasks:
        for t in done_tasks:
            timer = time_left_done(t["completed_at"]) if t.get("completed_at") else "⚠️ Pas de timestamp"
            col1, col2 = st.columns([3,1])
            with col1: st.markdown(f"**{t['title']}** — 👤 {t['assigned_to']} — {timer}")
            with col2:
                if st.button("Supprimer", key=f"admin_del_{t['id']}"):
                    api_call("DELETE", f"/tasks/{t['id']}", headers=auth_headers()); st.rerun()
    else:
        st.info("Aucune tâche terminée.")
    st.divider()
    st.subheader("👥 Tous les utilisateurs")
    for u in team:
        st.markdown(f"**{u['name']}** — {u['role'].capitalize()}")
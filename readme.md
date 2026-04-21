# 🚀 Team Manager — Gestion d'équipe intelligente

> Application web de gestion de tâches et d'équipe avec tableau Kanban, IA intégrée et système d'authentification.

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?style=flat&logo=streamlit&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat&logo=sqlite&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)

---

## 📸 Aperçu

| Dashboard | Kanban Board | Gestion d'équipe |
|-----------|-------------|-----------------|
| Stats en temps réel | Colonnes To Do / En cours / Pause / Terminé | Liste des membres + tâches assignées |

---

## ✨ Fonctionnalités

- 🔐 **Authentification** — Connexion sécurisée, création de compte, rôles admin/member
- 📊 **Dashboard** — Statistiques en temps réel avec graphiques
- 📌 **Kanban Board** — Glissement de tâches entre colonnes (To Do → En cours → Pause → Terminé)
- 🤖 **IA intégrée** — Création automatique de tâches depuis une description en langage naturel
- 👥 **Gestion d'équipe** — Ajout de membres, assignation de tâches, suivi par personne
- ⏳ **Suppression automatique** — Les tâches terminées disparaissent après 24h
- ⚙️ **Panel Admin** — Gestion avancée réservée aux administrateurs
- 🎨 **UI moderne** — Design dark mode, responsive, avec indicateurs de priorité

---

## 🛠️ Stack technique

| Couche | Technologie |
|--------|-------------|
| **Backend** | FastAPI + SQLModel + SQLite |
| **Frontend** | Streamlit |
| **Base de données** | SQLite (via SQLModel / ORM) |
| **IA** | OpenAI API (GPT) |
| **Déploiement** | Render (backend) + Streamlit Cloud (frontend) |

---

## 📁 Structure du projet

```
team-manager/
│
├── main.py              # Backend FastAPI (API REST)
├── app.py               # Frontend Streamlit
├── database.db          # Base de données SQLite (générée automatiquement)
├── requirements.txt     # Dépendances Python
├── .gitignore           # Fichiers exclus du repo
└── README.md            # Documentation
```

---

## ⚡ Installation locale

### 1. Cloner le repo

```bash
git clone https://github.com/TON_USERNAME/team-manager.git
cd team-manager
```

### 2. Créer un environnement virtuel

```bash
python -m venv venv
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Lancer le backend

```bash
uvicorn main:app --reload
# API disponible sur http://localhost:8000
# Docs Swagger sur http://localhost:8000/docs
```

### 5. Lancer le frontend (dans un second terminal)

```bash
streamlit run app.py
# Interface disponible sur http://localhost:8501
```

---

## 🌐 Déploiement en production

### Backend → Render

1. Crée un compte sur [render.com](https://render.com)
2. **New Web Service** → connecte ton repo GitHub
3. Paramètres :
   - **Build Command** : `pip install -r requirements.txt`
   - **Start Command** : `uvicorn main:app --host 0.0.0.0 --port 10000`
4. Copie l'URL générée (ex: `https://team-manager-api.onrender.com`)
5. Dans `app.py`, remplace `API_URL` par cette URL

### Frontend → Streamlit Cloud

1. Va sur [share.streamlit.io](https://share.streamlit.io)
2. Connecte ton GitHub et sélectionne `app.py`
3. Déploie en un clic ✅

---

## 🔑 Compte admin par défaut

Au premier lancement, un compte admin est créé automatiquement :

```
Nom d'utilisateur : admin
Mot de passe      : admin
```

> ⚠️ Pense à changer ce mot de passe en production !

---

## 🤝 Contribuer

Les contributions sont les bienvenues !

```bash
# Fork le projet
# Crée une branche
git checkout -b feature/ma-fonctionnalite

# Commit
git commit -m "feat: ajout de ma fonctionnalité"

# Push et ouvre une Pull Request
git push origin feature/ma-fonctionnalite
```

---

## 📄 Licence

Ce projet est sous licence **MIT** — libre d'utilisation, modification et distribution.

---

<div align="center">
  Fait avec ❤️ · <a href="https://github.com/TON_USERNAME">GitHub</a>
</div>
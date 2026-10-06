# 🤖 AI Data Analyst

> Assistant d'analyse de données piloté par l'intelligence artificielle pour explorer, comprendre et transformer des données avec une approche agentique.

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688?style=for-the-badge&logo=fastapi)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?style=for-the-badge&logo=postgresql)
![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react)

</div>

## 📌 Vue d'ensemble

AI Data Analyst est un projet académique visant à concevoir un assistant intelligent capable de :

- importer et analyser des jeux de données,
- interpréter les résultats via une logique d'IA,
- proposer des insights exploitables,
- faciliter l'interaction entre l'utilisateur et les données.

Le projet combine un backend API robuste avec une interface utilisateur moderne, dans une architecture pensée pour le traitement de données et l'analyse intelligente.

## ✨ Fonctionnalités

- Analyse de datasets structurés et semi-structurés,
- assistance à la compréhension des données,
- API REST avec authentification,
- gestion des utilisateurs et des analyses,
- interface web pour interagir facilement avec le système,
- architecture modulaire pour extension future.

## 🏗️ Architecture du projet

```text
AI-Project/
├── backend/                 # API FastAPI + services métiers
│   ├── app/
│   ├── uploads/
│   ├── .env
│   ├── requirements.txt
│   └── README.md
├── frontend/               # Interface utilisateur (si présent)
│   ├── src/
│   ├── package.json
│   └── README.md
├── .gitignore
├── README.md
└── .env.example
```

## 🧰 Stack technique

- Python 3.11+
- FastAPI
- SQLAlchemy
- PostgreSQL
- JWT Authentication
- React / Vite (si applicable au frontend)
- Git + GitHub

## 🚀 Installation

### 1. Cloner le projet

```bash
git clone https://github.com/BouthaynaHammami/AI-Project.git
cd AI-Project
```

### 2. Créer et activer l’environnement virtuel Python

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
```

Sous Windows PowerShell :

```powershell
cd backend
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Installer les dépendances backend

```bash
pip install -r requirements.txt
```

### 4. Configurer les variables d'environnement

Copier `backend/.env.example` vers `backend/.env`. Pour SQLite en local, définir
`DATABASE_URL=sqlite:///./database.db`. `ENV=dev` permet une clé JWT temporaire
si `JWT_SECRET_KEY` est vide. Sans SMTP, le code de vérification est écrit dans
les logs uniquement en développement. Pour voir les emails, démarrer Mailpit
(SMTP `localhost:1025`, interface `http://localhost:8025`).

```env
DATABASE_URL=postgresql+psycopg2://postgres:123@localhost:5432/ai_data_analyst
ENV=dev
JWT_SECRET_KEY=
JWT_EXPIRE_MINUTES=30
FRONTEND_ORIGIN=http://localhost:5173
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_FROM=AI Data Analyst <no-reply@localhost>
SMTP_TLS=false
```

## ▶️ Lancer l'application

### Backend (premier terminal)

```bash
cd backend
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend (second terminal)

```bash
cd frontend
npm ci
npm run dev
```

Ouvrir l’adresse Vite affichée dans le terminal, généralement
`http://localhost:5173`.

### Documentation API

Une fois le backend démarré, ouvrez :

```text
http://localhost:8000/docs
```

## 🔐 Endpoints principaux

### Authentification

- `POST /auth/signup` — inscription et envoi d’un code de vérification
- `POST /auth/verify-email`
- `POST /auth/resend-code`
- `POST /auth/login`
- `GET /auth/me`
- `PUT /auth/me`
- `POST /auth/logout`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`

Les codes expirent après 10 minutes. Les comptes antérieurs à cette vérification
peuvent être marqués comme vérifiés après migration avec
`UPDATE users SET is_verified = TRUE WHERE is_verified = FALSE;`.

Le frontend conserve actuellement le jeton d’accès dans `localStorage` pour
préserver la compatibilité avec l’API bearer existante. Une faille XSS pourrait
permettre à un script injecté de lire ce jeton ; déployer une politique CSP
stricte et éviter toute injection HTML non assainie. Le passage à un cookie
`httpOnly` nécessitera aussi une protection CSRF.

### Données

- `GET /datasets`
- `POST /datasets`

### Analyses

- `GET /analyses`
- `POST /analyses`

## 📁 Structure interne du backend

```text
backend/
├── app/
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── schemas/
│   ├── services/
│   └── main.py
├── uploads/
├── .env
├── requirements.txt
├── README.md
└── uvicorn
```

## 🧪 Développement

- Le backend crée automatiquement les tables nécessaires au démarrage.
- PostgreSQL est recommandé en production ; SQLite est pris en charge pour le développement local.
- Les routes sensibles sont protégées par authentification JWT.
- En développement, les codes sont écrits dans les logs seulement avec `ENV=dev` sans SMTP. En production, configurez SMTP et une clé JWT aléatoire d’au moins 32 caractères.
- Après migration, les comptes historiques peuvent être marqués comme vérifiés avec `UPDATE users SET is_verified = TRUE WHERE is_verified = FALSE;`.

## 🛠️ Dépannage

### Le backend ne démarre pas

- Vérifier que le virtual environment est activé,
- vérifier que PostgreSQL est bien démarré,
- valider le contenu de `.env`,
- réinstaller les dépendances si nécessaire.

### Problème de connexion à la base

- Vérifier l'URL de connexion `DATABASE_URL`,
- vérifier le nom de la base, le port et les identifiants,
- vérifier que le service PostgreSQL tourne correctement.

## 📚 À retenir

Ce projet est conçu comme une base solide pour une solution d'analyse de données assistée par IA, avec une architecture scalable et extensible.

## 📝 Licence

Ce projet est destiné à un usage académique et de démonstration.

---

Projet développé dans le cadre d'un travail académique sur l'analyse de données assistée par l'IA.

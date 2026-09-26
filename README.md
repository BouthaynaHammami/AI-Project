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

### 2. Créer un environnement virtuel

```bash
python -m venv .venv
source .venv/bin/activate
```

Sous Windows PowerShell :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Installer les dépendances backend

```bash
cd backend
pip install -r requirements.txt
```

### 4. Configurer les variables d'environnement

Créer un fichier `.env` dans le dossier `backend` avec une configuration similaire à :

```env
DATABASE_URL=postgresql+psycopg2://postgres:123@localhost:5432/ai_data_analyst
JWT_SECRET_KEY=your_secret_key
FRONTEND_ORIGIN=http://localhost:5173
```

## ▶️ Lancer l'application

### Backend

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Documentation API

Une fois le backend démarré, ouvrez :

```text
http://localhost:8000/docs
```

## 🔐 Endpoints principaux

### Authentification

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`

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
- PostgreSQL est requis pour le stockage des données.
- Les routes sensibles sont protégées par authentification JWT.

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

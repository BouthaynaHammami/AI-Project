# 📊 AI Data Analyst

Projet académique — Assistant d'analyse de données par IA (approche agentique)

**École :** ESPRIT (École Supérieure Privée d'Ingénierie et de Technologies)
**Classe :** 5ème 7
**Module :** Intelligence Artificielle (IA)
## Équipe

Projet réalisé dans le cadre du module **Intelligence Artificielle** .

- Bouthayna Hammami
- Sourour Alaimi
- Mayssa Klibi
- Islem Bouchaala
- Hazem Ouasli
- Islem Raissi

## Description

**AI Data Analyst** est une application web full-stack qui permet à un utilisateur d'importer un fichier de données (CSV/Excel) et de poser des questions en langage naturel pour obtenir une analyse automatique — sous forme de texte et de graphiques — sans écrire une seule ligne de code.

L'utilisateur pose une question du type *"Quel mois a le meilleur chiffre d'affaires ?"*, et l'IA :
1. Génère le code Python/Pandas correspondant
2. L'exécute sur les vraies données du fichier importé
3. Corrige automatiquement le code en cas d'erreur
4. Reformule le résultat en une réponse claire, en français

## Objectifs du projet

- Permettre à n'importe quel utilisateur, technique ou non, d'analyser un jeu de données simplement en posant des questions
- Démontrer une architecture **agentique** : l'IA ne se contente pas de répondre, elle génère et exécute du code pour produire une vraie analyse
- Construire une application complète et fonctionnelle : authentification, upload de fichiers, historique des analyses, interface de chat
- Utiliser des modèles IA accessibles gratuitement (ou à très faible coût) pour rester reproductible dans un cadre académique

## Fonctionnement, étape par étape

1. L'utilisateur importe un fichier (ex : `ventes_2026.csv`)
2. Il écrit une question en langage naturel : *"Quel mois a le meilleur chiffre d'affaires ?"*
3. Le backend envoie la question + un aperçu du dataset à un LLM (via l'API Groq)
4. Le LLM génère du code Python/Pandas qui répond à la question
5. Le code s'exécute sur les vraies données ; en cas d'erreur, l'IA corrige automatiquement (1 tentative)
6. Le résultat est reformulé en français et présenté avec un graphique

## Stack technique

| Composant | Technologie |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| Base de données | PostgreSQL (SQLite en fallback pour le dev local) |
| Authentification | JWT (python-jose) + bcrypt |
| Frontend | React 19, TypeScript, Vite, TailwindCSS v4 |
| Analyse de données | Pandas |
| Modèle IA | Qwen 3.8 27B via l'API Groq (gratuit) |
| Graphiques | Recharts |

## Fonctionnalités actuelles

- ✅ Authentification complète (signup / login / logout / gestion du profil)
- ✅ Import de fichiers CSV/XLSX avec aperçu des données (lignes, colonnes, 5 premières lignes)
- ✅ Interface de chat pour poser des questions en langage naturel
- ✅ Génération de code Pandas par IA + exécution sur les vraies données
- ✅ Correction automatique du code en cas d'erreur (1 retry)
- ✅ Génération de graphiques à partir des résultats de l'analyse
- ✅ Historique des analyses par utilisateur, consultable à tout moment

## Structure du projet

```
├── backend/          # API FastAPI (auth, upload, analyse IA)
│   ├── app/
│   │   ├── api/          # routes : auth, files, analysis
│   │   ├── models/       # modèles SQLAlchemy (users, datasets, analyses)
│   │   ├── schemas/      # schémas Pydantic
│   │   ├── services/     # logique métier (fichiers, IA)
│   │   └── core/         # config, sécurité, base de données
│   └── requirements.txt
├── frontend/         # Application React
│   └── src/
│       ├── components/   # Sidebar, ChatWindow, AnalysisBar, etc.
│       ├── hooks/        # useDemoData (état central)
│       ├── services/     # appels API (auth, fichiers, analyses)
│       └── types.ts
└── .gitignore
```

## Installation et démarrage

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env   # renseigner DATABASE_URL et GROQ_API_KEY
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Variables d'environnement (backend/.env)

```
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/ai_data_analyst
JWT_SECRET_KEY=change-me-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
FRONTEND_ORIGIN=http://localhost:5173
GROQ_API_KEY=your-groq-api-key
```



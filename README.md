# Campus Desk — Student Management System

A full-stack student directory and academic dashboard built with vanilla HTML, CSS and JavaScript, Flask, SQLAlchemy, SQLite, and PostgreSQL. The same REST API serves the dashboard and Postman clients.

The Overview (`/#overview`) and Students (`/#students`) routes render separate page sections. Overview shows statistics and charts with a short directory preview; Students shows the full searchable, filterable directory and student actions. Sidebar links and browser history keep the visible page in sync with the URL.

## Project structure

```text
student-management/
├── api/index.py                    # Vercel Python entry point
├── app/
│   ├── __init__.py                 # App factory, database configuration
│   ├── extensions.py               # SQLAlchemy extension
│   ├── models.py                   # Student model
│   ├── routes/
│   │   ├── api.py                  # REST endpoints and validation
│   │   └── web.py                  # Dashboard page
│   ├── static/
│   │   ├── css/styles.css
│   │   └── js/app.js
│   └── templates/index.html
├── postman/                        # Importable Postman collection
├── tests/test_api.py
├── .env.example
├── requirements.txt
├── run.py
└── vercel.json
```

## Local setup (Windows PowerShell)

From this directory:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python run.py
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000). The default `DATABASE_URL=sqlite:///students.db` creates the local database automatically. `FLASK_DEBUG=1` enables the development reloader; do not enable debug mode in production.

To run tests:

```powershell
python -m unittest discover -s tests -v
```

## Student record

`id` is the database-generated Student ID. Each student also has a full name, unique roll number, unique email, phone number, department, course, year of study (1–4), and date of entry as a four-digit year from 1900 through the current year. Existing date values are retained in the database and returned/displayed as their admission year.

## REST API

All responses are JSON. Successful list responses use `{"data": [...], "count": n}`; individual resources and dashboard statistics use `{"data": ...}`. Validation errors include field-level `details`; duplicates return HTTP 400 during validation (or HTTP 409 if the database detects a concurrent duplicate).

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/students` | List students |
| `GET` | `/api/students?search=maya` | Search full name or roll number |
| `GET` | `/api/students?department=Computer%20Science` | Filter by department |
| `GET` | `/api/students/{id}` | Get a student profile |
| `POST` | `/api/students` | Create a student |
| `PUT` | `/api/students/{id}` | Replace a student's editable fields |
| `DELETE` | `/api/students/{id}` | Delete a student |
| `GET` | `/api/dashboard/stats` | Totals, department/year distribution, recent students |

Example create/update body:

```json
{
  "full_name": "Maya Chen",
  "roll_number": "CS-2025-014",
  "email": "maya.chen@example.edu",
  "phone_number": "+1 (555) 123-4567",
  "department": "Computer Science",
  "course": "BSc Computer Science",
  "year_of_study": 2,
  "date_of_admission": "2025"
}
```

`date_of_admission` remains the API field name for compatibility, but it now accepts only a four-digit year such as `"2025"`; full dates, non-digits, years before 1900, and future years are rejected.

## Postman

In Postman, choose **Import** and select `postman/Student Management API.postman_collection.json`. The `baseUrl` collection variable defaults to `http://127.0.0.1:5000`. Run **Create student** first; its test script saves the returned ID to `studentId` for the profile, update, and delete requests.

## Neon PostgreSQL and Vercel deployment

1. Create a Neon project and copy its pooled or direct connection string. Keep it private.
2. Deploy this directory as the Vercel project root (or set the Vercel project **Root Directory** to `student-management` in a repository containing this folder).
3. In Vercel project settings, add `DATABASE_URL` for the Production (and Preview, if needed) environment, using the Neon connection string. Do not commit credentials or put them in `vercel.json`.
4. Deploy. `vercel.json` routes requests to the Flask Python function; Vercel installs packages from `requirements.txt`.

The app loads the project `.env` file during application creation without overriding environment variables already supplied by the operating system or deployment platform. PostgreSQL URLs beginning with `postgres://` or `postgresql://` are normalized to the installed `psycopg` SQLAlchemy driver and use `sslmode=verify-full`, `channel_binding=require`, and the Mozilla CA bundle provided by `certifi` for certificate and hostname verification. When `DATABASE_URL` is unset, local SQLite is used. Vercel's filesystem is ephemeral, so configure Neon for deployed environments; SQLite is for local development and tests. The schema is initialized with the existing SQLAlchemy models via `create_all()` when the app starts.

## Notes

- Search and department filtering can be combined.
- Email and roll number uniqueness is case-insensitive at the API validation layer.
- Student records are served by the same-origin Flask app; no CORS configuration or frontend build step is required.
- Set a strong `SECRET_KEY` environment variable when deploying if session-based features are added.

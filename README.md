# 🪺 BlogsNest

A modern, fast, and feature-rich asynchronous blogging platform built with **FastAPI**, **SQLAlchemy**, and **RabbitMQ**.

---

## 🚀 Features

- **🔐 Passwordless OTP Authentication**:
  - Secure email-based OTP (One-Time Password) registration and login.
  - JWT-based authentication stored in secure cookies and headers.
  - User profiles with name, DOB, and gender customization.

- **📝 Complete Blog Management (CRUD)**:
  - Create, read, edit, and delete blog posts.
  - Rich reading layout with author details, timestamps (IST converted), and reading engagement.

- **❤️ Social & Engagement**:
  - Real-time like/unlike functionality with unique constraints per user.
  - Interactive discussion comments on blog posts.

- **📊 Personal Dashboard & Analytics**:
  - Overview of user blogs, total blog counts, and community metrics.

- **⚡ Asynchronous Event-Driven Architecture (RabbitMQ)**:
  - Background workers handle decoupled tasks: sending OTP emails, notification events on blog publication, new comments, and audit logging.
  - Built-in automatic retry mechanism (`x-retry-count`) for resilient message processing.
  - **Zero-Dependency Fallback**: Easily switch to synchronous mode (`USE_RABBITMQ=false`) without needing RabbitMQ or Erlang installed!

- **🎨 Modern SSR Frontend**:
  - Server-Side Rendered (SSR) with Jinja2 templates and clean responsive design.

---

## 🛠️ Tech Stack

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/)
- **Server**: [Uvicorn](https://www.uvicorn.org/)
- **Database & ORM**: [SQLite](https://www.sqlite.org/) + [SQLAlchemy](https://www.sqlalchemy.org/)
- **Message Broker**: [RabbitMQ](https://www.rabbitmq.com/) with [Pika](https://pika.readthedocs.io/)
- **Authentication**: JWT ([python-jose](https://github.com/mpdavis/python-jose)) & OTP tokens
- **Templating**: [Jinja2](https://palletsprojects.com/p/jinja/)
- **Form & Validation**: [Pydantic](https://docs.pydantic.dev/) & [email-validator](https://github.com/JoshData/python-email-validator)

---

## 📁 Project Structure

```text
blognest/
├── app/
│   ├── auth/                    # Authentication module
│   │   ├── jwt_utils.py         # JWT token creation and extraction
│   │   ├── otp_utils.py         # OTP generation, storage, and validation
│   │   └── routes.py            # Login, Signup, OTP, and Logout routes
│   ├── blogs/                   # Blog and community module
│   │   └── routes.py            # Blog CRUD, comments, likes, dashboard
│   ├── rabbitmq/                # Asynchronous queue system
│   │   ├── consumer.py          # Background worker process with retry logic
│   │   ├── handlers.py          # Message handling routines (emails, logs)
│   │   └── publisher.py         # Message queue publisher with sync fallback
│   ├── config.py                # App configuration and environment variables
│   ├── database.py              # SQLAlchemy database session setup
│   ├── models.py                # Database models (User, Blog, Comment, Like, OTP, AuditLog)
│   ├── schemas.py               # Pydantic schemas for data validation
│   ├── template_filters.py      # Custom Jinja2 template filters (e.g., IST time)
│   └── main.py                  # FastAPI application entrypoint & route inclusion
├── static/                      # Static assets (CSS, JS, images)
├── templates/                   # Jinja2 HTML templates
│   ├── base.html                # Base layout template
│   ├── auth.html                # Authentication pages (Login / Signup / OTP)
│   ├── blog.html                # Single blog post & comments view
│   ├── blogs.html               # Public feed of all blog posts
│   ├── dashboard.html           # Author dashboard
│   └── profile.html             # User profile page
├── requirements.txt             # Python project dependencies
└── README.md                    # Project documentation
```

---

## ⚙️ Prerequisites

- **Python**: Version 3.10 or higher
- *(Optional)* **RabbitMQ**: Required only if `USE_RABBITMQ=true` (You can also run without RabbitMQ by setting `USE_RABBITMQ=false`).

---

## 📦 Installation & Setup

### 1. Clone or Open the Repository in VS Code
Open the `blognest` folder directly in VS Code:
```bash
code C:\Users\vrutanshi.p\blognest
```

### 2. Create and Activate a Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🔧 Environment Configuration

You can configure settings via environment variables or customize them directly in `app/config.py`:

| Variable | Default Value | Description |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite:///./blogapp.db` | SQLAlchemy connection URL |
| `JWT_SECRET` | `dev-secret-change-in-production` | Secret key for signing JWT tokens |
| `USE_RABBITMQ` | `true` | Set to `false` to disable RabbitMQ and run tasks synchronously |
| `RABBITMQ_HOST` | `localhost` | RabbitMQ server hostname |
| `SMTP_HOST` | `""` | SMTP mail server (e.g. `smtp.gmail.com`) |
| `SMTP_PORT` | `587` | SMTP mail port (default: 587) |
| `SMTP_USER` | `""` | Email address for SMTP sender |
| `SMTP_PASSWORD` | `""` | SMTP App Password |

> 💡 **Email OTP login:** OTPs are sent only through SMTP; OTP delivery fails explicitly when SMTP is not configured. The database stores a salted hash of each OTP, not its plaintext code, and existing plaintext OTP rows are hashed when the app starts. Other notification emails can still use `sent_emails.log` when SMTP is unavailable.

### Configure Gmail SMTP (PowerShell)

Create a Google App Password (requires 2-Step Verification), then set these variables in **each terminal** used to run the app and, when enabled, the RabbitMQ worker. Do not use your normal Gmail password or commit the App Password:

```powershell
$env:SMTP_HOST = "smtp.gmail.com"
$env:SMTP_PORT = "587"
$env:SMTP_USER = "youraddress@gmail.com"
$env:SMTP_PASSWORD = "your-16-character-app-password"
$env:SMTP_FROM = $env:SMTP_USER
$env:USE_RABBITMQ = "false"
uvicorn app.main:app --reload --port 8000
```

Set `USE_RABBITMQ` to `"false"` to run without RabbitMQ; if using RabbitMQ, start the worker in another terminal with the same SMTP variables.

---

## 🚀 Running the Application

### Option A: Running with RabbitMQ (Recommended for full async flow)

1. **Start RabbitMQ Server** (if installed or via Docker):
   ```bash
   docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
   ```

2. **Start the Background Consumer Worker** (in Terminal 1):
   ```powershell
   python -m app.rabbitmq.consumer
   ```

3. **Start the FastAPI Web Server** (in Terminal 2):
   ```powershell
   uvicorn app.main:app --reload --port 8000
   ```

---

### Option B: Quick Start without RabbitMQ (Synchronous Mode)

If you don't have RabbitMQ installed, simply run:

**PowerShell:**
```powershell
$env:USE_RABBITMQ="false"
uvicorn app.main:app --reload --port 8000
```

---

## 🌐 Accessing the Application

Once running, visit:
- **Home / Blog Feed**: [http://localhost:8000/blogs](http://localhost:8000/blogs)
- **User Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- **Login / Signup**: [http://localhost:8000/login](http://localhost:8000/login)
- **Interactive Swagger API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 🛣️ Key Routes Overview

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/` | Redirects to `/blogs` |
| `GET` | `/blogs` | Public feed of published blogs |
| `GET` | `/blog/{id}` | Detailed blog view with comments & like counter |
| `GET` | `/create` | Blog editor page (Protected) |
| `POST` | `/blogs/create` | Handle blog submission (Protected) |
| `POST` | `/blogs/{id}/like` | Toggle like/unlike on a blog post |
| `POST` | `/blogs/{id}/comment` | Add a comment to a blog post |
| `GET` | `/dashboard` | User personal dashboard (Protected) |
| `GET` | `/signup` | User registration page |
| `POST` | `/auth/register` | Initiates registration & sends OTP |
| `GET` | `/login` | User login page |
| `POST` | `/auth/request-otp` | Request OTP for existing account |
| `POST` | `/auth/verify-otp` | Verify OTP and issue JWT cookie |
| `GET` | `/logout` | Clears auth session cookie |

---

## 📝 License

This project is licensed under the MIT License.

without rabbitmq:
$env:USE_RABBITMQ="false"
uvicorn app.main:app --reload --port 8000

# CLAUDE.md - SoulTalk Backend

Focus on writing minimal, clean code following existing patterns.

## Commands
- `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` - Run dev server
- `alembic upgrade head` - Apply migrations
- `alembic revision --autogenerate -m "description"` - Create migration
- `pytest` - Run tests
- `black app/` - Format code
- `docker build -t soultalk-backend .` - Build Docker image

## Architecture

FastAPI backend with async SQLAlchemy 2.0 and PostgreSQL.

### File Structure
```
app/
├── main.py              # FastAPI app, lifespan, router mounting, CORS
├── core/
│   ├── config.py        # Settings (pydantic-settings, .env loaded)
│   └── security.py      # Token generation/hashing utilities
├── db/
│   ├── base.py          # DeclarativeBase with naming conventions
│   ├── session.py       # Async engine + sessionmaker (asyncpg)
│   └── dependencies.py  # get_db() FastAPI dependency (auto commit/rollback)
├── api/
│   ├── deps.py          # Auth dependencies: get_current_user, get_current_active_user
│   ├── auth.py          # POST register/login/refresh/logout, GET/PUT /me, OTP verify, password reset
│   ├── social_auth.py   # POST google/facebook login, link/unlink accounts
│   ├── journal.py       # CRUD /api/journal, background AI processing
│   ├── mood.py          # PUT/GET /api/mood/today (daily mood bar)
│   ├── streak.py        # GET /api/streak
│   ├── soul_bar.py      # GET /api/soul-bar
│   ├── transcription.py # POST /api/transcription (placeholder, returns 501)
│   ├── prompts.py       # GET /api/prompts (random journal prompts)
│   └── ws.py            # WebSocket /ws (JWT auth, ping keepalive, ConnectionManager)
├── models/
│   ├── user.py          # User (UUID PK, email, password_hash, profile fields, relationships)
│   ├── social_account.py# SocialAccount (ProviderEnum: google/facebook/email)
│   ├── refresh_token.py # RefreshToken (token_hash, expiry, revoked)
│   ├── email_verification.py # EmailVerificationToken (OTP hash, type, expiry)
│   ├── journal_entry.py # JournalEntry (raw_text, mood, AI fields, is_draft)
│   ├── daily_mood.py    # DailyMood (user_id + date unique, filled_count)
│   ├── user_streak.py   # UserStreak (current_streak, longest_streak)
│   └── soul_bar.py      # SoulBar (points float, total_filled int)
├── schemas/
│   ├── auth.py          # Registration, Login, OTP, password reset schemas
│   ├── user.py          # UserResponse, UserUpdate, LinkedAccountResponse
│   ├── journal.py       # JournalEntryCreate/Update/Response, MoodEnum (10 moods)
│   ├── mood.py          # DailyMoodCreate/Response
│   ├── streak.py        # StreakResponse
│   ├── soul_bar.py      # SoulBarResponse
│   └── transcription.py # TranscriptionResponse
└── services/
    ├── auth_service.py      # Register, login, token refresh (rotation), logout, OTP verify, password reset
    ├── user_service.py      # User CRUD, social account link/unlink, providers list
    ├── jwt_service.py       # JWT create/decode (python-jose), refresh token hash/verify
    ├── password_service.py  # Bcrypt hash/verify (passlib)
    ├── email_service.py     # SMTP email (aiosmtplib not used - uses smtplib), HTML templates
    ├── social_auth_service.py # Google ID token verify (google-auth), Facebook token verify (httpx)
    ├── journal_service.py   # CRUD, list with filters, update_ai_fields, has_entry_today
    ├── ai_service.py        # Anthropic Claude analysis (emotion, topics, coping, ai_response)
    ├── mood_service.py      # Upsert daily mood
    ├── streak_service.py    # Record journal entry, update streak counts
    ├── soul_bar_service.py  # Add points (1 per journal, 0.5 per mood), auto-reset at 6
    └── transcription_service.py # Placeholder for future server-side transcription
```

### Key Patterns
- **All models**: UUID PK, `mapped_column`, timezone-aware timestamps, `TYPE_CHECKING` for relationships
- **Auth flow**: Register -> OTP email -> verify OTP (auto-login) -> JWT access + refresh tokens
- **Auth dependency chain**: `HTTPBearer` -> `get_current_user` (any valid JWT) -> `get_current_active_user` (email verified)
- **Services**: Class-based, instantiated as module-level singletons, async methods take `AsyncSession` as first param
- **Error handling**: Services raise `ValueError`, API routes catch and convert to `HTTPException`
- **Background tasks**: `FastAPI BackgroundTasks` for AI processing (uses separate session via `async_session_maker`)
- **WebSocket**: JWT auth on connect (first message), `ConnectionManager` tracks user -> set of connections, sends AI results
- **Journal create**: Enforces 1 non-draft entry per day, triggers streak + SoulBar + AI analysis (background)
- **Password**: Bcrypt via passlib, complexity regex (upper+lower+digit+special, min 8)
- **Social auth**: Google (google-auth lib), Facebook (httpx to graph API); auto-link if email matches existing user

### Migrations (Alembic)
001: Initial auth tables (users, social_accounts, refresh_tokens, email_verification_tokens)
002: journal_entries
003: User profile fields (display_name, username, bio, pronoun)
004: daily_moods
005: user_streaks, soul_bars, is_draft on journal_entries
006: display_first_name on users
007: soul_bar points float -> Float

### API Routes
| Prefix | Tag | Key endpoints |
|--------|-----|---------------|
| /api/auth | Auth | register, login, refresh, logout, me (GET/PUT), verify-email, reset-password, change-password, check-username |
| /api/auth | Social | google, facebook, link/google, link/facebook, link/{provider} DELETE, linked-accounts |
| /api/journal | Journal | CRUD (POST, GET list, GET /{id}, PUT /{id}, DELETE /{id}) |
| /api/mood | Mood | PUT /today, GET /today |
| /api/streak | Streak | GET / |
| /api/soul-bar | SoulBar | GET / |
| /api/transcription | Transcription | POST / (file upload) |
| /api/prompts | Prompts | GET / (5 random prompts) |
| /ws | WebSocket | JWT auth, ping keepalive |

### Environment (.env)
Required: `DATABASE_URL`, `JWT_SECRET`, `SECRET_KEY`
Optional: `ANTHROPIC_API_KEY`, `SMTP_*`, `GOOGLE_CLIENT_ID`, `FACEBOOK_APP_*`
Default DB URL format: `postgresql+asyncpg://user:pass@host:port/dbname`

### Docker
- Dockerfile: python:3.11-slim, pip install requirements.txt, CMD uvicorn (no --reload in prod)
- docker-compose.prod.yml exists for production with Nginx
- Dev docker-compose in SoulTalk-Infra/ mounts source as volume for hot reload

### Notes
- In production, tables managed by Alembic only (no create_all)
- `extra = "ignore"` in Settings Config so unknown env vars don't crash
- SoulBar resets to 0 when reaching 6 points, increments total_filled
- Journal AI uses `claude-haiku-4-5-20251001` model by default
- Username can only be set once (enforced in PUT /me)

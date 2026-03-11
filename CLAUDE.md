# CLAUDE.md - SoulTalk Backend

Focus on writing minimal, clean code following existing patterns.

## Git Conventions
- Commit messages: single line only, no multi-line bodies, no Co-Authored-By

## Commands
- `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload` - Run dev server
- `alembic upgrade head` - Apply migrations
- `alembic revision --autogenerate -m "description"` - Create migration
- `pytest` - Run tests
- `black app/` - Format code
- `docker build -t soultalk-backend .` - Build Docker image
- `python -m tests.test_pipeline --dry-run` - Validate test personas
- `python -m tests.test_pipeline --persona maya --skip-respond` - Run tagger test for one persona
- `python -m tests.test_pipeline --output results.json` - Full pipeline test with results

## Architecture

FastAPI backend with async SQLAlchemy 2.0 and PostgreSQL (pgvector).

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
│   ├── journal.py       # CRUD /api/journal, background AI pipeline, tags/response joins
│   ├── ai_profile.py    # GET/PUT /api/profile/ai-preferences
│   ├── mood.py          # PUT/GET /api/mood/today (daily mood bar)
│   ├── streak.py        # GET /api/streak
│   ├── soul_bar.py      # GET /api/soul-bar
│   ├── transcription.py # POST /api/transcription (placeholder, returns 501)
│   ├── prompts.py       # GET /api/prompts (5 random journal prompts)
│   └── ws.py            # WebSocket /ws (JWT auth, ping keepalive, ConnectionManager)
├── models/
│   ├── user.py              # User (UUID PK, email, password_hash, profile fields)
│   ├── social_account.py    # SocialAccount (ProviderEnum: google/facebook/email)
│   ├── refresh_token.py     # RefreshToken (token_hash, expiry, revoked)
│   ├── email_verification.py# EmailVerificationToken (OTP hash, type, expiry)
│   ├── journal_entry.py     # JournalEntry (raw_text, mood, ai_processing_status, is_draft)
│   ├── daily_mood.py        # DailyMood (user_id + date unique, filled_count)
│   ├── user_streak.py       # UserStreak (current_streak, longest_streak)
│   ├── soul_bar.py          # SoulBar (points float, total_filled int)
│   ├── entry_tags.py        # EntryTags (JSONB tags, Vector(1024) embedding, indexed extraction cols)
│   ├── ai_response.py       # AIResponse (response_text, mode, hints, token tracking)
│   ├── soulsight.py         # Soulsight (window dates, status, content, aggregate_stats)
│   ├── scenario_playbook.py # ScenarioPlaybook (String PK, ARRAY retrieval_tags)
│   ├── daily_aggregate.py   # DailyAggregate (JSONB distributions)
│   └── user_ai_profile.py   # UserAIProfile (tone_preference, spiritual_metadata, soulpal_name)
├── schemas/
│   ├── auth.py          # Registration, Login, OTP, password reset schemas
│   ├── user.py          # UserResponse, UserUpdate, LinkedAccountResponse
│   ├── journal.py       # JournalEntryCreate/Update/Response, TagsSummary, AIResponseSummary
│   ├── ai_profile.py    # AIProfileUpdate, AIProfileResponse
│   ├── mood.py          # DailyMoodCreate/Response
│   ├── streak.py        # StreakResponse
│   ├── soul_bar.py      # SoulBarResponse
│   └── transcription.py # TranscriptionResponse
└── services/
    ├── auth_service.py      # Register, login, token refresh (rotation), logout, OTP verify
    ├── user_service.py      # User CRUD, social account link/unlink, providers list
    ├── jwt_service.py       # JWT create/decode (python-jose), refresh token hash/verify
    ├── password_service.py  # Bcrypt hash/verify (passlib)
    ├── email_service.py     # SMTP email (smtplib), HTML templates
    ├── social_auth_service.py # Google ID token verify, Facebook token verify (httpx)
    ├── journal_service.py   # CRUD, list with filters, has_entry_today
    ├── mood_service.py      # Upsert daily mood
    ├── streak_service.py    # Record journal entry, update streak counts
    ├── soul_bar_service.py  # Add points (1 per journal, 0.5 per mood), auto-reset at 6
    ├── transcription_service.py # Placeholder for future server-side transcription
    ├── ai_schemas/
    │   └── tags_v1.py       # TagsV1 Pydantic model (~50 fields, 12 sections, Literal enums)
    ├── ai_prompts/
    │   ├── tagging.py       # Tagging system/developer/user prompts for Haiku
    │   ├── response.py      # Response prompts + MODE_INSTRUCTIONS dict for 7 modes
    │   └── soulsight.py     # SoulSight prompt (Phase 5)
    ├── ai_data/
    │   └── scenario_playbooks.json  # 20 curated coaching scenarios (ST-SCEN-001 to 020)
    └── ai/
        ├── safety.py            # validate_tags(), is_crisis(), generate_safety_redirect()
        ├── tagging_service.py   # Haiku structured extraction with JSON retry
        ├── embedding_service.py # Voyage AI AsyncClient wrapper
        ├── mode_selector.py     # Pure Python rules engine (7 modes, 4 hints)
        ├── retrieval_service.py # Scenario matching (SQL array overlap) + pgvector cosine similarity
        ├── response_service.py  # Sonnet coaching response generation
        └── pipeline.py          # 6-step orchestrator: tag → embed → mode → retrieve → respond → complete
```

### AI Pipeline (5 steps per journal entry)

1. **Tag** (Haiku) — Structured extraction into TagsV1 (12 sections: emotions, nervous_system, topics, coping, self_talk, cognition, orientation, continuity, intensity_pattern, load, risk, confidence)
2. **Embed** (Voyage AI) — 1024-dim vector via `voyage-3-lite`, stored in entry_tags with HNSW index
3. **Mode Select** (Python) — Deterministic rules engine, priority: CRISIS_OVERRIDE > SOFT_LANDING > NO_MORE_HOMEWORK > CONTINUITY_KEEPER > INTEGRATION > CLEAN_MIRROR > DEFAULT_REFLECT. Plus 4 hints: REPAIR_NOT_PUNISHMENT, CRITIC_SOFTENING, ATTACHMENT_LOOP, SCARCITY_SPIRAL
4. **Retrieve** — Scenario playbooks (PostgreSQL array overlap) + similar past entries (pgvector cosine) + recent context aggregation
5. **Respond** (Sonnet) — Coaching response with mode-specific instructions. Crisis entries bypass LLM → safety redirect

### Key Patterns
- **All models**: UUID PK, `mapped_column`, timezone-aware timestamps, `TYPE_CHECKING` for relationships
- **Auth flow**: Register -> OTP email -> verify OTP (auto-login) -> JWT access + refresh tokens
- **Auth dependency chain**: `HTTPBearer` -> `get_current_user` (any valid JWT) -> `get_current_active_user` (email verified)
- **Services**: Class-based, instantiated as module-level singletons, async methods take `AsyncSession` as first param
- **Error handling**: Services raise `ValueError`, API routes catch and convert to `HTTPException`
- **Background tasks**: `FastAPI BackgroundTasks` for AI processing (uses separate session via `async_session_maker`)
- **WebSocket**: JWT auth on connect (first message), `ConnectionManager` tracks user -> set of connections, pushes AI results
- **Journal create**: Enforces 1 non-draft entry per day, triggers streak + SoulBar + AI pipeline (background)
- **AI pipeline**: Runs as background task with independent DB sessions per step. Each step commits independently. On failure, status set to "failed" with error stored. GET endpoint re-triggers if stuck pending >5min.
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
008: CREATE EXTENSION vector (pgvector)
009: entry_tags with Vector(1024) embedding, HNSW cosine index, JSONB tags
010: ai_responses (response_text, mode, hints, token tracking)
011: soulsights (window dates, status, content, aggregate_stats)
012: scenario_playbooks with GIN index on retrieval_tags
013: daily_aggregates (JSONB distributions)
014: user_ai_profiles (tone_preference, spiritual_metadata, soulpal_name)
015: Clean journal_entries (drop legacy AI columns, add ai_processing_status/error/started_at)
016: Seed 20 scenario playbooks from JSON

### API Routes
| Prefix | Tag | Key endpoints |
|--------|-----|---------------|
| /api/auth | Auth | register, login, refresh, logout, me (GET/PUT), verify-email, reset-password, change-password, check-username |
| /api/auth | Social | google, facebook, link/google, link/facebook, link/{provider} DELETE, linked-accounts |
| /api/journal | Journal | CRUD (POST, GET list, GET /{id}, PUT /{id}, DELETE /{id}). GET returns tags + ai_response via selectinload |
| /api/profile/ai-preferences | AI Profile | GET / (create default if missing), PUT / (main_focus, tone_preference, soulpal_name, spiritual_metadata) |
| /api/mood | Mood | PUT /today, GET /today |
| /api/streak | Streak | GET / |
| /api/soul-bar | SoulBar | GET / |
| /api/transcription | Transcription | POST / (file upload) |
| /api/prompts | Prompts | GET / (5 random prompts) |
| /ws | WebSocket | JWT auth, ping keepalive, pushes journal_ai_complete events |

### Environment (.env)
Required: `DATABASE_URL`, `JWT_SECRET`, `SECRET_KEY`
AI pipeline: `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`
Optional: `SMTP_*`, `GOOGLE_CLIENT_ID`, `FACEBOOK_APP_*`
Default DB URL format: `postgresql+asyncpg://user:pass@host:port/dbname`

### Docker
- Dockerfile: python:3.11-slim, pip install requirements.txt, CMD uvicorn (no --reload in prod)
- docker-compose.prod.yml: pgvector/pgvector:pg15 (not plain postgres), Redis 7-alpine, backend with 2 workers
- Dev docker-compose in SoulTalk-Infra/ mounts source as volume for hot reload

### Testing
```
tests/
├── test_pipeline.py           # Full pipeline runner with 5 personas (60 entries)
├── test_kaggle_validation.py  # Haiku tagger validation against Kaggle emotion-labeled dataset
└── test_data/
    ├── personas.json          # 5 mock personas with 10-15 day journal arcs
    └── kaggle_emotion_map.py  # Kaggle label -> TagsV1 enum mapping + agreement checkers
```

**Personas** (designed to cover all 7 modes + 4 hints):
- **Maya** (28, PM) — burnout arc: NO_MORE_HOMEWORK, SOFT_LANDING, CLEAN_MIRROR
- **Kai** (35, writer) — grief arc: SOFT_LANDING, CLEAN_MIRROR, CONTINUITY_KEEPER
- **Priya** (31, founder) — anxiety-control arc: CLEAN_MIRROR (direct tone), SOFT_LANDING, SCARCITY_SPIRAL hint
- **Sam** (24, student) — crisis arc: CRISIS_OVERRIDE, SOFT_LANDING, REPAIR_NOT_PUNISHMENT hint
- **Alex** (29, yoga teacher) — spiritual integration arc: INTEGRATION, CONTINUITY_KEEPER

### Notes
- In production, tables managed by Alembic only (no create_all)
- `extra = "ignore"` in Settings Config so unknown env vars don't crash
- SoulBar resets to 0 when reaching 6 points, increments total_filled
- Username can only be set once (enforced in PUT /me)
- pgvector requires `pgvector/pgvector:pg15` Docker image (not plain `postgres:15`)
- Crisis entries bypass Sonnet entirely → static safety redirect with helpline numbers
- Scenario playbooks seeded via migration 016 from `ai_data/scenario_playbooks.json`

## FAQ

### How much does the AI pipeline cost per user?

| Per entry | Model | Cost |
|-----------|-------|------|
| Tag | Haiku (~1300 in / ~700 out tokens) | ~$0.004 |
| Embed | Voyage-3-lite (~300 tokens) | ~$0.0003 |
| Respond | Sonnet (~3000 in / ~300 out tokens) | ~$0.014 |
| **Total per entry** | | **~$0.018** |

Scaling estimates (1 entry/user/day):

| Usage | Monthly cost |
|-------|-------------|
| 1 user | ~$0.54 |
| 100 DAU | ~$54 |
| 1,000 DAU | ~$540 |
| 10,000 DAU | ~$5,400 |

Sonnet response generation is ~78% of per-entry cost. Swapping to Haiku for responses would drop to ~$0.006/entry (~3x cheaper) at the cost of response quality.

### How much does the test suite cost to run?

| Run type | Command | Cost |
|----------|---------|------|
| Tags + mode only | `--skip-embed --skip-respond` | ~$0.23 |
| Single persona full | `--persona maya` | ~$0.23 |
| All 5 personas full | (no flags) | ~$1.05 |
| Kaggle validation (50 entries) | `test_kaggle_validation --limit 50` | ~$0.19 |

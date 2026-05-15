# 🇮🇳 Government Schemes AI Agent — WhatsApp Bot

A production-grade WhatsApp bot that helps Indian citizens discover government schemes they're eligible for and guides them through the application process step-by-step.

## Architecture

The system has **3 layers**:

| Layer | Role | Technology |
|-------|------|------------|
| **Deterministic Engine** | Flow control, state machine, eligibility filtering | Python (pure logic) |
| **LLM Layer** | Language simplification, Q&A fallback, multilingual | OpenAI GPT-4o-mini |
| **WhatsApp Layer** | Message sending/receiving, interactive buttons | Meta Cloud API |

> **Key principle:** The backend controls the flow. AI is only used for language tasks, never for flow decisions.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your keys
```

You'll need:
- **WhatsApp Cloud API** credentials from [Meta Developer Console](https://developers.facebook.com/)
- **OpenAI API key** from [OpenAI Platform](https://platform.openai.com/)

### 3. Run the Server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Test Locally (No WhatsApp Needed!)

The `/test` endpoint lets you simulate conversations:

```bash
# Start a conversation
curl -X POST http://localhost:8000/test \
  -H "Content-Type: application/json" \
  -d '{"phone": "919999999999", "message": "hi"}'

# Select category
curl -X POST http://localhost:8000/test \
  -H "Content-Type: application/json" \
  -d '{"phone": "919999999999", "message": "1"}'

# Continue the flow...
```

Or visit **http://localhost:8000/docs** for the interactive Swagger UI.

## WhatsApp Setup

### Step 1: Meta Developer Account
1. Go to [developers.facebook.com](https://developers.facebook.com/)
2. Create a new app → Select "Business" type
3. Add the **WhatsApp** product

### Step 2: Get Credentials
From the WhatsApp product dashboard:
- Copy the **Temporary Access Token**
- Copy the **Phone Number ID**

### Step 3: Configure Webhook
1. Your server must be publicly accessible (use [ngrok](https://ngrok.com/) for local dev)
2. Set webhook URL to: `https://your-domain.com/webhook`
3. Set verify token to match `WHATSAPP_VERIFY_TOKEN` in your `.env`
4. Subscribe to `messages` webhook field

### Using ngrok for local development:
```bash
ngrok http 8000
# Copy the https URL and set it as your webhook URL in Meta Console
```

## Conversation Flow

```
User sends "Hi"
    │
    ▼
┌─────────────────────┐
│  Category Selection  │  ← Student / Farmer / Job Seeker / Other
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│    Ask Income        │  ← Below 1L / 1-3L / 3-5L / Above 5L
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│    Ask State         │  ← Maharashtra, Kerala, etc.
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Special Category    │  ← SC/ST / Girl Child / Senior / None
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Show Matched        │  ← Deterministic eligibility matching
│  Schemes             │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Deep Guide          │  ← Step-by-step application guide
│  (+ AI Q&A)          │     AI answers follow-up questions
└─────────────────────┘
```

## Project Structure

```
AIAgent/
├── app/
│   ├── main.py              # FastAPI endpoints
│   ├── config.py             # Environment config
│   ├── whatsapp/
│   │   ├── client.py         # Send messages via WhatsApp API
│   │   └── models.py         # Webhook payload parsing
│   ├── engine/
│   │   ├── state_machine.py  # Deterministic conversation flow
│   │   ├── scheme_matcher.py # Eligibility matching engine
│   │   └── models.py         # State/flow enums & models
│   ├── ai/
│   │   ├── llm.py            # OpenAI integration
│   │   └── prompts.py        # System & user prompts
│   └── data/
│       ├── store.py           # SQLite user state persistence
│       └── schemes.json       # Government schemes dataset
├── .env.example
├── requirements.txt
└── README.md
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check |
| `GET` | `/webhook` | Meta webhook verification |
| `POST` | `/webhook` | Incoming WhatsApp messages |
| `POST` | `/test` | Local testing (no WhatsApp needed) |

## Government Schemes Included

| # | Scheme | Categories |
|---|--------|-----------|
| 1 | PM Scholarship Scheme | Student |
| 2 | PM-KISAN Samman Nidhi | Farmer |
| 3 | PM MUDRA Yojana | Job Seeker, Farmer |
| 4 | Sukanya Samriddhi Yojana | Other (Girl Child) |
| 5 | PMEGP | Job Seeker |
| 6 | PM Awas Yojana – Gramin | Farmer, Other |
| 7 | NSAP Old Age Pension | Other (Senior Citizen) |
| 8 | Skill India – PMKVY | Student, Job Seeker |
| 9 | Ayushman Bharat – PMJAY | All categories |
| 10 | Stand Up India | Job Seeker, Other (SC/ST/Women) |

## Adding New Schemes

Edit `app/data/schemes.json` and add entries following this format:

```json
{
  "id": "unique-scheme-id",
  "name": "Scheme Display Name",
  "category": ["student", "farmer", "job_seeker", "other"],
  "eligibility": {
    "max_income": 300000,
    "occupation": null,
    "states": "all",
    "special_category": null,
    "description": "Human-readable eligibility text"
  },
  "documents": ["Document 1", "Document 2"],
  "benefits": "What the user gets",
  "application_url": "https://...",
  "how_to_apply": ["Step 1", "Step 2", "Step 3"]
}
```

## Deployment

### Render / Railway
1. Push to GitHub
2. Connect repo to Render/Railway
3. Set environment variables from `.env.example`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### Docker
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## License

MIT
"# AIGovernmentAssistent" 

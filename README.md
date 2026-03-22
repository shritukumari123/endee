# 🧠 Engram — Personal AI Second Brain
### Powered by [Endee](https://github.com/endee-io/endee) Vector Database

> *"An engram is the physical trace a memory leaves in the brain. Engram does the same for your knowledge."*

---

## 🎯 Problem Statement

Knowledge workers — students, researchers, professionals — accumulate hundreds of documents, notes, PDFs, and files over years. The problem is not storage. The problem is **retrieval and connection**.

- You forget what you wrote 3 months ago
- Keyword search fails when you remember the idea but not the exact words
- No tool connects related knowledge across different documents automatically
- No system tells you what you are missing or where you contradict yourself

**Engram solves this.** Upload everything. Ask anything. Let AI find the connections you missed.

---

## 🚀 What Engram Does

Engram is a **personal AI knowledge management system** that turns your documents into a searchable, queryable, self-organising second brain — powered entirely by Endee as the vector database.

| Feature | Description |
|---|---|
| 🔍 **Semantic Search** | Find memories by meaning, not keywords. "programming skills" finds "Languages: C++, Python" |
| 💬 **Ask AI (RAG)** | Ask questions, get answers grounded in YOUR documents with source citations |
| 🌐 **Related Memories** | Automatically surfaces forgotten documents related to what you are reading |
| 🤖 **Autonomous Agent** | Scans your entire knowledge base and finds patterns, contradictions, and gaps |
| 📤 **Universal Ingestion** | PDF (including scanned/OCR), DOCX, TXT, MD, CSV — all supported |

---

## 🏗️ System Design

```
User uploads file (PDF / DOCX / TXT / MD / CSV)
              │
              ▼
     ┌─────────────────┐
     │   File Parser   │  ← PyMuPDF + OCR fallback for scanned PDFs
     └────────┬────────┘
              │  clean text
              ▼
     ┌─────────────────┐
     │    Chunker      │  ← 400-word chunks, 50-word overlap
     └────────┬────────┘
              │  MemoryChunk objects
              ▼
     ┌─────────────────┐
     │  Local Embedder │  ← all-MiniLM-L6-v2 (FREE, no API key)
     └────────┬────────┘
              │  384-dim vectors
              ▼
     ┌─────────────────┐
     │  Deduplication  │  ← Search Endee, skip if cosine ≥ 0.85
     └────────┬────────┘
              │  unique vectors only
              ▼
     ┌─────────────────────────────────────────┐
     │           ENDEE VECTOR DATABASE         │
     │                                         │
     │  engram_memories  ← document chunks     │
     │  engram_entities  ← extracted persons,  │
     │                      places, concepts   │
     │  engram_insights  ← agent discoveries   │
     │  engram_timeline  ← time-tagged memory  │
     └─────────────────────────────────────────┘
              │
      ┌───────┼────────────┐
      ▼       ▼            ▼
  Search    RAG         Agent
  Engine  Pipeline    Monitor
      │       │            │
      └───────┴────────────┘
                   │
                   ▼
         Streamlit Dashboard
```

---

## 🗄️ How Endee is Used — 5 Distinct Ways

This is the core of the project. Endee is not just storage — it is the **reasoning engine**.

### 1. `engram_memories` — The Knowledge Store
Every document chunk is embedded locally (free, no API cost) and stored as a 384-dimensional vector in Endee. Semantic search queries this index in milliseconds across thousands of chunks.

```python
# Store
idx.upsert([{"id": chunk.id, "vector": embedding, "meta": metadata}])

# Search — finds "programming skills" even if document says "Languages: C++, Python"
results = idx.query(vector=query_embedding, top_k=10)
```

### 2. `engram_memories` — Semantic Deduplication
Before inserting any chunk, Engram queries Endee for cosine similarity ≥ 0.85 in the same source file. If a near-identical chunk exists it is skipped. **No hash can catch two versions of the same idea written differently. Vectors can.**

```python
matches = idx.query(vector=embedding, top_k=1)
if matches[0]["similarity"] >= 0.85 and same_source:
    skip()  # duplicate detected semantically
```

### 3. `engram_entities` — Entity Knowledge Graph
Named entities (people, places, organisations, decisions) are extracted from every chunk and stored as separate vectors. Search for "Rahul" and find every document that mentions him — even if spelled differently in context.

### 4. `engram_insights` — Agent Memory
Every insight the autonomous agent generates (pattern, contradiction, knowledge gap) is stored as a vector in Endee. Future agent runs **recall past discoveries** by searching this index — the agent builds on its own memory across sessions.

### 5. `engram_timeline` — Temporal Memory
Time-tagged memory entries enable queries like "what was I thinking about in January?" — temporal vector search that no keyword database can replicate.

---

## 🤖 Autonomous Agent

The agent runs on a schedule (or manually) and performs 4 tasks by scanning Endee:

| Task | What it does |
|---|---|
| **Pattern Detection** | Finds topics you write about most frequently |
| **Contradiction Detection** | Finds documents where you stated conflicting things |
| **Knowledge Gap Detection** | Identifies topics mentioned but not deeply covered |
| **Forgotten Memory** | Surfaces chunks not retrieved in 30+ days |

All discoveries are stored back into `engram_insights` — so the agent remembers what it already found.

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Vector Database | **Endee** (local Docker) |
| Embeddings | `all-MiniLM-L6-v2` via sentence-transformers — **100% free, local** |
| LLM (RAG + Agent) | **Groq API** — `llama-3.3-70b-versatile` — **100% free** |
| PDF Parsing | PyMuPDF + Tesseract OCR (scanned PDF fallback) |
| API | FastAPI |
| Dashboard | Streamlit |
| Language | Python 3.11+ |

**Zero cost to run.** No OpenAI API key needed. Embeddings are local. LLM uses Groq free tier.

---

## 📁 Project Structure

```
engram/
├── core/
│   ├── models.py          # Pydantic data models
│   └── indexes.py         # Endee index management
├── ingestion/
│   ├── file_parser.py     # PDF, DOCX, CSV, TXT, MD parser + OCR
│   ├── chunker.py         # Text chunking with overlap
│   └── engine.py          # Full ingestion pipeline + deduplication
├── search/
│   └── search_engine.py   # Semantic search + multi-query search
├── rag/
│   └── rag_pipeline.py    # RAG — retrieval + Groq generation
├── recommendations/
│   └── recommender.py     # Related memories + forgotten memory finder
├── agents/
│   └── monitor_agent.py   # Autonomous pattern/gap/contradiction agent
├── dashboard/
│   └── app.py             # Streamlit UI (6 pages)
├── utils/
│   ├── endee_client.py    # Endee SDK wrapper
│   └── embeddings.py      # Local embedder (free)
├── tests/
│   └── test_day1.py       # Unit tests
├── .env.example           # Environment template
├── docker-compose.yml     # Endee + app setup
└── requirements.txt
```

---

## ⚙️ Setup & Installation

### Prerequisites
- Python 3.11+
- Docker Desktop
- Git

### Step 1 — Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/endee.git
cd endee/engram
```

### Step 2 — Start Endee with Docker

```bash
docker run -d --name endee-server -p 8080:8080 \
  -v endee-data:/data endeeio/endee-server:latest
```

Verify Endee is running:
```bash
curl http://localhost:8080/api/v1/health
# Expected: {"status":"ok"}
```

### Step 3 — Create virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### Step 4 — Install dependencies

```bash
pip install -r requirements.txt
```

### Step 5 — Configure environment

```bash
cp .env.example .env
```

Open `.env` and set:
```env
OPENAI_API_KEY=your_groq_api_key_here   # Get free at console.groq.com
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile
```

> **Embeddings are 100% free and local — no API key needed for search.**
> Groq key is only needed for RAG answers and Agent insights.
> Get a free Groq key at: https://console.groq.com

### Step 6 — Run the dashboard

```bash
streamlit run dashboard/app.py
```

Open your browser at: **http://localhost:8501**

---

## 🎬 Demo Walkthrough

### Step 1 — Upload documents
Go to **📤 Upload** → drop any PDF, DOCX, TXT, or CSV → click **Ingest into Endee**

Watch the terminal: chunks are embedded locally and stored in Endee in real time.

### Step 2 — Semantic Search
Go to **🔍 Search** → type `technical skills`

Even if your document says "Languages: C++, Python, R" — Engram finds it. That is vector search.

### Step 3 — Ask AI
Go to **💬 Ask AI** → type `What are my qualifications?`

Get a grounded answer with exact source citations from your documents. Not hallucinated — retrieved from Endee.

### Step 4 — Related Memories
Go to **🌐 Related** → type `machine learning`

See how the topic connects across all your uploaded files automatically.

### Step 5 — Run the Agent
Go to **🤖 Agent** → click **Run Agent Now**

Watch the autonomous agent scan your entire Endee knowledge base and surface patterns, contradictions, and knowledge gaps you did not know existed.

---

## 🔑 Key Technical Decisions

**Why local embeddings?**
`all-MiniLM-L6-v2` produces 384-dimensional vectors — high quality, fast on CPU, completely free. No per-token cost, no rate limits, works offline.

**Why Groq instead of OpenAI?**
Groq provides `llama-3.3-70b-versatile` completely free with generous rate limits. The API is 100% OpenAI-compatible — zero code changes needed.

**Why 4 separate Endee indexes?**
Each index serves a different semantic purpose. Mixing memories, entities, insights, and timeline entries into one index would pollute search results. Separation gives precise, relevant retrieval for each use case.

**Why semantic deduplication over hash-based?**
Hash-based deduplication only catches exact duplicates. If the same document is uploaded twice with minor edits, a hash check misses it. Vector similarity catches near-duplicates — two different descriptions of the same meeting, the same idea written differently.

---

## 📋 Environment Variables

| Variable | Description | Default |
|---|---|---|
| `ENDEE_BASE_URL` | Endee server URL | `http://localhost:8080` |
| `OPENAI_API_KEY` | Groq API key | — |
| `LLM_BASE_URL` | Groq API base URL | — |
| `LLM_MODEL` | LLM model name | `llama-3.3-70b-versatile` |
| `LOCAL_EMBEDDING_MODEL` | Sentence transformer model | `all-MiniLM-L6-v2` |
| `CHUNK_SIZE` | Words per chunk | `400` |
| `CHUNK_OVERLAP` | Overlap between chunks | `50` |
| `DEDUP_THRESHOLD` | Cosine similarity dedup threshold | `0.85` |

---

## 🙏 Acknowledgements

- [Endee](https://github.com/endee-io/endee) — high-performance vector database that makes this project possible
- [sentence-transformers](https://www.sbert.net/) — free local embeddings
- [Groq](https://console.groq.com) — free LLM inference
- [Streamlit](https://streamlit.io) — dashboard framework

Self-Supervised Modular Context-Aware AI Framework (MCAF)

A modular AI agent system that can search, execute, and generate Python tools in real time. The framework integrates a state-machine-driven reasoning agent, a semantic search engine, and a sandboxed execution environment.

Overview

Frontend: SvelteKit (Svelte 5 runes)

Backend: FastAPI

Database: SQLite + SQLAlchemy

Communication: WebSocket streaming

LLM: Gemini API (multi-key rotation)

Core Components
1. Tool Store Backend (FastAPI + SQLite)

Stores Python tools with metadata, parameters, execution count, and bug logs

Semantic search using exact match, fuzzy match, Jaccard overlap, and metadata boosting

Sandboxed tool execution (exec) with restricted globals

Tool chaining via execute_tool()

2. Agent Engine

Six-state FSM: respond, fetch_tool, use_tool, analyze_tools_for_composite, create_tool, exit_response

Enforces search-before-create and reuse-before-generate policies

Streams reasoning, actions, and results through WebSocket

3. Frontend (SvelteKit)

Real-time chat interface

Structured rendering of agent iterations

LocalStorage persistence for conversations and UI state

API Summary
Tool Store (Port 8000)
GET  /tools
GET  /tools/{id}
POST /tools
POST /tools/{id}/execute
GET  /tools/search/{query}
POST /tools/{id}/clear-bugs

Proxy (Port 8001)
WS   /ws/ask
POST /ask

Running the Project
Frontend
cd frontend
npm install
npm run dev

Backend
cd backend
uvicorn main:app --reload

Key Features

Real-time bidirectional streaming

Dynamic tool creation + composition

Transparent reasoning steps

Semantic search (≥90% relevance)

Sandboxed execution with error tracking

Multi-key rate-limited LLM integration

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Starting the Application
- **Quick start**: `./run.sh` (starts the FastAPI server on port 8000)
- **Manual start**: `cd backend && uv run uvicorn app:app --reload --port 8000 --host 0.0.0.0`
- **Install dependencies**: `uv sync`

### Environment Setup
- Requires Python 3.13+
- Uses `uv` for dependency management
- Requires `ANTHROPIC_API_KEY` in `.env` file for AI functionality

### Application Access
- Web interface: http://localhost:8000
- API documentation: http://localhost:8000/docs

## High-Level Architecture

This is a **Retrieval-Augmented Generation (RAG) system** for querying course materials with the following key components:

### Core Architecture Pattern
The system follows a modular RAG architecture with these main layers:

1. **FastAPI Web Layer** (`backend/app.py`)
   - REST API endpoints for queries and course statistics
   - Serves static frontend files
   - CORS middleware for development

2. **RAG Orchestration** (`backend/rag_system.py`)
   - Main coordinator that connects all components
   - Handles document ingestion and query processing
   - Manages conversation sessions and AI tool integration

3. **Vector Storage** (`backend/vector_store.py`)
   - ChromaDB-based semantic search using sentence transformers
   - Dual collections: course catalog (metadata) and course content (chunks)
   - Smart course name resolution and filtered searches

4. **AI Generation** (`backend/ai_generator.py`)
   - Anthropic Claude integration with tool support
   - Conversation history management
   - Tool-based search capabilities

5. **Document Processing** (`backend/document_processor.py`)
   - Ingests course documents from text files
   - Chunks content with configurable overlap
   - Extracts course/lesson metadata

### Key Design Patterns

**Tool-Based Search**: The AI uses search tools rather than direct vector retrieval, allowing for more intelligent query processing and course resolution.

**Dual Vector Collections**: Separates course metadata (titles, instructors) from content chunks for more efficient search and filtering.

**Session Management**: Maintains conversation history for context-aware responses.

**Modular Configuration**: All settings centralized in `backend/config.py` with environment variable support.

### Data Models (`backend/models.py`)
- `Course`: Course metadata with lessons
- `CourseChunk`: Text chunks for vector storage  
- `Lesson`: Individual lesson within a course

### Frontend
Simple HTML/CSS/JavaScript interface in `frontend/` directory served as static files.

## Important Implementation Notes

- Course documents are expected in `docs/` directory as `.txt`, `.pdf`, or `.docx` files
- Vector embeddings use "all-MiniLM-L6-v2" model
- ChromaDB persists to `./chroma_db` directory
- No test framework is currently configured
- No linting/formatting tools are configured in the project
- use uv to run Python files
- always use uv to run the server do not use pip directly
- use uv to manage all the dependencies
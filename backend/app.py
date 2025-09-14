import warnings
warnings.filterwarnings("ignore", message="resource_tracker: There appear to be.*")

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel
from typing import List, Optional, Union
import os
import time

from config import config
from rag_system import RAGSystem

# Initialize FastAPI app
app = FastAPI(title="Course Materials RAG System", root_path="")

# Add request logging middleware for debugging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    print(f"🌐 Incoming request: {request.method} {request.url}")
    print(f"📍 Headers: {dict(request.headers)}")
    print(f"🔗 Client: {request.client}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    print(f"✅ Response: {response.status_code} (took {process_time:.3f}s)")
    print(f"📤 Response headers: {dict(response.headers)}")
    print("---")
    
    return response

# Add trusted host middleware for proxy
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

# Enable CORS with proper settings for proxy
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Initialize RAG system
rag_system = RAGSystem(config)

# Pydantic models for request/response
class QueryRequest(BaseModel):
    """Request model for course queries"""
    query: str
    session_id: Optional[str] = None

class ClearSessionRequest(BaseModel):
    """Request model for clearing a session"""
    session_id: str

class SourceItem(BaseModel):
    """Source item that can have a text and optional link"""
    text: str
    link: Optional[str] = None

class QueryResponse(BaseModel):
    """Response model for course queries"""
    answer: str
    sources: List[Union[str, SourceItem]]
    session_id: str

class CourseStats(BaseModel):
    """Response model for course statistics"""
    total_courses: int
    course_titles: List[str]

# API Endpoints

@app.post("/api/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """Process a query and return response with sources"""
    try:
        # Create session if not provided
        session_id = request.session_id
        if not session_id:
            session_id = rag_system.session_manager.create_session()
        
        # Process query using RAG system
        answer, sources = rag_system.query(request.query, session_id)
        
        return QueryResponse(
            answer=answer,
            sources=sources,
            session_id=session_id
        )
    except Exception as e:
        error_msg = str(e)
        # Check for common API errors and provide better messages
        if "credit balance is too low" in error_msg:
            raise HTTPException(
                status_code=402, 
                detail="Anthropic API credit balance too low. Please add credits to your account."
            )
        elif "invalid_request_error" in error_msg:
            raise HTTPException(
                status_code=400,
                detail=f"API request error: {error_msg}"
            )
        else:
            raise HTTPException(status_code=500, detail=error_msg)

@app.get("/api/courses", response_model=CourseStats)
async def get_course_stats():
    """Get course analytics and statistics"""
    try:
        analytics = rag_system.get_course_analytics()
        return CourseStats(
            total_courses=analytics["total_courses"],
            course_titles=analytics["course_titles"]
        )
    except Exception as e:
        error_msg = str(e)
        # Check for common API errors and provide better messages
        if "credit balance is too low" in error_msg:
            raise HTTPException(
                status_code=402, 
                detail="Anthropic API credit balance too low. Please add credits to your account."
            )
        elif "invalid_request_error" in error_msg:
            raise HTTPException(
                status_code=400,
                detail=f"API request error: {error_msg}"
            )
        else:
            raise HTTPException(status_code=500, detail=error_msg)

@app.post("/api/clear-session")
async def clear_session(request: ClearSessionRequest):
    """Clear a conversation session"""
    try:
        rag_system.session_manager.clear_session(request.session_id)
        return {"success": True, "message": "Session cleared successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    """Load initial documents on startup"""
    docs_path = "../docs"
    if os.path.exists(docs_path):
        print("Loading initial documents...")
        try:
            courses, chunks = rag_system.add_course_folder(docs_path, clear_existing=False)
            print(f"Loaded {courses} courses with {chunks} chunks")
        except Exception as e:
            print(f"Error loading documents: {e}")

# Custom static file handler with no-cache headers for development
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from pathlib import Path


class DevStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if isinstance(response, FileResponse):
            # Add no-cache headers for development
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response
    
    
# Serve static files for the frontend
app.mount("/", StaticFiles(directory="../frontend", html=True), name="static")
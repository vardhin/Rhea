from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional, Dict, Any
import traceback
import sys
from io import StringIO
import contextlib
import re
from difflib import SequenceMatcher

Base = declarative_base()

# SQLAlchemy Model
class CodeTool(Base):
    __tablename__ = 'code_tools'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=False)
    code = Column(Text, nullable=False)
    category = Column(String(50))
    required_params = Column(JSON)
    optional_params = Column(JSON)
    return_schema = Column(JSON)
    examples = Column(JSON)
    is_active = Column(Boolean, default=True)
    is_bugged = Column(Boolean, default=False)
    bug_count = Column(Integer, default=0)
    last_bug_report = Column(DateTime)
    bug_details = Column(JSON)
    execution_count = Column(Integer, default=0)
    last_executed = Column(DateTime)
    tags = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Pydantic Models
class CodeToolCreate(BaseModel):
    name: str = Field(..., max_length=100)
    description: str
    code: str
    category: Optional[str] = None
    required_params: Optional[List[str]] = []
    optional_params: Optional[Dict[str, Any]] = {}
    return_schema: Optional[Dict[str, Any]] = None
    examples: Optional[List[Dict[str, Any]]] = None
    tags: Optional[List[str]] = []

class CodeToolUpdate(BaseModel):
    description: Optional[str] = None
    code: Optional[str] = None
    category: Optional[str] = None
    required_params: Optional[List[str]] = None
    optional_params: Optional[Dict[str, Any]] = None
    return_schema: Optional[Dict[str, Any]] = None
    examples: Optional[List[Dict[str, Any]]] = None
    is_active: Optional[bool] = None
    tags: Optional[List[str]] = None

class CodeToolResponse(BaseModel):
    id: int
    name: str
    description: str
    code: str
    category: Optional[str]
    required_params: Optional[List[str]]
    optional_params: Optional[Dict[str, Any]]
    return_schema: Optional[Dict[str, Any]]
    examples: Optional[List[Dict[str, Any]]]
    is_active: bool
    is_bugged: bool
    bug_count: int
    execution_count: int
    last_executed: Optional[datetime]
    tags: Optional[List[str]]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ExecuteRequest(BaseModel):
    params: Dict[str, Any] = {}

class ExecuteResponse(BaseModel):
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float
    stdout: Optional[str] = None

# Database Manager
class CodeToolManager:
    def __init__(self, db_url: str = "sqlite:///code_tools.db"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        SessionLocal = sessionmaker(bind=self.engine)
        self.SessionLocal = SessionLocal
    
    def get_tool_executor(self, db: Session):
        """
        Returns a function that can be used within tool code to execute other tools
        """
        def execute_tool(tool_name: str, params: Dict[str, Any]) -> Any:
            """Execute another tool by name and return its result"""
            tool = db.query(CodeTool).filter(CodeTool.name == tool_name).first()
            if not tool:
                raise ValueError(f"Tool '{tool_name}' not found")
            
            if not tool.is_active:
                raise ValueError(f"Tool '{tool_name}' is not active")
            
            if tool.is_bugged:
                raise ValueError(f"Tool '{tool_name}' is marked as bugged")
            
            # Execute the tool
            result = self.execute_code(tool.code, params, db)
            
            if not result["success"]:
                raise RuntimeError(f"Tool '{tool_name}' failed: {result['error']}")
            
            return result["result"]
        
        return execute_tool
    
    def execute_code(self, code: str, params: Dict[str, Any], db: Session = None) -> Dict[str, Any]:
        """Safely execute code with parameters"""
        stdout_capture = StringIO()
        
        try:
            # Create execution namespace with params
            exec_globals = {
                "params": params, 
                "__builtins__": __builtins__
            }
            
            # Add tool executor if database session is provided
            if db:
                exec_globals["execute_tool"] = self.get_tool_executor(db)
            
            # Capture stdout
            with contextlib.redirect_stdout(stdout_capture):
                exec(code, exec_globals)
            
            # Get result if defined
            result = exec_globals.get("result", None)
            
            return {
                "success": True,
                "result": result,
                "stdout": stdout_capture.getvalue()
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc(),
                "stdout": stdout_capture.getvalue()
            }
    
    def intelligent_search(self, query: str, tools: List[CodeTool], threshold: float = 0.3) -> List[tuple]:
        """
        Intelligent tool search with semantic matching
        Returns list of (tool, score) tuples sorted by relevance
        """
        query_lower = query.lower()
        query_words = set(re.findall(r'\w+', query_lower))
        
        # Common synonyms and related terms
        synonyms = {
            'calculate': ['compute', 'find', 'determine', 'get'],
            'convert': ['transform', 'change', 'translate'],
            'factorial': ['fact', 'permutation'],
            'temperature': ['temp', 'fahrenheit', 'celsius', 'kelvin'],
            'count': ['number', 'quantity', 'amount'],
            'character': ['char', 'letter', 'symbol'],
            'string': ['text', 'word'],
            'add': ['sum', 'plus', 'addition'],
            'subtract': ['minus', 'difference'],
            'multiply': ['times', 'product'],
            'divide': ['division', 'quotient'],
        }
        
        # Expand query with synonyms
        expanded_words = set(query_words)
        for word in query_words:
            for key, values in synonyms.items():
                if word == key or word in values:
                    expanded_words.add(key)
                    expanded_words.update(values)
        
        results = []
        
        for tool in tools:
            score = 0.0
            
            # Text fields to search
            name_lower = tool.name.lower()
            desc_lower = tool.description.lower()
            tags_lower = ' '.join(tool.tags or []).lower()
            category_lower = (tool.category or '').lower()
            
            # Combined text
            combined_text = f"{name_lower} {desc_lower} {tags_lower} {category_lower}"
            tool_words = set(re.findall(r'\w+', combined_text))
            
            # 1. Exact substring match in name (highest priority)
            if query_lower in name_lower:
                score += 10.0
            
            # 2. Exact substring match in description
            if query_lower in desc_lower:
                score += 5.0
            
            # 3. Word overlap with expanded query
            word_overlap = len(expanded_words & tool_words)
            if word_overlap > 0:
                score += word_overlap * 2.0
            
            # 4. Fuzzy matching on name
            name_similarity = SequenceMatcher(None, query_lower, name_lower).ratio()
            score += name_similarity * 3.0
            
            # 5. Fuzzy matching on description
            desc_similarity = SequenceMatcher(None, query_lower, desc_lower).ratio()
            score += desc_similarity * 2.0
            
            # 6. Tag exact matches
            for tag in (tool.tags or []):
                if tag.lower() in expanded_words:
                    score += 3.0
            
            # 7. Category match
            if category_lower in expanded_words or any(word in category_lower for word in expanded_words):
                score += 2.0
            
            # 8. Check if query describes what tool does
            # Extract key action words
            action_words = ['calculate', 'compute', 'convert', 'find', 'count', 'get', 'transform']
            query_actions = [w for w in expanded_words if w in action_words]
            tool_actions = [w for w in tool_words if w in action_words]
            
            if query_actions and tool_actions:
                action_overlap = len(set(query_actions) & set(tool_actions))
                score += action_overlap * 1.5
            
            # 9. Boost score for active, non-bugged tools
            if tool.is_active:
                score *= 1.1
            if not tool.is_bugged:
                score *= 1.1
            
            # 10. Boost frequently used tools slightly
            if tool.execution_count > 0:
                score += min(tool.execution_count * 0.1, 2.0)
            
            if score > threshold:
                results.append((tool, score))
        
        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results

# FastAPI App
app = FastAPI(title="Code Tool Store API", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

manager = CodeToolManager()

# Dependency
def get_db():
    db = manager.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# CRUD Endpoints

@app.post("/tools/", response_model=CodeToolResponse, status_code=201)
def create_tool(tool: CodeToolCreate, db: Session = Depends(get_db)):
    """Create a new code tool"""
    # Check if tool exists
    existing = db.query(CodeTool).filter(CodeTool.name == tool.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Tool with this name already exists")
    
    db_tool = CodeTool(**tool.dict())
    db.add(db_tool)
    db.commit()
    db.refresh(db_tool)
    return db_tool

@app.get("/tools/", response_model=List[CodeToolResponse])
def list_tools(
    active_only: bool = True,
    exclude_bugged: bool = True,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all tools with optional filtering"""
    query = db.query(CodeTool)
    
    if active_only:
        query = query.filter(CodeTool.is_active == True)
    if exclude_bugged:
        query = query.filter(CodeTool.is_bugged == False)
    if category:
        query = query.filter(CodeTool.category == category)
    
    return query.all()

@app.get("/tools/{tool_id}", response_model=CodeToolResponse)
def get_tool(tool_id: int, db: Session = Depends(get_db)):
    """Get a specific tool by ID"""
    tool = db.query(CodeTool).filter(CodeTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool

@app.get("/tools/name/{tool_name}", response_model=CodeToolResponse)
def get_tool_by_name(tool_name: str, db: Session = Depends(get_db)):
    """Get a specific tool by name"""
    tool = db.query(CodeTool).filter(CodeTool.name == tool_name).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool

@app.put("/tools/{tool_id}", response_model=CodeToolResponse)
def update_tool(tool_id: int, updates: CodeToolUpdate, db: Session = Depends(get_db)):
    """Update a tool"""
    tool = db.query(CodeTool).filter(CodeTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    update_data = updates.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(tool, key, value)
    
    tool.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(tool)
    return tool

@app.delete("/tools/{tool_id}")
def delete_tool(tool_id: int, db: Session = Depends(get_db)):
    """Delete a tool"""
    tool = db.query(CodeTool).filter(CodeTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    db.delete(tool)
    db.commit()
    return {"message": "Tool deleted successfully"}

@app.post("/tools/{tool_id}/deactivate")
def deactivate_tool(tool_id: int, db: Session = Depends(get_db)):
    """Deactivate a tool"""
    tool = db.query(CodeTool).filter(CodeTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    tool.is_active = False
    tool.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Tool deactivated successfully"}

# Execution Endpoints

@app.post("/tools/{tool_id}/execute", response_model=ExecuteResponse)
def execute_tool_by_id(tool_id: int, request: ExecuteRequest, db: Session = Depends(get_db)):
    """Execute a tool by ID"""
    tool = db.query(CodeTool).filter(CodeTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    if not tool.is_active:
        raise HTTPException(status_code=400, detail="Tool is not active")
    
    if tool.is_bugged:
        raise HTTPException(status_code=400, detail="Tool is marked as bugged")
    
    # Execute code with database session for tool chaining
    start_time = datetime.utcnow()
    result = manager.execute_code(tool.code, request.params, db)
    execution_time = (datetime.utcnow() - start_time).total_seconds()
    
    # Update execution stats
    tool.execution_count += 1
    tool.last_executed = datetime.utcnow()
    
    # Handle bugs
    if not result["success"]:
        tool.bug_count += 1
        tool.is_bugged = True
        tool.last_bug_report = datetime.utcnow()
        
        bug_detail = {
            "timestamp": datetime.utcnow().isoformat(),
            "error": result["error"],
            "traceback": result.get("traceback"),
            "params": request.params
        }
        
        if tool.bug_details:
            tool.bug_details.append(bug_detail)
        else:
            tool.bug_details = [bug_detail]
    
    db.commit()
    
    return ExecuteResponse(
        success=result["success"],
        result=result.get("result"),
        error=result.get("error"),
        execution_time=execution_time,
        stdout=result.get("stdout")
    )

@app.post("/tools/name/{tool_name}/execute", response_model=ExecuteResponse)
def execute_tool_by_name(tool_name: str, request: ExecuteRequest, db: Session = Depends(get_db)):
    """Execute a tool by name"""
    tool = db.query(CodeTool).filter(CodeTool.name == tool_name).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    return execute_tool_by_id(tool.id, request, db)

# Bug Management

@app.post("/tools/{tool_id}/clear-bugs")
def clear_bug_status(tool_id: int, db: Session = Depends(get_db)):
    """Clear bug status for a tool"""
    tool = db.query(CodeTool).filter(CodeTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    tool.is_bugged = False
    tool.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Bug status cleared"}

@app.get("/tools/bugged/list", response_model=List[CodeToolResponse])
def list_bugged_tools(db: Session = Depends(get_db)):
    """List all bugged tools"""
    return db.query(CodeTool).filter(CodeTool.is_bugged == True).all()

# Search

@app.get("/tools/search/{query}", response_model=List[CodeToolResponse])
def search_tools(
    query: str, 
    exclude_bugged: bool = True, 
    limit: int = 10,
    threshold: float = 0.3,
    db: Session = Depends(get_db)
):
    """
    Intelligent search for tools by name, description, tags, or functionality
    
    Args:
        query: Search query
        exclude_bugged: Exclude bugged tools (default: True)
        limit: Maximum number of results (default: 10)
        threshold: Minimum relevance score (default: 0.3)
    """
    # Get all potentially matching tools
    query_obj = db.query(CodeTool)
    
    if exclude_bugged:
        query_obj = query_obj.filter(CodeTool.is_bugged == False)
    
    all_tools = query_obj.all()
    
    # Use intelligent search
    scored_results = manager.intelligent_search(query, all_tools, threshold)
    
    # Return top results
    top_tools = [tool for tool, score in scored_results[:limit]]
    
    # Debug: print scores
    print(f"\nSearch query: '{query}'")
    print(f"Found {len(scored_results)} relevant tools:")
    for tool, score in scored_results[:5]:
        print(f"  - {tool.name}: {score:.2f}")
    
    return top_tools

@app.get("/tools/search-debug/{query}")
def search_tools_debug(
    query: str, 
    exclude_bugged: bool = True,
    threshold: float = 0.3,
    db: Session = Depends(get_db)
):
    """
    Debug version of search that returns scores
    """
    query_obj = db.query(CodeTool)
    
    if exclude_bugged:
        query_obj = query_obj.filter(CodeTool.is_bugged == False)
    
    all_tools = query_obj.all()
    scored_results = manager.intelligent_search(query, all_tools, threshold)
    
    return {
        "query": query,
        "total_tools": len(all_tools),
        "results": [
            {
                "id": tool.id,
                "name": tool.name,
                "description": tool.description,
                "score": round(score, 2),
                "tags": tool.tags,
                "category": tool.category
            }
            for tool, score in scored_results
        ]
    }

@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
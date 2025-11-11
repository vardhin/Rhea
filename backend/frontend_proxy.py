from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import asyncio
import json
import os
import time
from dotenv import load_dotenv
from google import genai  # Changed from google.generativeai

# Import from existing modules
from tool_use import ToolUseAgent, IterationContext
from tool_store import (
    CodeToolCreate, CodeToolUpdate, CodeToolResponse, 
    ExecuteRequest, get_db, CodeTool
)
from sqlalchemy.orm import Session

load_dotenv()

# Initialize FastAPI
app = FastAPI(title="Tool Use Frontend Proxy", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define GeminiAPIManager class BEFORE using it
class GeminiAPIManager:
    def __init__(self, api_keys: List[str]):
        if not api_keys:
            raise ValueError("No API keys provided")
        
        self.api_keys = api_keys
        self.current_index = 0
        self.clients = [genai.Client(api_key=key) for key in api_keys]
        self.last_request_time = 0
        self.key_cooldowns = {}  # Track when each key was last overloaded
        
        print(f"Initialized with {len(api_keys)} API keys")
    
    def _wait_for_rate_limit(self):
        """Ensure minimum time between requests"""
        MIN_REQUEST_INTERVAL = 3.0  # seconds between requests
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < MIN_REQUEST_INTERVAL:
            sleep_time = MIN_REQUEST_INTERVAL - time_since_last
            print(f"Rate limiting: waiting {sleep_time:.2f} seconds...")
            time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def _get_next_available_client(self) -> tuple:
        """Get next available client, skipping recently failed ones"""
        now = time.time()
        
        # Try to find a key that's not in cooldown
        for _ in range(len(self.clients)):
            client = self.clients[self.current_index]
            key_number = self.current_index + 1
            
            # Check if key is in cooldown (wait 60 seconds after overload)
            last_fail = self.key_cooldowns.get(self.current_index, 0)
            if now - last_fail > 60:  # 60 second cooldown
                self.current_index = (self.current_index + 1) % len(self.clients)
                return client, key_number
            
            self.current_index = (self.current_index + 1) % len(self.clients)
        
        # All keys in cooldown - wait and retry with first one
        print("All API keys in cooldown. Waiting 30 seconds...")
        time.sleep(30)
        return self.clients[0], 1
    
    def generate_content(self, model: str, contents: str, max_retries: int = None) -> Any:
        """Generate content with automatic retry on overload"""
        if max_retries is None:
            max_retries = len(self.api_keys) * 2  # Try each key twice
        
        last_error = None
        
        for attempt in range(max_retries):
            self._wait_for_rate_limit()
            
            client, key_number = self._get_next_available_client()
            
            try:
                print(f"Using API key #{key_number} (attempt {attempt + 1}/{max_retries})")
                response = client.models.generate_content(
                    model=model,
                    contents=contents
                )
                
                # Clear cooldown on success
                if key_number - 1 in self.key_cooldowns:
                    del self.key_cooldowns[key_number - 1]
                
                return response
                
            except Exception as e:
                error_msg = str(e).lower()
                last_error = e
                
                if any(keyword in error_msg for keyword in ['overload', 'quota', 'rate limit', '429', '503']):
                    print(f"API key #{key_number} overloaded: {e}")
                    # Mark key as failed
                    self.key_cooldowns[key_number - 1] = time.time()
                    
                    if attempt < max_retries - 1:
                        print(f"Switching to next API key...")
                        continue
                else:
                    raise e
        
        raise Exception(f"All API keys exhausted after {max_retries} attempts. Last error: {last_error}")
    
    def generate_content_stream(self, model: str, contents: str, max_retries: int = None):
        """Generate content with streaming"""
        if max_retries is None:
            max_retries = len(self.api_keys) * 2
        
        last_error = None
        
        for attempt in range(max_retries):
            self._wait_for_rate_limit()
            
            client, key_number = self._get_next_available_client()
            
            try:
                print(f"Using API key #{key_number} (streaming, attempt {attempt + 1}/{max_retries})")
                
                # Use streaming API
                response = client.models.generate_content_stream(
                    model=model,
                    contents=contents
                )
                
                # Clear cooldown on success
                if key_number - 1 in self.key_cooldowns:
                    del self.key_cooldowns[key_number - 1]
                
                return response
                
            except Exception as e:
                error_msg = str(e).lower()
                last_error = e
                
                if any(keyword in error_msg for keyword in ['overload', 'quota', 'rate limit', '429', '503']):
                    print(f"API key #{key_number} overloaded: {e}")
                    self.key_cooldowns[key_number - 1] = time.time()
                    
                    if attempt < max_retries - 1:
                        continue
                else:
                    raise e
        
        raise Exception(f"All API keys exhausted. Last error: {last_error}")

# Initialize agent
api_keys = []
for i in range(1, 8):
    key = os.getenv(f"GEMINI_API_KEY_{i}")
    if key:
        api_keys.append(key)

if not api_keys:
    raise ValueError("No API keys found! Please set GEMINI_API_KEY_1 to GEMINI_API_KEY_7")

# Initialize the GeminiAPIManager
api_manager = GeminiAPIManager(api_keys)

# Initialize agent with api_manager
agent = ToolUseAgent(api_keys)
agent.api_manager = api_manager  # Add the api_manager to agent

# WebSocket Models
class QuestionRequest(BaseModel):
    question: str

# Simple message format for frontend
def create_message(type: str, data: Any) -> str:
    """Create simple message format: TYPE|JSON_DATA"""
    return json.dumps({"type": type, "data": data})

# WebSocket endpoint for question processing
@app.websocket("/ws/ask")
async def websocket_ask(websocket: WebSocket):
    await websocket.accept()
    
    try:
        # Receive question
        data = await websocket.receive_text()
        request = json.loads(data)
        question = request.get("question", "")
        
        if not question:
            await websocket.send_text(create_message("error", {"message": "No question provided"}))
            return
        
        # Send start message
        await websocket.send_text(create_message("start", {"question": question}))
        
        # Create context
        context = IterationContext(question=question, iteration=0, history=[])
        system_prompt = agent._build_system_prompt()
        
        # Iterative processing
        for i in range(10):  # MAX_ITERATIONS
            context.iteration = i + 1
            
            # Send iteration start
            await websocket.send_text(create_message("iteration", {
                "number": context.iteration,
                "status": "starting"
            }))
            
            # Build prompt
            user_prompt = agent._build_user_prompt(context)
            
            # Call Gemini with streaming
            try:
                await websocket.send_text(create_message("thinking", {
                    "message": "Consulting AI..."
                }))
                
                # Use streaming API
                response_stream = agent.api_manager.generate_content_stream(
                    model="gemini-2.5-flash",
                    contents=f"{system_prompt}\n\n{user_prompt}"
                )
                
                response_text = ""
                for chunk in response_stream:
                    if hasattr(chunk, 'text') and chunk.text:
                        # Stream each chunk to frontend
                        await websocket.send_text(create_message("stream", {
                            "chunk": chunk.text
                        }))
                        response_text += chunk.text
                
                # Send complete response marker
                await websocket.send_text(create_message("response_complete", {
                    "text": response_text
                }))
                
            except Exception as e:
                await websocket.send_text(create_message("error", {
                    "message": f"AI Error: {str(e)}"
                }))
                return
            
            # Parse response
            agent_state = agent._parse_gemini_response(response_text)
            
            # Send state
            await websocket.send_text(create_message("state", {
                "state": agent_state.state,
                "reasoning": agent_state.reasoning
            }))
            
            # Execute action
            await websocket.send_text(create_message("action", {
                "state": agent_state.state,
                "action": agent_state.action
            }))
            
            result = agent._execute_state(agent_state, context)
            
            # Send result
            await websocket.send_text(create_message("result", {
                "state": agent_state.state,
                "result": result
            }))
            
            # Add to history
            context.history.append({
                "state": agent_state.state,
                "reasoning": agent_state.reasoning,
                "action": agent_state.action,
                "result": result
            })
            
            # Check for exit
            if agent_state.state == "exit_response":
                await websocket.send_text(create_message("final", {
                    "answer": agent_state.action.get('final_answer'),
                    "confidence": agent_state.action.get('confidence'),
                    "iterations": context.iteration
                }))
                return
        
        # Max iterations reached
        await websocket.send_text(create_message("timeout", {
            "message": "Maximum iterations reached",
            "iterations": context.iteration
        }))
        
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        try:
            await websocket.send_text(create_message("error", {
                "message": str(e)
            }))
        except:
            pass

# REST endpoint for simple question (non-streaming)
@app.post("/ask")
async def ask_question(request: QuestionRequest):
    """Non-streaming endpoint for questions"""
    try:
        result = agent.process_question(request.question)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= TOOL STORE PROXY ENDPOINTS =============

@app.post("/tools", response_model=CodeToolResponse, status_code=201)
def create_tool(tool: CodeToolCreate, db: Session = Depends(get_db)):
    """Create a new code tool"""
    from tool_store import app as tool_app
    return tool_app.dependency_overrides.get(get_db, get_db)

@app.get("/tools", response_model=List[CodeToolResponse])
def list_tools(
    active_only: bool = True,
    exclude_bugged: bool = True,
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all tools"""
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
    """Get tool by ID"""
    tool = db.query(CodeTool).filter(CodeTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool

@app.get("/tools/name/{tool_name}", response_model=CodeToolResponse)
def get_tool_by_name(tool_name: str, db: Session = Depends(get_db)):
    """Get tool by name"""
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
    
    from datetime import datetime
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

@app.post("/tools/{tool_id}/execute")
def execute_tool_by_id(tool_id: int, request: ExecuteRequest, db: Session = Depends(get_db)):
    """Execute tool by ID"""
    tool = db.query(CodeTool).filter(CodeTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    if not tool.is_active:
        raise HTTPException(status_code=400, detail="Tool is not active")
    
    if tool.is_bugged:
        raise HTTPException(status_code=400, detail="Tool is marked as bugged")
    
    # Execute code
    from datetime import datetime
    start_time = datetime.utcnow()
    result = agent.tool_store.tool_store.manager.execute_code(tool.code, request.params)
    execution_time = (datetime.utcnow() - start_time).total_seconds()
    
    # Update execution stats
    tool.execution_count += 1
    tool.last_executed = datetime.utcnow()
    
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
    
    return {
        "success": result["success"],
        "result": result.get("result"),
        "error": result.get("error"),
        "execution_time": execution_time,
        "stdout": result.get("stdout")
    }

@app.post("/tools/name/{tool_name}/execute")
def execute_tool_by_name(tool_name: str, request: ExecuteRequest, db: Session = Depends(get_db)):
    """Execute tool by name"""
    tool = db.query(CodeTool).filter(CodeTool.name == tool_name).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    return execute_tool_by_id(tool.id, request, db)

@app.get("/tools/search/{query}", response_model=List[CodeToolResponse])
def search_tools(
    query: str,
    exclude_bugged: bool = True,
    limit: int = 10,
    threshold: float = 0.3,
    db: Session = Depends(get_db)
):
    """Search tools"""
    from tool_store import CodeToolManager
    
    manager = CodeToolManager()
    
    query_obj = db.query(CodeTool)
    if exclude_bugged:
        query_obj = query_obj.filter(CodeTool.is_bugged == False)
    
    all_tools = query_obj.all()
    scored_results = manager.intelligent_search(query, all_tools, threshold)
    
    top_tools = [tool for tool, score in scored_results[:limit]]
    return top_tools

@app.get("/tools/bugged/list", response_model=List[CodeToolResponse])
def list_bugged_tools(db: Session = Depends(get_db)):
    """List all bugged tools"""
    return db.query(CodeTool).filter(CodeTool.is_bugged == True).all()

@app.post("/tools/{tool_id}/clear-bugs")
def clear_bug_status(tool_id: int, db: Session = Depends(get_db)):
    """Clear bug status"""
    tool = db.query(CodeTool).filter(CodeTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    from datetime import datetime
    tool.is_bugged = False
    tool.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Bug status cleared"}

@app.post("/tools/{tool_id}/deactivate")
def deactivate_tool(tool_id: int, db: Session = Depends(get_db)):
    """Deactivate a tool"""
    tool = db.query(CodeTool).filter(CodeTool.id == tool_id).first()
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    
    from datetime import datetime
    tool.is_active = False
    tool.updated_at = datetime.utcnow()
    db.commit()
    return {"message": "Tool deactivated successfully"}

# Health check
@app.get("/")
def root():
    return {
        "service": "Tool Use Frontend Proxy",
        "version": "1.0.0",
        "endpoints": {
            "websocket": "/ws/ask",
            "rest": "/ask",
            "tools": "/tools"
        },
        "api_keys_loaded": len(api_keys)
    }

# Run server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
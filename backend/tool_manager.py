from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from typing import List, Optional, Dict, Any

Base = declarative_base()

class Tool(Base):
    __tablename__ = 'tools'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tool_name = Column(String(100), unique=True, nullable=False)
    tool_description = Column(Text, nullable=False)
    tool_category = Column(String(50), nullable=False)
    tool_endpoint = Column(String(255), nullable=False)
    tool_params = Column(JSON, nullable=False)  # Complete param schema
    required_params = Column(JSON, nullable=False)  # List of required param names
    optional_params = Column(JSON)  # Dict of optional params with defaults
    return_schema = Column(JSON)  # Expected return format
    examples = Column(JSON)  # Usage examples
    is_active = Column(Boolean, default=True)
    is_bugged = Column(Boolean, default=False)  # NEW: Track if tool is buggy
    bug_count = Column(Integer, default=0)  # NEW: Number of times tool failed
    last_bug_report = Column(DateTime)  # NEW: When was last bug reported
    bug_details = Column(JSON)  # NEW: Store bug information
    auth_required = Column(Boolean, default=False)
    rate_limit = Column(Integer)  # Calls per minute/hour
    tags = Column(JSON)  # List of tags
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ToolManager:
    def __init__(self, db_url: str = "sqlite:///tools.db"):
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()
    
    # CREATE
    def create_tool(self, tool_data: Dict[str, Any]) -> Tool:
        tool = Tool(**tool_data)
        self.session.add(tool)
        self.session.commit()
        self.session.refresh(tool)
        return tool
    
    # READ
    def get_tool(self, tool_id: int) -> Optional[Tool]:
        return self.session.query(Tool).filter(Tool.id == tool_id).first()
    
    def get_tool_by_name(self, tool_name: str) -> Optional[Tool]:
        return self.session.query(Tool).filter(Tool.tool_name == tool_name).first()
    
    def get_all_tools(self, active_only: bool = True, exclude_bugged: bool = False) -> List[Tool]:
        """Get all tools with optional filtering"""
        query = self.session.query(Tool)
        if active_only:
            query = query.filter(Tool.is_active == True)
        if exclude_bugged:
            query = query.filter(Tool.is_bugged == False)
        return query.all()
    
    def get_tools_by_category(self, category: str, exclude_bugged: bool = False) -> List[Tool]:
        """Get tools by category with optional bug filtering"""
        query = self.session.query(Tool).filter(Tool.tool_category == category)
        if exclude_bugged:
            query = query.filter(Tool.is_bugged == False)
        return query.all()
    
    def search_tools(self, query: str, exclude_bugged: bool = False) -> List[Tool]:
        """Search tools with optional bug filtering"""
        search = f"%{query}%"
        query_obj = self.session.query(Tool).filter(
            (Tool.tool_name.like(search)) | 
            (Tool.tool_description.like(search))
        )
        if exclude_bugged:
            query_obj = query_obj.filter(Tool.is_bugged == False)
        return query_obj.all()
    
    # UPDATE
    def update_tool(self, tool_id: int, updates: Dict[str, Any]) -> Optional[Tool]:
        tool = self.get_tool(tool_id)
        if tool:
            for key, value in updates.items():
                setattr(tool, key, value)
            tool.updated_at = datetime.utcnow()
            self.session.commit()
            self.session.refresh(tool)
        return tool
    
    # DELETE
    def delete_tool(self, tool_id: int) -> bool:
        tool = self.get_tool(tool_id)
        if tool:
            self.session.delete(tool)
            self.session.commit()
            return True
        return False
    
    def deactivate_tool(self, tool_id: int) -> bool:
        return self.update_tool(tool_id, {"is_active": False}) is not None
    
    # BUG MANAGEMENT
    def mark_tool_as_bugged(self, tool_name: str, error_details: Dict[str, Any]) -> Optional[Tool]:
        """Mark a tool as bugged and store error details"""
        tool = self.get_tool_by_name(tool_name)
        if tool:
            tool.is_bugged = True
            tool.bug_count = (tool.bug_count or 0) + 1
            tool.last_bug_report = datetime.utcnow()
            
            # Store bug details
            if tool.bug_details:
                tool.bug_details.append(error_details)
            else:
                tool.bug_details = [error_details]
            
            self.session.commit()
            self.session.refresh(tool)
        return tool
    
    def clear_tool_bug_status(self, tool_name: str) -> Optional[Tool]:
        """Clear bug status for a tool (after it's been fixed)"""
        tool = self.get_tool_by_name(tool_name)
        if tool:
            tool.is_bugged = False
            tool.updated_at = datetime.utcnow()
            self.session.commit()
            self.session.refresh(tool)
        return tool
    
    def get_bugged_tools(self) -> List[Tool]:
        """Get all tools marked as bugged"""
        return self.session.query(Tool).filter(Tool.is_bugged == True).all()
    
    # LLM Context Generation
    def get_tools_context(self, category: Optional[str] = None, exclude_bugged: bool = True) -> str:
        """Generate formatted context for LLM about available tools"""
        if category:
            tools = self.get_tools_by_category(category, exclude_bugged=exclude_bugged)
        else:
            tools = self.get_all_tools(exclude_bugged=exclude_bugged)
        
        context = "Available Tools:\n\n"
        for tool in tools:
            context += f"Tool: {tool.tool_name}\n"
            context += f"Description: {tool.tool_description}\n"
            context += f"Required Parameters: {tool.required_params}\n"
            context += f"Optional Parameters: {tool.optional_params}\n"
            if tool.examples:
                context += f"Examples: {tool.examples}\n"
            context += "\n"
        
        # Optionally include bugged tools warning
        if not exclude_bugged:
            bugged_tools = self.get_bugged_tools()
            if bugged_tools:
                context += "\n⚠️ Bugged Tools (avoid using):\n"
                for tool in bugged_tools:
                    context += f"- {tool.tool_name}: Failed {tool.bug_count} times\n"
        
        return context
    
    def close(self):
        self.session.close()
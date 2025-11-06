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
    
    def get_all_tools(self, active_only: bool = True) -> List[Tool]:
        query = self.session.query(Tool)
        if active_only:
            query = query.filter(Tool.is_active == True)
        return query.all()
    
    def get_tools_by_category(self, category: str) -> List[Tool]:
        return self.session.query(Tool).filter(Tool.tool_category == category).all()
    
    def search_tools(self, query: str) -> List[Tool]:
        search = f"%{query}%"
        return self.session.query(Tool).filter(
            (Tool.tool_name.like(search)) | 
            (Tool.tool_description.like(search))
        ).all()
    
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
    
    # LLM Context Generation
    def get_tools_context(self, category: Optional[str] = None) -> str:
        """Generate formatted context for LLM about available tools"""
        tools = self.get_tools_by_category(category) if category else self.get_all_tools()
        
        context = "Available Tools:\n\n"
        for tool in tools:
            context += f"Tool: {tool.tool_name}\n"
            context += f"Description: {tool.tool_description}\n"
            context += f"Required Parameters: {tool.required_params}\n"
            context += f"Optional Parameters: {tool.optional_params}\n"
            if tool.examples:
                context += f"Examples: {tool.examples}\n"
            context += "\n"
        
        return context
    
    def close(self):
        self.session.close()
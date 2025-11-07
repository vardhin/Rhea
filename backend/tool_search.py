from typing import List, Dict, Any, Optional, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from rank_bm25 import BM25Okapi
import re
from collections import defaultdict

class ToolSearchEngine:
    """Semantic search engine for tools using TF-IDF and BM25"""
    
    def __init__(self, registry):
        self.registry = registry
        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            stop_words='english',
            ngram_range=(1, 2),  # Unigrams and bigrams
            max_features=1000
        )
        self.tool_corpus = []
        self.tool_names = []
        self.tool_metadata = {}
        self.bm25 = None
        self._build_search_index()
    
    def _build_search_index(self):
        """Build searchable corpus from all tools"""
        tools = self.registry.list_tools()
        
        for tool_name, tool_info in tools.items():
            if not tool_info.get('available', True):
                continue
            
            # Create searchable text combining all relevant fields
            searchable_text = self._create_searchable_text(tool_info)
            
            self.tool_corpus.append(searchable_text)
            self.tool_names.append(tool_name)
            self.tool_metadata[tool_name] = tool_info
        
        if self.tool_corpus:
            # Build TF-IDF matrix
            self.tfidf_matrix = self.vectorizer.fit_transform(self.tool_corpus)
            
            # Build BM25 index
            tokenized_corpus = [doc.lower().split() for doc in self.tool_corpus]
            self.bm25 = BM25Okapi(tokenized_corpus)
    
    def _create_searchable_text(self, tool_info: Dict[str, Any]) -> str:
        """Create comprehensive searchable text from tool metadata"""
        parts = [
            tool_info['name'],
            tool_info['name'].replace('_', ' '),  # Handle snake_case
            tool_info['description'],
            tool_info.get('category', ''),
            ' '.join(tool_info.get('tags', [])),
            ' '.join(tool_info.get('required_params', [])),
            ' '.join(tool_info.get('optional_params', {}).keys())
        ]
        
        # Add parameter types and names
        for param_name, param_info in tool_info.get('params', {}).items():
            parts.append(param_name)
            parts.append(param_name.replace('_', ' '))
            if isinstance(param_info, dict):
                parts.append(param_info.get('type', ''))
        
        return ' '.join(filter(None, parts))
    
    def _preprocess_query(self, query: str) -> str:
        """Preprocess query for better matching"""
        # Convert to lowercase
        query = query.lower()
        
        # Expand common abbreviations
        abbreviations = {
            'calc': 'calculate calculation',
            'math': 'mathematics mathematical',
            'web': 'website internet',
            'db': 'database',
            'img': 'image',
            'vid': 'video',
            'txt': 'text',
            'doc': 'document',
        }
        
        for abbr, expansion in abbreviations.items():
            query = query.replace(abbr, expansion)
        
        return query
    
    def _extract_keywords(self, query: str) -> List[str]:
        """Extract important keywords from query"""
        # Remove common words and extract meaningful terms
        query = self._preprocess_query(query)
        
        # Split and filter
        words = re.findall(r'\b\w+\b', query)
        
        # Remove very common words not in stop_words
        common_words = {'need', 'want', 'use', 'help', 'tool', 'function', 'can', 'how'}
        keywords = [w for w in words if w not in common_words and len(w) > 2]
        
        return keywords
    
    def search(self, query: str, top_k: int = 3, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Search for tools using hybrid approach (TF-IDF + BM25 + keyword matching)
        
        Args:
            query: Natural language search query
            top_k: Number of results to return (default 3)
            category: Optional category filter
            
        Returns:
            List of top matching tools with scores
        """
        if not self.tool_corpus:
            return []
        
        query_processed = self._preprocess_query(query)
        keywords = self._extract_keywords(query)
        
        # 1. TF-IDF cosine similarity
        query_vec = self.vectorizer.transform([query_processed])
        tfidf_scores = cosine_similarity(query_vec, self.tfidf_matrix)[0]
        
        # 2. BM25 ranking
        query_tokens = query_processed.split()
        bm25_scores = self.bm25.get_scores(query_tokens)
        
        # 3. Keyword boost (exact matches in name, description, tags)
        keyword_scores = np.zeros(len(self.tool_names))
        for idx, tool_name in enumerate(self.tool_names):
            tool_info = self.tool_metadata[tool_name]
            score = 0
            
            for keyword in keywords:
                # Name match (highest weight)
                if keyword in tool_info['name'].lower():
                    score += 5.0
                
                # Description match
                if keyword in tool_info['description'].lower():
                    score += 2.0
                
                # Tag match
                if any(keyword in tag.lower() for tag in tool_info.get('tags', [])):
                    score += 3.0
                
                # Category match
                if keyword in tool_info.get('category', '').lower():
                    score += 2.5
                
                # Parameter match
                if any(keyword in param.lower() for param in tool_info.get('required_params', [])):
                    score += 1.5
            
            keyword_scores[idx] = score
        
        # Normalize scores to [0, 1] range
        tfidf_norm = tfidf_scores / (tfidf_scores.max() + 1e-10)
        bm25_norm = bm25_scores / (bm25_scores.max() + 1e-10)
        keyword_norm = keyword_scores / (keyword_scores.max() + 1e-10) if keyword_scores.max() > 0 else keyword_scores
        
        # Weighted combination (adjust weights based on your needs)
        final_scores = (
            0.3 * tfidf_norm +
            0.4 * bm25_norm +
            0.3 * keyword_norm
        )
        
        # Get top K indices
        top_indices = np.argsort(final_scores)[::-1]
        
        results = []
        for idx in top_indices:
            tool_name = self.tool_names[idx]
            tool_info = self.tool_metadata[tool_name]
            
            # Apply category filter if specified
            if category and tool_info.get('category') != category:
                continue
            
            # Only include results with non-zero scores
            if final_scores[idx] > 0.01:
                results.append({
                    'tool_name': tool_name,
                    'tool_info': tool_info,
                    'relevance_score': float(final_scores[idx]),
                    'score_breakdown': {
                        'tfidf': float(tfidf_norm[idx]),
                        'bm25': float(bm25_norm[idx]),
                        'keyword': float(keyword_norm[idx])
                    }
                })
            
            if len(results) >= top_k:
                break
        
        return results
    
    def get_tools_for_llm_context(self, query: str, max_tools: int = 3) -> str:
        """
        Generate formatted context for LLM with most relevant tools
        
        Args:
            query: User's natural language query/intent
            max_tools: Maximum number of tools to include
            
        Returns:
            Formatted string with tool information
        """
        results = self.search(query, top_k=max_tools)
        
        if not results:
            return "No relevant tools found for this query."
        
        context = f"Most relevant tools for: '{query}'\n\n"
        
        for i, result in enumerate(results, 1):
            tool = result['tool_info']
            score = result['relevance_score']
            
            context += f"{i}. Tool: {tool['name']} (Relevance: {score:.2f})\n"
            context += f"   Description: {tool['description']}\n"
            context += f"   Category: {tool['category']}\n"
            context += f"   Required Params: {', '.join(tool['required_params']) if tool['required_params'] else 'None'}\n"
            
            if tool.get('optional_params'):
                context += f"   Optional Params: {', '.join(tool['optional_params'].keys())}\n"
            
            if tool.get('tags'):
                context += f"   Tags: {', '.join(tool['tags'])}\n"
            
            context += "\n"
        
        return context
    
    def rebuild_index(self):
        """Rebuild search index (call after adding/removing tools)"""
        self.tool_corpus = []
        self.tool_names = []
        self.tool_metadata = {}
        self._build_search_index()
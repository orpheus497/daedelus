"""
Query Expansion for Daedelus Intelligence System.

Expands user queries with synonyms and related terms to improve search coverage
and recall, while maintaining precision through intelligent weighting.

Phase 5 - Intelligence System Enhancement
Created by: orpheus497
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

import yaml

logger = logging.getLogger(__name__)


class QueryExpander:
    """
    Expands search queries with synonyms and related terms.
    
    Uses a curated synonym dictionary for Linux/shell terminology to improve
    search quality by finding conceptually related content even when exact
    keywords don't match.
    
    Attributes:
        synonyms_dict: Mapping of terms to synonym lists
        reverse_index: Reverse mapping for efficient lookup
        max_expansions: Maximum number of synonyms per term
        stopwords: Common words to skip during expansion
    """
    
    def __init__(
        self,
        synonyms_path: Path | None = None,
        max_expansions: int = 3,
        include_original: bool = True
    ):
        """
        Initialize query expander.
        
        Args:
            synonyms_path: Path to synonyms YAML file
            max_expansions: Maximum synonyms to add per term
            include_original: Whether to include original term in expansion
        """
        self.max_expansions = max_expansions
        self.include_original = include_original
        
        # Stopwords to skip (too common for expansion)
        self.stopwords = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'be', 'been',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
            'should', 'may', 'might', 'can', 'this', 'that', 'these', 'those',
            'i', 'you', 'he', 'she', 'it', 'we', 'they', 'what', 'which', 'who',
            'when', 'where', 'why', 'how', 'my', 'your', 'his', 'her', 'its'
        }
        
        # Load synonyms
        if synonyms_path is None:
            # Default path
            synonyms_path = Path(__file__).parent.parent.parent / 'data' / 'synonyms' / 'shell_terms.yaml'
        
        self.synonyms_dict: Dict[str, List[str]] = {}
        self.reverse_index: Dict[str, List[str]] = {}
        
        self._load_synonyms(Path(synonyms_path))
        
        logger.info(f"QueryExpander initialized with {len(self.synonyms_dict)} synonym groups")
    
    def _load_synonyms(self, path: Path) -> None:
        """
        Load synonyms from YAML file.
        
        Args:
            path: Path to synonyms YAML file
        """
        if not path.exists():
            logger.warning(f"Synonyms file not found: {path}")
            return
        
        try:
            with open(path, 'r') as f:
                data = yaml.safe_load(f)
            
            if not data:
                logger.warning("Synonyms file is empty")
                return
            
            # Build synonyms dictionary
            for term, synonyms in data.items():
                if not isinstance(synonyms, list):
                    continue
                
                term_lower = term.lower()
                synonyms_lower = [s.lower() for s in synonyms]
                
                self.synonyms_dict[term_lower] = synonyms_lower
                
                # Build reverse index (synonym -> main term)
                for synonym in synonyms_lower:
                    if synonym not in self.reverse_index:
                        self.reverse_index[synonym] = []
                    self.reverse_index[synonym].append(term_lower)
            
            logger.info(f"Loaded {len(self.synonyms_dict)} synonym groups from {path}")
            
        except Exception as e:
            logger.error(f"Error loading synonyms: {e}")
    
    def expand_query(
        self,
        query: str,
        boost_original: float = 2.0,
        context: str | None = None
    ) -> List[Tuple[str, float]]:
        """
        Expand query with synonyms and related terms.
        
        Args:
            query: Original search query
            boost_original: Weight multiplier for original terms (vs synonyms)
            context: Optional context for context-aware expansion
            
        Returns:
            List of (expanded_term, weight) tuples
        """
        # Tokenize query
        tokens = self._tokenize(query)
        
        # Filter stopwords
        meaningful_tokens = [t for t in tokens if t.lower() not in self.stopwords]
        
        if not meaningful_tokens:
            # If all stopwords, keep original
            meaningful_tokens = tokens
        
        # Expand each term
        expanded = []
        seen = set()
        
        for token in meaningful_tokens:
            token_lower = token.lower()
            
            # Add original term with boost
            if self.include_original and token_lower not in seen:
                expanded.append((token, boost_original))
                seen.add(token_lower)
            
            # Find synonyms
            synonyms = self._get_synonyms(token_lower, context=context)
            
            # Add synonyms with decreasing weight
            for i, synonym in enumerate(synonyms[:self.max_expansions]):
                if synonym not in seen:
                    # Weight decreases: 1.0, 0.7, 0.5
                    weight = max(0.5, 1.0 - (i * 0.3))
                    expanded.append((synonym, weight))
                    seen.add(synonym)
        
        return expanded
    
    def expand_query_string(
        self,
        query: str,
        join_with: str = ' OR '
    ) -> str:
        """
        Expand query and return as string for FTS or search engines.
        
        Args:
            query: Original query
            join_with: String to join expanded terms (e.g., ' OR ', ' | ')
            
        Returns:
            Expanded query string
        """
        expanded = self.expand_query(query)
        
        # Sort by weight (highest first)
        expanded.sort(key=lambda x: x[1], reverse=True)
        
        # Join terms
        terms = [term for term, _ in expanded]
        return join_with.join(terms)
    
    def get_search_variants(self, query: str) -> List[str]:
        """
        Generate search query variants for multi-strategy search.
        
        Creates different query variations optimized for different search methods:
        - Exact phrase
        - Expanded with synonyms
        - Individual keywords
        - Partial matches
        
        Args:
            query: Original query
            
        Returns:
            List of query variants (ordered by specificity)
        """
        variants = []
        
        # 1. Exact phrase (highest priority)
        variants.append(query)
        
        # 2. Expanded with synonyms
        expanded_str = self.expand_query_string(query, join_with=' ')
        if expanded_str != query:
            variants.append(expanded_str)
        
        # 3. Individual keywords
        tokens = self._tokenize(query)
        meaningful = [t for t in tokens if t.lower() not in self.stopwords]
        if meaningful and len(meaningful) > 1:
            variants.append(' '.join(meaningful))
        
        # 4. Partial matches (for fuzzy search)
        if len(query) > 5:
            variants.append(query[:len(query)//2] + '*')  # Prefix match
        
        return variants
    
    def _get_synonyms(
        self,
        term: str,
        context: str | None = None
    ) -> List[str]:
        """
        Get synonyms for a term.
        
        Args:
            term: Term to expand
            context: Optional context for filtering
            
        Returns:
            List of synonyms
        """
        term_lower = term.lower()
        
        # Check direct synonyms
        if term_lower in self.synonyms_dict:
            synonyms = self.synonyms_dict[term_lower].copy()
        else:
            # Check if term is a synonym of something
            if term_lower in self.reverse_index:
                main_terms = self.reverse_index[term_lower]
                # Get synonyms of main term(s)
                synonyms = []
                for main_term in main_terms:
                    if main_term in self.synonyms_dict:
                        synonyms.extend(self.synonyms_dict[main_term])
                # Remove duplicates
                synonyms = list(set(synonyms))
            else:
                # No synonyms found
                return []
        
        # Context-based filtering (if provided)
        if context:
            synonyms = self._filter_by_context(synonyms, context)
        
        return synonyms
    
    def _filter_by_context(
        self,
        synonyms: List[str],
        context: str
    ) -> List[str]:
        """
        Filter synonyms based on context.
        
        Prioritizes synonyms that appear in or are related to the context.
        
        Args:
            synonyms: List of candidate synonyms
            context: Context string (e.g., current directory, recent commands)
            
        Returns:
            Filtered and sorted synonym list
        """
        context_lower = context.lower()
        
        # Score synonyms by context relevance
        scored = []
        for synonym in synonyms:
            score = 0
            
            # Boost if synonym appears in context
            if synonym in context_lower:
                score += 10
            
            # Boost if synonym is related to context keywords
            context_tokens = set(self._tokenize(context_lower))
            if synonym in context_tokens:
                score += 5
            
            scored.append((synonym, score))
        
        # Sort by score (highest first)
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return [synonym for synonym, _ in scored]
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text into words.
        
        Args:
            text: Text to tokenize
            
        Returns:
            List of tokens
        """
        # Split on whitespace and common separators
        tokens = re.findall(r'\b[\w-]+\b', text.lower())
        return tokens
    
    def add_synonyms(
        self,
        term: str,
        synonyms: List[str]
    ) -> None:
        """
        Add custom synonyms at runtime.
        
        Args:
            term: Main term
            synonyms: List of synonyms
        """
        term_lower = term.lower()
        synonyms_lower = [s.lower() for s in synonyms]
        
        if term_lower in self.synonyms_dict:
            # Extend existing
            existing = set(self.synonyms_dict[term_lower])
            existing.update(synonyms_lower)
            self.synonyms_dict[term_lower] = list(existing)
        else:
            # Create new
            self.synonyms_dict[term_lower] = synonyms_lower
        
        # Update reverse index
        for synonym in synonyms_lower:
            if synonym not in self.reverse_index:
                self.reverse_index[synonym] = []
            if term_lower not in self.reverse_index[synonym]:
                self.reverse_index[synonym].append(term_lower)
        
        logger.debug(f"Added synonyms for '{term}': {synonyms}")
    
    def get_expansion_stats(self) -> Dict[str, int]:
        """
        Get statistics about the synonym dictionary.
        
        Returns:
            Dictionary with stats
        """
        total_synonyms = sum(len(syns) for syns in self.synonyms_dict.values())
        avg_synonyms = total_synonyms / len(self.synonyms_dict) if self.synonyms_dict else 0
        
        return {
            'total_terms': len(self.synonyms_dict),
            'total_synonyms': total_synonyms,
            'avg_synonyms_per_term': round(avg_synonyms, 2),
            'reverse_index_size': len(self.reverse_index)
        }

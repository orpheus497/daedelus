"""
Hybrid search implementation combining keyword, semantic, and graph-based search.

Provides:
- Reciprocal Rank Fusion (RRF) algorithm
- Query type detection (factual, procedural, conceptual)
- Adaptive weight tuning based on query type
- Multi-source result combination and re-ranking

Created by: orpheus497
"""

import logging
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class HybridSearch:
    """
    Hybrid search engine combining multiple search strategies.
    
    Combines:
    1. Keyword search (BM25/FTS) - Fast, exact matching
    2. Semantic search (embeddings) - Conceptual similarity
    3. Graph search (NetworkX) - Related content discovery
    
    Uses Reciprocal Rank Fusion (RRF) to merge results with adaptive
    weights based on query type.
    
    Attributes:
        keyword_weight: Weight for keyword search (0.0-1.0)
        semantic_weight: Weight for semantic search (0.0-1.0)
        graph_weight: Weight for graph search (0.0-1.0)
        k: RRF constant (default: 60)
    """
    
    # Query types
    QUERY_FACTUAL = "factual"  # "what is X", "explain Y"
    QUERY_PROCEDURAL = "procedural"  # "how to X", "configure Y"
    QUERY_CONCEPTUAL = "conceptual"  # "understand X", "learn Y"
    QUERY_COMMAND = "command"  # "git commit", "docker build"
    
    # Default weights by query type
    DEFAULT_WEIGHTS = {
        QUERY_FACTUAL: {"keyword": 0.5, "semantic": 0.4, "graph": 0.1},
        QUERY_PROCEDURAL: {"keyword": 0.3, "semantic": 0.3, "graph": 0.4},
        QUERY_CONCEPTUAL: {"keyword": 0.2, "semantic": 0.5, "graph": 0.3},
        QUERY_COMMAND: {"keyword": 0.6, "semantic": 0.3, "graph": 0.1},
    }
    
    def __init__(
        self,
        keyword_weight: float = 0.4,
        semantic_weight: float = 0.4,
        graph_weight: float = 0.2,
        k: int = 60,
        adaptive: bool = True,
    ) -> None:
        """
        Initialize hybrid search engine.
        
        Args:
            keyword_weight: Default weight for keyword search
            semantic_weight: Default weight for semantic search
            graph_weight: Default weight for graph search
            k: RRF constant (higher = less aggressive fusion)
            adaptive: Enable adaptive weight tuning based on query type
        """
        self.keyword_weight = keyword_weight
        self.semantic_weight = semantic_weight
        self.graph_weight = graph_weight
        self.k = k
        self.adaptive = adaptive
        
        # Normalize weights
        self._normalize_weights()
        
        logger.info(
            f"Hybrid search initialized: keyword={self.keyword_weight:.2f}, "
            f"semantic={self.semantic_weight:.2f}, graph={self.graph_weight:.2f}"
        )
    
    def _normalize_weights(self) -> None:
        """Normalize weights to sum to 1.0."""
        total = self.keyword_weight + self.semantic_weight + self.graph_weight
        if total > 0:
            self.keyword_weight /= total
            self.semantic_weight /= total
            self.graph_weight /= total
    
    def detect_query_type(self, query: str) -> str:
        """
        Detect query type from query string.
        
        Args:
            query: Search query
        
        Returns:
            Query type constant
        """
        query_lower = query.lower()
        
        # Factual query patterns
        factual_patterns = [
            r"^what (is|are)",
            r"^explain",
            r"^define",
            r"^meaning of",
            r"^difference between",
        ]
        
        for pattern in factual_patterns:
            if re.search(pattern, query_lower):
                return self.QUERY_FACTUAL
        
        # Procedural query patterns
        procedural_patterns = [
            r"^how to",
            r"^how do i",
            r"^configure",
            r"^setup",
            r"^install",
            r"^create",
            r"^steps to",
        ]
        
        for pattern in procedural_patterns:
            if re.search(pattern, query_lower):
                return self.QUERY_PROCEDURAL
        
        # Conceptual query patterns
        conceptual_patterns = [
            r"^understand",
            r"^learn",
            r"^study",
            r"^overview of",
            r"^introduction to",
        ]
        
        for pattern in conceptual_patterns:
            if re.search(pattern, query_lower):
                return self.QUERY_CONCEPTUAL
        
        # Command query patterns (contains common commands)
        command_keywords = [
            "git", "docker", "npm", "pip", "apt", "yum", "systemctl",
            "ssh", "scp", "rsync", "tar", "grep", "sed", "awk",
        ]
        
        words = query_lower.split()
        if any(cmd in words for cmd in command_keywords):
            return self.QUERY_COMMAND
        
        # Default to factual if no pattern matches
        return self.QUERY_FACTUAL
    
    def get_adaptive_weights(self, query: str) -> Tuple[float, float, float]:
        """
        Get adaptive weights based on query type.
        
        Args:
            query: Search query
        
        Returns:
            Tuple of (keyword_weight, semantic_weight, graph_weight)
        """
        if not self.adaptive:
            return (self.keyword_weight, self.semantic_weight, self.graph_weight)
        
        query_type = self.detect_query_type(query)
        weights = self.DEFAULT_WEIGHTS.get(query_type, {})
        
        keyword_w = weights.get("keyword", self.keyword_weight)
        semantic_w = weights.get("semantic", self.semantic_weight)
        graph_w = weights.get("graph", self.graph_weight)
        
        logger.debug(
            f"Query type: {query_type}, weights: "
            f"keyword={keyword_w:.2f}, semantic={semantic_w:.2f}, graph={graph_w:.2f}"
        )
        
        return (keyword_w, semantic_w, graph_w)
    
    def reciprocal_rank_fusion(
        self,
        result_lists: List[List[Dict[str, Any]]],
        weights: List[float],
    ) -> List[Dict[str, Any]]:
        """
        Merge multiple ranked lists using Reciprocal Rank Fusion.
        
        RRF score for item d:
            score(d) = sum_r( weight_r / (k + rank_r(d)) )
        
        where r iterates over result lists.
        
        Args:
            result_lists: List of ranked result lists
            weights: Weight for each result list
        
        Returns:
            Merged and re-ranked results
        """
        if not result_lists:
            return []
        
        # Ensure weights sum to 1.0
        total_weight = sum(weights)
        if total_weight > 0:
            weights = [w / total_weight for w in weights]
        
        # Calculate RRF scores
        rrf_scores: Dict[str, float] = defaultdict(float)
        result_metadata: Dict[str, Dict[str, Any]] = {}
        
        for result_list, weight in zip(result_lists, weights):
            for rank, result in enumerate(result_list, start=1):
                result_id = result.get("id", str(result))
                
                # RRF formula: weight / (k + rank)
                rrf_score = weight / (self.k + rank)
                rrf_scores[result_id] += rrf_score
                
                # Store result metadata (from first occurrence)
                if result_id not in result_metadata:
                    result_metadata[result_id] = result
        
        # Sort by RRF score (descending)
        sorted_results = sorted(
            rrf_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )
        
        # Build final result list with scores
        merged_results = []
        for result_id, score in sorted_results:
            result = result_metadata.get(result_id, {"id": result_id})
            result["rrf_score"] = score
            merged_results.append(result)
        
        logger.debug(f"RRF merged {len(result_lists)} lists into {len(merged_results)} results")
        
        return merged_results
    
    def hybrid_search(
        self,
        query: str,
        keyword_results: List[Dict[str, Any]],
        semantic_results: List[Dict[str, Any]],
        graph_results: Optional[List[Dict[str, Any]]] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search by combining multiple result sources.
        
        Args:
            query: Search query string
            keyword_results: Results from keyword search (BM25/FTS)
            semantic_results: Results from semantic search (embeddings)
            graph_results: Results from graph traversal (optional)
            top_k: Number of top results to return
        
        Returns:
            Merged and re-ranked results
        """
        # Get adaptive weights
        keyword_w, semantic_w, graph_w = self.get_adaptive_weights(query)
        
        # Prepare result lists
        result_lists = [keyword_results, semantic_results]
        weights = [keyword_w, semantic_w]
        
        # Add graph results if available
        if graph_results and graph_w > 0:
            result_lists.append(graph_results)
            weights.append(graph_w)
        
        # Apply RRF
        merged_results = self.reciprocal_rank_fusion(result_lists, weights)
        
        # Return top K
        return merged_results[:top_k]
    
    def boost_results(
        self,
        results: List[Dict[str, Any]],
        boost_rules: Dict[str, float],
    ) -> List[Dict[str, Any]]:
        """
        Apply boost rules to results.
        
        Args:
            results: List of results with scores
            boost_rules: Dictionary of {field: boost_factor}
        
        Returns:
            Re-ranked results with boosts applied
        """
        boosted_results = []
        
        for result in results:
            score = result.get("rrf_score", result.get("score", 0.0))
            
            # Apply boosts
            for field, boost_factor in boost_rules.items():
                if result.get(field):
                    score *= boost_factor
            
            result["boosted_score"] = score
            boosted_results.append(result)
        
        # Re-sort by boosted score
        boosted_results.sort(key=lambda x: x.get("boosted_score", 0.0), reverse=True)
        
        return boosted_results
    
    def deduplicate_results(
        self,
        results: List[Dict[str, Any]],
        key: str = "id",
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate results, keeping highest scored.
        
        Args:
            results: List of results
            key: Field to use for deduplication
        
        Returns:
            Deduplicated results
        """
        seen = set()
        deduped = []
        
        for result in results:
            result_key = result.get(key)
            if result_key and result_key not in seen:
                seen.add(result_key)
                deduped.append(result)
        
        return deduped
    
    def expand_with_context(
        self,
        results: List[Dict[str, Any]],
        get_context_fn: Any,
        max_expansions: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Expand results with contextual information.
        
        Args:
            results: Original results
            get_context_fn: Function to get context for a result
            max_expansions: Maximum number of context items per result
        
        Returns:
            Results with context metadata
        """
        expanded = []
        
        for result in results:
            result_id = result.get("id")
            if not result_id:
                expanded.append(result)
                continue
            
            # Get context
            try:
                context = get_context_fn(result_id)
                result["context"] = {
                    "ancestors": context.get("ancestors", [])[:max_expansions],
                    "siblings": context.get("siblings", [])[:max_expansions],
                    "children": context.get("children", [])[:max_expansions],
                }
            except Exception as e:
                logger.warning(f"Failed to get context for {result_id}: {e}")
                result["context"] = {}
            
            expanded.append(result)
        
        return expanded
    
    def analyze_query_terms(self, query: str) -> Dict[str, Any]:
        """
        Analyze query to understand intent and important terms.
        
        Args:
            query: Search query
        
        Returns:
            Dictionary with analysis results
        """
        # Tokenize
        tokens = re.findall(r'\b\w+\b', query.lower())
        
        # Common stopwords
        stopwords = {
            "a", "an", "the", "is", "are", "was", "were", "be", "been",
            "being", "have", "has", "had", "do", "does", "did", "will",
            "would", "should", "could", "can", "may", "might", "must",
            "i", "you", "he", "she", "it", "we", "they", "what", "which",
            "who", "when", "where", "why", "how", "to", "of", "in", "on",
            "at", "by", "for", "with", "about", "as", "from",
        }
        
        # Filter stopwords
        content_words = [w for w in tokens if w not in stopwords]
        
        # Detect query intent keywords
        intent_keywords = {
            "install": "action",
            "configure": "action",
            "setup": "action",
            "create": "action",
            "delete": "action",
            "update": "action",
            "fix": "troubleshooting",
            "error": "troubleshooting",
            "problem": "troubleshooting",
            "issue": "troubleshooting",
            "explain": "learning",
            "what": "learning",
            "why": "learning",
            "how": "learning",
            "understand": "learning",
        }
        
        detected_intents = []
        for word in content_words:
            if word in intent_keywords:
                detected_intents.append(intent_keywords[word])
        
        # Count word frequency
        word_freq = Counter(content_words)
        
        return {
            "total_words": len(tokens),
            "content_words": content_words,
            "unique_words": len(set(content_words)),
            "word_frequency": dict(word_freq.most_common(5)),
            "detected_intents": list(set(detected_intents)),
            "query_type": self.detect_query_type(query),
        }
    
    def get_config(self) -> Dict[str, Any]:
        """
        Get current configuration.
        
        Returns:
            Configuration dictionary
        """
        return {
            "keyword_weight": self.keyword_weight,
            "semantic_weight": self.semantic_weight,
            "graph_weight": self.graph_weight,
            "k": self.k,
            "adaptive": self.adaptive,
        }
    
    def update_weights(
        self,
        keyword: Optional[float] = None,
        semantic: Optional[float] = None,
        graph: Optional[float] = None,
    ) -> None:
        """
        Update search weights.
        
        Args:
            keyword: New keyword weight (or None to keep current)
            semantic: New semantic weight (or None to keep current)
            graph: New graph weight (or None to keep current)
        """
        if keyword is not None:
            self.keyword_weight = keyword
        if semantic is not None:
            self.semantic_weight = semantic
        if graph is not None:
            self.graph_weight = graph
        
        self._normalize_weights()
        
        logger.info(
            f"Weights updated: keyword={self.keyword_weight:.2f}, "
            f"semantic={self.semantic_weight:.2f}, graph={self.graph_weight:.2f}"
        )

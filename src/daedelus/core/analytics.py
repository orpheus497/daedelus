"""
Analytics and metrics tracking for Daedelus search quality.

Provides:
- Search query logging and tracking
- Result interaction metrics
- Quality metrics (Precision@K, MRR, etc.)
- Performance metrics (cache hits, latency)
- Aggregation and reporting

Created by: orpheus497
"""

import logging
import sqlite3
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class SearchAnalytics:
    """
    Analytics engine for tracking search quality and performance.
    
    Tracks:
    - Search queries and their results
    - User interactions with results (clicks, executions)
    - Quality metrics (Precision@K, MRR, NDCG)
    - Performance metrics (latency, cache hits)
    - Query reformulation patterns
    
    Attributes:
        conn: SQLite database connection
    """
    
    # Analytics schema (extends main database)
    SCHEMA = """
    -- Search query log
    CREATE TABLE IF NOT EXISTS search_queries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        query TEXT NOT NULL,
        query_type TEXT,  -- keyword, semantic, hybrid
        results_count INTEGER,
        latency_ms REAL,
        cache_hit BOOLEAN DEFAULT 0,
        user_session TEXT,
        context TEXT  -- JSON: cwd, recent commands, etc.
    );
    
    -- Search results and interactions
    CREATE TABLE IF NOT EXISTS search_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        query_id INTEGER NOT NULL,
        rank INTEGER NOT NULL,  -- Position in result list
        result_id TEXT NOT NULL,  -- ID of the result (command, doc chunk, etc.)
        result_type TEXT,  -- command, documentation, example
        score REAL,  -- Relevance score
        clicked BOOLEAN DEFAULT 0,
        executed BOOLEAN DEFAULT 0,
        click_timestamp REAL,
        execution_timestamp REAL,
        FOREIGN KEY (query_id) REFERENCES search_queries(id)
    );
    
    -- Query reformulation tracking
    CREATE TABLE IF NOT EXISTS query_reformulations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        original_query_id INTEGER NOT NULL,
        reformulated_query_id INTEGER NOT NULL,
        time_diff_seconds REAL,
        FOREIGN KEY (original_query_id) REFERENCES search_queries(id),
        FOREIGN KEY (reformulated_query_id) REFERENCES search_queries(id)
    );
    
    -- Cache performance metrics
    CREATE TABLE IF NOT EXISTS cache_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        cache_type TEXT NOT NULL,  -- keyword, semantic, rag
        hit_rate REAL,
        miss_rate REAL,
        eviction_count INTEGER,
        total_size INTEGER,
        avg_latency_ms REAL
    );
    
    -- Indexes for performance
    CREATE INDEX IF NOT EXISTS idx_search_timestamp ON search_queries(timestamp);
    CREATE INDEX IF NOT EXISTS idx_search_type ON search_queries(query_type);
    CREATE INDEX IF NOT EXISTS idx_search_cache ON search_queries(cache_hit);
    CREATE INDEX IF NOT EXISTS idx_result_query ON search_results(query_id);
    CREATE INDEX IF NOT EXISTS idx_result_clicked ON search_results(clicked);
    CREATE INDEX IF NOT EXISTS idx_result_executed ON search_results(executed);
    """
    
    def __init__(self, db_path: Path) -> None:
        """
        Initialize analytics with database connection.
        
        Args:
            db_path: Path to SQLite database
        """
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Connect to database
        self.conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            timeout=30.0,
        )
        self.conn.row_factory = sqlite3.Row
        
        # Initialize schema
        self._init_schema()
        
        logger.info("Search analytics initialized")
    
    def _init_schema(self) -> None:
        """Create analytics tables if they don't exist."""
        try:
            self.conn.executescript(self.SCHEMA)
            self.conn.commit()
            logger.debug("Analytics schema initialized")
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize analytics schema: {e}")
            raise
    
    def log_search(
        self,
        query: str,
        query_type: str,
        results: List[Dict[str, Any]],
        latency_ms: float,
        cache_hit: bool = False,
        user_session: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Log a search query and its results.
        
        Args:
            query: Search query string
            query_type: Type of search (keyword, semantic, hybrid)
            results: List of result dictionaries
            latency_ms: Query latency in milliseconds
            cache_hit: Whether this was a cache hit
            user_session: User session identifier
            context: Additional context (cwd, recent commands, etc.)
        
        Returns:
            Query ID for tracking
        """
        import json
        
        timestamp = time.time()
        context_json = json.dumps(context) if context else None
        
        cursor = self.conn.execute(
            """
            INSERT INTO search_queries 
            (timestamp, query, query_type, results_count, latency_ms, 
             cache_hit, user_session, context)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                query,
                query_type,
                len(results),
                latency_ms,
                cache_hit,
                user_session,
                context_json,
            ),
        )
        
        query_id = cursor.lastrowid
        
        # Log each result
        for rank, result in enumerate(results, start=1):
            self.conn.execute(
                """
                INSERT INTO search_results
                (query_id, rank, result_id, result_type, score)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    query_id,
                    rank,
                    result.get("id", f"result_{rank}"),
                    result.get("type", "unknown"),
                    result.get("score", 0.0),
                ),
            )
        
        self.conn.commit()
        logger.debug(f"Logged search query: {query} ({len(results)} results)")
        
        return query_id
    
    def track_result_click(self, query_id: int, result_rank: int) -> None:
        """
        Track when a user clicks on a search result.
        
        Args:
            query_id: ID of the search query
            result_rank: Position of the result in the list (1-based)
        """
        timestamp = time.time()
        
        self.conn.execute(
            """
            UPDATE search_results
            SET clicked = 1, click_timestamp = ?
            WHERE query_id = ? AND rank = ?
            """,
            (timestamp, query_id, result_rank),
        )
        
        self.conn.commit()
        logger.debug(f"Tracked click: query={query_id}, rank={result_rank}")
    
    def track_result_execution(self, query_id: int, result_rank: int) -> None:
        """
        Track when a user executes a command from search results.
        
        Args:
            query_id: ID of the search query
            result_rank: Position of the result in the list (1-based)
        """
        timestamp = time.time()
        
        self.conn.execute(
            """
            UPDATE search_results
            SET executed = 1, execution_timestamp = ?
            WHERE query_id = ? AND rank = ?
            """,
            (timestamp, query_id, result_rank),
        )
        
        self.conn.commit()
        logger.debug(f"Tracked execution: query={query_id}, rank={result_rank}")
    
    def track_reformulation(
        self, original_query_id: int, reformulated_query_id: int
    ) -> None:
        """
        Track when a user reformulates a query.
        
        Args:
            original_query_id: ID of original query
            reformulated_query_id: ID of reformulated query
        """
        # Calculate time difference
        cursor = self.conn.execute(
            """
            SELECT 
                q1.timestamp as t1,
                q2.timestamp as t2
            FROM search_queries q1, search_queries q2
            WHERE q1.id = ? AND q2.id = ?
            """,
            (original_query_id, reformulated_query_id),
        )
        
        row = cursor.fetchone()
        if row:
            time_diff = row["t2"] - row["t1"]
            
            self.conn.execute(
                """
                INSERT INTO query_reformulations
                (original_query_id, reformulated_query_id, time_diff_seconds)
                VALUES (?, ?, ?)
                """,
                (original_query_id, reformulated_query_id, time_diff),
            )
            
            self.conn.commit()
            logger.debug(f"Tracked reformulation: {original_query_id} → {reformulated_query_id}")
    
    def log_cache_metrics(
        self,
        cache_type: str,
        hit_rate: float,
        miss_rate: float,
        eviction_count: int,
        total_size: int,
        avg_latency_ms: float,
    ) -> None:
        """
        Log cache performance metrics.
        
        Args:
            cache_type: Type of cache (keyword, semantic, rag)
            hit_rate: Cache hit rate (0.0-1.0)
            miss_rate: Cache miss rate (0.0-1.0)
            eviction_count: Number of evictions
            total_size: Current cache size
            avg_latency_ms: Average latency for cached queries
        """
        timestamp = time.time()
        
        self.conn.execute(
            """
            INSERT INTO cache_metrics
            (timestamp, cache_type, hit_rate, miss_rate, eviction_count,
             total_size, avg_latency_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                cache_type,
                hit_rate,
                miss_rate,
                eviction_count,
                total_size,
                avg_latency_ms,
            ),
        )
        
        self.conn.commit()
    
    def calculate_precision_at_k(self, k: int = 5, days: int = 7) -> float:
        """
        Calculate Precision@K for recent queries.
        
        Precision@K = (# relevant results in top K) / K
        We consider a result "relevant" if it was clicked or executed.
        
        Args:
            k: Number of top results to consider
            days: Number of days to look back
        
        Returns:
            Average Precision@K across all queries
        """
        since_timestamp = time.time() - (days * 86400)
        
        cursor = self.conn.execute(
            """
            SELECT 
                q.id,
                COUNT(CASE WHEN r.rank <= ? AND (r.clicked = 1 OR r.executed = 1) 
                      THEN 1 END) as relevant_in_k
            FROM search_queries q
            LEFT JOIN search_results r ON q.id = r.query_id
            WHERE q.timestamp >= ?
            GROUP BY q.id
            HAVING COUNT(r.id) >= ?
            """,
            (k, since_timestamp, k),
        )
        
        precisions = []
        for row in cursor.fetchall():
            precision = row["relevant_in_k"] / k
            precisions.append(precision)
        
        if precisions:
            avg_precision = sum(precisions) / len(precisions)
            logger.debug(f"Precision@{k} (last {days} days): {avg_precision:.3f}")
            return avg_precision
        
        return 0.0
    
    def calculate_mrr(self, days: int = 7) -> float:
        """
        Calculate Mean Reciprocal Rank for recent queries.
        
        MRR = Average of (1 / rank of first relevant result)
        
        Args:
            days: Number of days to look back
        
        Returns:
            Mean Reciprocal Rank
        """
        since_timestamp = time.time() - (days * 86400)
        
        cursor = self.conn.execute(
            """
            SELECT 
                q.id,
                MIN(r.rank) as first_relevant_rank
            FROM search_queries q
            JOIN search_results r ON q.id = r.query_id
            WHERE q.timestamp >= ?
              AND (r.clicked = 1 OR r.executed = 1)
            GROUP BY q.id
            """,
            (since_timestamp,),
        )
        
        reciprocal_ranks = []
        for row in cursor.fetchall():
            rr = 1.0 / row["first_relevant_rank"]
            reciprocal_ranks.append(rr)
        
        if reciprocal_ranks:
            mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)
            logger.debug(f"MRR (last {days} days): {mrr:.3f}")
            return mrr
        
        return 0.0
    
    def get_top_queries(self, limit: int = 10, days: int = 7) -> List[Tuple[str, int]]:
        """
        Get most frequent queries.
        
        Args:
            limit: Number of queries to return
            days: Number of days to look back
        
        Returns:
            List of (query, count) tuples
        """
        since_timestamp = time.time() - (days * 86400)
        
        cursor = self.conn.execute(
            """
            SELECT query, COUNT(*) as count
            FROM search_queries
            WHERE timestamp >= ?
            GROUP BY query
            ORDER BY count DESC
            LIMIT ?
            """,
            (since_timestamp, limit),
        )
        
        return [(row["query"], row["count"]) for row in cursor.fetchall()]
    
    def get_worst_queries(self, limit: int = 10, days: int = 7) -> List[Tuple[str, float]]:
        """
        Get queries with poorest results (no clicks/executions).
        
        Args:
            limit: Number of queries to return
            days: Number of days to look back
        
        Returns:
            List of (query, results_count) tuples with 0 interactions
        """
        since_timestamp = time.time() - (days * 86400)
        
        cursor = self.conn.execute(
            """
            SELECT 
                q.query,
                q.results_count,
                COUNT(r.id) as total_results,
                SUM(CASE WHEN r.clicked = 1 OR r.executed = 1 THEN 1 ELSE 0 END) as interactions
            FROM search_queries q
            LEFT JOIN search_results r ON q.id = r.query_id
            WHERE q.timestamp >= ?
            GROUP BY q.id
            HAVING interactions = 0 AND total_results > 0
            ORDER BY q.results_count DESC
            LIMIT ?
            """,
            (since_timestamp, limit),
        )
        
        return [(row["query"], row["results_count"]) for row in cursor.fetchall()]
    
    def get_cache_stats(self, cache_type: Optional[str] = None, days: int = 7) -> Dict[str, Any]:
        """
        Get cache performance statistics.
        
        Args:
            cache_type: Specific cache type (or None for all)
            days: Number of days to look back
        
        Returns:
            Dictionary of cache statistics
        """
        since_timestamp = time.time() - (days * 86400)
        
        if cache_type:
            cursor = self.conn.execute(
                """
                SELECT 
                    AVG(hit_rate) as avg_hit_rate,
                    AVG(miss_rate) as avg_miss_rate,
                    MAX(total_size) as max_size,
                    AVG(avg_latency_ms) as avg_latency
                FROM cache_metrics
                WHERE cache_type = ? AND timestamp >= ?
                """,
                (cache_type, since_timestamp),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT 
                    cache_type,
                    AVG(hit_rate) as avg_hit_rate,
                    AVG(miss_rate) as avg_miss_rate,
                    MAX(total_size) as max_size,
                    AVG(avg_latency_ms) as avg_latency
                FROM cache_metrics
                WHERE timestamp >= ?
                GROUP BY cache_type
                """,
                (since_timestamp,),
            )
        
        if cache_type:
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {}
        else:
            results = {}
            for row in cursor.fetchall():
                results[row["cache_type"]] = dict(row)
            return results
    
    def get_summary_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Get comprehensive summary statistics.
        
        Args:
            days: Number of days to look back
        
        Returns:
            Dictionary of summary statistics
        """
        since_timestamp = time.time() - (days * 86400)
        
        # Query stats
        cursor = self.conn.execute(
            """
            SELECT 
                COUNT(*) as total_queries,
                AVG(results_count) as avg_results,
                AVG(latency_ms) as avg_latency,
                SUM(cache_hit) * 100.0 / COUNT(*) as cache_hit_rate
            FROM search_queries
            WHERE timestamp >= ?
            """,
            (since_timestamp,),
        )
        
        query_stats = dict(cursor.fetchone())
        
        # Result interaction stats
        cursor = self.conn.execute(
            """
            SELECT 
                COUNT(*) as total_results,
                SUM(clicked) as clicked_results,
                SUM(executed) as executed_results
            FROM search_results r
            JOIN search_queries q ON r.query_id = q.id
            WHERE q.timestamp >= ?
            """,
            (since_timestamp,),
        )
        
        result_stats = dict(cursor.fetchone())
        
        # Quality metrics
        precision_5 = self.calculate_precision_at_k(k=5, days=days)
        mrr = self.calculate_mrr(days=days)
        
        return {
            "period_days": days,
            "query_stats": query_stats,
            "result_stats": result_stats,
            "quality_metrics": {
                "precision_at_5": precision_5,
                "mrr": mrr,
            },
        }
    
    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.debug("Analytics database connection closed")

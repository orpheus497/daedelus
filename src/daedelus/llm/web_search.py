"""
Web search functionality with AI summarization.

Provides web search capabilities with intelligent summarization using LLM.
"""

import logging
from typing import Any

import requests

from daedelus.llm.llm_manager import LLMManager

logger = logging.getLogger(__name__)


class WebSearcher:
    """Handles web searches and AI-powered summarization."""

    def __init__(self, llm_manager: LLMManager):
        """
        Initialize web searcher.

        Args:
            llm_manager: LLM manager instance for summarization
        """
        self.llm = llm_manager
        self.timeout = 10

    def search(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """
        Search the web using DuckDuckGo API.

        Args:
            query: Search query string
            max_results: Maximum number of results to return

        Returns:
            List of search result dictionaries

        Raises:
            requests.RequestException: If web search fails
        """
        logger.info(f"Searching web for: {query}")

        # Use DuckDuckGo Instant Answer API (no API key required)
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        }

        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()

        results = []

        # Add abstract if available
        if data.get("Abstract"):
            results.append(
                {
                    "title": data.get("Heading", "Summary"),
                    "text": data["Abstract"],
                    "url": data.get("AbstractURL", ""),
                }
            )

        # Add related topics
        if data.get("RelatedTopics"):
            for topic in data["RelatedTopics"][:max_results]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append(
                        {
                            "title": topic.get("FirstURL", "").split("/")[-1],
                            "text": topic["Text"],
                            "url": topic.get("FirstURL", ""),
                        }
                    )

        logger.info(f"Found {len(results)} web results")
        return results[:max_results]

    def summarize_results(
        self, query: str, results: list[dict[str, Any]], detailed: bool = False
    ) -> str:
        """
        Summarize search results using LLM.

        Args:
            query: Original search query
            results: List of search result dictionaries
            detailed: Whether to provide detailed summary

        Returns:
            AI-generated summary of search results
        """
        if not results:
            # No results - use LLM's base knowledge (with Phi-3 chat format)
            prompt = f"""<|system|>
You are a helpful assistant. Answer questions clearly and accurately based on your knowledge.<|end|>
<|user|>
{query}<|end|>
<|assistant|>
"""

            return self.llm.generate(
                prompt, max_tokens=300, temperature=0.3, stop=["<|end|>", "<|user|>"]
            )

        # Build results context
        results_text = ""
        for i, result in enumerate(results, 1):
            results_text += f"\n{i}. {result.get('title', 'Result')}\n"
            results_text += f"   {result.get('text', '')}\n"
            if result.get("url"):
                results_text += f"   Source: {result['url']}\n"

        # Create summarization prompt
        if detailed:
            max_tokens = 600
            instruction = "Provide a comprehensive and detailed summary in 3-4 paragraphs"
        else:
            max_tokens = 400
            instruction = "Provide a clear and concise summary in 2-3 paragraphs"

        # Format in Phi-3 chat format
        prompt = f"""<|system|>
You are a helpful assistant that summarizes web search results clearly and accurately.<|end|>
<|user|>
Based on the following web search results, provide an informative summary.

Query: {query}

Search Results:{results_text}

{instruction}:<|end|>
<|assistant|>
"""

        summary = self.llm.generate(
            prompt, max_tokens=max_tokens, temperature=0.3, stop=["<|end|>", "<|user|>"]
        )

        logger.info("Generated summary from search results")
        return summary

    def search_and_summarize(
        self, query: str, max_results: int = 5, detailed: bool = False
    ) -> dict[str, Any]:
        """
        Perform web search and return AI-summarized results.

        Args:
            query: Search query
            max_results: Maximum number of search results
            detailed: Whether to provide detailed summary

        Returns:
            Dictionary with 'summary', 'results', and 'sources'
        """
        # Perform search
        try:
            results = self.search(query, max_results)
        except requests.RequestException as e:
            logger.warning(f"Web search failed: {e}, using LLM knowledge only")
            results = []

        # Generate summary
        summary = self.summarize_results(query, results, detailed)

        # Extract sources
        sources = [r.get("url") for r in results if r.get("url")]

        return {"summary": summary, "results": results, "sources": sources, "query": query}

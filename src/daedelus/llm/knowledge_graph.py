"""
Knowledge graph structure for Daedelus Redbook documentation.

Provides:
- Graph-based representation of knowledge base
- Chapter/section hierarchy
- Command-to-concept relationships
- Graph traversal for related content discovery
- NetworkX integration for efficient queries

Created by: orpheus497
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import networkx as nx
except ImportError:
    nx = None
    logging.warning("NetworkX not installed. Knowledge graph features disabled.")

logger = logging.getLogger(__name__)


class KnowledgeGraph:
    """
    Graph-based knowledge representation for documentation.
    
    Builds a directed graph where:
    - Nodes represent chapters, sections, commands, concepts
    - Edges represent relationships (contains, related_to, prerequisite, etc.)
    
    Enables:
    - Hierarchical traversal (parent/child sections)
    - Related content discovery
    - Command-to-documentation linking
    - Contextual result expansion
    
    Attributes:
        graph: NetworkX DiGraph instance
    """
    
    # Node types
    NODE_CHAPTER = "chapter"
    NODE_SECTION = "section"
    NODE_COMMAND = "command"
    NODE_CONCEPT = "concept"
    NODE_EXAMPLE = "example"
    
    # Edge types
    EDGE_CONTAINS = "contains"
    EDGE_RELATED = "related_to"
    EDGE_PREREQUISITE = "prerequisite"
    EDGE_DEMONSTRATES = "demonstrates"
    EDGE_REFERENCES = "references"
    
    def __init__(self) -> None:
        """Initialize empty knowledge graph."""
        if nx is None:
            raise ImportError(
                "NetworkX is required for knowledge graph. "
                "Install with: pip install networkx"
            )
        
        self.graph = nx.DiGraph()
        logger.info("Knowledge graph initialized")
    
    def add_chapter(
        self,
        chapter_id: str,
        title: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a chapter node to the graph.
        
        Args:
            chapter_id: Unique identifier for the chapter
            title: Chapter title
            metadata: Additional metadata (file_path, topics, etc.)
        """
        self.graph.add_node(
            chapter_id,
            type=self.NODE_CHAPTER,
            title=title,
            **(metadata or {}),
        )
        logger.debug(f"Added chapter: {title}")
    
    def add_section(
        self,
        section_id: str,
        title: str,
        chapter_id: str,
        parent_section_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a section node and link to parent.
        
        Args:
            section_id: Unique identifier for the section
            title: Section title
            chapter_id: Parent chapter ID
            parent_section_id: Parent section ID (for nested sections)
            metadata: Additional metadata (content, level, etc.)
        """
        self.graph.add_node(
            section_id,
            type=self.NODE_SECTION,
            title=title,
            chapter_id=chapter_id,
            **(metadata or {}),
        )
        
        # Link to parent chapter or section
        parent_id = parent_section_id if parent_section_id else chapter_id
        self.graph.add_edge(parent_id, section_id, type=self.EDGE_CONTAINS)
        
        logger.debug(f"Added section: {title} (parent: {parent_id})")
    
    def add_command(
        self,
        command: str,
        description: str,
        related_sections: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a command node and link to related sections.
        
        Args:
            command: Command name (e.g., 'git', 'docker')
            description: Brief description
            related_sections: List of section IDs where this command appears
            metadata: Additional metadata (flags, examples, etc.)
        """
        command_id = f"cmd:{command}"
        
        self.graph.add_node(
            command_id,
            type=self.NODE_COMMAND,
            command=command,
            description=description,
            **(metadata or {}),
        )
        
        # Link to related sections
        for section_id in related_sections:
            if self.graph.has_node(section_id):
                self.graph.add_edge(section_id, command_id, type=self.EDGE_DEMONSTRATES)
        
        logger.debug(f"Added command: {command} ({len(related_sections)} sections)")
    
    def add_concept(
        self,
        concept_id: str,
        name: str,
        related_sections: List[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a concept node and link to related sections.
        
        Args:
            concept_id: Unique concept identifier
            name: Concept name (e.g., 'permissions', 'networking')
            related_sections: List of section IDs covering this concept
            metadata: Additional metadata (definition, keywords, etc.)
        """
        self.graph.add_node(
            concept_id,
            type=self.NODE_CONCEPT,
            name=name,
            **(metadata or {}),
        )
        
        # Link to related sections
        for section_id in related_sections:
            if self.graph.has_node(section_id):
                self.graph.add_edge(section_id, concept_id, type=self.EDGE_DEMONSTRATES)
        
        logger.debug(f"Added concept: {name} ({len(related_sections)} sections)")
    
    def add_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Add a relationship between two nodes.
        
        Args:
            source_id: Source node ID
            target_id: Target node ID
            rel_type: Relationship type (EDGE_* constant)
            metadata: Additional edge metadata
        """
        if not self.graph.has_node(source_id):
            logger.warning(f"Source node not found: {source_id}")
            return
        
        if not self.graph.has_node(target_id):
            logger.warning(f"Target node not found: {target_id}")
            return
        
        self.graph.add_edge(source_id, target_id, type=rel_type, **(metadata or {}))
        logger.debug(f"Added edge: {source_id} -{rel_type}-> {target_id}")
    
    def find_related_content(
        self,
        node_id: str,
        max_depth: int = 2,
        rel_types: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find content related to a given node via graph traversal.
        
        Args:
            node_id: Starting node ID
            max_depth: Maximum traversal depth (1-3 recommended)
            rel_types: Relationship types to follow (None = all)
        
        Returns:
            List of related nodes with metadata and distance
        """
        if not self.graph.has_node(node_id):
            logger.warning(f"Node not found: {node_id}")
            return []
        
        related = []
        visited = {node_id}
        
        # BFS traversal with depth tracking
        queue = [(node_id, 0)]  # (node, depth)
        
        while queue:
            current_node, depth = queue.pop(0)
            
            if depth >= max_depth:
                continue
            
            # Get outgoing edges
            for neighbor in self.graph.successors(current_node):
                if neighbor in visited:
                    continue
                
                edge_data = self.graph.get_edge_data(current_node, neighbor)
                edge_type = edge_data.get("type", "unknown")
                
                # Filter by relationship type if specified
                if rel_types and edge_type not in rel_types:
                    continue
                
                # Add to results
                node_data = self.graph.nodes[neighbor]
                related.append(
                    {
                        "id": neighbor,
                        "distance": depth + 1,
                        "rel_type": edge_type,
                        "node_type": node_data.get("type", "unknown"),
                        "title": node_data.get("title", node_data.get("name", neighbor)),
                        "metadata": node_data,
                    }
                )
                
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))
        
        # Sort by distance (closest first)
        related.sort(key=lambda x: x["distance"])
        
        logger.debug(f"Found {len(related)} related nodes for {node_id}")
        return related
    
    def get_node_context(self, node_id: str) -> Dict[str, Any]:
        """
        Get full context for a node (ancestors, siblings, children).
        
        Args:
            node_id: Node ID to get context for
        
        Returns:
            Dictionary with ancestors, siblings, children
        """
        if not self.graph.has_node(node_id):
            return {}
        
        # Get ancestors (parent chapters/sections)
        ancestors = []
        current = node_id
        while True:
            parents = list(self.graph.predecessors(current))
            if not parents:
                break
            
            parent = parents[0]  # Assume single parent for hierarchy
            parent_data = self.graph.nodes[parent]
            ancestors.append(
                {
                    "id": parent,
                    "type": parent_data.get("type"),
                    "title": parent_data.get("title", parent_data.get("name", parent)),
                }
            )
            current = parent
        
        # Get siblings (nodes with same parent)
        siblings = []
        parents = list(self.graph.predecessors(node_id))
        if parents:
            parent = parents[0]
            for sibling in self.graph.successors(parent):
                if sibling != node_id:
                    sibling_data = self.graph.nodes[sibling]
                    siblings.append(
                        {
                            "id": sibling,
                            "type": sibling_data.get("type"),
                            "title": sibling_data.get("title", sibling_data.get("name", sibling)),
                        }
                    )
        
        # Get children
        children = []
        for child in self.graph.successors(node_id):
            child_data = self.graph.nodes[child]
            children.append(
                {
                    "id": child,
                    "type": child_data.get("type"),
                    "title": child_data.get("title", child_data.get("name", child)),
                }
            )
        
        return {
            "ancestors": ancestors[::-1],  # Root to immediate parent
            "siblings": siblings,
            "children": children,
        }
    
    def find_shortest_path(self, source_id: str, target_id: str) -> List[str]:
        """
        Find shortest path between two nodes.
        
        Args:
            source_id: Source node ID
            target_id: Target node ID
        
        Returns:
            List of node IDs forming the path
        """
        try:
            path = nx.shortest_path(self.graph, source_id, target_id)
            return path
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []
    
    def get_centrality(self, top_n: int = 10) -> List[Tuple[str, float]]:
        """
        Get most central/important nodes by PageRank.
        
        Args:
            top_n: Number of top nodes to return
        
        Returns:
            List of (node_id, centrality_score) tuples
        """
        try:
            pagerank = nx.pagerank(self.graph)
            sorted_nodes = sorted(pagerank.items(), key=lambda x: x[1], reverse=True)
            return sorted_nodes[:top_n]
        except Exception as e:
            logger.error(f"Failed to calculate centrality: {e}")
            return []
    
    def build_from_redbook(self, redbook_path: Path) -> None:
        """
        Build knowledge graph from Redbook markdown files.
        
        Args:
            redbook_path: Path to Redbook directory
        """
        redbook_path = Path(redbook_path)
        if not redbook_path.exists():
            logger.error(f"Redbook path not found: {redbook_path}")
            return
        
        # Pattern to extract headings
        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        command_pattern = re.compile(r"`([a-z0-9_-]+)`", re.IGNORECASE)
        
        # Process each markdown file
        for md_file in redbook_path.glob("**/*.md"):
            chapter_id = md_file.stem
            
            try:
                content = md_file.read_text()
                
                # Extract chapter title (first # heading)
                first_heading = heading_pattern.search(content)
                if not first_heading:
                    continue
                
                chapter_title = first_heading.group(2).strip()
                
                # Add chapter node
                self.add_chapter(
                    chapter_id,
                    chapter_title,
                    metadata={"file_path": str(md_file)},
                )
                
                # Extract sections and subsections
                previous_section = None
                section_stack = [(chapter_id, 0)]  # (id, level)
                
                for match in heading_pattern.finditer(content):
                    level = len(match.group(1))  # Number of #
                    title = match.group(2).strip()
                    
                    if level == 1:  # Chapter heading, already added
                        continue
                    
                    # Create section ID
                    section_id = f"{chapter_id}:{title.lower().replace(' ', '_')}"
                    
                    # Find parent section (closest lower level)
                    while section_stack and section_stack[-1][1] >= level:
                        section_stack.pop()
                    
                    parent_id = section_stack[-1][0] if section_stack else chapter_id
                    parent_section_id = parent_id if parent_id != chapter_id else None
                    
                    # Add section
                    self.add_section(
                        section_id,
                        title,
                        chapter_id,
                        parent_section_id=parent_section_id,
                        metadata={"level": level},
                    )
                    
                    section_stack.append((section_id, level))
                    previous_section = section_id
                
                # Extract commands mentioned in this chapter
                commands = set(command_pattern.findall(content))
                
                # Common shell commands to extract
                for cmd in commands:
                    if len(cmd) <= 2:  # Skip single letters
                        continue
                    
                    if previous_section:
                        self.add_command(
                            cmd,
                            f"Command from {chapter_title}",
                            [previous_section],
                        )
                
                logger.debug(f"Processed chapter: {chapter_title}")
                
            except Exception as e:
                logger.error(f"Failed to process {md_file}: {e}")
                continue
        
        logger.info(
            f"Knowledge graph built: {self.graph.number_of_nodes()} nodes, "
            f"{self.graph.number_of_edges()} edges"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get graph statistics.
        
        Returns:
            Dictionary with node/edge counts by type
        """
        stats = {
            "total_nodes": self.graph.number_of_nodes(),
            "total_edges": self.graph.number_of_edges(),
            "nodes_by_type": {},
            "edges_by_type": {},
        }
        
        # Count nodes by type
        for node, data in self.graph.nodes(data=True):
            node_type = data.get("type", "unknown")
            stats["nodes_by_type"][node_type] = stats["nodes_by_type"].get(node_type, 0) + 1
        
        # Count edges by type
        for source, target, data in self.graph.edges(data=True):
            edge_type = data.get("type", "unknown")
            stats["edges_by_type"][edge_type] = stats["edges_by_type"].get(edge_type, 0) + 1
        
        return stats
    
    def save_graph(self, output_path: Path) -> None:
        """
        Save graph to file (GraphML format).
        
        Args:
            output_path: Path to save graph
        """
        try:
            nx.write_graphml(self.graph, output_path)
            logger.info(f"Knowledge graph saved to {output_path}")
        except Exception as e:
            logger.error(f"Failed to save graph: {e}")
    
    def load_graph(self, input_path: Path) -> None:
        """
        Load graph from file.
        
        Args:
            input_path: Path to load graph from
        """
        try:
            self.graph = nx.read_graphml(input_path)
            logger.info(f"Knowledge graph loaded from {input_path}")
        except Exception as e:
            logger.error(f"Failed to load graph: {e}")

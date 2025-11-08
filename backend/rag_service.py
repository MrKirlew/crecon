"""
RAG Service - Retrieval Augmented Generation with Qdrant
Provides semantic search over user's executive knowledge base
Indexes documents, emails, and conversation history
"""
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchParams
)
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
from datetime import datetime
import logging
from config import settings

logger = logging.getLogger(__name__)


class RAGService:
    """
    Retrieval Augmented Generation service using Qdrant vector database
    Handles embedding, indexing, and semantic search
    """

    def __init__(self):
        # Initialize Qdrant client
        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port
        )

        # Initialize embedding model
        logger.info(f"Loading embedding model: {settings.embedding_model}")
        self.embedding_model = SentenceTransformer(settings.embedding_model)

        # Collection name
        self.collection_name = settings.qdrant_collection_name

        # Ensure collection exists
        self._ensure_collection_exists()

    def _ensure_collection_exists(self):
        """Create collection if it doesn't exist"""
        try:
            self.client.get_collection(self.collection_name)
            logger.info(f"Collection '{self.collection_name}' already exists")
        except Exception:
            logger.info(f"Creating collection '{self.collection_name}'")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=settings.embedding_dimension,
                    distance=Distance.COSINE
                )
            )

    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding vector for text

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        embedding = self.embedding_model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def index_document(
        self,
        document_id: str,
        text: str,
        metadata: Optional[Dict] = None
    ) -> bool:
        """
        Index a document for RAG retrieval

        Args:
            document_id: Unique identifier for the document
            text: Document content
            metadata: Additional metadata (source, date, type, etc.)

        Returns:
            True if successful
        """
        try:
            # Generate embedding
            embedding = self.embed_text(text)

            # Prepare metadata
            payload = {
                "text": text,
                "indexed_at": datetime.utcnow().isoformat(),
                **(metadata or {})
            }

            # Create point
            point = PointStruct(
                id=hash(document_id) % (10 ** 8),  # Convert string ID to integer
                vector=embedding,
                payload=payload
            )

            # Upsert to collection
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )

            logger.info(f"Indexed document: {document_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to index document {document_id}: {e}")
            return False

    def index_documents_batch(
        self,
        documents: List[Dict[str, any]]
    ) -> int:
        """
        Index multiple documents in batch

        Args:
            documents: List of dicts with 'id', 'text', and optional 'metadata'

        Returns:
            Number of successfully indexed documents
        """
        points = []

        for doc in documents:
            try:
                embedding = self.embed_text(doc['text'])

                payload = {
                    "text": doc['text'],
                    "indexed_at": datetime.utcnow().isoformat(),
                    **(doc.get('metadata', {}))
                }

                point = PointStruct(
                    id=hash(doc['id']) % (10 ** 8),
                    vector=embedding,
                    payload=payload
                )

                points.append(point)

            except Exception as e:
                logger.error(f"Failed to prepare document {doc.get('id')}: {e}")
                continue

        if points:
            try:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                logger.info(f"Batch indexed {len(points)} documents")
                return len(points)
            except Exception as e:
                logger.error(f"Failed to batch index documents: {e}")
                return 0

        return 0

    def search(
        self,
        query: str,
        top_k: int = None,
        score_threshold: float = None,
        filters: Optional[Dict] = None
    ) -> List[Dict]:
        """
        Semantic search for relevant context

        Args:
            query: Search query
            top_k: Number of results to return (default from settings)
            score_threshold: Minimum similarity score (default from settings)
            filters: Optional metadata filters (e.g., {"source": "gmail"})

        Returns:
            List of search results with text and metadata
        """
        top_k = top_k or settings.rag_top_k
        score_threshold = score_threshold or settings.rag_score_threshold

        try:
            # Generate query embedding
            query_embedding = self.embed_text(query)

            # Prepare filter if provided
            filter_obj = None
            if filters:
                conditions = [
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                    for key, value in filters.items()
                ]
                filter_obj = Filter(must=conditions) if conditions else None

            # Search
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k,
                score_threshold=score_threshold,
                query_filter=filter_obj
            )

            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "text": result.payload.get("text", ""),
                    "score": result.score,
                    "metadata": {
                        k: v for k, v in result.payload.items()
                        if k not in ["text", "indexed_at"]
                    },
                    "indexed_at": result.payload.get("indexed_at")
                })

            logger.info(f"Found {len(formatted_results)} results for query")
            return formatted_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    def get_rag_context(
        self,
        query: str,
        top_k: int = None,
        filters: Optional[Dict] = None
    ) -> str:
        """
        Get formatted RAG context string for LLM prompt

        Args:
            query: Search query
            top_k: Number of results
            filters: Optional metadata filters

        Returns:
            Formatted context string
        """
        results = self.search(query, top_k=top_k, filters=filters)

        if not results:
            return ""

        # Format context
        context_parts = [
            "# Relevant Context from Knowledge Base\n"
        ]

        for i, result in enumerate(results, 1):
            source = result['metadata'].get('source', 'Unknown')
            context_parts.append(
                f"\n## Context {i} (Source: {source}, Relevance: {result['score']:.2f})\n"
                f"{result['text']}\n"
            )

        return "\n".join(context_parts)

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document from the index

        Args:
            document_id: Document ID to delete

        Returns:
            True if successful
        """
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=[hash(document_id) % (10 ** 8)]
            )
            logger.info(f"Deleted document: {document_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete document {document_id}: {e}")
            return False

    def get_collection_stats(self) -> Dict:
        """
        Get statistics about the collection

        Returns:
            Dict with collection stats
        """
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                "total_points": collection_info.points_count,
                "vectors_config": str(collection_info.config.params.vectors),
                "status": collection_info.status
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}


# Global RAG service instance
rag_service = None


def get_rag_service() -> RAGService:
    """Dependency injection for FastAPI routes"""
    global rag_service
    if rag_service is None:
        rag_service = RAGService()
    return rag_service

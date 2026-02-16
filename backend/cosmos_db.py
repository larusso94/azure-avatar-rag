"""Cosmos DB client for Avatar RAG system."""
import time
import uuid
from typing import List, Dict, Any, Optional
from .config import config
from .logger import log_info, log_error, log_warning, log_debug

try:
    from azure.cosmos import CosmosClient, PartitionKey
    from azure.cosmos.partition_key import PartitionKey
    HAS_COSMOS = True
except ImportError:
    HAS_COSMOS = False

class CosmosDBClient:
    """Cosmos DB client for storing document chunks and embeddings."""
    
    def __init__(self):
        self.endpoint = config.cosmos_endpoint
        self.key = config.cosmos_key
        self.database_name = config.cosmos_database
        self.container_name = config.cosmos_container
        
        self.client = None
        self.database = None
        self.container = None
        self.connected = False
        self.document_count = 0  # Track document count for optimization
        
        self._connect()
    
    def _connect(self):
        """Connect to Cosmos DB."""
        if not HAS_COSMOS:
            log_error("azure-cosmos package not installed")
            return
        
        if not self.endpoint or not self.key:
            log_warning("Cosmos DB credentials missing")
            return
        
        try:
            self.client = CosmosClient(self.endpoint, credential=self.key)
            
            # Create database if not exists
            self.database = self.client.create_database_if_not_exists(
                id=self.database_name
            )
            
            # Get existing container (don't create)
            try:
                self.container = self.database.get_container_client(self.container_name)
                # Verify container exists by reading its properties
                self.container.read()
                log_info(f"Container '{self.container_name}' found and accessible")
            except Exception as get_error:
                # Container doesn't exist - raise error instead of creating
                log_error(f"Container '{self.container_name}' not found in database '{self.database_name}'")
                log_error(f"Error details: {str(get_error)}")
                log_error(f"Please create the container manually in Azure Portal with vector policies:")
                log_error(f"  - Partition key: /id")
                log_error(f"  - Vector embedding path: /embedding")
                log_error(f"  - Data type: float32")
                log_error(f"  - Dimensions: {config.embedding_dim}")
                log_error(f"  - Distance function: cosine")
                log_error(f"  - Index type: quantizedFlat")
                raise Exception(f"Container '{self.container_name}' not found. Create it manually in Azure Portal first.")
            
            # Check document count at startup for optimization
            self._update_document_count()
            
            self.connected = True
            log_info("Connected to Cosmos DB",
                    database=self.database_name,
                    container=self.container_name)
            
        except Exception as e:
            log_error(f"Failed to connect to Cosmos DB: {e}")
            self.connected = False
    
    def is_available(self) -> bool:
        """Check if Cosmos DB is available."""
        return self.connected and self.container is not None
    
    def has_documents(self) -> bool:
        """Check if container has any documents."""
        return self.document_count > 0
    
    def _update_document_count(self):
        """Update cached document count."""
        try:
            query = "SELECT VALUE COUNT(1) FROM c"
            items = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            self.document_count = items[0] if items else 0
            log_info("Document count updated", count=self.document_count)
        except Exception as e:
            log_warning(f"Failed to get document count: {e}")
            self.document_count = 0
    
    def upsert_chunks(self, chunks: List[Dict[str, Any]]) -> int:
        """Upsert document chunks to Cosmos DB.
        
        Args:
            chunks: List of chunk documents with embeddings
            
        Returns:
            Number of successfully upserted chunks
        """
        if not self.is_available():
            log_error("Cosmos DB not available for upsert")
            return 0
        
        success_count = 0
        start = time.time()
        
        for chunk in chunks:
            try:
                self.container.upsert_item(chunk)
                success_count += 1
                log_debug("Chunk upserted", 
                         id=chunk.get("id", "unknown"))
            except Exception as e:
                log_error(f"Failed to upsert chunk: {e}",
                         id=chunk.get("id", "unknown"))
        
        # Update document count after successful upserts
        if success_count > 0:
            self._update_document_count()
        
        elapsed = time.time() - start
        log_info("Batch upsert complete",
                total=len(chunks),
                success=success_count,
                failed=len(chunks) - success_count,
                elapsed_ms=int(elapsed * 1000))
        
        return success_count
    
    def search_similar(self, 
                      query_vector: List[float], 
                      top_k: int = 5,
                      min_similarity: float = 0.7) -> List[Dict[str, Any]]:
        """Search for similar chunks using vector similarity.
        
        Args:
            query_vector: Query embedding vector
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of similar chunks with metadata
        """
        if not self.is_available():
            log_error("Cosmos DB not available for search")
            return []
        
        # Skip search if container is empty
        if not self.has_documents():
            log_info("Container empty, skipping vector search")
            return []
        
        try:
            # Use VectorDistance for native similarity search
            # VectorDistance returns distance (0=identical, 1=opposite)
            # We want documents with LOW distance (high similarity)
            query = """
            SELECT TOP @top_k c.id, c.filename, c.text, c.chunk_index,
                   VectorDistance(c.embedding, @embedding) AS distance
            FROM c
            ORDER BY VectorDistance(c.embedding, @embedding)
            """
            
            parameters = [
                {"name": "@embedding", "value": query_vector},
                {"name": "@top_k", "value": top_k}
            ]
            
            items = self.container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            )
            
            results = []
            for item in items:
                distance = item.get("distance", 1.0)
                similarity = 1 - distance  # Convert distance to similarity
                
                # Filter by min_similarity threshold
                if similarity >= min_similarity:
                    results.append({
                        "id": item.get("id"),
                        "filename": item.get("filename"),
                        "text": item.get("text"),
                        "chunk_index": item.get("chunk_index"),
                        "similarity": similarity
                    })
            
            log_info("Vector search complete", returned=len(results))
            return results
            
        except Exception as e:
            log_error(f"Vector search failed: {e}")
            return []
    
    def _cosine_similarity_fast(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors (optimized)."""
        if len(vec1) != len(vec2):
            return 0.0
        
        # Use generator expressions for better memory efficiency
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        
        # Early exit if dot product is too small
        if abs(dot_product) < 1e-10:
            return 0.0
        
        norm1_sq = sum(a * a for a in vec1)
        norm2_sq = sum(b * b for b in vec2)
        
        if norm1_sq == 0 or norm2_sq == 0:
            return 0.0
        
        return dot_product / (norm1_sq ** 0.5 * norm2_sq ** 0.5)
    
    def delete_document(self, doc_id: str) -> int:
        """Delete all chunks for a document.
        
        Args:
            doc_id: Document identifier
            
        Returns:
            Number of deleted chunks
        """
        if not self.is_available():
            log_error("Cosmos DB not available for delete")
            return 0
        
        try:
            query = "SELECT c.id FROM c WHERE c.doc_id = @doc_id"
            chunk_ids = [
                item["id"] for item in self.container.query_items(
                    query=query,
                    parameters=[{"name": "@doc_id", "value": doc_id}],
                    enable_cross_partition_query=True
                )
            ]
            
            deleted = 0
            for chunk_id in chunk_ids:
                try:
                    self.container.delete_item(
                        item=chunk_id,
                        partition_key=doc_id
                    )
                    deleted += 1
                except Exception as e:
                    log_warning(f"Failed to delete chunk: {e}",
                               id=chunk_id)
            
            log_info("Document deleted",
                    doc_id=doc_id,
                    chunks_deleted=deleted)
            
            return deleted
            
        except Exception as e:
            log_error(f"Failed to delete document: {e}",
                     doc_id=doc_id)
            return 0
    
    def list_documents(self) -> List[Dict[str, Any]]:
        """List all unique documents in the database.
        
        Returns:
            List of document metadata
        """
        if not self.is_available():
            log_error("Cosmos DB not available")
            return []
        
        try:
            # Get distinct doc_ids with metadata
            query = """
            SELECT DISTINCT 
                c.doc_id, 
                c.filename, 
                c.uploaded_at 
            FROM c
            """
            docs = list(self.container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            log_info("Documents listed", count=len(docs))
            return docs
            
        except Exception as e:
            log_error(f"Failed to list documents: {e}")
            return []

__all__ = ["CosmosDBClient"]

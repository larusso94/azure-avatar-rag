"""Embeddings client for Avatar RAG system."""
import time
import hashlib
from functools import lru_cache
from typing import List
from .config import config
from .logger import log_info, log_error, log_warning, log_debug

class EmbeddingsClient:
    """Generate embeddings using Azure OpenAI."""
    
    def __init__(self):
        self.endpoint = config.openai_endpoint
        self.api_key = config.openai_api_key
        self.deployment = config.openai_embed_deployment
        self.api_version = config.openai_api_version
        self.dim = config.embedding_dim
        
        self._client = None
        self._cache = {}  # Cache for embeddings
        self._max_cache_size = 100
        
        if self.endpoint and self.api_key:
            try:
                from openai import AzureOpenAI
                self._client = AzureOpenAI(
                    azure_endpoint=self.endpoint,
                    api_key=self.api_key,
                    api_version=self.api_version
                )
                log_info("Embeddings client initialized", 
                        deployment=self.deployment)
            except Exception as e:
                log_error(f"Failed to initialize embeddings client: {e}")
                self._client = None
        else:
            log_warning("Embeddings client not initialized - missing config")
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a list of texts with caching.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        start = time.time()
        
        # Prepare lists for batch processing
        texts_to_embed = []
        indices_to_embed = []
        cached_vectors = []
        cached_indices = []
        
        # Check cache for each text
        for i, text in enumerate(texts):
            cache_key = self._get_cache_key(text)
            if cache_key in self._cache:
                cached_vectors.append(self._cache[cache_key])
                cached_indices.append(i)
                log_debug("Cache hit for embedding")
            else:
                texts_to_embed.append(text)
                indices_to_embed.append(i)
        
        # Embed uncached texts
        if texts_to_embed:
            log_info("Generating embeddings", 
                    total=len(texts),
                    cached=len(cached_vectors),
                    new=len(texts_to_embed))
            
            try:
                if self._client:
                    new_vectors = self._embed_with_openai_retry(texts_to_embed)
                else:
                    new_vectors = self._embed_fallback(texts_to_embed)
                
                # Update cache with new vectors
                for text, vector in zip(texts_to_embed, new_vectors):
                    cache_key = self._get_cache_key(text)
                    self._update_cache(cache_key, vector)
                    
            except Exception as e:
                log_error(f"Embeddings generation failed: {e}", fallback=True)
                new_vectors = self._embed_fallback(texts_to_embed)
        else:
            new_vectors = []
        
        # Reconstruct results in original order
        vectors = [None] * len(texts)
        for idx, vec in zip(cached_indices, cached_vectors):
            vectors[idx] = vec
        for idx, vec in zip(indices_to_embed, new_vectors):
            vectors[idx] = vec
        
        elapsed = time.time() - start
        log_info("Embeddings ready",
                count=len(vectors),
                elapsed_ms=int(elapsed * 1000))
        
        return vectors
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()
    
    def _update_cache(self, key: str, vector: List[float]):
        """Update cache with LRU eviction."""
        if len(self._cache) >= self._max_cache_size:
            # Remove oldest entry (simple FIFO, could use OrderedDict for true LRU)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = vector
    
    def _embed_with_openai_retry(self, texts: List[str], max_retries: int = 3) -> List[List[float]]:
        """Generate embeddings using Azure OpenAI with retry logic."""
        for attempt in range(max_retries):
            try:
                response = self._client.embeddings.create(
                    model=self.deployment,
                    input=texts,
                    dimensions=self.dim  # Specify dimensions explicitly
                )
                
                vectors = []
                for item in response.data:
                    vectors.append(item.embedding)
                
                return vectors
                
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt)  # Exponential backoff: 1s, 2s, 4s
                    log_warning(f"Embedding attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    raise
    
    def _embed_fallback(self, texts: List[str]) -> List[List[float]]:
        """Generate deterministic fallback vectors."""
        log_warning("Using fallback embeddings", count=len(texts))
        
        vectors = []
        for i, text in enumerate(texts):
            # Simple hash-based vector
            base = sum(ord(c) for c in text) or 1
            vector = [((base * (j + i + 1)) % 17) / 17 for j in range(self.dim)]
            vectors.append(vector)
        
        return vectors

__all__ = ["EmbeddingsClient"]

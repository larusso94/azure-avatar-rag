"""Document chunking for Avatar RAG system."""
import re
from typing import List, Dict
from .config import config
from .logger import log_info, log_warning, log_debug

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False
    tiktoken = None

class DocumentChunker:
    """Chunks documents into smaller pieces for embedding."""
    
    def __init__(self):
        self.target_tokens = config.chunk_target_tokens
        self.max_tokens = config.chunk_max_tokens
        self.overlap_tokens = config.chunk_overlap_tokens
        self.min_chunk_tokens = config.chunk_min_chunk_tokens
        
        self._enc = None
        if HAS_TIKTOKEN:
            try:
                self._enc = tiktoken.encoding_for_model("gpt-4")
                log_debug("Tiktoken encoder initialized")
            except Exception as e:
                log_warning(f"Tiktoken fallback: {e}")
                self._enc = None
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self._enc:
            return len(self._enc.encode(text))
        # Fallback: estimate 1 token = 4 characters
        return len(text) // 4
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        parts = re.split(r'(?<=[.!?])\s+', text.strip())
        return [p.strip() for p in parts if p.strip()]
    
    def chunk_document(self, text: str, doc_id: str) -> List[Dict]:
        """Chunk a document into smaller pieces.
        
        Args:
            text: Document text to chunk
            doc_id: Unique document identifier
            
        Returns:
            List of chunk dictionaries with text and metadata
        """
        sentences = self._split_sentences(text)
        chunks = []
        current_sentences = []
        current_tokens = 0
        
        log_info("Starting chunking", 
                 doc_id=doc_id,
                 text_length=len(text),
                 sentences=len(sentences))
        
        for sentence in sentences:
            sentence_tokens = self._count_tokens(sentence)
            
            # If single sentence is too large, split it
            if sentence_tokens > self.max_tokens:
                if current_sentences:
                    chunks.append({
                        "text": " ".join(current_sentences),
                        "chunk_index": len(chunks),
                        "doc_id": doc_id
                    })
                    current_sentences = []
                    current_tokens = 0
                
                # Hard split large sentence
                hard_chunks = self._hard_split(sentence)
                for hc in hard_chunks:
                    chunks.append({
                        "text": hc,
                        "chunk_index": len(chunks),
                        "doc_id": doc_id
                    })
                continue
            
            # Add sentence to current chunk if it fits
            if current_tokens + sentence_tokens <= self.target_tokens:
                current_sentences.append(sentence)
                current_tokens += sentence_tokens
            else:
                # Save current chunk and start new one
                if current_sentences:
                    chunks.append({
                        "text": " ".join(current_sentences),
                        "chunk_index": len(chunks),
                        "doc_id": doc_id
                    })
                current_sentences = [sentence]
                current_tokens = sentence_tokens
        
        # Add remaining sentences
        if current_sentences:
            chunks.append({
                "text": " ".join(current_sentences),
                "chunk_index": len(chunks),
                "doc_id": doc_id
            })
        
        # Merge small chunks
        chunks = self._merge_small_chunks(chunks)
        
        # Apply overlap
        chunks = self._apply_overlap(chunks)
        
        log_info("Chunking complete",
                 doc_id=doc_id,
                 total_chunks=len(chunks),
                 avg_tokens=sum(self._count_tokens(c["text"]) for c in chunks) // len(chunks) if chunks else 0)
        
        return chunks
    
    def _hard_split(self, text: str) -> List[str]:
        """Hard split text that exceeds max tokens."""
        if self._enc:
            tokens = self._enc.encode(text)
            parts = []
            for i in range(0, len(tokens), self.max_tokens):
                sub_tokens = tokens[i:i + self.max_tokens]
                parts.append(self._enc.decode(sub_tokens))
            return parts
        else:
            # Fallback: split by characters
            size = self.max_tokens * 4
            return [text[i:i+size] for i in range(0, len(text), size)]
    
    def _merge_small_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """Merge chunks that are too small."""
        if not chunks:
            return []
        
        merged = []
        buffer = None
        
        for chunk in chunks:
            tokens = self._count_tokens(chunk["text"])
            
            if tokens < self.min_chunk_tokens:
                if buffer is None:
                    buffer = chunk.copy()
                else:
                    buffer["text"] += " " + chunk["text"]
                    if self._count_tokens(buffer["text"]) >= self.min_chunk_tokens:
                        merged.append(buffer)
                        buffer = None
            else:
                if buffer:
                    merged.append(buffer)
                    buffer = None
                merged.append(chunk)
        
        if buffer:
            merged.append(buffer)
        
        # Re-index chunks
        for i, chunk in enumerate(merged):
            chunk["chunk_index"] = i
        
        return merged
    
    def _apply_overlap(self, chunks: List[Dict]) -> List[Dict]:
        """Apply overlap between chunks."""
        if self.overlap_tokens <= 0 or len(chunks) < 2:
            return chunks
        
        overlapped = []
        for i, chunk in enumerate(chunks):
            if i == 0:
                overlapped.append(chunk)
                continue
            
            # Get tail from previous chunk
            prev_text = chunks[i-1]["text"]
            tail = self._get_tail(prev_text, self.overlap_tokens)
            
            # Combine with current chunk
            new_chunk = chunk.copy()
            new_chunk["text"] = tail + " " + chunk["text"]
            overlapped.append(new_chunk)
        
        return overlapped
    
    def _get_tail(self, text: str, overlap_tokens: int) -> str:
        """Get the tail of text with approximately overlap_tokens."""
        if self._enc:
            tokens = self._enc.encode(text)
            if len(tokens) <= overlap_tokens:
                return text
            tail_tokens = tokens[-overlap_tokens:]
            return self._enc.decode(tail_tokens)
        else:
            # Fallback: use characters
            approx_chars = overlap_tokens * 4
            return text[-approx_chars:] if len(text) > approx_chars else text

__all__ = ["DocumentChunker"]

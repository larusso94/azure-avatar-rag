"""Document processor for Avatar RAG system."""
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from .config import config
from .logger import log_info, log_error
from .chunker import DocumentChunker
from .embedder import EmbeddingsClient
from .cosmos_db import CosmosDBClient

class DocumentProcessor:
    """Process documents: extract text, chunk, embed, and store."""
    
    def __init__(self, cosmos_client=None):
        self.chunker = DocumentChunker()
        self.embedder = EmbeddingsClient()
        # Use shared Cosmos DB client if provided, otherwise create new
        self.cosmos = cosmos_client if cosmos_client else CosmosDBClient()
    
    def process_file(self, filepath: Path, filename: str) -> Dict[str, Any]:
        """Process a file and store in knowledge base.
        
        Args:
            filepath: Path to the file
            filename: Original filename
            
        Returns:
            Processing result with statistics
        """
        log_info("Processing file", filename=filename)
        
        try:
            # Extract text from file
            text = self._extract_text(filepath)
            
            if not text:
                return {
                    "success": False,
                    "error": "No text could be extracted from file"
                }
            
            # Generate document ID
            doc_id = str(uuid.uuid4())
            
            # Chunk document
            chunks = self.chunker.chunk_document(text, doc_id)
            
            if not chunks:
                return {
                    "success": False,
                    "error": "No chunks generated from document"
                }
            
            # Extract texts for embedding
            chunk_texts = [chunk["text"] for chunk in chunks]
            
            # Generate embeddings
            embeddings = self.embedder.embed_texts(chunk_texts)
            
            if len(embeddings) != len(chunks):
                return {
                    "success": False,
                    "error": "Embedding count mismatch"
                }
            
            # Prepare documents for Cosmos DB
            current_time = datetime.utcnow().isoformat()
            cosmos_docs = []
            
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                doc = {
                    "id": f"{doc_id}::{i}",
                    "filename": filename,
                    "chunk_index": i,
                    "text": chunk["text"],
                    "embedding": embedding,
                    "uploaded_at": current_time,
                    "text_length": len(chunk["text"])
                }
                cosmos_docs.append(doc)
            
            # Upsert to Cosmos DB
            success_count = self.cosmos.upsert_chunks(cosmos_docs)
            
            result = {
                "success": True,
                "id": doc_id,
                "filename": filename,
                "total_chunks": len(chunks),
                "stored_chunks": success_count,
                "text_length": len(text),
                "uploaded_at": current_time
            }
            
            log_info("File processed successfully",
                    filename=filename,
                    chunks=success_count)
            
            return result
            
        except Exception as e:
            log_error(f"File processing failed: {e}", filename=filename)
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_text(self, filepath: Path) -> str:
        """Extract text from file based on extension."""
        ext = filepath.suffix.lower()
        
        try:
            if ext == '.txt' or ext == '.md':
                return self._extract_from_txt(filepath)
            elif ext == '.pdf':
                return self._extract_from_pdf(filepath)
            elif ext == '.docx':
                return self._extract_from_docx(filepath)
            else:
                return ""
        except Exception as e:
            log_error(f"Text extraction failed: {e}", filepath=str(filepath))
            return ""
    
    def _extract_from_txt(self, filepath: Path) -> str:
        """Extract text from txt/md file."""
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    
    def _extract_from_pdf(self, filepath: Path) -> str:
        """Extract text from PDF file."""
        try:
            import PyPDF2
            text = []
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text.append(page.extract_text())
            return "\n".join(text)
        except ImportError:
            log_error("PyPDF2 not installed, cannot process PDF")
            return ""
    
    def _extract_from_docx(self, filepath: Path) -> str:
        """Extract text from DOCX file."""
        try:
            import docx
            doc = docx.Document(filepath)
            return "\n".join([para.text for para in doc.paragraphs])
        except ImportError:
            log_error("python-docx not installed, cannot process DOCX")
            return ""

__all__ = ["DocumentProcessor"]

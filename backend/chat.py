"""Chat client with RAG for Avatar system."""
import time
from typing import List, Dict, Any
from .config import config
from .logger import log_info, log_error, log_warning
from .embedder import EmbeddingsClient
from .cosmos_db import CosmosDBClient

class ChatClient:
    """Chat client with RAG support using Azure OpenAI."""
    
    def __init__(self, cosmos_client=None):
        self.endpoint = config.openai_endpoint
        self.api_key = config.openai_api_key
        self.deployment = config.openai_chat_deployment
        self.api_version = config.openai_api_version
        
        self.embedder = EmbeddingsClient()
        # Use shared Cosmos DB client if provided, otherwise create new
        self.cosmos = cosmos_client if cosmos_client else CosmosDBClient()
        
        self._client = None
        self._available_docs_cache = None  # Cache for available documents
        
        if self.endpoint and self.api_key:
            try:
                from openai import AzureOpenAI
                self._client = AzureOpenAI(
                    azure_endpoint=self.endpoint,
                    api_key=self.api_key,
                    api_version=self.api_version
                )
                log_info("Chat client initialized", 
                        deployment=self.deployment)
                # Load available documents cache at startup
                self.refresh_documents_cache()
            except Exception as e:
                log_error(f"Failed to initialize chat client: {e}")
    
    def chat_with_rag(self, 
                     user_message: str, 
                     conversation_history: List[Dict[str, str]] = None,
                     top_k: int = 3) -> str:
        """Chat with RAG support.
        
        Args:
            user_message: User's question
            conversation_history: Previous messages in conversation
            top_k: Number of relevant chunks to retrieve
            
        Returns:
            Assistant's response
        """
        if not self._client:
            return "Lo siento, el servicio de chat no está disponible en este momento."
        
        log_info("Processing chat request", message_length=len(user_message))
        
        # Use cached list of available documents
        available_docs = self._available_docs_cache
        
        # Get relevant context from knowledge base
        context = self._get_relevant_context(user_message, top_k)
        
        # Build messages
        messages = self._build_messages(user_message, context, conversation_history, available_docs)
        
        # Call Azure OpenAI with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self.deployment,
                    messages=messages
                )
                
                answer = response.choices[0].message.content
                
                log_info("Chat response generated",
                        prompt_tokens=response.usage.prompt_tokens,
                        completion_tokens=response.usage.completion_tokens,
                        total_tokens=response.usage.total_tokens,
                        attempt=attempt + 1)
                
                return answer
                
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (2 ** attempt)
                    log_warning(f"Chat attempt {attempt + 1} failed, retrying in {wait_time}s: {e}")
                    time.sleep(wait_time)
                else:
                    log_error(f"Chat completion failed after {max_retries} attempts: {e}")
                    return f"Lo siento, hubo un error al procesar tu pregunta. Por favor intenta de nuevo."
    
    def _get_relevant_context(self, query: str, top_k: int) -> str:
        """Retrieve relevant context from knowledge base."""
        try:
            # Generate embedding for query
            query_vectors = self.embedder.embed_texts([query])
            if not query_vectors:
                return ""
            
            query_vector = query_vectors[0]
            
            # Search similar chunks
            similar_chunks = self.cosmos.search_similar(
                query_vector=query_vector,
                top_k=top_k,
                min_similarity=0.6
            )
            
            if not similar_chunks:
                return ""
            
            # Build context from chunks (optimized format)
            context_parts = []
            for i, chunk in enumerate(similar_chunks):
                text = chunk.get("text", "").strip()
                filename = chunk.get("filename", "unknown")
                
                # More concise format
                context_parts.append(f"[{filename}] {text}")
            
            context = "\n\n".join(context_parts)
            
            log_info("Context retrieved",
                    chunks=len(similar_chunks),
                    context_length=len(context))
            
            return context
            
        except Exception as e:
            log_error(f"Context retrieval failed: {e}")
            return ""
    
    def refresh_documents_cache(self):
        """Refresh the cache of available documents."""
        self._available_docs_cache = self._get_available_documents()
        log_info("Documents cache refreshed")
    
    def _get_available_documents(self) -> str:
        """Get formatted list of available documents in the knowledge base."""
        try:
            docs = self.cosmos.list_documents()
            if not docs:
                return "No hay documentos en la base de conocimiento."
            
            doc_list = []
            for doc in docs:
                filename = doc.get('filename', 'unknown')
                uploaded_at = doc.get('uploaded_at', 'unknown')
                doc_list.append(f"- {filename} (subido: {uploaded_at})")
            
            return "\n".join(doc_list)
        except Exception as e:
            log_error(f"Failed to get document list: {e}")
            return "No se pudo obtener la lista de documentos."
    
    def _build_messages(self, 
                       user_message: str, 
                       context: str,
                       conversation_history: List[Dict[str, str]] = None,
                       available_docs: str = None) -> List[Dict[str, str]]:
        """Build messages for chat completion."""
        messages = []
        
        # System message with context (optimized)
        system_message = """Eres un asistente virtual que responde preguntas usando la base de conocimiento.

Instrucciones:
- Usa el contexto para responder
- Respuestas claras y breves (2-3 frases)
- Si no hay información relevante, indícalo
- Responde en español
"""
        
        # Add available documents list
        if available_docs:
            system_message += f"\n\nDOCUMENTOS DISPONIBLES EN LA BASE DE CONOCIMIENTO:\n{available_docs}"
        
        # Add relevant context chunks
        if context:
            system_message += f"\n\nCONTEXTO RELEVANTE PARA ESTA PREGUNTA:\n{context}"
        
        messages.append({"role": "system", "content": system_message})
        
        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history[-5:])  # Last 5 messages
        
        # Add user message
        messages.append({"role": "user", "content": user_message})
        
        return messages

__all__ = ["ChatClient"]

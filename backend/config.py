"""Configuration for Azure Avatar RAG System."""
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base directory
BASE_DIR = Path(__file__).parent.parent

@dataclass
class AvatarRAGConfig:
    """Configuration for Avatar RAG System."""
    
    # Azure Speech Services
    speech_key: str = os.getenv("AZURE_SPEECH_KEY", "")
    speech_region: str = os.getenv("AZURE_SPEECH_REGION", "swedencentral")
    speech_endpoint: str = f"https://{speech_region}.api.cognitive.microsoft.com/"
    
    # Azure OpenAI Configuration
    openai_endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    openai_api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    openai_api_version: str = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
    openai_chat_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_CHAT", "gpt-5-mini-deployment")
    openai_embed_deployment: str = os.getenv("AZURE_OPENAI_DEPLOYMENT_EMBED", "text-embedding-3-large")
    
    # Cosmos DB Configuration
    cosmos_endpoint: str = os.getenv("COSMOS_ENDPOINT", "")
    cosmos_key: str = os.getenv("COSMOS_KEY", "")
    cosmos_database: str = os.getenv("COSMOS_DATABASE", "avatarrag")
    cosmos_container: str = os.getenv("COSMOS_CONTAINER_KB", "knowledge_base")
    cosmos_container_sessions: str = os.getenv("COSMOS_CONTAINER_SESSIONS", "sessions")
    
    # Avatar Configuration
    avatar_character: str = os.getenv("AVATAR_CHARACTER", "lisa")
    avatar_style: str = os.getenv("AVATAR_STYLE", "casual-sitting")
    avatar_voice: str = os.getenv("AVATAR_VOICE", "en-US-AvaMultilingualNeural")
    
    # Embedding Configuration
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "3072"))
    embedding_model: str = "text-embedding-3-large"
    
    # Chunking Configuration
    chunk_target_tokens: int = int(os.getenv("CHUNK_SIZE", "500"))
    chunk_max_tokens: int = int(os.getenv("CHUNK_SIZE", "500")) + 50
    chunk_overlap_tokens: int = int(os.getenv("CHUNK_OVERLAP", "50"))
    chunk_min_chunk_tokens: int = 60
    
    # RAG Configuration
    top_k_results: int = int(os.getenv("TOP_K_RESULTS", "3"))
    similarity_threshold: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
    max_response_tokens: int = int(os.getenv("MAX_RESPONSE_TOKENS", "500"))
    
    # Processing Configuration
    batch_size: int = 25
    max_file_size_mb: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
    supported_extensions: tuple = ('.txt', '.pdf', '.docx', '.md')
    
    # Upload Configuration
    upload_dir: Path = BASE_DIR / "uploads"
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def validate(self):
        """Validate required configuration."""
        required = [
            ("AZURE_SPEECH_KEY", self.speech_key),
            ("AZURE_OPENAI_ENDPOINT", self.openai_endpoint),
            ("AZURE_OPENAI_API_KEY", self.openai_api_key),
            ("COSMOS_ENDPOINT", self.cosmos_endpoint),
            ("COSMOS_KEY", self.cosmos_key),
        ]
        
        missing = [name for name, value in required if not value]
        
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                f"Please check your .env file."
            )

# Global config instance
config = AvatarRAGConfig()

# Validate on import
try:
    config.validate()
except ValueError as e:
    print(f"⚠️  Configuration Error: {e}")
    print("💡 Make sure to create a .env file based on .env.example")

__all__ = ["config", "AvatarRAGConfig"]

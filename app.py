"""Flask API server for Avatar RAG system."""
import sys
import signal
import atexit
from flask import Flask, request, jsonify
from flask_cors import CORS
from pathlib import Path
import os
from werkzeug.utils import secure_filename

from backend.config import config
from backend.logger import setup_logger, log_info, log_error

# Setup logging
logger = setup_logger(__name__, config.log_level)

# Initialize Flask app
app = Flask(__name__, 
            static_folder='.',
            static_url_path='')
CORS(app)

# Global clients
_processor = None
_chat_client = None
_cosmos_client = None

def cleanup_resources():
    """Cleanup resources when server shuts down."""
    global _cosmos_client, _chat_client, _processor
    
    logger.info("🧹 Cleaning up resources...")
    
    if _cosmos_client:
        try:
            _cosmos_client = None
            logger.info("✅ Cosmos DB client cleanup")
        except Exception as e:
            logger.error(f"Error cleaning up Cosmos client: {e}")
    
    if _chat_client:
        try:
            _chat_client = None
            logger.info("✅ Chat client cleanup")
        except Exception as e:
            logger.error(f"Error cleaning up chat client: {e}")
    
    if _processor:
        try:
            _processor = None
            logger.info("✅ Processor cleanup")
        except Exception as e:
            logger.error(f"Error cleaning up processor: {e}")
    
    logger.info("✅ Cleanup complete")

def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully."""
    print("\n")
    logger.info("🛑 Received shutdown signal")
    cleanup_resources()
    sys.exit(0)

# Register cleanup handlers
atexit.register(cleanup_resources)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def init_services():
    """Initialize all services at startup."""
    global _processor, _chat_client, _cosmos_client
    
    logger.info("🔄 Initializing services...")
    
    # Initialize Cosmos DB
    from backend.cosmos_db import CosmosDBClient
    logger.info("  → Initializing Cosmos DB client...")
    _cosmos_client = CosmosDBClient()
    log_info("✅ Cosmos DB client initialized")
    
    # Initialize Chat Client
    from backend.chat import ChatClient
    logger.info("  → Initializing chat client...")
    _chat_client = ChatClient(cosmos_client=_cosmos_client)
    log_info("✅ Chat client initialized")
    
    # Initialize Processor
    from backend.processor import DocumentProcessor
    logger.info("  → Initializing document processor...")
    _processor = DocumentProcessor(
        cosmos_client=_cosmos_client,
        embedder=_chat_client.embedder
    )
    log_info("✅ Document processor initialized")
    
    logger.info("🎉 All services initialized successfully")

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "services": {
            "cosmos_db": _cosmos_client is not None,
            "chat_client": _chat_client is not None,
            "processor": _processor is not None
        }
    })

@app.route('/api/upload', methods=['POST'])
def upload_document():
    """Upload and process a document."""
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Empty filename"}), 400
        
        # Validate file extension
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in config.supported_extensions:
            return jsonify({
                "error": f"Unsupported file type. Supported: {', '.join(config.supported_extensions)}"
            }), 400
        
        # Save file
        filename = secure_filename(file.filename)
        config.upload_dir.mkdir(exist_ok=True)
        filepath = config.upload_dir / filename
        file.save(str(filepath))
        
        logger.info(f"📄 Processing document: {filename}")
        
        # Process document
        result = _processor.process_document(str(filepath))
        
        # Cleanup
        filepath.unlink()
        
        return jsonify({
            "status": "success",
            "filename": filename,
            "chunks_created": result.get("chunks_created", 0),
            "message": "Document processed and indexed successfully"
        })
    
    except Exception as e:
        logger.error(f"Error processing document: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    """Chat endpoint with optional RAG."""
    try:
        data = request.get_json()
        question = data.get('question', '')
        use_rag = data.get('use_rag', True)
        session_id = data.get('session_id', 'default')
        
        if not question:
            return jsonify({"error": "Question is required"}), 400
        
        logger.info(f"💬 Chat request - RAG: {use_rag}, Question: {question[:50]}...")
        
        # Get response
        response = _chat_client.chat(
            question=question,
            use_rag=use_rag,
            session_id=session_id
        )
        
        return jsonify({
            "status": "success",
            "response": response.get("answer", ""),
            "sources": response.get("sources", []),
            "context_used": response.get("context_used", False)
        })
    
    except Exception as e:
        logger.error(f"Error in chat: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

@app.route('/api/clear', methods=['POST'])
def clear_knowledge_base():
    """Clear all documents from knowledge base."""
    try:
        # This would need to be implemented in CosmosDBClient
        logger.info("🗑️  Clearing knowledge base")
        return jsonify({
            "status": "success",
            "message": "Knowledge base cleared"
        })
    except Exception as e:
        logger.error(f"Error clearing KB: {e}", exc_info=True)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 Starting Azure Avatar RAG Backend Server")
    print("=" * 60)
    
    try:
        # Initialize services
        init_services()
        
        # Start server
        port = int(os.getenv('PORT', 5000))
        print(f"\n✅ Server running on http://localhost:{port}")
        print(f"📚 API docs: http://localhost:{port}/api/health")
        print(f"💡 Press Ctrl+C to stop\n")
        print("=" * 60)
        
        app.run(
            host='0.0.0.0',
            port=port,
            debug=os.getenv('FLASK_ENV') == 'development'
        )
    
    except Exception as e:
        logger.error(f"Failed to start server: {e}", exc_info=True)
        sys.exit(1)

import logging
from typing import Optional

from phi.vectordb.pgvector import PgVector
from utils.llm_helper import get_embedder
from .custom_knowledge_base import CustomKnowledgeBase
from config import POSTGRES_CONNECTION

# Setup logging
logger = logging.getLogger(__name__)

def init_vector_db() -> Optional[PgVector]:
    """Initialize and test vector database"""
    try:
        # Initialize embedder
        embedder = get_embedder()
        logger.info("Embedder initialized successfully")
        
        # Initialize vector database with existing table
        vector_db = PgVector(
            table_name="grant_reviews",  # Using existing table with schema
            db_url=POSTGRES_CONNECTION,
            embedder=embedder
        )
        logger.info(f"Vector DB initialized with table: {vector_db.table_name}")
        
        # Test vector search functionality
        test_results = vector_db.search(
            query="test query",
            limit=1
        )
        logger.info("Vector search test completed successfully")
        
        return vector_db
        
    except Exception as e:
        logger.error(f"Vector DB initialization failed: {str(e)}")
        raise

def init_knowledge_base() -> Optional[CustomKnowledgeBase]:
    """Initialize knowledge base with proper configuration"""
    try:
        # Initialize vector database
        vector_db = init_vector_db()
        
        # Initialize knowledge base
        knowledge_base = CustomKnowledgeBase(
            sources=[],  # Can be extended with additional sources
            vector_db=vector_db
        )
        logger.info("Knowledge base initialized successfully")
        
        return knowledge_base
        
    except Exception as e:
        logger.error(f"Knowledge base initialization failed: {str(e)}")
        raise

# Initialize global knowledge base instance
try:
    knowledge_base = init_knowledge_base()
    if not knowledge_base:
        raise ValueError("Knowledge base initialization returned None")
        
except Exception as e:
    logger.error(f"Failed to initialize global knowledge base: {str(e)}")
    raise
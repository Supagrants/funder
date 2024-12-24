# knowledge.py

import logging

from phi.vectordb.pgvector import PgVector

from utils.llm_helper import get_embedder
from .custom_knowledge_base import CustomKnowledgeBase
from config import POSTGRES_CONNECTION

# Setup logging
logger = logging.getLogger(__name__)

# Initialize a unified PgVector for all documents

try:
    embedder = get_embedder()
   
except Exception as e:
    logger.error(f"Embedder initialization/test failed: {str(e)}")
    raise


# Initialize PgVector with explicit error handling
try:
    vector_db = PgVector(
        table_name="grant_reviews",
        db_url=POSTGRES_CONNECTION,
        embedder=embedder
    )
    logger.info(f"Vector DB initialized successfully with table: {vector_db.table_name}")
    
    # Test vector search functionality
    test_results = vector_db.search(
        query="test query",
        limit=1
    )
    logger.info(f"Vector search test {'successful' if test_results is not None else 'failed'}")
    
except Exception as e:
    logger.error(f"Vector DB initialization/test failed: {str(e)}")
    raise

# Initialize knowledge base
knowledge_base = CustomKnowledgeBase(
    sources=[],
    vector_db=vector_db,
)
logger.info("Knowledge base initialized successfully")
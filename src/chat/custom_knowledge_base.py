import logging
import json
import hashlib
from typing import List, Optional, Dict, Any
from datetime import datetime
import psycopg2
from psycopg2.extras import Json
from phi.knowledge.agent import AgentKnowledge
from phi.vectordb.pgvector import PgVector
from utils.llm_helper import get_embedder

# Setup logging
logger = logging.getLogger(__name__)

class CustomKnowledgeBase(AgentKnowledge):
    """Knowledge base for managing grant reviews."""

    def __init__(self, vector_db: PgVector):
        super().__init__(vector_db=vector_db)

    def _format_application_data(self, application_content: Dict[str, Any]) -> Dict[str, Any]:
        """Format application data for storage"""
        return {
            "id": application_content.get('id'),
            "name": application_content.get('name'),
            "content": application_content.get('content'),
            "meta_data": application_content.get('meta_data', {}),
            "document_type": application_content.get('document_type', 'application'),
            "created_at": application_content.get('created_at', datetime.now().isoformat())
        }

    async def add_review(
        self, 
        user_id: str, 
        application_content: Dict[str, Any], 
        review_content: str
    ) -> str:
        """
        Add a grant review to the knowledge base.
        
        Args:
            user_id (str): The applicant's user ID
            application_content (Dict): The original application content
            review_content (str): The review content/feedback
            
        Returns:
            str: Content hash of the saved review
        """
        table_name = "grant_reviews"
        try:
            # Get embedding for the review content
            embedder = get_embedder()
            embedding = embedder.get_embedding(review_content)
            
            # Generate content hash
            content_hash = hashlib.md5(review_content.encode()).hexdigest()
            
            # Format application data
            formatted_app = self._format_application_data(application_content)
            
            # Prepare metadata
            meta_data = {
                "user_id": user_id,
                "application_id": formatted_app["id"],
                "application_date": formatted_app["created_at"],
                "review_type": "grant_review"
            }

            # Create connection and insert review
            with psycopg2.connect(self.vector_db.db_url) as conn:
                with conn.cursor() as cur:
                    query = """
                    INSERT INTO {} (
                        id,
                        name,
                        content,
                        meta_data,
                        embedding,
                        document_type,
                        content_hash,
                        usage,
                        filters
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """.format(table_name)
                    
                    values = (
                        content_hash,                      # id
                        f"Grant Review - {user_id}",       # name
                        review_content,                    # content
                        Json(meta_data),                   # meta_data
                        embedding,                         # embedding
                        "grant_review",                    # document_type
                        content_hash,                      # content_hash
                        Json({}),                         # usage
                        Json({})                          # filters
                    )
                    
                    cur.execute(query, values)
                    conn.commit()
                
            logger.info(f"Saved grant review for user {user_id}")
            return content_hash
            
        except Exception as e:
            logger.error(f"Error saving grant review: {str(e)}")
            raise

    async def get_reviews(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Get all grant reviews for a specific user.
        
        Args:
            user_id (str): The applicant's user ID

        Returns:
            List[Dict]: List of reviews with their details

        """

        table_name = "grant_reviews"
        try:
            with psycopg2.connect(self.vector_db.db_url) as conn:
                with conn.cursor() as cur:
                    query = """
                    SELECT 
                        id,
                        name,
                        content,
                        meta_data,
                        created_at,
                        usage,
                        filters
                    FROM {} 
                    WHERE meta_data->>'user_id' = %s 
                    ORDER BY created_at DESC
                    """.format(table_name)
                    
                    cur.execute(query, (user_id,))
                    reviews = cur.fetchall()

                    formatted_reviews = []
                    for review in reviews:
                        formatted_review = {
                            "id": review[0],
                            "name": review[1],
                            "content": review[2],
                            "meta_data": review[3],
                            "created_at": review[4].isoformat() if review[4] else None,
                            "usage": review[5],
                            "filters": review[6]
                        }
                        formatted_reviews.append(formatted_review)

            logger.info(f"Retrieved {len(formatted_reviews)} reviews for user {user_id}")
            return formatted_reviews

        except Exception as e:
            logger.error(f"Error retrieving reviews for user {user_id}: {str(e)}")
            raise

    async def get_latest_review(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent review for a user.
        
        Args:
            user_id (str): The applicant's user ID

        Returns:
            Optional[Dict]: Most recent review or None if not found
        """
        reviews = await self.get_reviews(user_id)
        return reviews[0] if reviews else None
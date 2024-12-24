import logging
import json
import hashlib
from typing import List, Optional, Dict, Any
import psycopg2
from phi.knowledge.agent import AgentKnowledge
from phi.vectordb.pgvector import PgVector
from utils.llm_helper import get_embedder

# Setup logging
logger = logging.getLogger(__name__)

class CustomKnowledgeBase(AgentKnowledge):
    """Knowledge base for managing grant reviews."""

    def __init__(self, sources: List[AgentKnowledge], vector_db: PgVector):
        super().__init__(sources=sources, vector_db=vector_db)

    async def add_review(self, user_id: str, application_content: Dict[str, Any], review_content: str):
        """
        Add a grant review to the knowledge base.
        
        Args:
            user_id (str): The applicant's user ID
            application_content (Dict): The original application content
            review_content (str): The review content/feedback
        """
        try:
            # Get embedding
            embedder = get_embedder()
            embedding = embedder.get_embedding(review_content)
            
            # Generate content hash
            content_hash = hashlib.md5(review_content.encode()).hexdigest()
            
            # Prepare metadata
            meta_data = {
                "user_id": user_id,
                "application_id": application_content[0]['id'] if application_content else None,
                "application_date": application_content[0]['created_at'] if application_content else None,
                "review_type": "grant_review"
            }

            # Create connection and insert review
            conn = psycopg2.connect(self.vector_db.db_url)
            cur = conn.cursor()

            query = """
            INSERT INTO ai.grant_reviews (
                id,
                name,
                content,
                meta_data,
                embedding,
                document_type,
                content_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """
            
            values = (
                content_hash,                      # id
                f"Grant Review - {user_id}",       # name
                review_content,                    # content
                json.dumps(meta_data),             # meta_data
                embedding,                         # embedding
                "grant_review",                    # document_type
                content_hash                       # content_hash
            )
            
            cur.execute(query, values)
            conn.commit()
            
            cur.close()
            conn.close()
                
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
        try:
            conn = psycopg2.connect(self.vector_db.db_url)
            cur = conn.cursor()

            query = """
            SELECT 
                id,
                name,
                content,
                meta_data,
                created_at
            FROM ai.grant_reviews 
            WHERE meta_data->>'user_id' = %s 
            ORDER BY created_at DESC
            """
            
            cur.execute(query, (user_id,))
            reviews = cur.fetchall()

            formatted_reviews = []
            for review in reviews:
                formatted_review = {
                    "id": review[0],
                    "name": review[1],
                    "content": review[2],
                    "meta_data": review[3],
                    "created_at": review[4].isoformat() if review[4] else None
                }
                formatted_reviews.append(formatted_review)

            cur.close()
            conn.close()

            logger.info(f"Retrieved {len(formatted_reviews)} reviews for user {user_id}")
            return formatted_reviews

        except Exception as e:
            logger.error(f"Error retrieving reviews for user {user_id}: {str(e)}")
            raise

    async def get_latest_review(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent grant review for a user.
        
        Args:
            user_id (str): The applicant's user ID

        Returns:
            Optional[Dict]: The latest review or None if not found
        """
        try:
            reviews = await self.get_reviews(user_id)
            return reviews[0] if reviews else None
        except Exception as e:
            logger.error(f"Error retrieving latest review for user {user_id}: {str(e)}")
            return None
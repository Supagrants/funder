from dataclasses import dataclass
from typing import Optional, List, Dict, Any
import logging
from datetime import datetime

from phi.agent import Agent, RunResponse, AgentMemory
from phi.memory.db.postgres import PgMemoryDb
from phi.storage.agent.postgres import PgAgentStorage
from phi.tools.duckduckgo import DuckDuckGo

from chat import knowledge
from chat.token_limit_agent import TokenLimitAgent
from config import POSTGRES_CONNECTION, MAX_HISTORY
from utils.llm_helper import get_llm_model
from tools.github_tools import GithubCommitStats
from tools.perplexity_tools import PerplexitySearch

# Constants
ABOUT = """I am a Grant Application Assistant specializing in helping users complete funding applications. I analyze project details and provide guidance for Solana grant applications, ensuring applications are complete, compelling, and properly evaluated."""

BACKGROUND = """I help evaluate grant applications by analyzing:

Core Application Components (40 points):
- Project Fundamentals (15 points):
  * Project Name and Description
  * Website and Online Presence
  * Location and Contact Information
  * Solana Integration

- Technical Infrastructure (25 points):
  * GitHub Repository Quality
  * Technical Architecture
  * Development Progress
  * Open Source Status

Project Impact & Innovation (30 points):
- Market & Innovation (15 points):
  * Problem Solution Fit
  * Market Opportunity
  * Technical Innovation

- Public Good Impact (15 points):
  * Community Benefit
  * Ecosystem Contribution
  * Accessibility

Team & Execution (30 points):
- Team Capability (15 points):
  * Technical Expertise
  * Track Record
  * Team Completeness

- Implementation Plan (15 points):
  * Budget Allocation
  * Development Roadmap
  * Success Metrics"""

@dataclass
class ApplicationContext:
    """Data class to store application context information"""
    user_id: str
    chat_id: str
    message: str
    review_history: Optional[List[Dict[str, Any]]] = None
    is_new_application: bool = False

class GrantReviewAgent:
    """Grant Review Agent for evaluating Solana grant applications"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        
    async def _create_context(self, msg: str, user_id: str) -> str:
        """Create review context based on message type"""
        if "New Grant Application Received" in msg:
            return f"""
            New Grant Application Review:
            
            Applicant ID: {user_id}
            Application Content:
            {msg}

            Please evaluate this application based on:
            1. Technical Feasibility
            2. Team Capability
            3. Market Impact
            4. Public Good Value
            5. Resource Requirements
            """
        else:
            review_history = await knowledge.knowledge_base.get_reviews(user_id)
            return f"""
            Previous Reviews:
            {review_history}

            Current Query:
            {msg}
            """

    def _initialize_agent(self, user_id: str, chat_id: str) -> TokenLimitAgent:
        """Initialize the token limit agent with necessary configuration"""
        return TokenLimitAgent(
            name="Grant Review Agent",
            model=get_llm_model(),
            session_id=f"grant_review_{user_id}_{chat_id}",
            user_id=user_id,
            memory=AgentMemory(
                db=PgMemoryDb(
                    table_name="grant_agent_memory",
                    db_url=POSTGRES_CONNECTION
                ),
                create_user_memories=True,
                create_session_summary=True,
                num_memories=10,
            ),
            storage=PgAgentStorage(
                table_name="grant_agent_sessions",
                db_url=POSTGRES_CONNECTION
            ),
            num_history_responses=MAX_HISTORY,
            description=f"{ABOUT}\n\nBackground Information:\n{BACKGROUND}",
            add_datetime_to_instructions=True,
            add_history_to_messages=True,
            read_chat_history=True,
            knowledge=knowledge.knowledge_base,
            search_knowledge=True,
            tools=[
                GithubCommitStats(),
                PerplexitySearch()
            ],
            telemetry=False,
        )

    async def next_action(
        self,
        msg: str,
        user_id: str,
        chat_id: str,
        reply_function: Optional[callable] = None,
        processing_id: Optional[str] = None
    ) -> str:
        """
        Process the next action for grant review
        
        Args:
            msg: Input message
            user_id: User identifier
            chat_id: Chat session identifier
            reply_function: Optional callback for replies
            processing_id: Optional processing identifier
            
        Returns:
            str: Response content
        """
        self.logger.info(f"Starting grant review for user {user_id} with message: {msg[:50]}...")

        try:
            # Create context
            context = await self._create_context(msg, user_id)
            
            # Initialize agent
            agent = self._initialize_agent(user_id, chat_id)
            
            # Process review
            self.logger.info("Processing grant review with context")
            response: RunResponse = agent.run(context)
            self.logger.info(f"Review response generated for user {user_id}")

            # Save review if new application
            if "New Grant Application Received" in msg:
                await knowledge.knowledge_base.add_review(
                    user_id=user_id,
                    application_content=msg,
                    review_content=response.get_content_as_string()
                )

            # Handle reply callback
            if reply_function:
                await reply_function(response.get_content_as_string())

            return response.get_content_as_string()

        except Exception as e:
            self.logger.error(f"Error during grant review for user {user_id}: {str(e)}")
            raise
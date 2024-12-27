from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
import logging
from datetime import datetime
import json

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

# Constants remain the same as before
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
class ApplicationData:
    """Structured application data"""
    id: str
    name: str
    content: str
    meta_data: Dict[str, Any]
    document_type: str
    created_at: str

@dataclass
class ApplicationContext:
    """Data class to store application context information"""
    user_id: str
    chat_id: str
    message: str
    application_data: Optional[ApplicationData] = None
    review_history: Optional[List[Dict[str, Any]]] = None
    is_new_application: bool = False

class GrantReviewAgent:
    """Grant Review Agent for evaluating Solana grant applications"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _parse_application_data(self, msg: str) -> Optional[ApplicationData]:
        """Parse application data from message"""
        try:
            # Extract JSON-like content from the message
            start_idx = msg.find('{')
            end_idx = msg.rfind('}') + 1
            if start_idx == -1 or end_idx == 0:
                return None
                
            json_str = msg[start_idx:end_idx]
            data = json.loads(json_str)
            
            return ApplicationData(
                id=data.get('id', ''),
                name=data.get('name', ''),
                content=data.get('content', ''),
                meta_data=data.get('meta_data', {}),
                document_type=data.get('document_type', ''),
                created_at=data.get('created_at', '')
            )
        except Exception as e:
            self.logger.error(f"Error parsing application data: {str(e)}")
            return None

    def _extract_application_sections(self, content: str) -> Dict[str, Any]:
        """Extract structured sections from application content"""
        sections = {
            "project_name": "",
            "website": "",
            "location": "",
            "contact_details": {},
            "solana_account": "",
            "funding_category": "",
            "project_description": "",
            "funding_amount": "",
            "open_source": None,
            "budget": {},
            "metrics": {},
            "funding_status": "",
            "team": {},
            "competitive_analysis": "",
            "public_good_impact": "",
            "technical_requirements": {}
        }
        
        # Add section extraction logic here
        try:
            # Extract project name
            if "Company/Project Name:" in content:
                sections["project_name"] = content.split("Company/Project Name:")[1].split("\n")[0].strip()
            
            # Extract project description
            if "Project Description and Vision:" in content:
                sections["project_description"] = content.split("Project Description and Vision:")[1].split("\n\n")[0].strip()
            
            # Add more section extractions as needed
            
        except Exception as e:
            self.logger.error(f"Error extracting sections: {str(e)}")
            
        return sections
        
    async def _create_context(self, msg: str, user_id: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Create review context based on message type"""
        structured_data = None
        
        if "New Grant Application Received" in msg:
            app_data = self._parse_application_data(msg)
            if app_data:
                structured_data = self._extract_application_sections(app_data.content)
                context = f"""
                New Grant Application Review:
                
                Applicant ID: {user_id}
                Application ID: {app_data.id}
                Submission Date: {app_data.created_at}
                
                Application Content:
                {app_data.content}

                Please evaluate this application based on:
                1. Technical Feasibility (25 points)
                2. Team Capability (15 points)
                3. Market Impact (15 points)
                4. Public Good Value (15 points)
                5. Resource Requirements (15 points)
                
                Provide a structured evaluation following the scoring rubric in the background information.
                """
            else:
                context = f"Error: Unable to parse application data from message: {msg[:100]}..."
        else:
            review_history = await knowledge.knowledge_base.get_reviews(user_id)
            context = f"""
            Previous Reviews:
            {review_history}

            Current Query:
            {msg}
            """
            
        return context, structured_data

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
        """Process the next action for grant review"""
        self.logger.info(f"Starting grant review for user {user_id} with message: {msg[:50]}...")

        try:
            # Create context and get structured data
            context, structured_data = await self._create_context(msg, user_id)
            
            # Initialize agent
            agent = self._initialize_agent(user_id, chat_id)
            
            # Process review
            self.logger.info("Processing grant review with context")
            response: RunResponse = agent.run(context)
            response_content = response.get_content_as_string()
            
            # Save review if new application
            if "New Grant Application Received" in msg and structured_data:
                await knowledge.knowledge_base.add_review(
                    user_id=user_id,
                    application_content=msg,
                    review_content=response_content,
                    structured_data=structured_data
                )

            # Handle reply callback
            if reply_function:
                await reply_function(response_content)

            return response_content

        except Exception as e:
            error_msg = f"Error during grant review for user {user_id}: {str(e)}"
            self.logger.error(error_msg)
            if reply_function:
                await reply_function(f"An error occurred while processing the application: {str(e)}")
            raise
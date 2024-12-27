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
ABOUT = """I am a Grant Application Assistant that evaluates Solana grant applications. I analyze available project details and provide comprehensive reviews based on provided information, focusing on technical feasibility, innovation, and ecosystem impact. I evaluate what is presented without requesting additional information."""

BACKGROUND = """I evaluate grant applications using the following scoring framework, assessing only the information provided:

            Core Application Components (40 points):
            - Project Fundamentals (15 points):
            * Project Name and Description (5 points)
            * Website and Online Presence (3 points)
            * Location and Contact Information (2 points)
            * Solana Integration (5 points)

            - Technical Infrastructure (25 points):
            * GitHub Repository Quality (7 points)
            * Technical Architecture (7 points)
            * Development Progress (6 points)
            * Open Source Status (5 points)

            Project Impact & Innovation (30 points):
            - Market & Innovation (15 points):
            * Problem Solution Fit (5 points)
            * Market Opportunity (5 points)
            * Technical Innovation (5 points)

            - Public Good Impact (15 points):
            * Community Benefit (5 points)
            * Ecosystem Contribution (5 points)
            * Accessibility (5 points)

            Team & Execution (30 points):
            - Team Capability (15 points):
            * Technical Expertise (5 points)
            * Track Record (5 points)
            * Team Completeness (5 points)

            - Implementation Plan (15 points):
            * Budget Allocation (5 points)
            * Development Roadmap (5 points)
            * Success Metrics (5 points)

            Review Guidelines:
            1. Evaluate only based on information provided in the application
            2. Score each category based on available information
            3. If information is missing for a category, score as 0 points
            4. Provide specific feedback on strengths and areas that lack information
            5. Focus on constructive evaluation of what is presented
            6. Generate final score based on complete evaluation
            7. Include brief justification for each scoring category

            Output Format:
            {
            "scores": {
                "project_fundamentals": {"score": X, "max": 15, "notes": "..."},
                "technical_infrastructure": {"score": X, "max": 25, "notes": "..."},
                "market_innovation": {"score": X, "max": 15, "notes": "..."},
                "public_good_impact": {"score": X, "max": 15, "notes": "..."},
                "team_capability": {"score": X, "max": 15, "notes": "..."},
                "implementation_plan": {"score": X, "max": 15, "notes": "..."}
            },
            "total_score": X,
            "max_score": 100,
            "summary": "Overall evaluation summary...",
            "key_strengths": ["strength1", "strength2"...],
            "key_gaps": ["gap1", "gap2"...]
            }"""


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
            # Core Application Components
            "project_fundamentals": {
                "name": "",
                "website": "",
                "location": "",
                "solana_integration": ""
            },
            "technical_infrastructure": {
                "github": "",
                "architecture": "",
                "progress": "",
                "open_source": ""
            },
            # Project Impact & Innovation
            "market_innovation": {
                "problem_solution": "",
                "market_opportunity": "",
                "innovation": ""
            },
            "public_good_impact": {
                "community_benefit": "",
                "ecosystem_contribution": "",
                "accessibility": ""
            },
            # Team & Execution
            "team_capability": {
                "expertise": "",
                "track_record": "",
                "completeness": ""
            },
            "implementation_plan": {
                "budget": "",
                "roadmap": "",
                "metrics": ""
            }
        }
        
        try:
            # Project Fundamentals
            if "Company/Project Name:" in content:
                sections["project_fundamentals"]["name"] = content.split("Company/Project Name:")[1].split("\n")[0].strip()
            
            if "Website URL:" in content:
                sections["project_fundamentals"]["website"] = content.split("Website URL:")[1].split("\n")[0].strip()
                
            if "Location Information" in content:
                sections["project_fundamentals"]["location"] = content.split("Location Information")[1].split("\n")[0].strip()
                
            if "Solana Integration:" in content:
                sections["project_fundamentals"]["solana_integration"] = content.split("Solana Integration:")[1].split("\n")[0].strip()

            # Technical Infrastructure
            if "Project GitHub Repository:" in content:
                sections["technical_infrastructure"]["github"] = content.split("Project GitHub Repository:")[1].split("\n")[0].strip()
                
            if "Technical Architecture:" in content:
                sections["technical_infrastructure"]["architecture"] = content.split("Technical Architecture:")[1].split("\n\n")[0].strip()
                
            if "Development Progress:" in content:
                sections["technical_infrastructure"]["progress"] = content.split("Development Progress:")[1].split("\n\n")[0].strip()
                
            if "Open Source Status:" in content:
                sections["technical_infrastructure"]["open_source"] = content.split("Open Source Status:")[1].split("\n")[0].strip()

            # Market & Innovation
            if "Problem Solution Fit:" in content:
                sections["market_innovation"]["problem_solution"] = content.split("Problem Solution Fit:")[1].split("\n\n")[0].strip()
                
            if "Market Opportunity:" in content:
                sections["market_innovation"]["market_opportunity"] = content.split("Market Opportunity:")[1].split("\n\n")[0].strip()
                
            if "Technical Innovation:" in content:
                sections["market_innovation"]["innovation"] = content.split("Technical Innovation:")[1].split("\n\n")[0].strip()

            # Public Good Impact
            if "Community Benefit:" in content:
                sections["public_good_impact"]["community_benefit"] = content.split("Community Benefit:")[1].split("\n\n")[0].strip()
                
            if "Ecosystem Contribution:" in content:
                sections["public_good_impact"]["ecosystem_contribution"] = content.split("Ecosystem Contribution:")[1].split("\n\n")[0].strip()
                
            if "Accessibility:" in content:
                sections["public_good_impact"]["accessibility"] = content.split("Accessibility:")[1].split("\n\n")[0].strip()

            # Team Capability
            if "Team Qualifications:" in content:
                sections["team_capability"]["expertise"] = content.split("Team Qualifications:")[1].split("\n\n")[0].strip()
                sections["team_capability"]["track_record"] = sections["team_capability"]["expertise"]  # Often combined in Team Qualifications
                sections["team_capability"]["completeness"] = sections["team_capability"]["expertise"]  # Often combined in Team Qualifications

            # Implementation Plan
            if "Budget Proposal:" in content:
                sections["implementation_plan"]["budget"] = content.split("Budget Proposal:")[1].split("\n\n")[0].strip()
                
            if "Development Roadmap:" in content:
                sections["implementation_plan"]["roadmap"] = content.split("Development Roadmap:")[1].split("\n\n")[0].strip()
                
            if "Success Metrics:" in content:
                sections["implementation_plan"]["metrics"] = content.split("Success Metrics:")[1].split("\n\n")[0].strip()
                
        except Exception as e:
            self.logger.error(f"Error extracting sections: {str(e)}")
            
        return sections
        
    async def _create_context(self, msg: str, user_id: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Create review context based on message type with tool integration"""
        structured_data = None
        
        if "New Grant Application Received" in msg:
            app_data = self._parse_application_data(msg)
            if app_data:
                structured_data = self._extract_application_sections(app_data.content)
                
                # Extract GitHub repository if available
                github_analysis = ""
                if structured_data["technical_infrastructure"]["github"]:
                    try:
                        repo_url = structured_data["technical_infrastructure"]["github"]
                        # Extract owner/repo format from URL
                        repo_parts = repo_url.replace("https://github.com/", "").replace(".git", "").split('/')
                        if len(repo_parts) >= 2:
                            repo_name = f"{repo_parts[-2]}/{repo_parts[-1]}"
                            github_tool = GithubCommitStats()
                            github_stats_str = await github_tool.get_monthly_commit_count(repo_name)
                            github_stats = json.loads(github_stats_str)
                            
                            if 'error' not in github_stats:
                                github_analysis = f"""
                                GitHub Repository Analysis:
                                - Repository: {github_stats['repository']}
                                - Commit Activity (Last 30 Days): {github_stats['commit_count']} commits
                                - Analysis Period: {github_stats['since']}
                                """
                            else:
                                github_analysis = f"\nGitHub Analysis: Repository analysis failed - {github_stats['error']}"
                    except Exception as e:
                        self.logger.error(f"Error analyzing GitHub repository: {str(e)}")
                        github_analysis = "\nGitHub Analysis: Unable to analyze repository activity"

                # Perform market research using Perplexity
                market_analysis = ""
                if structured_data["market_innovation"]["problem_solution"]:
                    try:
                        search_tool = PerplexitySearch()
                        market_query = f"Analyze market opportunity and competition for: {structured_data['market_innovation']['problem_solution']}. Focus on market size, competitors, and growth potential."
                        market_results = await search_tool.perplexity_search(market_query)
                        
                        market_analysis = f"""
                            Market Research Analysis:
                            {market_results}
                            """
                    except Exception as e:
                        self.logger.error(f"Error performing market research: {str(e)}")
                        market_analysis = "\nMarket Analysis: Unable to retrieve market insights"

                context = f"""
            New Grant Application Review:

            Applicant ID: {user_id}
            Application ID: {app_data.id}
            Submission Date: {app_data.created_at}

            Application Content:
            {app_data.content}

            Technical Analysis:{github_analysis}

            Market Research:{market_analysis}

            Please evaluate this application based on the scoring rubric in the background information:

            Core Application Components (40 points):
            - Project Fundamentals (15 points)
            - Technical Infrastructure (25 points)

            Project Impact & Innovation (30 points):
            - Market & Innovation (15 points)
            - Public Good Impact (15 points)

            Team & Execution (30 points):
            - Team Capability (15 points)
            - Implementation Plan (15 points)

            Evaluation Notes:
            1. For Technical Infrastructure scoring:
            - Consider the GitHub commit activity as an indicator of development progress
            - High activity (>30 commits/month) suggests active development
            - Low activity (<10 commits/month) may indicate limited progress

            2. For Market & Innovation scoring:
            - Use the market research analysis to validate market opportunity claims
            - Consider market size and competition information
            - Evaluate growth potential based on market insights

            Generate your evaluation in the required JSON format with specific notes for each category.
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
            print("Processing grant review with context")
            response: RunResponse = agent.run(context)
            response_content = response.get_content_as_string()
            print(response_content)
            # Save review if new application
            if "New Grant Application Received" in msg and structured_data:
                await knowledge.knowledge_base.add_review(
                    user_id=user_id,
                    application_content=msg,
                    review_content=response_content
                )

            print("Saving review")
            # Handle reply callback
            if reply_function:
                await reply_function(response_content)

            print("Returning response")
            return response_content

        except Exception as e:
            error_msg = f"Error during grant review for user {user_id}: {str(e)}"
            self.logger.error(error_msg)
            if reply_function:
                await reply_function(f"An error occurred while processing the application: {str(e)}")
            raise
import logging
from phi.agent import Agent, RunResponse, AgentMemory
from phi.memory.db.postgres import PgMemoryDb
from phi.storage.agent.postgres import PgAgentStorage
from phi.tools.duckduckgo import DuckDuckGo

from chat import prompts, knowledge
from chat.token_limit_agent import TokenLimitAgent
from chat.prompts.prompts_medium import ABOUT, BACKGROUND
from config import POSTGRES_CONNECTION, MAX_HISTORY
from utils.llm_helper import get_llm_model
from tools.github_tools import GithubCommitStats
from tools.perplexity_tools import PerplexitySearch

# Setup logging
logger = logging.getLogger(__name__)

async def next_action(msg: str, user_id: str, chat_id: str, mongo, reply_function=None, processing_id=None):
    logger.info(f"Starting grant review for user {user_id} with message: {msg[:50]}...")

    try:
        # Parse application data if it's a new submission
        if "New Grant Application Received" in msg:
            try:
                # Get application details from message
                application_data = await knowledge.knowledge_base.get_application_data(msg)
                
                # Create review context
                context = f"""
                New Grant Application Review:
                
                Applicant ID: {user_id}
                Application Content:
                {application_data}

                Please evaluate this application based on:
                1. Technical Feasibility
                2. Team Capability
                3. Market Impact
                4. Public Good Value
                5. Resource Requirements
                """
            except Exception as e:
                logger.error(f"Error parsing application data: {str(e)}")
                context = msg
        else:
            # Get existing review history
            try:
                review_history = await knowledge.knowledge_base.get_reviews(user_id)
                context = f"""
                Previous Reviews:
                {review_history}

                Current Query:
                {msg}
                """
            except Exception as e:
                logger.error(f"Error retrieving review history: {str(e)}")
                context = msg

        agent = TokenLimitAgent(
            name="Grant Review Agent",
            model=get_llm_model(),
            session_id=f"grant_review_{user_id}_{chat_id}",
            user_id=user_id,
            memory=AgentMemory(
                db=PgMemoryDb(table_name="grant_agent_memory", db_url=POSTGRES_CONNECTION), 
                create_user_memories=True, 
                create_session_summary=True,
                num_memories=10,
            ),
            storage=PgAgentStorage(table_name="grant_agent_sessions", db_url=POSTGRES_CONNECTION),
            num_history_responses=MAX_HISTORY,
            description=f"{ABOUT}\n\nBackground Information:\n{BACKGROUND}",
            add_datetime_to_instructions=True,
            add_history_to_messages=True,
            read_chat_history=True,
            knowledge=knowledge.knowledge_base,
            search_knowledge=True,
            tools=[
                GithubCommitStats(),  # For reviewing code contributions
                PerplexitySearch()    # For market research
            ],
            telemetry=False,
        )

        logger.info("Processing grant review with context")
        response: RunResponse = agent.run(context)
        logger.info(f"Review response generated for user {user_id}")

        # Save the review
        if "New Grant Application Received" in msg:
            await knowledge.knowledge_base.add_review(
                user_id=user_id,
                application_content=application_data,
                review_content=response.get_content_as_string()
            )

        if reply_function:
            await reply_function(response.get_content_as_string())

    except Exception as e:
        logger.error(f"Error during grant review for user {user_id}: {str(e)}")
        raise
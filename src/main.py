"""
Primary Author(s)
Juan C. Dorado: https://github.com/jdorado/
Ben Lai: https://github.com/laichunpongben/
"""
# main.py

import traceback
import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict
import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks
from pydantic import BaseModel
from telegram.ext import Application
from dotenv import load_dotenv
import json
from chat.router import GrantReviewAgent
from utils.telegram_helper import TelegramHelper
from utils.logging_helper import setup_logging
from config import TELEGRAM_BOT, TELEGRAM_BOT_HANDLE
from telegram import ReplyKeyboardMarkup

load_dotenv()

# Setup logging
logger = setup_logging(log_file='logs/main.log', level=logging.INFO)


# Create Pydantic model for application data
class ApplicationData(BaseModel):
    application: str  # This will hold the stringified application JSON

class TelegramUpdate(BaseModel):
    update_id: int
    message: dict

class ApiCall(BaseModel):
    token: str


# Initialize Application with increased connection pool size
application = (
    Application.builder()
    .token(TELEGRAM_BOT)
    .connection_pool_size(100)
    .build()
)

# Initialize TelegramHelper with the Application's Bot instance
tg = TelegramHelper(application.bot)

# Initialize MongoDB without connecting on startup


class TelegramUpdate(BaseModel):
    update_id: int
    message: dict


class ApiCall(BaseModel):
    token: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for FastAPI.
    Handles startup and shutdown events.
    """
    print("Starting up the application.")
    try:
        logger.info("Starting up the application.")

        # Properly start the Telegram bot
        await application.initialize()
        await application.start()
        yield
    finally:
        logger.info("Shutting down the application.")
        await application.stop()
        await application.shutdown()


# Assign the lifespan handler to the FastAPI app
app = FastAPI(lifespan=lifespan)



@app.api_route("/submit/", methods=["GET", "POST"])
async def process_application(request: Request, application: ApplicationData = None):
    try:
        if request.method == "GET":
            return {"status": "success", "message": "GET request received", "data": None}

        if request.method == "POST":
            logger.info("POST request received")

            # Log the raw application object
            logger.info(f"Raw application data: {application}")

            # Parse the stringified application data
            app_data = json.loads(application.application)
            logger.info(f"Parsed application data: {app_data}")

            # Extract user information
            user_id = app_data['meta_data'].get('user_id') if 'meta_data' in app_data else None
            original_chat_id = app_data['meta_data'].get('chat_id') if 'meta_data' in app_data else None
            message_id = app_data.get('id')

            funder_chat_id = 1002322529093  # Hardcoded funder's chat ID
            logger.info(f"User ID: {user_id}, Original Chat ID: {original_chat_id}, Funder Chat ID: {funder_chat_id}, Message ID: {message_id}")

            if not user_id:
                error_msg = "Missing user_id in application"
                logger.error(error_msg)
                await notify_funder_error(funder_chat_id, error_msg, app_data)
                return {"status": "error", "message": "Invalid application data"}

            # Format application text for funder
            text = format_application_text(app_data, user_id, message_id)
            logger.info(f"Formatted text for next action: {text}")

            try:
                # Define a reply function for the funder
                async def telegram_reply(msg, reply_markup=None):
                    await tg.send_message_with_retry(funder_chat_id, msg, reply_markup=reply_markup)

                router = GrantReviewAgent()
                # Call the router's next_action function for the funder
                review_result = await router.next_action(
                    text,
                    user_id,
                    funder_chat_id,  # Send to funder's chat
                    reply_function=telegram_reply,
                    processing_id=message_id
                )

                if not review_result:
                    raise Exception("Review generation failed - empty response")

                return {"status": "success", "message": "Application received and review generated"}

            except Exception as review_error:
                error_msg = f"⚠️ Error Generating Review:\n\nApplication ID: {message_id}\nError: {str(review_error)}"
                logger.error(f"Review generation failed: {str(review_error)}")
                await notify_funder_error(funder_chat_id, error_msg, app_data)
                return {"status": "error", "message": "Failed to generate review"}

    except json.JSONDecodeError as e:
        error_msg = f"Failed to parse application JSON: {str(e)}"
        logger.error(error_msg)
        await notify_funder_error(funder_chat_id, error_msg, None)
        return {"status": "error", "message": "Invalid application format"}
    except Exception as e:
        error_msg = f"Error processing application: {str(e)}"
        logger.error(error_msg)
        await notify_funder_error(funder_chat_id, error_msg, None)
        return {"status": "error", "message": "Internal server error"}

async def notify_funder_error(funder_chat_id: int, error_message: str, app_data: Optional[Dict] = None):
    """Send error notification to funder's chat"""
    try:
        error_text = f"""
    ⚠️ Application Processing Error

    Error Details:
    {error_message}

    """
        if app_data:
                error_text += f"""
    Application Information:
    - ID: {app_data.get('id', 'N/A')}
    - Name: {app_data.get('name', 'N/A')}
    - Type: {app_data.get('document_type', 'N/A')}
    - Created: {app_data.get('created_at', 'N/A')}
    """

        await tg.send_message_with_retry(funder_chat_id, error_text)
    except Exception as e:
        logger.error(f"Failed to send error notification to funder: {str(e)}")

def format_application_text(app_data: Dict, user_id: str, message_id: str) -> str:
    """Format application text for review"""
    return (
        f"📝 New Grant Application Received\n\n"
        f"From User ID: {user_id}\n"
        f"Application ID: {message_id}\n"
        f"Document: {app_data['name']}\n"
        f"Content: {app_data['content']}\n"
        f"Created: {app_data['created_at']}\n"
        f"Type: {app_data['document_type']}\n"
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=6010,
        reload=True,
        log_config=None
    )

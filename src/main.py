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

import uvicorn
from fastapi import FastAPI, Request, BackgroundTasks
from pydantic import BaseModel
from telegram.ext import Application
from dotenv import load_dotenv
import json
from chat import router, knowledge
from utils.telegram_helper import TelegramHelper
from utils.logging_helper import setup_logging
from config import TELEGRAM_BOT, TELEGRAM_BOT_HANDLE
from telegram import ReplyKeyboardMarkup

load_dotenv()

# Setup logging
logger = setup_logging(log_file='logs/main.log', level=logging.INFO)

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



@app.post("/submit")
async def process_application(application: Application, background_tasks: BackgroundTasks):
    try:
        # Parse the stringified application data
        app_data = json.loads(application.application)
        
        # Extract user information
        user_id = app_data[0]['meta_data'].get('user_id') if app_data else None
        chat_id = 2322529093
        
        if not user_id or not chat_id:
            logger.error("Missing user_id or chat_id in application")
            return {"status": "error", "message": "Invalid application data"}

        async def telegram_reply(msg, reply_markup=None):
            await tg.send_message_with_retry(chat_id, msg, reply_markup=reply_markup)

        # Format application for review
        application_summary = []
        for item in app_data:
            application_summary.append(
                f"Document: {item['name']}\n"
                f"Content: {item['content'][:500]}...\n"  # First 500 chars
                f"Created: {item['created_at']}\n"
                f"Type: {item['document_type']}\n"
                f"---"
            )

        # Notify agent about new application
        message = (
            f"📝 New Grant Application Received\n\n"
            f"From User ID: {user_id}\n"
            f"Application Items: {len(app_data)}\n\n"
            f"Application Content:\n"
            f"{''.join(application_summary)}"
        )

        # Process with next_action
        await router.next_action(
            message, 
            user_id,
            chat_id,
            mongo=None,
            reply_function=telegram_reply,
            processing_id=None
        )

        return {"status": "success", "message": "Application received and being processed"}
        
    except json.JSONDecodeError:
        logger.error("Failed to parse application JSON")
        return {"status": "error", "message": "Invalid application format"}
    except Exception as e:
        logger.error(f"Error processing application: {str(e)}")
        return {"status": "error", "message": "Internal server error"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=6010,
        reload=True,
        log_config=None
    )

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
            # Respond with a simple message for GET requests
            return {"status": "success", "message": "GET request received", "data": None}

        if request.method == "POST":
            logger.info("POST request received")

            # Log the raw application object
            logger.info(f"Raw application data: {application}")

            # Parse the stringified application data
            app_data = json.loads(application.application)
            logger.info(f"Parsed application data: {app_data}")

            # Extract user information directly from the dictionary
            user_id = app_data['meta_data'].get('user_id') if 'meta_data' in app_data else None
            chat_id = 2322529093  # Funder's chat ID
            logger.info(f"User ID: {user_id}, Chat ID: {chat_id}")

            if not user_id or not chat_id:
                logger.error("Missing user_id or chat_id in application")
                return {"status": "error", "message": "Invalid application data"}

            # Format application for review
            application_summary = (
                f"Document: {app_data['name']}\n"
                f"Content: {app_data['content'][:500]}...\n"  # First 500 chars
                f"Created: {app_data['created_at']}\n"
                f"Type: {app_data['document_type']}\n"
                f"---"
            )
            logger.info(f"Application Summary: {application_summary}")

            # Return a success response
            return {
                "status": "success",
                "message": "Application received and being processed",
                "data": application_summary,
            }

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse application JSON: {str(e)}")
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

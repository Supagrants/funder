# token_limit_agent.py

import logging
from typing import Any, List, Optional, Tuple, Union, Dict
from collections import deque
from phi.model.message import Message
from phi.agent import Agent
from config import TOKEN_LIMIT, TOOL_MESSAGE_CHAR_TRUNCATE_LIMIT, MAX_HISTORY

# Setup logging
logger = logging.getLogger(__name__)

RESET_KEYWORD = '/reset'

class TokenLimitAgent(Agent):
    """
    An Agent that enforces a token limit on the messages sent to the model when first loading chat history.
    It truncates the content of the oldest 'tool' messages to the first 1000 characters
    until the total token count is within the specified limit.
    """

    def get_messages_for_run(
        self,
        *,
        message: Optional[Union[str, List, Dict, Message]] = None,
        audio: Optional[Any] = None,
        images: Optional[List[Any]] = None,
        videos: Optional[List[Any]] = None,
        messages: Optional[List[Union[Dict, Message]]] = None,
        **kwargs: Any,
    ) -> Tuple[Optional[Message], List[Message], List[Message]]:
        """
        Override the get_messages_for_run method to enforce a token limit by truncating
        the content of 'tool' messages until the total token count is within the limit.
        """
        # Call the superclass method to get the initial messages
        system_message, user_messages, messages_for_model = super().get_messages_for_run(
            message=message,
            audio=audio,
            images=images,
            videos=videos,
            messages=messages,
            **kwargs,
        )
            
        # Find the index of the last /reset message, ensuring to skip the system message
        reset_index = None
        for i in range(len(messages_for_model) - 1, -1, -1):  # Iterate in reverse order
            msg = messages_for_model[i]
            if msg.content is not None and RESET_KEYWORD in msg.content.lower() and msg.role != 'system':  # content: '@<id>: /reset'
                reset_index = i
                break

        # If we found a reset message, filter out all messages before it, but keep the system message
        if reset_index is not None:
            messages_for_model = [messages_for_model[0]] + messages_for_model[reset_index + 1:]
            logger.debug(f"Messages after last reset: {len(messages_for_model)} messages.")

        # Calculate the total approximate token count
        total_char_count = sum(len(msg.content) for msg in messages_for_model if msg.content)
        total_tokens = total_char_count // 4  # Approximate tokens

        logger.debug(f"Initial total tokens: {total_tokens}")

        # If within limit, return as is
        if total_tokens <= TOKEN_LIMIT:
            logger.debug("Total tokens within limit. No messages truncated.")
            return system_message, user_messages, messages_for_model

        # Identify all 'tool' messages in chronological order
        tool_messages = [msg for msg in messages_for_model if msg.role == 'tool']
        logger.debug(f"Number of 'tool' messages: {len(tool_messages)}")

        # Use a deque for efficient popping from the left (oldest messages)
        tool_messages_deque = deque(tool_messages)

        # Iterate and truncate the oldest 'tool' messages until within token limit
        while total_tokens > TOKEN_LIMIT and tool_messages_deque:
            oldest_tool_message = tool_messages_deque.popleft()

            if oldest_tool_message.content and len(oldest_tool_message.content) > TOOL_MESSAGE_CHAR_TRUNCATE_LIMIT:
                # Truncate the content to the first 1000 characters
                original_length = len(oldest_tool_message.content)
                truncated_content = oldest_tool_message.content[:TOOL_MESSAGE_CHAR_TRUNCATE_LIMIT]
                oldest_tool_message.content = truncated_content

                # Recalculate the token count reduction
                reduced_chars = original_length - len(truncated_content)
                total_char_count -= reduced_chars
                total_tokens = total_char_count // 3

                logger.debug(
                    f"Truncated a 'tool' message from {original_length} to {len(truncated_content)} characters. "
                    f"New total tokens: {total_tokens}"
                )
            else:
                logger.debug(
                    f"Skipped truncating a 'tool' message as it is already within the truncate limit."
                )

        if total_tokens > TOKEN_LIMIT:
            logger.warning(
                f"Unable to reduce token count to {TOKEN_LIMIT}. Current tokens: {total_tokens}"
            )
        else:
            logger.debug("Token limit enforced successfully through message truncation.")

        return system_message, user_messages, messages_for_model

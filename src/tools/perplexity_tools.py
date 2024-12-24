
import os
import json
from typing import Optional, Any
import requests
from phi.tools import Toolkit
from phi.utils.log import logger
from phi.agent import Agent


class PerplexitySearch(Toolkit):
    """
    A tool for searching using the Perplexity API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "llama-3.1-sonar-small-128k-online",
        max_tokens: Optional[int] = None,
        temperature: float = 0.2,
        top_p: float = 0.9,
        search_domain_filter = ["perplexity.ai"],
        return_images: bool = False,
        return_related_questions: bool = False,
        search_recency_filter: str = "month",
        top_k: int = 0,
        presence_penalty: int = 0,
        frequency_penalty: int = 1,
        base_url: str = "https://api.perplexity.ai/chat/completions",
    ):
        super().__init__(name="perplexity_search")
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.search_domain_filter = search_domain_filter
        self.return_images = return_images
        self.return_related_questions = return_related_questions
        self.search_recency_filter = search_recency_filter
        self.top_k = top_k
        self.presence_penalty = presence_penalty
        self.frequency_penalty = frequency_penalty
        self.base_url = base_url
        self.register(self.perplexity_search)

    def perplexity_search(self, query: str) -> str:
        """
        Searches Perplexity for a specified query.

        Args:
            query (str): The search term.

        Returns:
            A JSON-formatted string containing the search result.
        """
        logger.debug(f"Searching Perplexity for query: {query}")

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "Be precise and concise."
                },
                {
                    "role": "user",
                    "content": query
                }
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "search_domain_filter": self.search_domain_filter,
            "return_images": self.return_images,
            "return_related_questions": self.return_related_questions,
            "search_recency_filter": self.search_recency_filter,
            "top_k": self.top_k,
             "stream": False,
            "presence_penalty": self.presence_penalty,
            "frequency_penalty": self.frequency_penalty
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            result = response.text

            response_json = json.loads(result)
            content = response_json['choices'][0]['message']['content']




            return content
        except requests.exceptions.RequestException as e:
            logger.error(f"Error during Perplexity search: {e}")
            return json.dumps({"error": str(e)})


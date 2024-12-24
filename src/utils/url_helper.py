# utils/url_helper.py

import re
from typing import List, Optional
from urllib.parse import urlparse, urlunparse, quote, unquote
import logging

# Configure logger for this module
logger = logging.getLogger(__name__)

def is_valid_url(url: str) -> bool:
    """
    Validate the URL format.

    Args:
        url (str): The URL to validate.

    Returns:
        bool: True if valid, False otherwise.
    """
    logger.debug(f"Validating URL: '{url}'")
    # Comprehensive URL regex pattern with named groups
    url_regex = re.compile(
        r'^(?P<scheme>https?://)'  # scheme
        r'(?P<host>('
            r'(?P<domain>([A-Za-z0-9-]+\.)+[A-Za-z]{2,})'  # domain
            r'|'
            r'localhost'  # localhost
            r'|'
            r'\[(?P<ipv6>[A-Fa-f0-9:]+)\]'  # IPv6
        r'))'
        r'(?::(?P<port>\d{1,5}))?'  # optional port
        r'(?P<path>/\S*)?'  # optional path
        r'$', re.IGNORECASE
    )

    match = re.match(url_regex, url)
    if match:
        port = match.group('port')
        if port:
            try:
                port_num = int(port)
                if not (1 <= port_num <= 65535):
                    logger.debug(f"Invalid port number: {port_num}")
                    return False
            except ValueError:
                logger.debug(f"Port '{port}' is not a valid integer.")
                return False
        logger.debug(f"URL '{url}' is valid.")
        return True
    else:
        logger.debug(f"URL '{url}' is invalid.")
        return False

def extract_valid_urls(content: str, entity_urls: Optional[List[str]] = None) -> List[str]:
    """
    Extract and validate URLs from message content and message entities.

    Args:
        content (str): The text content of the message.
        entity_urls (Optional[List[str]]): List of URLs extracted from message entities.

    Returns:
        List[str]: A list of validated and cleaned URLs.
    """
    logger.debug(f"Extracting URLs from content: '{content[:50]}...'")
    potential_urls = []

    # Improved regex pattern to match full URLs, including IPv6 and ports
    url_pattern = re.compile(
        r'(?:(?<=\s)|(?<=^))'  # Positive lookbehind for space or start of string
        r'(?:https?://|www\.)?'  # Optional scheme
        r'(?:\[[A-Fa-f0-9:]+\]|localhost|(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,})'  # IPv6, localhost, or domain
        r'(?:\:\d{1,5})?'  # Optional port
        r'(?:/\S*)?',  # Optional path, query, fragment
        re.IGNORECASE
    )

    # Extract URLs using re.finditer to capture full matches
    regex_urls = [match.group(0) for match in url_pattern.finditer(content)]
    potential_urls.extend(regex_urls)
    logger.debug(f"URLs extracted via regex: {regex_urls}")

    # Incorporate URLs from message entities if provided
    if entity_urls:
        potential_urls.extend(entity_urls)
        logger.debug(f"URLs extracted from entities: {entity_urls}")

    # Initialize list to hold validated URLs
    extracted_urls = []

    for url in potential_urls:
        # Remove trailing punctuation
        cleaned_url = url.rstrip('.,;!?)"]\'')
        logger.debug(f"URL after stripping punctuation: '{cleaned_url}'")

        # If URL doesn't have a scheme, prepend 'https://'
        if not re.match(r'^https?://', cleaned_url, re.IGNORECASE):
            cleaned_url = 'https://' + cleaned_url
            logger.debug(f"URL after prepending scheme: '{cleaned_url}'")

        # Validate URL
        if is_valid_url(cleaned_url):
            # Additional check to ensure the URL is not part of an email
            pattern = re.escape(url)
            matches = list(re.finditer(pattern, content))
            skip = False
            for match_obj in matches:
                start_index = match_obj.start()
                if start_index > 0 and content[start_index - 1] == '@':
                    logger.debug(f"URL '{cleaned_url}' is part of an email and will be skipped.")
                    skip = True
                    break
            if skip:
                continue  # Skip URLs that are part of an email address
            extracted_urls.append(cleaned_url)
            logger.debug(f"Valid URL added: '{cleaned_url}'")
        else:
            logger.debug(f"Invalid URL skipped: '{cleaned_url}'")

    # Remove duplicates while preserving order
    unique_urls = list(dict.fromkeys(extracted_urls))
    logger.debug(f"Unique validated URLs: {unique_urls}")

    return unique_urls

def normalize_url(url: str) -> str:
    """
    Normalize URL to avoid duplication by:
    - Lowercasing the scheme and network location.
    - Removing default ports.
    - Removing fragments and query parameters.
    - Resolving redundant path segments.
    - Ensuring consistent trailing slashes.
    - Converting Unicode domain names to punycode.

    Args:
        url (str): The URL to normalize.

    Returns:
        str: Normalized URL as string.
    """
    try:
        logger.debug(f"Normalizing URL: '{url}'")
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Handle Internationalized Domain Names (IDN)
        if 'xn--' not in netloc:
            hostname = parsed.hostname.encode('idna').decode('ascii') if parsed.hostname else ''
            if parsed.port:
                netloc = f"{hostname}:{parsed.port}"
            else:
                netloc = hostname

        # Remove default ports
        if (scheme == 'http' and parsed.port == 80) or (scheme == 'https' and parsed.port == 443):
            netloc = parsed.hostname.encode('idna').decode('ascii') if parsed.hostname else netloc

        # Normalize path
        path = unquote(parsed.path)  # Decode percent-encoded characters
        path = re.sub(r'/+', '/', path)  # Replace multiple slashes with single slash
        path = re.sub(r'/\./', '/', path)  # Remove /./
        path = re.sub(r'/[^/]+/\.\./', '/', path)  # Remove /something/../
        path = re.sub(r'/$', '/', path)  # Ensure single trailing slash

        # Re-encode path
        path = quote(path, safe="/-_.~")

        # Reconstruct the URL without query and fragment
        normalized_url = urlunparse((scheme, netloc, path, '', '', ''))
        
        logger.debug(f"Normalized URL: Original='{url}' | Normalized='{normalized_url}'")
        return normalized_url
    except Exception as e:
        logger.error(f"Error normalizing URL '{url}': {e}")
        return url  # Return the original URL if normalization fails

def get_domain(url: str) -> str:
    """
    Extract the domain from a URL.

    Args:
        url (str): The URL to extract the domain from.

    Returns:
        str: The domain of the URL.
    """
    try:
        logger.debug(f"Extracting domain from URL: '{url}'")
        parsed = urlparse(url)
        domain = parsed.hostname.lower() if parsed.hostname else ''
        logger.debug(f"Extracted domain '{domain}' from URL '{url}'.")
        return domain
    except Exception as e:
        logger.error(f"Error extracting domain from URL '{url}': {e}")
        return ''

def strip_query_and_fragment(url: str) -> str:
    """
    Remove query parameters and fragments from a URL.

    Args:
        url (str): The URL to strip.

    Returns:
        str: The URL without query and fragment.
    """
    try:
        logger.debug(f"Stripping query and fragment from URL: '{url}'")
        parsed = urlparse(url)
        stripped_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        logger.debug(f"Stripped URL: Original='{url}' | Stripped='{stripped_url}'")
        return stripped_url
    except Exception as e:
        logger.error(f"Error stripping query and fragment from URL '{url}': {e}")
        return url

def ensure_trailing_slash(url: str) -> str:
    """
    Ensure that the URL ends with a trailing slash.

    Args:
        url (str): The URL to modify.

    Returns:
        str: The URL with a trailing slash.
    """
    if not url.endswith('/'):
        logger.debug(f"Adding trailing slash to URL '{url}'.")
        return url + '/'
    return url

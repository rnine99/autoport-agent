import asyncio
import logging
import os
from typing import Dict, List, Optional

from tavily import AsyncTavilyClient

from src.tools.utils.validation_utils import validate_image_url

logger = logging.getLogger(__name__)


class TavilySearchWrapper:
    """Tavily search API wrapper using official AsyncTavilyClient SDK."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        country: Optional[str] = None,
    ):
        self._api_key = api_key or os.environ.get("TAVILY_API_KEY", "")
        if not self._api_key:
            raise ValueError("TAVILY_API_KEY not provided or found in environment")
        self._client = AsyncTavilyClient(api_key=self._api_key)
        self._country = country

    async def raw_results(
        self,
        query: str,
        max_results: Optional[int] = 5,
        search_depth: Optional[str] = "advanced",
        include_domains: Optional[List[str]] = None,
        exclude_domains: Optional[List[str]] = None,
        include_answer: Optional[bool] = False,
        include_raw_content: Optional[bool] = False,
        include_images: Optional[bool] = False,
        include_image_descriptions: Optional[bool] = False,
        include_favicon: Optional[bool] = False,
        time_range: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        topic: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Dict:
        """Get results from the Tavily Search API"""
        # Determine country: method param > instance config
        effective_country = country or self._country

        # Build search kwargs
        kwargs = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_domains": include_domains or [],
            "exclude_domains": exclude_domains or [],
            "include_answer": include_answer,
            "include_raw_content": include_raw_content,
            "include_images": include_images,
            "include_image_descriptions": include_image_descriptions,
        }

        # Optional parameters
        if include_favicon:
            kwargs["include_favicon"] = include_favicon
        if time_range:
            kwargs["time_range"] = time_range
        if start_date:
            kwargs["start_date"] = start_date
        if end_date:
            kwargs["end_date"] = end_date
        if topic:
            kwargs["topic"] = topic

        # Country only valid for topic="general" (or no topic)
        if effective_country:
            if topic is None or topic == "general":
                kwargs["country"] = effective_country
            else:
                logger.warning(
                    f"country='{effective_country}' ignored: only valid for topic='general', "
                    f"but topic='{topic}' was specified"
                )

        return await self._client.search(**kwargs)

    async def clean_results_with_images(
        self, raw_results: Dict[str, List[Dict]]
    ) -> List[Dict]:
        """Clean results from Tavily Search API with async image validation.

        Uses lenient validation (HEAD request) to filter out inaccessible images
        for frontend display. This is different from strict validation used for
        OpenAI Vision API.

        Args:
            raw_results: Raw results from Tavily API

        Returns:
            List of cleaned results with only accessible images
        """
        results = raw_results["results"]
        clean_results = []

        # Process page results (no validation needed)
        for result in results:
            clean_result = {
                "type": "page",
                "title": result["title"],
                "url": result["url"],
                "content": result["content"],
                "score": result["score"],
            }
            if raw_content := result.get("raw_content"):
                clean_result["raw_content"] = raw_content
            clean_results.append(clean_result)

        # Process images with concurrent lenient validation
        images = raw_results.get("images", [])
        if not images:
            return clean_results

        logger.debug(f"Validating {len(images)} image(s) from Tavily (lenient mode for frontend)")

        async def validate_single_image(image) -> Optional[Dict]:
            """Helper to validate a single image and return cleaned result.

            Handles both string URLs and dict format for robustness:
            - String format: When include_image_descriptions=False (URL only)
            - Dict format: When include_image_descriptions=True (URL + description)
            """
            # Handle both string URLs and dict format
            if isinstance(image, str):
                url = image
                description = ""
            elif isinstance(image, dict):
                url = image.get("url", "")
                description = image.get("description", "")
            else:
                logger.warning(f"Unexpected image format: {type(image).__name__}, skipping")
                return None

            if not url:
                return None

            # Use lenient validation (HEAD request) with longer timeout for frontend display
            validated_url = await validate_image_url(url, timeout=10, strict=False)

            if validated_url:
                return {
                    "type": "image",
                    "image_url": validated_url,  # Use validated URL (possibly upgraded to HTTPS)
                    "image_description": description,
                }
            else:
                logger.debug(f"Skipping inaccessible image URL: {url}")
                return None

        # Run all validations concurrently
        validation_results = await asyncio.gather(
            *[validate_single_image(img) for img in images],
            return_exceptions=True
        )

        # Filter out None values and exceptions
        valid_images = []
        for result in validation_results:
            if result and not isinstance(result, Exception):
                valid_images.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Image validation error: {result}")

        # Add validated images to results
        clean_results.extend(valid_images)

        logger.debug(f"Image validation: {len(valid_images)}/{len(images)} images accessible")

        return clean_results

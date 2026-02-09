import asyncio
import io
import logging
import unicodedata
from typing import Any

import httpx
from django.conf import settings
from pypdf import PdfReader
from tavily import AsyncTavilyClient

logger = logging.getLogger(__name__)


class AdmissionStatusService:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self.search_delay = 1
        self.download_delay = 1
        self.language_search = "pt"
        self.http_client = http_client
        self.number_of_search_results = 3
        self.tavily_api_key = getattr(settings, "TAVILY_API_KEY", None)

    def _normalize_text(self, name: str) -> str:
        name = name.strip()

        normalized_name = unicodedata.normalize("NFKD", name)

        characters_without_accents = "".join(
            [
                character
                for character in normalized_name
                if not unicodedata.combining(character)
            ]
        )

        return characters_without_accents.lower()

    async def _search_for_pdfs(
        self, student_name: str, year: int
    ) -> tuple[str, list[dict[str, str]]]:
        query = f"{student_name} aprovado vestibular {year}"

        logger.info(f"Searching Tavily for PDFs with query: {query}")

        if not self.tavily_api_key:
            logger.error("Tavily API Key is not configured.")
            return query, []

        try:
            tavily_client = AsyncTavilyClient(api_key=self.tavily_api_key)

            response = await tavily_client.search(
                query,
                search_depth="advanced",
                max_results=self.number_of_search_results,
                include_answer=False,
                include_raw_content=False,
                include_images=False,
            )

            results = response.get("results", [])

            pdf_results = [
                {"url": item["url"], "title": item.get("title", "No Title Found")}
                for item in results
                if "url" in item and item.get("url", "").lower().endswith(".pdf")
            ]

            return query, pdf_results

        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return query, []

    async def _download_pdf(
        self,
        pdf_url: str,
    ) -> bytes | None:
        logger.info(f"Downloading PDF from {pdf_url}")

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

        try:
            response = await self.http_client.get(pdf_url, timeout=30, headers=headers)
            response.raise_for_status()

            return response.content
        except httpx.RequestError as error:
            logger.warning(f"Failed to download PDF {pdf_url}: {error}")

            return None
        except Exception as error:
            logger.warning(f"Unexpected error saving PDF {pdf_url}: {error}")

            return None

    async def _search_student_in_pdf(
        self, pdf_content: bytes, normalized_name: str
    ) -> bool:
        logger.info("Searching for student in in-memory PDF content")

        return await asyncio.to_thread(
            self._search_student_in_pdf_sync, pdf_content, normalized_name
        )

    def _search_student_in_pdf_sync(
        self, pdf_content: bytes, normalized_name: str
    ) -> bool:
        try:
            reader = PdfReader(io.BytesIO(pdf_content))

            for page in reader.pages:
                text = page.extract_text()

                if text and normalized_name in self._normalize_text(text):
                    return True

            return False
        except Exception as e:
            logger.warning(f"Error searching text in PDF content: {e}")

            return False

    async def check_admission_status(
        self, students_names: list[str], year: int
    ) -> list[dict[str, Any]]:
        found_results = []

        for student_name in students_names:
            normalized_student_name = self._normalize_text(student_name)

            logger.info(f"Processing student: {student_name} for year {year}")

            query_used, pdf_results = await self._search_for_pdfs(student_name, year)

            await asyncio.sleep(self.search_delay)

            if not pdf_results:
                logger.info(f'No PDFs found for "{student_name}" in {year}.')
                continue

            student_found_in_year = False
            for pdf_info in pdf_results:
                pdf_url = pdf_info["url"]
                search_title = pdf_info["title"]
                pdf_content = await self._download_pdf(pdf_url)

                await asyncio.sleep(self.download_delay)

                if not pdf_content:
                    logger.warning(f"Failed to download PDF from: {pdf_url}")
                    continue

                is_found = await self._search_student_in_pdf(
                    pdf_content, normalized_student_name
                )

                if is_found:
                    logger.info(
                        f'SUCCESS! Student "{student_name}" FOUND in PDF from {pdf_url}'
                    )

                    result = {
                        "student_name": student_name,
                        "normalized_name": normalized_student_name,
                        "year_found": year,
                        "search_query": query_used,
                        "pdf_url": pdf_url,
                        "search_title": search_title,
                    }

                    found_results.append(result)

                    student_found_in_year = True

            if not student_found_in_year:
                logger.info(
                    f'Student "{student_name}" not found in any list for the year {year}.'
                )

        logger.info("Search process finished!")
        return found_results

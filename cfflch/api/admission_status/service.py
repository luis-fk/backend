import asyncio
import io
import logging
from collections.abc import Callable, Coroutine
from typing import Any

import httpx
from asgiref.sync import sync_to_async
from django.conf import settings
from pypdf import PdfReader
from tavily import AsyncTavilyClient

from cfflch.api.admission_status.schemas import (
    StudentFoundResult,
    StudentNotFoundResult,
    StudentResult,
)
from cfflch.api.admission_status.utils import normalize_text
from cfflch.models import AdmissionPDF, AdmissionResult, ClassRoom

logger = logging.getLogger(__name__)

OnStudentDone = Callable[[list[StudentResult]], Coroutine[Any, Any, None]]


class AdmissionStatusService:
    def __init__(self, http_client: httpx.AsyncClient) -> None:
        self.search_delay = 1
        self.download_delay = 1
        self.language_search = "pt"
        self.http_client = http_client
        self.number_of_search_results = 5
        self.tavily_api_key = getattr(settings, "TAVILY_API_KEY", None)
        self.tavily_client = (
            AsyncTavilyClient(api_key=self.tavily_api_key)
            if self.tavily_api_key
            else None
        )

    async def _search_for_pdfs(
        self, student_name: str, year: int
    ) -> tuple[str, list[dict[str, str]]]:
        query = (
            f"{student_name} aprovado classificado"
            f" convocado selecionado vestibular {year}"
        )

        logger.info(f"Searching Tavily for PDFs with query: {query}")

        if not self.tavily_client:
            logger.error("Tavily API Key is not configured.")
            return query, []

        try:
            response = await self.tavily_client.search(
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
                if "url" in item and ".pdf" in item.get("url", "").lower()
            ]

            return query, pdf_results

        except Exception as e:
            logger.error(f"Tavily search failed: {e}")
            return query, []

    async def _download_pdf(self, pdf_url: str) -> bytes | None:
        logger.info(f"Downloading PDF from {pdf_url}")

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )
        }

        try:
            response = await self.http_client.get(pdf_url, timeout=30, headers=headers)
            response.raise_for_status()
            return response.content
        except httpx.RequestError as error:
            logger.warning(f"Failed to download PDF {pdf_url}: {error}")
            return None
        except Exception as error:
            logger.warning(f"Unexpected error downloading PDF {pdf_url}: {error}")
            return None

    async def _search_student_in_pdf(
        self, pdf_content: bytes, normalized_name: str
    ) -> bool:
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

                if text and normalized_name in normalize_text(text):
                    return True

            return False
        except Exception as e:
            logger.warning(f"Error searching text in PDF content: {e}")
            return False

    async def _process_student(
        self, student_name: str, year: int
    ) -> list[StudentResult]:
        normalized_student_name = normalize_text(student_name)

        logger.info(f"Processing student for year {year}")

        query_used, pdf_results = await self._search_for_pdfs(student_name, year)

        await asyncio.sleep(self.search_delay)

        not_found = StudentNotFoundResult(student_name=student_name)

        if not pdf_results:
            logger.info(f"No PDFs found for student in {year}.")
            return [not_found]

        async def process_pdf(pdf_info: dict[str, str]) -> StudentResult | None:
            pdf_url = pdf_info["url"]
            search_title = pdf_info["title"]
            pdf_content = await self._download_pdf(pdf_url)

            if not pdf_content:
                logger.warning(f"Failed to download PDF from: {pdf_url}")
                return None

            is_found = await self._search_student_in_pdf(
                pdf_content, normalized_student_name
            )

            if not is_found:
                return None

            logger.info(
                f'SUCCESS! Student "{student_name}" FOUND in PDF from {pdf_url}'
            )
            return StudentFoundResult(
                student_name=student_name,
                normalized_name=normalized_student_name,
                year_found=year,
                search_query=query_used,
                pdf_url=pdf_url,
                search_title=search_title,
            )

        pdf_matches = await asyncio.gather(*[process_pdf(p) for p in pdf_results])
        found: list[StudentResult] = [r for r in pdf_matches if r is not None]

        if not found:
            logger.info(
                f'Student "{student_name}" not found in any list for the year {year}.'
            )
            return [not_found]

        return found

    async def check_admission_status(
        self,
        students_names: list[str],
        year: int,
        class_name: str | None = None,
        on_student_done: OnStudentDone | None = None,
    ) -> None:
        normalized_names = {normalize_text(n): n for n in students_names}

        get_existing = sync_to_async(
            lambda: list(
                AdmissionResult.objects.filter(
                    student_name_normalized__in=list(normalized_names.keys()), year=year
                ).prefetch_related("pdfs")
            )
        )
        existing_records: list[AdmissionResult] = await get_existing()
        existing_by_normalized = {
            r.student_name_normalized: r for r in existing_records
        }

        classroom = await self._resolve_classroom(class_name)

        if classroom is not None:
            for record in existing_records:
                await self._update_classroom_if_changed(record, classroom)

        async def results_for_existing(record: AdmissionResult) -> list[StudentResult]:
            pdfs = list(record.pdfs.all())
            if pdfs:
                entries: list[StudentResult] = [
                    StudentFoundResult(
                        student_name=record.student_name,
                        normalized_name=record.student_name_normalized,
                        year_found=record.year,
                        search_query="",
                        pdf_url=pdf.url,
                        search_title=pdf.search_title,
                    )
                    for pdf in pdfs
                ]
            else:
                entries = [StudentNotFoundResult(student_name=record.student_name)]
            if on_student_done:
                await on_student_done(entries)
            return entries

        new_names = [
            original
            for normalized, original in normalized_names.items()
            if normalized not in existing_by_normalized
        ]

        async def search_and_notify(name: str) -> list[StudentResult]:
            entries = await self._process_student(name, year)
            if on_student_done:
                await on_student_done(entries)
            return entries

        searched_results = await asyncio.gather(
            *[search_and_notify(name) for name in new_names]
        )
        await asyncio.gather(*[results_for_existing(r) for r in existing_records])

        all_new = [e for batch in searched_results for e in batch]
        await self._persist_results(all_new, year, classroom)

        logger.info("Search process finished!")

    async def _resolve_classroom(self, class_name: str | None) -> ClassRoom | None:
        if not class_name:
            return None
        normalized_class = normalize_text(class_name)
        get_or_create_classroom = sync_to_async(ClassRoom.objects.get_or_create)
        try:
            classroom, _ = await get_or_create_classroom(
                name_normalized=normalized_class,
                defaults={"name": class_name},
            )
            return classroom
        except Exception as e:
            logger.error(f"Failed to get or create classroom: {e}")
            return None

    async def _update_classroom_if_changed(
        self, record: AdmissionResult, classroom: ClassRoom | None
    ) -> None:
        if record.class_room_id != (classroom.pk if classroom else None):
            update_record = sync_to_async(record.save)
            record.class_room = classroom
            try:
                await update_record(update_fields=["class_room"])
            except Exception as e:
                logger.error(f"Failed to update classroom on admission result: {e}")

    async def _persist_results(
        self,
        all_results: list[StudentResult],
        year: int,
        classroom: ClassRoom | None,
    ) -> None:
        for item in all_results:
            normalized_name = normalize_text(item.student_name)
            get_or_create_result = sync_to_async(AdmissionResult.objects.get_or_create)
            try:
                result, _ = await get_or_create_result(
                    student_name_normalized=normalized_name,
                    year=year,
                    defaults={
                        "student_name": item.student_name,
                        "class_room": classroom,
                    },
                )
            except Exception as e:
                logger.error(f"Failed to get or create admission result: {e}")
                continue

            await self._update_classroom_if_changed(result, classroom)

            if not isinstance(item, StudentFoundResult):
                continue

            pdf_exists = sync_to_async(
                AdmissionPDF.objects.filter(result=result, url=item.pdf_url).exists
            )
            try:
                if not await pdf_exists():
                    create_pdf = sync_to_async(AdmissionPDF.objects.create)
                    await create_pdf(
                        result=result,
                        url=item.pdf_url,
                        search_title=item.search_title[:512],
                    )
            except Exception as e:
                logger.error(f"Failed to create admission PDF: {e}")

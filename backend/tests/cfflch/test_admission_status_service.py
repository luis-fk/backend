import asyncio
import gc
import io
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, TypeVar

import httpx
import pytest
from pypdf import PdfWriter
from pypdf.generic import ContentStream, DictionaryObject, NameObject
from pytest_django import Settings

from cfflch.api.admission_status.schemas import (
    StudentFoundResult,
    StudentNotFoundResult,
    StudentResult,
    StudentSearchFailedResult,
)
from cfflch.api.admission_status.service import AdmissionStatusService
from cfflch.api.admission_status.utils import normalize_text
from cfflch.models import AdmissionPDF, AdmissionResult, ClassRoom

# transaction=True: the service queries from worker threads, each with its own
# connection, outside the transaction a test runs in. Those connections can't see
# the test's rows, and the test can't roll theirs back.
DATABASES = pytest.mark.django_db(databases=["default", "cfflch_db"], transaction=True)

QUERY = "Fulano de Tal aprovado classificado convocado selecionado vestibular 2025"
LIST_URL = "https://vestibular.exemplo.br/aprovados.pdf"

T = TypeVar("T")


def pdf(*pages: str) -> bytes:
    """A PDF with one line of text on each page, in a font pypdf reads back."""
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
            NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
        }
    )
    for line in pages:
        page = writer.add_blank_page(width=600, height=800)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        content = ContentStream(None, writer)
        content.set_data(
            b"BT /F1 12 Tf 50 700 Td (" + line.encode("cp1252") + b") Tj ET"
        )
        page.replace_contents(content)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


@dataclass
class FakeWeb:
    """Stands in for Tavily and for the sites that host the lists."""

    results: list[dict[str, str]] = field(default_factory=list)
    pdfs: dict[str, bytes] = field(default_factory=dict)
    offline: set[str] = field(default_factory=set)
    queries: list[str] = field(default_factory=list)
    search_is_down: bool = False

    def publish(self, url: str, title: str, *pages: str) -> None:
        """A search result that links to a PDF with these pages."""
        self.results.append({"url": url, "title": title})
        self.pdfs[url] = pdf(*pages)

    async def search(self, query: str, **_options: Any) -> dict[str, Any]:
        self.queries.append(query)
        if self.search_is_down:
            raise RuntimeError("Tavily is down.")
        return {"results": self.results}

    def serve(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url in self.offline:
            raise httpx.ConnectError("The site is offline.", request=request)
        if url not in self.pdfs:
            return httpx.Response(404)
        return httpx.Response(200, content=self.pdfs[url])


@pytest.fixture(autouse=True)
def no_tavily_key(settings: Settings) -> None:
    """Keeps the real Tavily client out, even with a key in the .env."""
    settings.TAVILY_API_KEY = None


def run(
    web: FakeWeb, step: Callable[[AdmissionStatusService], Coroutine[Any, Any, T]]
) -> T:
    """Runs step with a service that searches and downloads from web."""

    async def scenario() -> T:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(web.serve)
        ) as client:
            service = AdmissionStatusService(http_client=client)
            service.tavily_client = web
            service.search_delay = 0
            return await step(service)

    return asyncio.run(scenario())


def check(
    web: FakeWeb, names: list[str], year: int = 2025, class_name: str | None = None
) -> list[list[StudentResult]]:
    """Searches like the route does and returns what each student sent."""
    sent: list[list[StudentResult]] = []

    async def on_student_done(entries: list[StudentResult]) -> None:
        sent.append(entries)

    run(
        web,
        lambda service: service.check_admission_status(
            names, year, class_name, on_student_done
        ),
    )
    # The worker threads are gone, but their connections stay open until the garbage
    # collector frees them, and PostgreSQL can't drop a test database still in use.
    gc.collect()
    return sent


def found(url: str, title: str, query: str = QUERY) -> StudentFoundResult:
    return StudentFoundResult(
        student_name="Fulano de Tal",
        normalized_name="fulano de tal",
        year_found=2025,
        search_query=query,
        pdf_url=url,
        search_title=title,
    )


FAILED = StudentSearchFailedResult(student_name="Fulano de Tal")


def known_student(
    year: int = 2025, class_room: ClassRoom | None = None
) -> AdmissionResult:
    return AdmissionResult.objects.create(
        student_name="Fulano de Tal",
        student_name_normalized="fulano de tal",
        year=year,
        class_room=class_room,
    )


def class_room(name: str) -> ClassRoom:
    return ClassRoom.objects.create(name=name, name_normalized=normalize_text(name))


def is_in_pdf(content: bytes, name: str) -> bool | None:
    return run(
        FakeWeb(),
        lambda service: service._search_student_in_pdf(content, normalize_text(name)),
    )


def test_the_search_keeps_only_links_to_pdfs() -> None:
    web = FakeWeb(
        results=[
            {"url": LIST_URL, "title": "Aprovados 2025"},
            {"url": "https://exemplo.br/Lista.PDF?pagina=2", "title": "Lista"},
            {"url": "https://exemplo.br/noticia-aprovados", "title": "Notícia"},
            {"url": "https://exemplo.br/segunda-chamada.pdf"},
            {"title": "Resultado sem link"},
        ]
    )

    query, links = run(
        web, lambda service: service._search_for_pdfs("Fulano de Tal", 2025)
    )

    assert query == QUERY
    assert links == [
        {"url": LIST_URL, "title": "Aprovados 2025"},
        {"url": "https://exemplo.br/Lista.PDF?pagina=2", "title": "Lista"},
        {"url": "https://exemplo.br/segunda-chamada.pdf", "title": "No Title Found"},
    ]


def test_a_name_is_found_whatever_its_case_and_accents() -> None:
    content = pdf("Lista de aprovados", "12. BELTRANA CONCEIÇÃO - Medicina")

    assert is_in_pdf(content, "Beltrana Conceicao")
    assert is_in_pdf(content, "  beltrana conceição ")


def test_a_name_missing_from_the_list_is_not_found() -> None:
    assert not is_in_pdf(
        pdf("1. Sicrano Araújo", "2. Beltrana Conceição"), "Fulano de Tal"
    )


def test_a_name_inside_a_longer_name_is_not_found() -> None:
    assert not is_in_pdf(pdf("1. Joana de Tal", "2. Ana de Tallis"), "Ana de Tal")


def test_a_file_that_is_not_a_pdf_cannot_be_read() -> None:
    assert is_in_pdf(b"<html>Page not found</html>", "Fulano de Tal") is None


def test_a_student_is_found_in_every_list_that_names_them() -> None:
    web = FakeWeb()
    web.publish(LIST_URL, "Aprovados 2025", "1. FULANO DE TAL")
    web.publish("https://exemplo.br/medicina.pdf", "Medicina", "1. Beltrana Conceição")
    web.publish("https://exemplo.br/chamada.pdf", "Segunda chamada", "7. Fulano de Tal")

    results = run(web, lambda service: service._process_student("Fulano de Tal", 2025))

    assert results == [
        found(LIST_URL, "Aprovados 2025"),
        found("https://exemplo.br/chamada.pdf", "Segunda chamada"),
    ]


def test_lists_that_fail_to_download_are_skipped() -> None:
    web = FakeWeb()
    web.results.append({"url": "https://exemplo.br/removida.pdf", "title": "Removida"})
    web.publish(
        "https://fora-do-ar.exemplo.br/lista.pdf", "Fora do ar", "FULANO DE TAL"
    )
    web.offline.add("https://fora-do-ar.exemplo.br/lista.pdf")
    web.publish(LIST_URL, "Aprovados 2025", "1. FULANO DE TAL")

    results = run(web, lambda service: service._process_student("Fulano de Tal", 2025))

    assert results == [found(LIST_URL, "Aprovados 2025")]


def test_a_student_missing_from_the_lists_that_could_be_read_is_not_found() -> None:
    web = FakeWeb()
    web.results.append({"url": "https://exemplo.br/removida.pdf", "title": "Removida"})
    web.publish(LIST_URL, "Aprovados 2025", "1. Sicrano Araújo")

    results = run(web, lambda service: service._process_student("Fulano de Tal", 2025))

    assert results == [StudentNotFoundResult(student_name="Fulano de Tal")]


def test_the_search_fails_when_no_list_can_be_read() -> None:
    web = FakeWeb()
    web.results.append({"url": "https://exemplo.br/removida.pdf", "title": "Removida"})
    web.publish(
        "https://fora-do-ar.exemplo.br/lista.pdf", "Fora do ar", "FULANO DE TAL"
    )
    web.offline.add("https://fora-do-ar.exemplo.br/lista.pdf")
    web.results.append({"url": LIST_URL, "title": "Aprovados 2025"})
    web.pdfs[LIST_URL] = b"<html>Captcha</html>"

    results = run(web, lambda service: service._process_student("Fulano de Tal", 2025))

    assert results == [FAILED]


def test_the_search_fails_when_tavily_fails() -> None:
    web = FakeWeb(search_is_down=True)

    results = run(web, lambda service: service._process_student("Fulano de Tal", 2025))

    assert results == [FAILED]


def test_the_search_fails_without_a_tavily_key() -> None:
    async def search_without_key(service: AdmissionStatusService) -> Any:
        service.tavily_client = None
        return await service._process_student("Fulano de Tal", 2025)

    assert run(FakeWeb(), search_without_key) == [FAILED]


@DATABASES
def test_a_student_found_is_saved_with_the_lists_and_the_class() -> None:
    web = FakeWeb()
    web.publish(LIST_URL, "Aprovados 2025", "1. FULANO DE TAL")
    web.publish("https://exemplo.br/chamada.pdf", "Segunda chamada", "7. Fulano de Tal")

    sent = check(web, ["Fulano de Tal"], class_name="3A")

    assert sent == [
        [
            found(LIST_URL, "Aprovados 2025"),
            found("https://exemplo.br/chamada.pdf", "Segunda chamada"),
        ]
    ]
    result = AdmissionResult.objects.get()
    assert (result.student_name, result.student_name_normalized, result.year) == (
        "Fulano de Tal",
        "fulano de tal",
        2025,
    )
    assert not result.approved
    assert result.class_room_id == ClassRoom.objects.get(name="3A").id
    assert list(result.pdfs.order_by("id").values_list("url", "search_title")) == [
        (LIST_URL, "Aprovados 2025"),
        ("https://exemplo.br/chamada.pdf", "Segunda chamada"),
    ]


@DATABASES
def test_a_student_not_on_any_list_is_saved_as_not_found() -> None:
    web = FakeWeb()
    web.publish(LIST_URL, "Aprovados 2025", "1. Sicrano Araújo")

    sent = check(web, ["Fulano de Tal"])

    assert sent == [[StudentNotFoundResult(student_name="Fulano de Tal")]]
    result = AdmissionResult.objects.get()
    assert result.student_name == "Fulano de Tal"
    assert not result.pdfs.exists()


@DATABASES
def test_a_failed_search_is_not_saved_so_the_next_one_searches_again() -> None:
    web = FakeWeb(search_is_down=True)

    assert check(web, ["Fulano de Tal"]) == [[FAILED]]
    assert not AdmissionResult.objects.exists()

    web.search_is_down = False
    web.publish(LIST_URL, "Aprovados 2025", "1. FULANO DE TAL")

    assert check(web, ["Fulano de Tal"]) == [[found(LIST_URL, "Aprovados 2025")]]
    assert web.queries == [QUERY, QUERY]
    assert AdmissionResult.objects.get().pdfs.count() == 1


@DATABASES
def test_a_known_student_is_answered_from_the_database_without_searching() -> None:
    class_a = class_room("3A")
    result = known_student(class_room=class_a)
    AdmissionPDF.objects.create(result=result, url=LIST_URL, search_title="Aprovados")
    web = FakeWeb()

    sent = check(web, ["  FULANO DE TÁL "])

    assert web.queries == []
    assert sent == [[found(LIST_URL, "Aprovados", query="")]]
    result.refresh_from_db()
    assert result.class_room_id == class_a.id
    assert AdmissionResult.objects.count() == 1


@DATABASES
def test_a_known_student_searched_with_another_class_moves_to_it() -> None:
    result = known_student(class_room=class_room("3A"))
    class_b = class_room("3B")

    check(FakeWeb(), ["Fulano de Tal"], class_name=" 3b ")

    result.refresh_from_db()
    assert result.class_room_id == class_b.id
    assert ClassRoom.objects.count() == 2


@DATABASES
def test_the_same_name_in_another_year_is_searched_again() -> None:
    known_student(year=2024)
    web = FakeWeb()

    check(web, ["Fulano de Tal"], year=2025)

    assert web.queries == [QUERY]
    assert sorted(AdmissionResult.objects.values_list("year", flat=True)) == [
        2024,
        2025,
    ]


@DATABASES
def test_a_long_search_title_is_cut_to_fit_its_column() -> None:
    title = "Aprovados " + "x" * 600
    web = FakeWeb()
    web.publish(LIST_URL, title, "1. FULANO DE TAL")

    check(web, ["Fulano de Tal"])

    assert AdmissionPDF.objects.get().search_title == title[:512]

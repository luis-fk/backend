from langsmith.utils import tracing_is_enabled


def test_the_tests_send_nothing_to_langsmith() -> None:
    """backend/.env may turn LangSmith tracing on, which would send the LangChain
    calls of the tests over the network."""
    assert not tracing_is_enabled()

import pytest

from app.sql_guard import validate_select


@pytest.mark.parametrize(
    "query",
    [
        "SELECT 1",
        "SELECT * FROM glpi_tickets",
        "SELECT id FROM glpi_tickets;",
        """
        WITH recent_tickets AS (
            SELECT id
            FROM glpi_tickets
        )
        SELECT * FROM recent_tickets
        """,
    ],
)
def test_accepts_read_only_queries(query: str) -> None:
    result = validate_select(query)

    assert result
    assert not result.endswith(";")


@pytest.mark.parametrize(
    ("query", "expected_message"),
    [
        ("", "não pode estar vazia"),
        ("   ;   ", "não pode estar vazia"),
        ("UPDATE glpi_tickets SET name = 'x'", "SELECT ou WITH"),
        ("DELETE FROM glpi_tickets", "SELECT ou WITH"),
        ("SELECT 1; SELECT 2", "Apenas uma instrução"),
        (
            "SELECT * FROM glpi_tickets INTO OUTFILE '/tmp/test'",
            "operação não permitida",
        ),
    ],
)
def test_rejects_unsafe_queries(
    query: str,
    expected_message: str,
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        validate_select(query)

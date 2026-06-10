import re

FORBIDDEN_SQL_PATTERN = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|REPLACE|MERGE|"
    r"CREATE|ALTER|DROP|TRUNCATE|RENAME|"
    r"GRANT|REVOKE|SET|USE|CALL|DO|"
    r"LOAD|HANDLER|LOCK|UNLOCK|"
    r"INTO\s+OUTFILE|INTO\s+DUMPFILE"
    r")\b",
    re.IGNORECASE,
)


def validate_select(query: str) -> str:
    normalized_query = query.strip().rstrip(";").strip()

    if not normalized_query:
        raise ValueError("A consulta SQL não pode estar vazia.")

    if ";" in normalized_query:
        raise ValueError("Apenas uma instrução SQL é permitida.")

    if not re.match(r"^(SELECT|WITH)\b", normalized_query, re.IGNORECASE):
        raise ValueError("A consulta deve começar com SELECT ou WITH.")

    if FORBIDDEN_SQL_PATTERN.search(normalized_query):
        raise ValueError("A consulta contém uma operação não permitida.")

    return normalized_query

import traceback
from collections import deque
from typing import Any, Dict, Iterable, List

import sqlparse
from marvin.extensions.tools.services.sql_database import SQLDatabase
from marvin.extensions.tools.tool import get_config_from_context, tool
from marvin.extensions.tools.tool_kit import ToolKit
from pydantic import BaseModel, Field
from sqlparse.sql import Token, TokenList
from sqlparse.tokens import Keyword

REPORTS_PARAM_TOKEN = "$$"
# Change the behavior of reports
SQL_BLACKLIST = (
    # DML
    "COMMIT",
    "DELETE",
    "INSERT",
    "MERGE",
    "REPLACE",
    "ROLLBACK",
    "SET",
    "START",
    "UPDATE",
    "UPSERT",
    # DDL
    "ALTER",
    "CREATE",
    "DROP",
    "RENAME",
    "TRUNCATE",
    # DCL
    "GRANT",
    "REVOKE",
)


def passes_blacklist(
    sql: str, blacklist: Iterable[str] = None
) -> tuple[bool, Iterable[str]]:
    sql_strings = sqlparse.split(sql)
    keyword_tokens = set()
    for sql_string in sql_strings:
        statements = sqlparse.parse(sql_string)
        for statement in statements:
            for token in walk_tokens(statement):
                if not token.is_whitespace and not isinstance(token, TokenList):
                    if token.ttype in Keyword:
                        keyword_tokens.add(str(token.value).upper())

    blacklist = blacklist or SQL_BLACKLIST
    fails = [bl_word for bl_word in blacklist if bl_word.upper() in keyword_tokens]

    return not bool(fails), fails


def walk_tokens(token: TokenList) -> Iterable[Token]:
    """
    Generator to walk all tokens in a Statement
    https://stackoverflow.com/questions/54982118/parse-case-when-statements-with-sqlparse
    :param token: TokenList
    """
    queue = deque([token])
    while queue:
        token = queue.popleft()
        if isinstance(token, TokenList):
            queue.extend(token)
        yield token


class QueryResult(BaseModel):
    data: List[Dict[str, Any]] = Field(description="The result data of the query")
    headers: List[str] = Field(description="The column headers of the result")
    message: str = Field(description="Additional message about the query execution")


class TableList(BaseModel):
    tables: List[str] = Field(description="List of available tables in the database")


class TableDescription(BaseModel):
    description: str = Field(
        description="CREATE TABLE statements for the specified tables"
    )


class TableCreateColumn(BaseModel):
    name: str = Field(description="The name of the column")
    type: str = Field(description="The type of the column")


class TableCreate(BaseModel):
    table_name: str = Field(description="The name of the table to create")
    columns: List[TableCreateColumn] | List[str] = Field(
        description="The columns of the table"
    )


class RowData(BaseModel):
    values: Dict[str, Any] = Field(
        description="Dictionary of column names and their values"
    )


class RowCondition(BaseModel):
    condition: str = Field(description="SQL condition for identifying the row(s)")


class RowUpdate(BaseModel):
    updates: Dict[str, Any] = Field(
        description="Dictionary of column names and their new values"
    )
    condition: str = Field(
        description="SQL condition for identifying the row(s) to update"
    )


class ColumnDefinition(BaseModel):
    name: str = Field(description="Name of the column")
    type: str = Field(description="SQL type of the column")


class Config(BaseModel):
    database: str = Field(description="The name of the database", default="default")
    url: str = Field(description="The URL of the database", default="")
    use_default_database: bool = Field(
        description="Whether to use the default database", default=True
    )
    readonly: bool = Field(
        description="Whether the database is readonly", default=False
    )


SQL_READ_BLACKLIST = (
    "COMMIT",
    "DELETE",
    "MERGE",
    "REPLACE",
    "ROLLBACK",
    "SET",
    "START",
    "UPDATE",
    "UPSERT",
    "ALTER",
    "CREATE",
    "DROP",
    "RENAME",
    "TRUNCATE",
    "GRANT",
    "REVOKE",
)


def db_connection(url):
    # if db is neon then add options endpoint
    engine_args = {}
    if "postgresql" in url:
        url = url.replace("postgresql", "postgresql+psycopg")
    if "neon.tech" in url and "options=endpoint" not in url:
        ex = url.split("@")[1]
        endpoint = ex.split(".")[0]
        url = url + f"&options=endpoint%3D{endpoint}"
    if "sqlite" in url:
        engine_args = {"connect_args": {"check_same_thread": False}}
    return SQLDatabase.from_uri(url, engine_args=engine_args)


@tool(
    name="db_query",
    description="Query database table and receive the result",
    config=Config().model_json_schema(),
)
def db_query(query: str) -> QueryResult:
    config = get_config_from_context(config_key=["database", "default_database"])
    url = config.get("url")
    readonly = config.get("readonly", True)

    if readonly:
        passes, reason = passes_blacklist(query, blacklist=SQL_READ_BLACKLIST)
        if not passes:
            return QueryResult(data=[], headers=[], message=f"Error: {reason}")

    try:
        connection = db_connection(url)
        return connection.run(query)
        
    except Exception as e:
        traceback.print_exc()
        return QueryResult(data=[], headers=[], message=f"Error: {str(e)}")


@tool(
    name="db_list_tables",
    description="Lists the available tables in the database",
    config=Config().model_json_schema(),
)
def db_list_tables() -> TableList:
    config = get_config_from_context(config_key=["database", "default_database"])
    url = config.get("url")
    try:
        connection = db_connection(url)
        tables = connection.get_usable_table_names()
        return TableList(tables=tables)
    except Exception as e:
        return TableList(tables=[], message=f"Error: {str(e)}")


@tool(
    name="db_describe_tables",
    description="Describes the specified tables in the database",
    config=Config().model_json_schema(),
)
def db_describe_tables(tables: List[str]) -> TableDescription:
    config = get_config_from_context(config_key="database")
    url = config.get("url")
    try:
        connection = db_connection(url)
        definition = connection.get_table_info(tables)
        return TableDescription(description=definition)
    except Exception as e:
        return TableDescription(description=f"Error: {str(e)}")


@tool(
    name="db_create_table",
    description="Creates a new table in the database",
    config=Config().model_json_schema(),
)
def db_create_table(table: TableCreate) -> TableDescription:
    config = get_config_from_context(config_key=["database", "default_database"])
    url = config.get("url")
    allow_create = not config.get("readonly", False)
    if isinstance(table, dict):
        table = TableCreate(**table)

    if not allow_create:
        return TableDescription(description="Error: Create is not allowed.")
    try:
        connection = db_connection(url)
        if isinstance(table.columns[0], TableCreateColumn):
            column_definitions = [f"{col.name} {col.type}" for col in table.columns]
        else:
            column_definitions = table.columns
        connection.run(
            f"CREATE TABLE {table.table_name} ({', '.join(column_definitions)})"
        )
        return TableDescription(
            description=f"Table {table.table_name} created successfully."
        )
    except Exception as e:
        return TableDescription(description=f"Error:db_create_table: {str(e)}")


@tool(name="db_query_checker", description="Checks the SQL query for common mistakes")
def db_query_checker(query: str, dialect: str) -> str:
    template = f"""
    {query}
        Double check the {dialect} query above for common mistakes, including:
        - Using NOT IN with NULL values
        - Using UNION when UNION ALL should have been used
        - Using BETWEEN for exclusive ranges
        - Data type mismatch in predicates
        - Properly quoting identifiers
        - Using the correct number of arguments for functions
        - Casting to the correct data type
        - Using the proper columns for joins

        If there are any of the above mistakes, rewrite the query.
        If there are no mistakes, just reproduce the original query.
        Use the format below:

        ```sql
        the query
        ```
    """
    return template


database_toolkit = ToolKit.create_toolkit(
    name="database",
    id="database",
    description="A toolkit for interacting with the database",
    tools=[
        db_query,
        db_list_tables,
        db_describe_tables,
        db_create_table,
    ],
    config_schema=Config().model_json_schema(),
    requires_config=True,
    icon="Database",
)


default_database_toolkit = ToolKit.create_toolkit(
    name="default_database",
    id="default_database",
    description="A toolkit for interacting with the default database",
    tools=[
        db_query,
        db_list_tables,
        db_describe_tables,
        db_create_table,
    ],
    config_schema=Config().model_json_schema(),
    requires_config=True,
    icon="Database",
    config={
        "defautl_database": "default",
        "url": "sqlite:///:memory:",
        "readonly": False,
    },
)

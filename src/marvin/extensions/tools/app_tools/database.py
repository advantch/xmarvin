import traceback
from typing import Any, Dict, List

from apps.ai.agent.monitoring.logging import pretty_log
from apps.dashboard.sql_utils import passes_blacklist
from marvin.extensions.tools.services.sql_database import SQLDatabase
from marvin.extensions.tools.tool import get_config_from_context, tool
from marvin.extensions.tools.tool_kit import ToolKit
from pydantic import BaseModel, Field


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
        result = connection.run(query)
        if result.get("data") and len(result.get("data")) > 0:
            return QueryResult(
                data=result.get("data"),
                headers=result.get("headers"),
                message="Query has been run and data is visible to user.",
            )
        return QueryResult(data=[], headers=[], message="Success: Query executed.")
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
    name="db_update_table",
    description="Updates the specified table in the database",
    config=Config().model_json_schema(),
)
def db_update_table(table: str, columns: List[str]) -> TableDescription:
    config = get_config_from_context(config_key=["database", "default_database"])
    url = config.get("url")
    allow_update = not config.get("readonly", False)
    if not allow_update:
        return TableDescription(description="Error: Update is not allowed.")
    try:
        connection = db_connection(url)
        connection.run(f"UPDATE {table} SET {', '.join(columns)}")
        return TableDescription(description=f"Table {table} updated successfully.")
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
    pretty_log(f"Creating table {table.table_name} with columns {table.columns}")
    if not allow_create:
        return TableDescription(description="Error: Create is not allowed.")
    try:
        connection = db_connection(url)
        pretty_log(f"Creating table {table.table_name} with columns {table.columns}")
        if isinstance(table.columns[0], TableCreateColumn):
            column_definitions = [f"{col.name} {col.type}" for col in table.columns]
        else:
            column_definitions = table.columns
        pretty_log(
            f"Creating table {table.table_name} with columns {column_definitions}"
        )
        connection.run(
            f"CREATE TABLE {table.table_name} ({', '.join(column_definitions)})"
        )
        return TableDescription(
            description=f"Table {table.table_name} created successfully."
        )
    except Exception as e:
        return TableDescription(description=f"Error:db_create_table: {str(e)}")


@tool(
    name="db_drop_table",
    description="Drops the specified table from the database",
    config=Config().model_json_schema(),
)
def db_drop_table(table: str) -> TableDescription:
    config = get_config_from_context(config_key=["database", "default_database"])
    url = config.get("url")
    allow_drop = not config.get("readonly", False)
    if not allow_drop:
        return TableDescription(description="Error: Drop is not allowed.")
    try:
        connection = db_connection(url)
        connection.run(f"DROP TABLE {table}")
        return TableDescription(description=f"Table {table} dropped successfully.")
    except Exception as e:
        return TableDescription(description=f"Error: {str(e)}")


@tool(
    name="db_add_row",
    description="Adds a new row to the specified table",
    config=Config().model_json_schema(),
)
def db_add_row(table: str, row: RowData) -> TableDescription:
    config = get_config_from_context(config_key=["database", "default_database"])
    url = config.get("url")
    if config.get("readonly", False):
        return TableDescription(
            description="Error: Add row is not allowed in readonly mode."
        )
    if isinstance(row, dict):
        row = RowData.model_validate(row)
    try:
        connection = db_connection(url)
        columns = ", ".join(row.values.keys())
        placeholders = ", ".join(["?"] * len(row.values))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        pretty_log(f"Adding row to {table} with query: {query}")

        connection.run(query, list(row.values.values()))
        return TableDescription(description=f"Row added to {table} successfully.")
    except Exception as e:
        return TableDescription(description=f"Error: {str(e)}")


@tool(
    name="db_remove_row",
    description="Removes a row from the specified table based on a condition",
    config=Config().model_json_schema(),
)
def db_remove_row(table: str, condition: RowCondition) -> TableDescription:
    config = get_config_from_context(config_key=["database", "default_database"])
    url = config.get("url")
    if config.get("readonly", False):
        return TableDescription(
            description="Error: Remove row is not allowed in readonly mode."
        )

    if isinstance(condition, dict):
        condition = RowCondition.model_validate(condition)
    try:
        connection = db_connection(url)
        query = f"DELETE FROM {table} WHERE {condition.condition}"
        connection.run(query)
        return TableDescription(
            description=f"Row(s) removed from {table} successfully."
        )
    except Exception as e:
        return TableDescription(description=f"Error: {str(e)}")


@tool(
    name="db_edit_row",
    description="Edits a row in the specified table based on a condition",
    config=Config().model_json_schema(),
)
def db_edit_row(table: str, update: RowUpdate) -> TableDescription:
    config = get_config_from_context(config_key=["database", "default_database"])
    url = config.get("url")
    if config.get("readonly", False):
        return TableDescription(
            description="Error: Edit row is not allowed in readonly mode."
        )
    if isinstance(update, dict):
        update = RowUpdate.model_validate(update)
    try:
        connection = db_connection(url)
        set_clause = ", ".join([f"{k} = %s" for k in update.updates.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE {update.condition}"
        connection.run(query, list(update.updates.values()))
        return TableDescription(description=f"Row(s) in {table} updated successfully.")
    except Exception as e:
        return TableDescription(description=f"Error: {str(e)}")


@tool(
    name="db_add_column",
    description="Adds a new column to the specified table",
    config=Config().model_json_schema(),
)
def db_add_column(table: str, column: ColumnDefinition) -> TableDescription:
    config = get_config_from_context(config_key=["database", "default_database"])
    url = config.get("url")
    if config.get("readonly", False):
        return TableDescription(
            description="Error: Add column is not allowed in readonly mode."
        )
    if isinstance(column, dict):
        column = ColumnDefinition.model_validate(column)
    try:
        connection = db_connection(url)
        query = f"ALTER TABLE {table} ADD COLUMN {column.name} {column.type}"

        connection.run(query)
        return TableDescription(
            description=f"Column {column.name} added to {table} successfully."
        )
    except Exception as e:
        return TableDescription(description=f"Error: {str(e)}")


@tool(
    name="db_remove_column",
    description="Removes a column from the specified table",
    config=Config().model_json_schema(),
)
def db_remove_column(table: str, column_name: str) -> TableDescription:
    config = get_config_from_context(config_key=["database", "default_database"])
    url = config.get("url")
    if config.get("readonly", False):
        return TableDescription(
            description="Error: Remove column is not allowed in readonly mode."
        )
    try:
        connection = db_connection(url)
        query = f"ALTER TABLE {table} DROP COLUMN {column_name}"
        connection.run(query)
        return TableDescription(
            description=f"Column {column_name} removed from {table} successfully."
        )
    except Exception as e:
        return TableDescription(description=f"Error: {str(e)}")


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
        db_update_table,
        db_create_table,
        db_drop_table,
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
        db_update_table,
        db_create_table,
        db_drop_table,
    ],
    config_schema=Config().model_json_schema(),
    requires_config=True,
    icon="Database",
    config={"database": "default", "url": "sqlite:///:memory:", "readonly": False},
)

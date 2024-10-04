import traceback
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, model_validator

from marvin.extensions.settings import extension_settings
from marvin.extensions.tools.services.sql_database import SQLDatabase, passes_blacklist
from marvin.extensions.tools.tool import get_config_from_context, tool
from marvin.extensions.tools.tool_kit import Toolkit


async def get_default_db_url():
    return extension_settings.global_context.get_default_db_url()


class Query(BaseModel):
    query: str = Field(description="The SQL query to execute")
    time_series_query: str | None = Field(
        description="The SQL query to execute for time series data if possible"
    )
    type: Literal["query"] = Field(
        description="The type of the result", default="query"
    )
    title: str = Field(description="Title to be used in charts and reports")
    description: str = Field(description="Description to be used in charts and reports")
    chart_type: Literal["bar", "line", "pie", "scatter", "area"] = Field(
        description="Type of chart to be used in reports"
    )
    x_axis: str = Field(description="X axis to be used in charts")
    y_axis: str = Field(description="Y axis to be used in charts")
    categories: List[str] = Field(
        description="Categories to be used in chart. Usually a date field."
    )


class QueryResult(BaseModel):
    data: List[Dict[str, Any]] = Field(description="The result data of the query")
    headers: List[str] = Field(description="The column headers of the result")
    message: str = Field(description="Additional message about the query execution")
    type: Literal["query_result"] = Field(
        description="The type of the result", default="query_result"
    )
    metadata: Dict[str, Any] | None = Field(
        description="Metadata about the query result", default=None
    )


class TableList(BaseModel):
    tables: List[str] = Field(description="List of available tables in the database")
    type: Literal["table_list"] = Field(
        description="The type of the result", default="table_list"
    )


class TableDescription(BaseModel):
    description: List[str] | str = Field(
        description="CREATE TABLE statements for the specified tables"
    )
    type: Literal["table_description"] = Field(
        description="The type of the result", default="table_description"
    )


class TableCreateColumn(BaseModel):
    name: str = Field(description="The name of the column")
    column_type: str = Field(description="The type of the column")
    is_primary_key: bool = Field(
        description="Whether the column is a primary key", default=False
    )
    auto_increment: bool = Field(
        description="Whether the column is an auto increment column", default=False
    )
    type: Literal["table_create_column"] = Field(
        description="The type of the result", default="table_create_column"
    )


class TableCreate(BaseModel):
    table_name: str = Field(
        description="The name of the table to create.Include at a minimum a primary key column named id"
    )
    columns: List[TableCreateColumn] | List[str] = Field(
        description="The columns of the table"
    )
    type: Literal["table_create"] = Field(
        description="The type of the result", default="table_create"
    )

    @model_validator(mode="after")
    def validate_columns(self):
        """Add primary key and auto increment to columns if not specified"""
        has_primary_key = False
        for column in self.columns:
            if isinstance(column, TableCreateColumn):
                if column.is_primary_key:
                    has_primary_key = True
                    if not column.auto_increment:
                        column.auto_increment = True

        if not has_primary_key:
            self.columns.append(
                TableCreateColumn(
                    name="id",
                    column_type="INTEGER",
                    is_primary_key=True,
                    auto_increment=True,
                )
            )
        return self


class RowData(BaseModel):
    values: Dict[str, Any] = Field(
        description="Dictionary of column names and their values"
    )
    type: Literal["row_data"] = Field(
        description="The type of the result", default="row_data"
    )


class RowCondition(BaseModel):
    condition: str = Field(description="SQL condition for identifying the row(s)")
    type: Literal["row_condition"] = Field(
        description="The type of the result", default="row_condition"
    )


class RowUpdate(BaseModel):
    updates: Dict[str, Any] = Field(
        description="Dictionary of column names and their new values"
    )
    condition: str = Field(
        description="SQL condition for identifying the row(s) to update"
    )
    type: Literal["row_update"] = Field(
        description="The type of the result", default="row_update"
    )


class ColumnDefinition(BaseModel):
    name: str = Field(description="Name of the column")
    type: str = Field(description="SQL type of the column")
    type: Literal["column_definition"] = Field(
        description="The type of the result", default="column_definition"
    )


class TableDataRequest(BaseModel):
    table_name: str = Field(description="The name of the table")
    limit: int = Field(description="The number of rows to return", default=1000)
    type: Literal["table_data_request"] = Field(
        description="The type of the result", default="table_data_request"
    )


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

CONFIG_KEYS = ["database", "default_database", "admin_database"]


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
async def db_query(query: str) -> QueryResult:
    config = get_config_from_context(config_key=CONFIG_KEYS)
    url = config.get("url", await get_default_db_url())
    readonly = config.get("readonly", False)

    if readonly:
        passes, reason = passes_blacklist(query, blacklist=SQL_READ_BLACKLIST)
        if not passes:
            return QueryResult(
                data=[],
                headers=[],
                message=f"Readonly Error: issues in statement: {reason}",
            )

    try:
        connection = db_connection(url)
        result = connection.run(query)
        if result.data:
            return QueryResult(
                data=result.data,
                headers=result.headers,
                message="Success: Query executed.",
            )
        else:
            return QueryResult(data=[], headers=[], message="Success: Query executed.")
    except Exception as e:
        traceback.print_exc()
        return QueryResult(data=[], headers=[], message=f"Error: {str(e)}")


@tool(
    name="db_table_data",
    description="Get the data from the specified table",
    config=Config().model_json_schema(),
)
async def db_table_data(
    table_name: str,
    limit: int,
) -> QueryResult:
    query = f"SELECT * FROM {table_name} LIMIT {limit}"
    return await db_query(query)


@tool(
    name="db_list_tables",
    description="Lists the available tables in the database",
    config=Config().model_json_schema(),
)
async def db_list_tables(filter: str = "all") -> TableList:
    config = get_config_from_context(config_key=CONFIG_KEYS)
    url = config.get("url", await get_default_db_url())
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
async def db_describe_tables(tables: List[str]) -> TableDescription:
    config = get_config_from_context(config_key=CONFIG_KEYS)
    url = config.get("url", await get_default_db_url())
    try:
        connection = db_connection(url)
        definition = connection.get_table_info(tables)
        return TableDescription(description=definition.table_statements())
    except Exception as e:
        return TableDescription(description=f"Error: {str(e)}")


database_toolkit = Toolkit.create_toolkit(
    name="database",
    id="database",
    description="A toolkit for interacting with the database",
    tools=[
        db_query,
        db_list_tables,
        db_describe_tables,
    ],
    config_schema=Config().model_json_schema(),
    requires_config=True,
    icon="Database",
)

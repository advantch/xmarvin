"""SQLAlchemy wrapper around a database."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Literal, Optional, Sequence, Union

import sqlalchemy
from langchain_core._api import deprecated
from pydantic import BaseModel
from sqlalchemy import (
    MetaData,
    Table,
    create_engine,
    inspect,
    select,
    text,
)
from sqlalchemy.engine import URL, Engine, Result
from sqlalchemy.exc import ProgrammingError, SQLAlchemyError
from sqlalchemy.schema import CreateTable
from sqlalchemy.sql.expression import Executable
from sqlalchemy.types import NullType

from marvin.extensions.utilities.logging import pretty_log


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    default: Optional[str] = None


class IndexInfo(BaseModel):
    name: str
    unique: bool
    columns: List[str]


class RelationInfo(BaseModel):
    from_table: str
    from_column: str
    to_table: str
    to_column: str


class TableInfo(BaseModel):
    name: str
    columns: Dict[str, ColumnInfo]
    primary_key: List[str]
    foreign_keys: List[RelationInfo]
    create_statement: str
    indexes: Optional[List[IndexInfo]] = None
    sample_rows: Optional[List[Dict[str, Any]]] = None


class DatabaseInfo(BaseModel):
    tables: Dict[str, TableInfo]


class QueryResult(BaseModel):
    headers: List[str]
    data: List[Dict[str, Any]]
    message: str = "Query executed successfully."


def _format_index(index: sqlalchemy.engine.interfaces.ReflectedIndex) -> str:
    return (
        f'Name: {index["name"]}, Unique: {index["unique"]},'
        f' Columns: {str(index["column_names"])}'
    )


def truncate_word(content: Any, *, length: int, suffix: str = "...") -> str:
    """
    Truncate a string to a certain number of words, based on the max string
    length.
    """

    if not isinstance(content, str) or length <= 0:
        return content

    if len(content) <= length:
        return content

    return content[: length - len(suffix)].rsplit(" ", 1)[0] + suffix


class SQLDatabase:
    """SQLAlchemy wrapper around a database."""

    def __init__(
        self,
        engine: Engine,
        schema: Optional[str] = None,
        metadata: Optional[MetaData] = None,
        ignore_tables: Optional[List[str]] = None,
        include_tables: Optional[List[str]] = None,
        sample_rows_in_table_info: int = 3,
        indexes_in_table_info: bool = False,
        custom_table_info: Optional[dict] = None,
        view_support: bool = False,
        max_string_length: int = 300,
        lazy_table_reflection: bool = False,
    ):
        """Create engine from database URI."""
        self._engine = engine
        self._schema = schema
        if include_tables and ignore_tables:
            raise ValueError("Cannot specify both include_tables and ignore_tables")

        self._inspector = inspect(self._engine)

        # including view support by adding the views as well as tables to the all
        # tables list if view_support is True
        self._all_tables = set(
            self._inspector.get_table_names(schema=schema)
            + (self._inspector.get_view_names(schema=schema) if view_support else [])
        )

        self._include_tables = set(include_tables) if include_tables else set()
        if self._include_tables:
            missing_tables = self._include_tables - self._all_tables
            if missing_tables:
                raise ValueError(
                    f"include_tables {missing_tables} not found in database"
                )
        self._ignore_tables = set(ignore_tables) if ignore_tables else set()
        if self._ignore_tables:
            missing_tables = self._ignore_tables - self._all_tables
            if missing_tables:
                raise ValueError(
                    f"ignore_tables {missing_tables} not found in database"
                )
        usable_tables = self.get_usable_table_names()
        self._usable_tables = set(usable_tables) if usable_tables else self._all_tables

        if not isinstance(sample_rows_in_table_info, int):
            raise TypeError("sample_rows_in_table_info must be an integer")

        self._sample_rows_in_table_info = sample_rows_in_table_info
        self._indexes_in_table_info = indexes_in_table_info

        self._custom_table_info = custom_table_info
        if self._custom_table_info:
            if not isinstance(self._custom_table_info, dict):
                raise TypeError(
                    "table_info must be a dictionary with table names as keys and the "
                    "desired table info as values"
                )
            # only keep the tables that are also present in the database
            intersection = set(self._custom_table_info).intersection(self._all_tables)
            self._custom_table_info = dict(
                (table, self._custom_table_info[table])
                for table in self._custom_table_info
                if table in intersection
            )

        self._max_string_length = max_string_length
        self._view_support = view_support

        self._metadata = metadata or MetaData()
        if not lazy_table_reflection:
            # including view support if view_support = true
            self._metadata.reflect(
                views=view_support,
                bind=self._engine,
                only=list(self._usable_tables),
                schema=self._schema,
            )

    @classmethod
    def from_uri(
        cls,
        database_uri: Union[str, URL],
        engine_args: Optional[dict] = None,
        **kwargs: Any,
    ) -> SQLDatabase:
        """Construct a SQLAlchemy engine from URI."""
        _engine_args = engine_args or {}
        return cls(create_engine(database_uri, **_engine_args), **kwargs)

    @property
    def dialect(self) -> str:
        """Return string representation of dialect to use."""
        return self._engine.dialect.name

    def get_usable_table_names(self) -> Iterable[str]:
        """Get names of tables available."""
        if self._include_tables:
            return sorted(self._include_tables)
        return sorted(self._all_tables - self._ignore_tables)

    @deprecated("0.0.1", alternative="get_usable_table_names", removal="0.3.0")
    def get_table_names(self) -> Iterable[str]:
        """Get names of tables available."""
        return self.get_usable_table_names()

    @property
    def table_info(self) -> DatabaseInfo:
        """Information about all tables in the database."""
        return self.get_table_info()

    def get_table_info(self, table_names: Optional[List[str]] = None) -> DatabaseInfo:
        """Get information about specified tables."""
        all_table_names = self.get_usable_table_names()
        if table_names is not None:
            missing_tables = set(table_names).difference(all_table_names)
            if missing_tables:
                raise ValueError(f"table_names {missing_tables} not found in database")
            all_table_names = table_names

        metadata_table_names = [tbl.name for tbl in self._metadata.sorted_tables]
        to_reflect = set(all_table_names) - set(metadata_table_names)
        if to_reflect:
            self._metadata.reflect(
                views=self._view_support,
                bind=self._engine,
                only=list(to_reflect),
                schema=self._schema,
            )

        meta_tables = [
            tbl
            for tbl in self._metadata.sorted_tables
            if tbl.name in set(all_table_names)
            and not (self.dialect == "sqlite" and tbl.name.startswith("sqlite_"))
        ]

        tables = {}
        for table in meta_tables:
            if self._custom_table_info and table.name in self._custom_table_info:
                tables[table.name] = self._parse_custom_table_info(
                    table.name, self._custom_table_info[table.name]
                )
                continue

            tables[table.name] = self._get_structured_table_info(table)

        return DatabaseInfo(tables=tables)

    def _get_structured_table_info(self, table: Table) -> TableInfo:
        columns = {
            col.name: ColumnInfo(
                name=col.name,
                type=str(col.type),
                nullable=col.nullable,
                default=str(col.default) if col.default else None,
            )
            for col in table.columns
            if not isinstance(col.type, NullType)
        }

        foreign_keys = [
            RelationInfo(
                from_table=table.name,
                from_column=fk.parent.name,
                to_table=fk.column.table.name,
                to_column=fk.column.name,
            )
            for fk in table.foreign_keys
        ]

        create_table = str(CreateTable(table).compile(self._engine))

        info = TableInfo(
            name=table.name,
            columns=columns,
            primary_key=[col.name for col in table.primary_key.columns],
            foreign_keys=foreign_keys,
            create_statement=create_table.rstrip(),
        )

        if self._indexes_in_table_info:
            info.indexes = self._get_table_indexes_structured(table)

        if self._sample_rows_in_table_info:
            info.sample_rows = self._get_sample_rows_structured(table)

        return info

    def _get_table_indexes_structured(self, table: Table) -> List[IndexInfo]:
        indexes = self._inspector.get_indexes(table.name)
        return [
            IndexInfo(
                name=index["name"],
                unique=index["unique"],
                columns=index["column_names"],
            )
            for index in indexes
        ]

    def _get_sample_rows_structured(self, table: Table) -> List[Dict[str, Any]]:
        command = select(table).limit(self._sample_rows_in_table_info)
        try:
            with self._engine.connect() as connection:
                result = connection.execute(command)
                return [dict(row) for row in result]
        except ProgrammingError:
            return []

    def _parse_custom_table_info(self, table_name: str, custom_info: str) -> TableInfo:
        # Implement this method to parse custom table info strings
        # into a structured format similar to _get_structured_table_info
        # For now, returning a placeholder
        return TableInfo(
            name=table_name,
            columns={},
            primary_key=[],
            foreign_keys=[],
            create_statement=custom_info,
        )

    def _get_table_indexes(self, table: Table) -> str:
        indexes = self._inspector.get_indexes(table.name)
        indexes_formatted = "\n".join(map(_format_index, indexes))
        return f"Table Indexes:\n{indexes_formatted}"

    def _get_sample_rows(self, table: Table) -> str:
        # build the select command
        command = select(table).limit(self._sample_rows_in_table_info)

        # save the columns in string format
        columns_str = "\t".join([col.name for col in table.columns])

        try:
            # get the sample rows
            with self._engine.connect() as connection:
                sample_rows_result = connection.execute(command)  # type: ignore
                # shorten values in the sample rows
                sample_rows = list(
                    map(lambda ls: [str(i)[:100] for i in ls], sample_rows_result)
                )

            # save the sample rows in string format
            sample_rows_str = "\n".join(["\t".join(row) for row in sample_rows])

        # in some dialects when there are no rows in the table a
        # 'ProgrammingError' is returned
        except ProgrammingError:
            sample_rows_str = ""

        return (
            f"{self._sample_rows_in_table_info} rows from {table.name} table:\n"
            f"{columns_str}\n"
            f"{sample_rows_str}"
        )

    def _execute(
        self,
        command: Union[str, Executable],
        fetch: Literal["all", "one", "cursor"] = "all",
        *,
        parameters: Optional[Dict[str, Any]] = None,
        execution_options: Optional[Dict[str, Any]] = None,
    ) -> Union[Sequence[Dict[str, Any]], Result]:
        """
        Executes SQL command through underlying engine.

        If the statement returns no rows, an empty list is returned.
        """
        parameters = parameters or {}
        execution_options = execution_options or {}
        with self._engine.begin() as connection:  # type: Connection  # type: ignore[name-defined]
            if self._schema is not None:
                if self.dialect == "snowflake":
                    connection.exec_driver_sql(
                        "ALTER SESSION SET search_path = %s",
                        (self._schema,),
                        execution_options=execution_options,
                    )
                elif self.dialect == "bigquery":
                    connection.exec_driver_sql(
                        "SET @@dataset_id=?",
                        (self._schema,),
                        execution_options=execution_options,
                    )
                elif self.dialect == "mssql":
                    pass
                elif self.dialect == "trino":
                    connection.exec_driver_sql(
                        "USE ?",
                        (self._schema,),
                        execution_options=execution_options,
                    )
                elif self.dialect == "duckdb":
                    # Unclear which parameterized argument syntax duckdb supports.
                    # The docs for the duckdb client say they support multiple,
                    # but `duckdb_engine` seemed to struggle with all of them:
                    # https://github.com/Mause/duckdb_engine/issues/796
                    connection.exec_driver_sql(
                        f"SET search_path TO {self._schema}",
                        execution_options=execution_options,
                    )
                elif self.dialect == "oracle":
                    connection.exec_driver_sql(
                        f"ALTER SESSION SET CURRENT_SCHEMA = {self._schema}",
                        execution_options=execution_options,
                    )
                elif self.dialect == "sqlany":
                    # If anybody using Sybase SQL anywhere database then it should not
                    # go to else condition. It should be same as mssql.
                    pass
                elif self.dialect == "postgresql":  # postgresql
                    connection.exec_driver_sql(
                        "SET search_path TO %s",
                        (self._schema,),
                        execution_options=execution_options,
                    )

            if isinstance(command, str):
                command = text(command)
            elif isinstance(command, Executable):
                pass
            else:
                raise TypeError(f"Query expression has unknown type: {type(command)}")
            cursor = connection.execute(
                command,
                parameters,
                execution_options=execution_options,
            )

            if cursor.returns_rows:
                if fetch == "all":
                    result = [x._asdict() for x in cursor.fetchall()]
                elif fetch == "one":
                    first_result = cursor.fetchone()
                    result = [] if first_result is None else [first_result._asdict()]
                elif fetch == "cursor":
                    return cursor
                else:
                    raise ValueError(
                        "Fetch parameter must be either 'one', 'all', or 'cursor'"
                    )
                return result
        return []

    def run(
        self,
        command: Union[str, Executable],
        fetch: Literal["all", "one", "cursor"] = "all",
        include_columns: bool = False,
        *,
        parameters: Optional[Dict[str, Any]] = None,
        execution_options: Optional[Dict[str, Any]] = None,
    ) -> QueryResult:
        """Execute a SQL command and return structured results."""
        pretty_log(f"Executing command: {command}")
        result = self._execute(
            command, fetch, parameters=parameters, execution_options=execution_options
        )

        if fetch == "cursor":
            raise ValueError("Fetch 'cursor' is not supported in structured output")

        headers = []
        data = []
        if result and len(result) > 0:
            headers = list(result[0].keys())
            data = [
                {
                    column: truncate_word(value, length=self._max_string_length)
                    for column, value in row.items()
                }
                for row in result
            ]
        pretty_log(f"Result: {data}")
        return QueryResult(
            headers=headers, data=data, message="Query executed successfully."
        )

    def get_table_info_no_throw(self, table_names: Optional[List[str]] = None) -> str:
        """Get information about specified tables.

        Follows best practices as specified in: Rajkumar et al, 2022
        (https://arxiv.org/abs/2204.00498)

        If `sample_rows_in_table_info`, the specified number of sample rows will be
        appended to each table description. This can increase performance as
        demonstrated in the paper.
        """
        try:
            return self.get_table_info(table_names)
        except ValueError as e:
            """Format the error message"""
            return f"Error: {e}"

    def run_no_throw(
        self,
        command: str,
        fetch: Literal["all", "one"] = "all",
        include_columns: bool = False,
        *,
        parameters: Optional[Dict[str, Any]] = None,
        execution_options: Optional[Dict[str, Any]] = None,
    ) -> Union[str, Sequence[Dict[str, Any]], Result[Any]]:
        """Execute a SQL command and return a string representing the results.

        If the statement returns rows, a string of the results is returned.
        If the statement returns no rows, an empty string is returned.

        If the statement throws an error, the error message is returned.
        """
        try:
            return self.run(
                command,
                fetch,
                parameters=parameters,
                execution_options=execution_options,
                include_columns=include_columns,
            )
        except SQLAlchemyError as e:
            """Format the error message"""
            return f"Error: {e}"

    def get_context(self) -> Dict[str, Any]:
        """Return db context that you may want in agent prompt."""
        table_names = list(self.get_usable_table_names())
        table_info = self.get_table_info()
        return {
            "table_info": table_info.model_dump(),
            "table_names": ", ".join(table_names),
        }

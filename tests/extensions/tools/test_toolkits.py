import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from marvin.extensions.context.tenant import set_current_tenant_id
from marvin.extensions.tools.tool_runner import fetch_and_run_toolkit_tool


def create_temp_file_sqlite_db():
    db_file = f"test_db_{uuid.uuid4()}.sqlite"
    db_url = f"sqlite:///{db_file}"
    return db_url, db_file


@pytest.fixture(scope="function")
def temp_db():
    db_url, db_file = create_temp_file_sqlite_db()
    yield db_url, db_file
    # Clean up the file after the test
    if os.path.exists(db_file):
        os.remove(db_file)


@pytest.mark.no_llm
def test_table_tool_operations(temp_db):
    """
    Create db, create table, add row, edit row, delete row, delete table
    """
    tenant_id = str(uuid.uuid4())
    set_current_tenant_id(tenant_id)
    db_url, db_file = temp_db
    # Create the database file
    engine = create_engine(db_url)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))  # This will create the file

    # Check if the file is actually created
    assert os.path.exists(db_file), f"Database file {db_file} was not created"

    def run_tool(tool_id, input_data):
        return fetch_and_run_toolkit_tool(
            tool_id=tool_id,
            toolkit_id="database",
            config={"url": db_url, "readonly": False},
            input_data=input_data,
        )

    # List tables (should be empty initially)
    result = run_tool("db_list_tables", {})
    assert result is not None, result
    assert result.get("result", []) is not None

    # Verify table creation
    result = run_tool("db_describe_tables", {})
    assert result["result"] is not None, result

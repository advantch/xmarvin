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
            toolkit_id="default_database",
            config={"url": db_url, "readonly": False},
            input_data=input_data,
        )

    # List tables (should be empty initially)
    result = run_tool("db_list_tables", {})
    assert result is not None, result
    assert len(result.get("result").tables) == 0, result

    # Create a table
    result = run_tool(
        "db_create_table",
        {
            "table": {
                "table_name": "notes",
                "columns": [
                    {"name": "id", "type": "INTEGER PRIMARY KEY AUTOINCREMENT"},
                    {"name": "date", "type": "DATE"},
                    {"name": "note", "type": "TEXT"},
                ],
            }
        },
    )
    assert result is not None, result
    assert "created successfully" in result["result"].description

    # Verify table creation
    result = run_tool("db_list_tables", {})
    assert "notes" in result["result"].tables

    # Add a row
    result = run_tool(
        "db_query",
        {"query": "INSERT INTO notes (date, note) VALUES ('2023-05-01', 'First note')"},
    )
    assert result["result"].message == "Query executed successfully."

    # Verify row addition
    result = run_tool("db_query", {"query": "SELECT * FROM notes"})
    assert len(result["result"].data) == 1
    assert result["result"].data[0]["note"] == "First note"

    # Add a column
    result = run_tool(
        "db_query", {"query": "ALTER TABLE notes ADD COLUMN category TEXT"}
    )
    assert result["result"].message == "Query executed successfully."

    # Edit a row
    result = run_tool(
        "db_query", {"query": "UPDATE notes SET category = 'personal' WHERE id = 1"}
    )
    assert result["result"].message == "Query executed successfully."

    # Verify edits
    result = run_tool("db_query", {"query": "SELECT * FROM notes"})
    assert len(result["result"].data) == 1
    assert result["result"].data[0]["category"] == "personal"

    # Delete a row
    result = run_tool("db_query", {"query": "DELETE FROM notes WHERE id = 1"})
    assert result["result"].message == "Query executed successfully."

    # Verify deletion
    result = run_tool("db_query", {"query": "SELECT * FROM notes"})
    assert len(result["result"].data) == 0

    # Delete table
    result = run_tool("db_query", {"query": "DROP TABLE notes"})
    assert result["result"].message == "Query executed successfully."

    # Final verification
    result = run_tool("db_list_tables", {})
    assert "notes" not in result["result"].tables


def test_table_relationships(temp_db):
    """
    Create db, create table, add row, edit row, delete row, delete table
    """

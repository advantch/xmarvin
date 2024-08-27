import pytest
from marvin.extensions.tools.tool_runner import fetch_and_run_toolkit_tool
from marvin.extensions.utilities.tenant import set_current_tenant_id



@pytest.mark.django_db
def test_table_tool_operations(tenant_user):
    """
    Create db, create table, add row, edit row, delete row, delete table
    """
    set_current_tenant_id(tenant_user.tenant.id)
    # create a default tenant database
    db = "sqlite:///:memory:"
    db_url = db

    def run_tool(tool_id, input_data):
        return fetch_and_run_toolkit_tool(
            tool_id=tool_id,
            toolkit_id="default_database",
            config={"url": db_url, 'readonly': False},
            input_data=input_data
        )

    # List tables (should be empty initially)
    result = run_tool("db_list_tables", {})
    assert result is not None, result
    assert len(result.get('result').tables) == 0, result

    # Create a table
    result = run_tool("db_create_table", {
        "table": {
            "table_name": "notes",
            "columns": [
                {"name": "id", "type": "INTEGER PRIMARY KEY AUTOINCREMENT"},
                {"name": "date", "type": "DATE"},
                {"name": "note", "type": "TEXT"}
            ]
        }
    })
    assert result is not None, result
    assert "created successfully" in result['result'].description

    # Verify table creation
    result = run_tool("db_list_tables", {})
    assert "notes" in result['result'].tables

    # Add a row
    result = run_tool("db_query", {
        "query": "INSERT INTO notes (date, note) VALUES ('2023-05-01', 'First note')"
    })
    assert result['result'].message == "Success: Query executed."

    # Verify row addition
    result = run_tool("db_query", {
        "query": "SELECT * FROM notes"
    })
    assert len(result['result'].data) == 1
    assert result['result'].data[0]['note'] == 'First note'

    # Add a column
    result = run_tool("db_query", {
        "query": "ALTER TABLE notes ADD COLUMN category TEXT"
    })
    assert result['result'].message == "Success: Query executed."

    # Edit a row
    result = run_tool("db_query", {
        "query": "UPDATE notes SET category = 'personal' WHERE id = 1"
    })
    assert result['result'].message == "Success: Query executed."

    # Verify edits
    result = run_tool("db_query", {
        "query": "SELECT * FROM notes"
    })
    assert len(result['result'].data) == 1
    assert result['result'].data[0]['category'] == 'personal'

    # Delete a row
    result = run_tool("db_query", {
        "query": "DELETE FROM notes WHERE id = 1"
    })
    assert result['result'].message == "Success: Query executed."

    # Verify deletion
    result = run_tool("db_query", {
        "query": "SELECT * FROM notes"
    })
    assert len(result['result'].data) == 0

    # Delete table
    result = run_tool("db_query", {
        "query": "DROP TABLE notes"
    })
    assert result['result'].message == "Success: Query executed."

    # Final verification
    result = run_tool("db_list_tables", {})
    assert "notes" not in result['result'].tables
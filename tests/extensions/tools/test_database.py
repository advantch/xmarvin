from marvin.extensions.tools.app_tools.database import db_connection
from marvin.extensions.tools.services.sql_database import SQLDatabase
import pytest
from marvin.extensions.tools.services.db import get_django_db_connection_url
from marvin.extensions.tools.services.db import (
    get_config_from_string,
    get_table_detail,
    get_table_names,
)


def test_get_config_from_string():
    url = "postgresql://pgbase:demox@ep-withered-dawn-00000.eu-central-1.aws.neon.tech/pgbase?sslmode=require&options=endpoint%3Dep-withered-dawn-00000"
    config = get_config_from_string(url)

    assert config is not None
    assert config["ENGINE"] == "django.db.backends.postgresql"
    assert config["NAME"] == "pgbase"
    assert config["USER"] == "pgbase"
    assert config["PASSWORD"] == "demox"
    assert config["HOST"] == "ep-withered-dawn-00000.eu-central-1.aws.neon.tech"
    assert config["OPTIONS"]["sslmode"] == "require"
    assert config["OPTIONS"]["options"] == "endpoint=ep-withered-dawn-00000"


def test_introspection():
    # Get the database connection
    connection = db_connection("sqlite:///:memory:")
    table_names = connection.get_table_names()
    # Iterate over the table names and retrieve column information
    for table_name in table_names:
        data = connection.get_table_info(table_name)
        assert data is not None, data
        assert isinstance(data, dict), data
        assert "columns" in data, data
        assert "table_name" in data, data
        assert "description" in data, data


def test_generates_correct_url_for_postgresql(mocker):
    mocker.patch(
        "marvin.extensions.tools.services.db.get_db_config",
        return_value={
            "ENGINE": "django.db.backends.postgresql",
            "USER": "testuser",
            "PASSWORD": "testpassword",
            "HOST": "localhost",
            "PORT": "5432",
            "NAME": "testdb",
        },
    )
    expected_url = "postgresql://testuser:testpassword@localhost:5432/testdb"
    assert get_django_db_connection_url() == expected_url

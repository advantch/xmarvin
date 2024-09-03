from marvin.extensions.utilities.logging import logger
from marvin.extensions.settings import extension_settings
try:
    import environ
    from django.conf import settings
    from django.db.utils import DEFAULT_DB_ALIAS, load_backend
except ImportError as e:
    print(f"ImportError: {e} - this package is only available in django")


def get_config_from_string(url):
    env = environ.Env()
    config = env.db_url_config(url)
    return config


def get_db_config(db_alias="default"):
    try:
        return settings.DATABASES[db_alias]
    except Exception as e:
        logger.error(f"Error getting db config: {e}")
        return {}


def get_django_db_connection_url(db_alias="default"):
    """
    Returns a connection url for a django database

    Note:
    Neon.tech requires ssl_mode=require + endpoint.
    """
    db_settings = get_db_config(db_alias)

    engine = db_settings["ENGINE"].split(".")[-1]
    username = db_settings.get("USER", "")
    password = db_settings.get("PASSWORD", "")
    host = db_settings.get("HOST", "")
    port = db_settings.get("PORT", "")
    dbname = db_settings.get("NAME", "")

    if engine == "sqlite3":
        db_url = f"sqlite:///{dbname}"
    else:
        db_url = f"{engine}://{username}:{password}@{host}:{port}/{dbname}"
    # neon db requires ssl_mode=require + endpoint.
    if "neon.tech" in db_url:
        options = db_settings.get("OPTIONS", {})
        db_url = f"{db_url}?sslmode=require&options={options.get('options')}"

    return db_url


def create_connection(alias=None, url=None):
    if alias is None:
        alias = DEFAULT_DB_ALIAS
    if url is not None:
        config = get_config_from_string(url)
    else:
        config = get_db_config(alias)
    defaults = {
        "DISABLE_SERVER_SIDE_CURSORS": True,
        "TIME_ZONE": "UTC",
        "CONN_HEALTH_CHECKS": False,
        "CONN_HEALTH_CHECKS_TIMEOUT": 1,
        "CONN_MAX_AGE": 0,
        "AUTOCOMMIT": True,
    }
    config.update(defaults)
    backend = load_backend(config["ENGINE"])
    return backend.DatabaseWrapper(config, alias)


def get_table_names(connection=None, url=None):
    cache_key = f"table_names_{url}"
    cache = extension_settings.storage.cache
    names = cache.get(cache_key)
    if names is not None:
        return names
    if connection is None:
        connection = create_connection(url=url)
    introspection = connection.introspection
    table_names = introspection.table_names()
    return table_names


def get_table_detail(table_name, connection=None, url=None):
    if connection is None:
        connection = create_connection(url=url)
    introspection = connection.introspection
    column_names = introspection.get_table_description(connection.cursor(), table_name)
    description = introspection.get_table_description(connection.cursor(), table_name)
    rows = {}
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 2")
        result = cursor.fetchall()
        rows = result
    detail = {
        "columns": column_names,
        "table_name": table_name,
        "description": description,
    }
    if rows:
        detail["rows"] = rows
    return detail


def introspect_db_table_full(connection=None, url=None):
    if connection is None:
        connection = create_connection(url=url)
    introspection = connection.introspection
    table_names = introspection.table_names()
    # colums
    columns = []
    db_data = {}

    for table_name in table_names:
        columns = get_table_detail(table_name, connection=connection, url=url)
        db_data[table_name] = {
            "columns": columns["columns"],
            "table_name": columns["table_name"],
        }
        # select first two rows
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 2")
            result = cursor.fetchall()
            db_data[table_name]["rows"] = result
    return db_data


def dictfetchall(cursor):
    """
    Return all rows from a cursor as a dict.
    Assume the column names are unique.
    """
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def headers_and_rows(cursor):
    headers = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    return {"headers": headers, "rows": rows}


def run_query(query, connection=None, url=None, as_dict=True):
    try:
        if connection is None:
            connection = create_connection(url=url)
        with connection.cursor() as cursor:
            logger.info(f"running query {query}")
            cursor.execute(query)
            if as_dict:
                result = dictfetchall(cursor)
            else:
                result = headers_and_rows(cursor)
        return result
    except Exception as e:
        return {"error": str(e)}

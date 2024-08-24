from apps.common.logging import logger
from django.conf import settings
from jira import JIRA

server = "https://digibri.atlassian.net"
vg_server = "https://vastgoeddata.atlassian.net"
token = settings.JIRA_TOKEN


def client():
    try:
        return JIRA(basic_auth=("themba@teamcoda.com", token), server=vg_server)
    except Exception as e:
        logger.error(e)


cl = client()


def me():
    return cl.myself()


def projects():
    return cl.projects()


def orgs():
    return cl.organizations()


def search_issues(project_key):
    cl = client()
    try:
        issues = cl.search_issues(f"project={project_key}")
        return issues
    except Exception as e:
        logger.error(e)


if __name__ == "__main__":
    pass

import httpx
from marvin.extensions.tools.tool import tool
from marvin.extensions.tools.tool_kit import ToolKit
from pydantic import BaseModel, Field


class WebBrowserResult(BaseModel):
    success: bool = Field(description="Whether the request was successful")
    status: int = Field(description="The HTTP status code of the request")
    title: str = Field(description="The title of the website")
    url: str = Field(description="The url of the website")
    content: str = Field(description="The content of the website")
    images: dict | list | None = Field(description="The images of the website")
    links: dict | list | None = Field(description="The links of the website")


@tool(
    name="web_browser",
    description="This tool is used to fetch data from websites.",
)
def web_browser(url: str) -> WebBrowserResult:
    """
    url: - https - url
    Returns webpage data from a url.
    DO NOT USE THIS for youtube videos,translation or generating images.
    """
    if url.startswith("http://"):
        url = url.replace("http://", "https://")
    fetch_url = "https://r.jina.ai/" + url
    headers = {
        "API-KEY": "test",
        "Accept": "application/json",
        "X-With-Generated-Alt": "true",
        "X-Timeout": "20",
        "X-With-Images-Summary": "true",
        "X-With-Links-Summary": "true",
    }
    res = httpx.get(fetch_url, headers=headers, timeout=420)
    if res.status_code == 200:
        return WebBrowserResult(
            success=True,
            status=res.json()["code"],
            title=res.json()["data"]["title"],
            url=res.json()["data"]["url"],
            content=res.json()["data"]["content"],
            images=res.json()["data"]["images"],
            links=res.json()["data"]["links"],
        )

    return WebBrowserResult(
        success=False,
        status=res.status_code,
        title="",
        url="",
        content=f"This page could not be fetched. {res.content}",
        images=None,
        links=None,
    )


web_browser_toolkit = ToolKit.create_toolkit(
    id="web_browser",
    tools=[web_browser],
    name="web_browser",
    description="This tool is used to fetch data from websites.",
    icon="Globe",
    categories=["web"],
)

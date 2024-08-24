from __future__ import annotations

import json
import re

import aiohttp
import requests
from django.conf import settings
from llama_index.core.schema import Document
from pydantic import BaseModel, Extra, Field, model_validator


class AnswerBox(BaseModel):
    snippet: str | None = None
    title: str | None = None
    link: str = None


class Sitelink(BaseModel):
    title: str = None
    link: str | None = None


class Attributes(BaseModel):
    duration: str | None = None
    posted: str | None = None


class OrganicItem(BaseModel):
    title: str | None
    link: str | None
    snippet: str | None
    date: str | None = None
    position: int | None = None
    sitelinks: list[Sitelink] | None = None
    attributes: Attributes | None = None
    image_url: str | None = None


class PeopleAlsoAskItem(BaseModel):
    question: str | None = None
    snippet: str | None = None
    title: str | None = None
    link: str | None = None


class RelatedSearch(BaseModel):
    query: str | None = None


class FastSerpSchema(BaseModel):
    answer_box: AnswerBox | None = Field(None, alias="answerBox")
    organic: list[OrganicItem] | None = None
    people_also_ask: list[PeopleAlsoAskItem] | None = Field(None, alias="peopleAlsoAsk")
    related_searches: list[RelatedSearch] | None = Field(None, alias="relatedSearches")

    def clean_string(self, string: str) -> str:
        """Clean string."""
        return re.sub(r"[^\x20-\x7E]", "", string)

    def top_ten_as_string_list(self) -> str:
        """Return the top ten results as a list of strings."""

        results = []
        if self.answer_box:
            answer_box = [
                "Answer box: "
                + self.clean_string(self.answer_box.title)
                + "\n"
                + self.clean_string(self.answer_box.snippet)
            ]
            results.extend(answer_box)
        if self.organic:
            results.extend(
                [
                    "title: "
                    + self.clean_string(item.title)
                    + "\n link: "
                    + item.link
                    + "\nsnippet: "
                    + self.clean_string(item.snippet)
                    for item in self.organic
                ]
            )
        if self.people_also_ask:
            people_also_ask = [
                "People also ask: "
                + self.clean_string(item.question)
                + "\n"
                + self.clean_string(item.snippet)
                for item in self.people_also_ask
            ]
            results.extend(people_also_ask)

        if self.related_searches:
            related_searches = [
                "Related searches: " + self.clean_string(item.query)
                for item in self.related_searches
            ]
            results.extend(related_searches)

        return "-----------\n".join(results)

    def as_documents(self):
        """Return the top ten results as a list of strings."""
        top_ten = [
            {
                "title": self.clean_string(item.title),
                "link": item.link,
                "snippet": self.clean_string(item.snippet),
            }
            for item in self.organic
        ]

        documents = []
        for item in top_ten:
            documents.append(
                Document(
                    text=item["snippet"],
                    extra_info={"title": item["title"], "url": item["link"]},
                )
            )
        if self.answer_box:
            documents.append(
                Document(
                    text=self.clean_string(self.answer_box.title),
                    extra_info={"url": self.answer_box.link},
                )
            )
        return documents


class SerperSearchArgsSchema(BaseModel):
    query: str = Field(..., alias="q")
    gl: str = "us"
    hl: str = "en"
    num: int = 10


class SerperAPIWrapper(BaseModel):
    """Wrapper around SerpAPI."""

    search_engine: str = Field(default="google")
    params: dict = Field(
        default={
            "api_key": settings.SERP_DEV_API_KEY,
            "include_answer_box": "true",
            "include_html": "false",
            "max_page": "2",
            "page": "1",
            "num": "20",
            "location": "USA",
            "autocorrect": "false",
        }
    )

    # make the http GET request to VALUE SERP

    aiosession: aiohttp.ClientSession | None = None

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid
        arbitrary_types_allowed = True

    @model_validator(mode="before")
    def validate_environment(cls, values: dict) -> dict:
        """Validate that api key and python package exists in environment."""

        return values

    async def arun(
        self,
        query: str,
        engine: str = "google",
        gl: str = "us",
        hl: str = "en",
        num: int = 10,
    ) -> str:
        """Use aiohttp to run query through SerpAPI and parse result."""

        def construct_url_and_params() -> tuple[str, dict[str, str]]:
            params = self.get_params(query, engine, gl, hl, num)
            url = "https://google.serper.dev/search"
            return url, params

        url, params = construct_url_and_params()
        if not self.aiosession:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    res = await response.json()
        else:
            async with self.aiosession.get(url, params=params) as response:
                res = await response.json()

        return self._process_response(res)

    def run_raw(
        self, query, engine="google", gl="us", hl="en", num=10
    ) -> FastSerpSchema:
        """Run query through SerpAPI and parse result."""

        def construct_url_and_params() -> tuple[str, dict[str, str]]:
            params = self.get_params(query, engine, gl, hl, num)
            url = "https://google.serper.dev/search"
            return url, params

        url, params = construct_url_and_params()
        response = requests.get(url, params=params)
        res = FastSerpSchema(**response.json())
        return res

    def run(
        self,
        query: str,
        engine: str = "google",
        gl: str = "us",
        hl: str = "en",
        num: int = 10,
    ) -> str:
        """Run query through SerpAPI and parse result."""

        def construct_url_and_params() -> tuple[str, dict[str, str]]:
            params = self.get_params(query, engine, gl, hl)
            url = "https://google.serper.dev/search"
            return url, params

        url, params = construct_url_and_params()
        response = requests.get(url, params=params)

        return self._process_response(response.json())

    def get_params(
        self,
        query: str,
        engine: str = "google",
        gl: str = "us",
        hl: str = "en",
        num: int = 10,
    ) -> dict[str, str]:
        """Get parameters for SerpAPI."""
        _params = {
            "q": query,
            "gl": gl,
            "hl": hl,
            "num": num,
        }
        params = {**self.params, **_params}
        return params

    @staticmethod
    def _process_response(res: dict) -> str:
        """Process response from ValueAPI."""
        try:
            response = FastSerpSchema(**res)
        except Exception as e:
            return f"Error unable to fetch results. please try another tool: {e}"

        if response.organic:
            return response.top_ten_as_string_list()
        if response.answer_box:
            return response.answer_box.snippet
        else:
            toret = "No good search result found"
            return toret


def search_tool(query: str) -> str:
    """
    Use this to search google for results
    """
    search_wrapper = SerperAPIWrapper()
    results = {"results": search_wrapper.run(query)}
    return json.dumps(results)

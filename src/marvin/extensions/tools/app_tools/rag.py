import re
from typing import List

import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationInfo, model_validator

client = instructor.from_openai(AsyncOpenAI())


class Fact(BaseModel):
    fact: str = Field(...)
    substring_quote: List[str] = Field(...)

    @model_validator(mode="after")
    def validate_sources(self, info: ValidationInfo) -> "Fact":
        text_chunks = info.context.get("text_chunk", None)
        spans = list(self.get_spans(text_chunks))
        self.substring_quote = [text_chunks[span[0] : span[1]] for span in spans]
        return self

    def get_spans(self, context):
        for quote in self.substring_quote:
            yield from self._get_span(quote, context)

    def _get_span(self, quote, context):
        for match in re.finditer(re.escape(quote), context):
            yield match.span()


class QuestionAnswer(BaseModel):
    question: str = Field(...)
    answer: List[Fact] = Field(...)

    @model_validator(mode="after")
    def validate_sources(self) -> "QuestionAnswer":
        self.answer = [fact for fact in self.answer if len(fact.substring_quote) > 0]
        return self


def ask_ai(question: str, context: str) -> QuestionAnswer:
    return client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_model=QuestionAnswer,
        messages=[
            {
                "role": "system",
                "content": "You are a world class algorithm to answer questions with correct and exact citations.",
            },
            {"role": "user", "content": f"{context}"},
            {"role": "user", "content": f"Question: {question}"},
        ],
        validation_context={"text_chunk": context},
    )

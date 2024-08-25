from pydantic import AnyHttpUrl


class BaseModelConfig:
    extra = "allow"
    allow_mutation = False
    arbitrary_types_allowed = True


class CustomUrl(AnyHttpUrl):
    pass

from pydantic import AnyHttpUrl, BaseModel


class BaseSchemaConfig(BaseModel.Config):
    extra = "allow"
    allow_mutation = False
    arbitrary_types_allowed = True


class CustomUrl(AnyHttpUrl):
    pass

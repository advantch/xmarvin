import json
from typing import Any, Dict, List, Optional, Union
from marvin.extensions.utilities.serialization import to_serializable
from pydantic import BaseModel, Field, field_validator, model_validator
from pathlib import Path


class BaseStorageLayer(BaseModel):
    """
    Base storage layer.
    """
    def get(self, key: str) -> Optional[Any]:
        raise NotImplementedError("Method not implemented.")
    
    def set(self, key: str, value: Any):
        raise NotImplementedError("Method not implemented.")
    
    def update(self, key: str, value: Any):
        raise NotImplementedError("Method not implemented.")    
    
    def create(self, key: str, value: Any):
        raise NotImplementedError("Method not implemented.")
    
    def delete(self, key: str):
        raise NotImplementedError("Method not implemented.")
    
    def list(self, **filters) -> List[Any]:
        raise NotImplementedError("Method not implemented.")
    
    def filter(self, **filters) -> List[Any]:
        raise NotImplementedError("Method not implemented.")
    

class MemStore(BaseStorageLayer):
    """
    Simple in memory storage layer.
    """
    core: Dict[str, Any] = {}
    prefix: str = "default"

    @model_validator(mode="after")
    def get_state(self) -> "MemStore":
        self.core[self.prefix] = {}
        return self

    @property
    def store(self) -> Dict[str, Any]:
        return self.core[self.prefix]

    def get(self, key: str) -> Optional[Any]:
        return self.store.get(key, None)

    def set(self, key: str, value: Any):
        self.store[key] = value
    
    def update(self, key: str, value: Any):
        self.store[key] = value

    def create(self, key: str, value: Any):
        self.store[key] = value

    def delete(self, key: str):
        del self.store[key]

    def filter(self, **filters) -> List[Any]:
        items = list(self.store.values())
        for key, value in filters.items():
            items = [item for item in items if getattr(item, key, None) == value]
        return items

    def list(self, **filters) -> List[Any]:
        return list(self.store.values())

class JsonFileStore(BaseStorageLayer):
    """
    Simple in memory storage layer.
    """
    core: Any = Field(default_factory=dict)
    prefix: str = "default"
    path: Path = Field(
        'state.json', description="The path to the file where state will be stored."
    )

    @field_validator("path")
    def _validate_path(cls, v: Union[str, Path]) -> Path:
        expanded_path = Path(v).expanduser().resolve()
        if not expanded_path.exists():
            expanded_path.parent.mkdir(parents=True, exist_ok=True)
            expanded_path.touch(exist_ok=True)
        return expanded_path

    @model_validator(mode="after")
    def get_state(self) -> "JsonFileStore":
        self.path = Path(self.path).expanduser().resolve()
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.touch(exist_ok=True)
        with open(self.path, "r") as f:
            try:
                self.core = json.load(f)
            except json.JSONDecodeError:
                self.core = {self.prefix: {}}
        return self

    def _save(self):
        with open(self.path, "w") as f:
            str_val = to_serializable(self.core)
            json.dump(str_val, f)

    @property
    def store(self) -> Dict[str, Any]:
        return self.core[self.prefix]

    def get(self, key: str) -> Optional[Any]:
        return self.store.get(key, None)

    def set(self, key: str, value: Any):
        self.store[str(key)] = value
        self._save()

    def update(self, key: str, value: Any):
        self.store[str(key)] = value
        self._save()

    def create(self, key: str, value: Any):
        self.store[str(key)] = value
        self._save()

    def delete(self, key: str):
        del self.store[str(key)]
        self._save()

    def list(self, **filters) -> List[Any]:
        items = list(self.store.values())
        for key, value in filters.items():
            items = [item for item in items if getattr(item, str(key), None) == value]
        return items
    
    def filter(self, **filters) -> List[Any]:
        items = list(self.store.values())
        for key, value in filters.items():
            items = [item for item in items if getattr(item, str(key), None) == value]
        return items
    


class DjangoModelStore(BaseStorageLayer):
    """
    Django model storage layer. 
    Expects a django model manager to be passed in.
    Must implement all the methods of the base storage layer.
    """
    manager: Any = Field(
        ..., description="The django model manager to use for storage."
    )
    id_key: str = Field(
        "id", description="The key to use for filtering the django model."
    )
    search_keys: List[str] = Field(
        ["id"], description="The keys to use for searching the django model."
    )

    def get(self, key: str) -> Optional[Any]:   
        return self.manager.objects.get(**{self.id_key: key})
    
    def set(self, key: str, value: Any):
        return self.manager.objects.get_or_create(**{self.id_key: key, **value})
    
    def delete(self, key: str):
        return self.manager.objects.filter(**{self.id_key: key}).delete()
    
    def list(self, **filters) -> List[Any]:
        return self.manager.objects.filter(**filters)
    
    def update(self, key: str, value: Any):
        return self.manager.objects.filter(**{self.id_key: key}).update(**value)
    
    def create(self, value: Any):
        return self.manager.objects.create(**value)
    
    def delete(self, key: str):
        return self.manager.objects.filter(**{self.id_key: key}).delete()
    
    def search(self, **filters) -> List[Any]:
        return self.manager.objects.filter(**filters)
    
    
    
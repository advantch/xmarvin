import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime, time
from uuid import UUID

import humps
import pydantic
from marvin.extensions.monitoring.logging import logger
from pydantic import BaseModel



class DefaultJsonEncoder(json.JSONEncoder):
    """UUID encoder for json"""

    @staticmethod
    def is_json_serializable(obj):
        try:
            json.dumps(obj)
            return True
        except (TypeError, OverflowError):
            return False

    def default(self, obj):
        cleaned_obj = obj

        if isinstance(cleaned_obj, BaseModel):
            try:
                data = cleaned_obj.model_dump()
            
                return data
            except Exception as e:
                logger.error(f"Failed to serialize {cleaned_obj} {e}")  
                return str(cleaned_obj)

        if isinstance(cleaned_obj, UUID):
            return str(cleaned_obj)

        if isinstance(cleaned_obj, datetime):
            return cleaned_obj.isoformat()

        if isinstance(cleaned_obj, date):
            return cleaned_obj.isoformat()

        if isinstance(cleaned_obj, time):
            return cleaned_obj.isoformat()
        if pydantic.dataclasses.is_pydantic_dataclass(cleaned_obj):
            return cleaned_obj.model_dump()
        
        try:
            from django.db import models
            from django.db.models.query import QuerySet
            from django.forms.models import model_to_dict
            
            if isinstance(cleaned_obj, models.Model):
                return model_to_dict(cleaned_obj)

            if isinstance(cleaned_obj, QuerySet):
                return [model_to_dict(model) for model in cleaned_obj]
        except ImportError:
            pass



        if is_dataclass(cleaned_obj):
            try:
                return asdict(cleaned_obj)
            except TypeError:
                return str(cleaned_obj)

        else:
            if not self.is_json_serializable(cleaned_obj):
                return str(cleaned_obj)
        return json.JSONEncoder.default(self, cleaned_obj)


def to_serializable(obj):
    return json.loads(json.dumps(obj, cls=DefaultJsonEncoder))


def camelized(obj):
    return humps.camelize(obj)

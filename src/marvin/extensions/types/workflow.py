import uuid
from datetime import datetime

from apps.ai.vflow.types import Node, ReactFlowData
from apps.common.schema import BaseSchemaConfig
from django.utils import timezone
from django_celery_beat.models import IntervalSchedule
from ninja import Schema


class WorkflowSchema(Schema):
    id: uuid.UUID | None = None
    name: str = "New Workflow"
    description: str = ""
    data: ReactFlowData
    created: str | datetime | None = None
    modified: str | datetime | None = None
    run_count: int | None = None

    class Config(BaseSchemaConfig):
        pass

    @classmethod
    def default_workflow(cls):
        return cls(
            name="New Workflow",
            data=ReactFlowData.default_flow(),
        )

    def schedule_node(self) -> Node:
        if not self.data.nodes or len(self.data.nodes) == 0:
            return None
        return self.data.nodes[0] if self.data.nodes[0].type == "trigger" else None

    def get_schedule_time(self):
        """
        Returns the schedule time for the workflow.
        If run_once, or specific_time, returns the time.
        if interval, returns None which will be run at start time or immediately and set to once.
        """
        schedule_node = self.schedule_node()
        if not schedule_node:
            return None
        if schedule_node.data.schedule == "run_once":
            return timezone.now()
        elif schedule_node.data.schedule == "interval":
            return timezone.now()
        elif schedule_node.data.schedule == "specific_time":
            return schedule_node.data.scheduled_at

    def celery_interval(self):
        """
        Returns the interval schedule for the workflow.
        Available for interval only.
        """
        schedule_node = self.schedule_node()
        if not schedule_node:
            return None
        schedule_time = self.get_schedule_time()
        if not schedule_time:
            return None
        interval = schedule_node.data.schedule == "interval"
        if interval:
            return IntervalSchedule.objects.get_or_create(
                every=schedule_node.data.interval_type(),
                period=schedule_node.data.interval_unit(),
            )
        return None

    def celery_one_off(self):
        schedule_node = self.schedule_node()
        if not schedule_node:
            return False
        return schedule_node.type == "run_once"


class WorkflowRunRequestMeta(Schema):
    workflow_id: uuid.UUID | None = None
    execution_id: uuid.UUID | None = None
    user_id: uuid.UUID | str | None = None
    created: datetime | str | None = None
    name: str | None = None
    description: str | None = None

    class Config(BaseSchemaConfig):
        pass


class WorkflowExecutionData(Schema):
    meta: WorkflowRunRequestMeta | None = None

    class Config(BaseSchemaConfig):
        pass


class WorkflowExecutionSchema(Schema):
    id: uuid.UUID | str | None = None
    name: str | None = None
    workflow_id: uuid.UUID | str | None = None
    status: str | None = None
    logs: list | None = None
    created: datetime | None = None
    modified: datetime | None = None
    data: WorkflowExecutionData | None = None

    class Config(BaseSchemaConfig):
        pass


class WorkflowRunResponse(Schema):
    status: str
    workflow_id: uuid.UUID | str
    execution: WorkflowExecutionSchema

    class Config(BaseSchemaConfig):
        pass


class WorkflowRunRequest(Schema):
    workflow_id: uuid.UUID | str
    override: bool = False

    class Config(BaseSchemaConfig):
        pass


class WorkflowStopRequest(Schema):
    execution_id: uuid.UUID | str

    class Config(BaseSchemaConfig):
        pass


class WorkflowStopResponse(Schema):
    status: str
    execution_id: uuid.UUID | str

    class Config(BaseSchemaConfig):
        pass

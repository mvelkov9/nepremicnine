"""Pydantic schemas for GUI phase 2 workbench APIs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkspaceBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    scope: str = Field(default="private", max_length=40)
    page: str = Field(min_length=1, max_length=80)
    filters: dict[str, Any] = Field(default_factory=dict)
    tab: str | None = Field(default=None, max_length=80)
    sort: str | None = Field(default=None, max_length=120)
    columns: list[str] = Field(default_factory=list)
    pinned: bool = False


class WorkspaceCreateRequest(WorkspaceBase):
    pass


class WorkspaceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    scope: str | None = Field(default=None, max_length=40)
    page: str | None = Field(default=None, min_length=1, max_length=80)
    filters: dict[str, Any] | None = None
    tab: str | None = Field(default=None, max_length=80)
    sort: str | None = Field(default=None, max_length=120)
    columns: list[str] | None = None
    pinned: bool | None = None


class SavedWorkspaceResponse(WorkspaceBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WatchlistCreateRequest(BaseModel):
    entity_type: str = Field(min_length=1, max_length=40)
    entity_key: str = Field(min_length=1, max_length=200)
    display_label: str = Field(min_length=1, max_length=200)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WatchlistItemResponse(BaseModel):
    id: int
    entity_type: str
    entity_key: str
    display_label: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class WatchlistFeedItemResponse(BaseModel):
    id: str
    entity_type: str
    entity_key: str
    display_label: str
    headline_value: float | int | None = None
    headline_label: str | None = None
    trend_value: float | None = None
    trend_label: str | None = None
    link: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)


class ActivityFeedItemResponse(BaseModel):
    id: str
    category: str
    title: str
    body: str | None = None
    link: str | None = None
    scope: str = "viewer"
    is_read: bool = False
    created_at: datetime | str
    payload: dict[str, Any] = Field(default_factory=dict)


class MarkActivityReadResponse(BaseModel):
    ok: bool = True
    unread: int = 0


class AdminRunSummaryResponse(BaseModel):
    id: str
    run_type: str
    status: str
    stage: str | None = None
    progress: int | None = None
    title: str
    summary: str | None = None
    created_at: datetime | str
    updated_at: datetime | str | None = None


class AdminRunDetailResponse(BaseModel):
    id: str
    run_type: str
    status: str
    stage: str | None = None
    progress: int | None = None
    title: str
    summary: str | None = None
    created_at: datetime | str
    updated_at: datetime | str | None = None
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    metrics: list[dict[str, Any]] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)

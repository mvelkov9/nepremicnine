"""Viewer/admin workbench persistence routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.stats import _find_municipality_frame, _prepare_market_df, _round_or_none, _viewer_frame
from app.database import get_db
from app.dependencies.auth import get_current_user
from app.models.activity import ActivityEvent
from app.models.user import User
from app.models.watchlist import WatchlistItem
from app.models.workspace import Workspace
from app.schemas.workbench import (
    SavedWorkspaceResponse,
    WatchlistCreateRequest,
    WatchlistFeedItemResponse,
    WatchlistItemResponse,
    WorkspaceCreateRequest,
    WorkspaceUpdateRequest,
)
from app.utils.cache import invalidate_request_caches
from app.utils.municipality import municipality_slug
from app.utils.slovenian_labels import labels_match

router = APIRouter(tags=["workbench"])


def _workspace_to_response(item: Workspace) -> SavedWorkspaceResponse:
    return SavedWorkspaceResponse(
        id=item.id,
        name=item.name,
        scope=item.scope,
        page=item.page,
        filters=json.loads(item.filters_json) if item.filters_json else {},
        tab=item.tab,
        sort=item.sort,
        columns=json.loads(item.columns_json) if item.columns_json else [],
        pinned=item.pinned,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _watchlist_to_response(item: WatchlistItem) -> WatchlistItemResponse:
    return WatchlistItemResponse(
        id=item.id,
        entity_type=item.entity_type,
        entity_key=item.entity_key,
        display_label=item.display_label,
        metadata=json.loads(item.metadata_json) if item.metadata_json else {},
        created_at=item.created_at,
    )


async def _record_activity(
    db: AsyncSession,
    *,
    user_id: int,
    scope: str,
    category: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
    payload: dict | None = None,
) -> None:
    db.add(
        ActivityEvent(
            user_id=user_id,
            scope=scope,
            category=category,
            title=title,
            body=body,
            link=link,
            payload_json=json.dumps(payload or {}, ensure_ascii=True),
        )
    )


def _watchlist_feed_for_municipality(item: WatchlistItem, df=None) -> WatchlistFeedItemResponse:
    if df is None:
        df = _prepare_market_df()
    if df is None or df.empty:
        return WatchlistFeedItemResponse(
            id=f"watchlist:{item.id}",
            entity_type=item.entity_type,
            entity_key=item.entity_key,
            display_label=item.display_label,
            link=f"/obcine/{municipality_slug(item.entity_key)}",
        )

    frame = _viewer_frame(df)
    municipality_df = _find_municipality_frame(frame, item.entity_key)
    if municipality_df.empty:
        return WatchlistFeedItemResponse(
            id=f"watchlist:{item.id}",
            entity_type=item.entity_type,
            entity_key=item.entity_key,
            display_label=item.display_label,
            link=f"/obcine/{municipality_slug(item.entity_key)}",
        )

    years = sorted([str(year) for year in municipality_df["_year"].dropna().unique().tolist()])
    latest_year = years[-1] if years else None
    previous_year = years[-2] if len(years) > 1 else None
    latest_df = municipality_df[municipality_df["_year"].astype(str) == latest_year] if latest_year else municipality_df
    previous_df = (
        municipality_df[municipality_df["_year"].astype(str) == previous_year]
        if previous_year
        else municipality_df.iloc[0:0]
    )
    previous_count = len(previous_df)
    trend_value = ((len(latest_df) - previous_count) / previous_count) * 100 if previous_count > 0 else None

    return WatchlistFeedItemResponse(
        id=f"watchlist:{item.id}",
        entity_type=item.entity_type,
        entity_key=municipality_slug(str(municipality_df["municipality"].iloc[0])),
        display_label=str(municipality_df["municipality"].iloc[0]),
        headline_value=_round_or_none(latest_df["_price_per_m2"].dropna().median()),
        headline_label="median_price_per_m2",
        trend_value=_round_or_none(trend_value, 1),
        trend_label="volume_delta_pct",
        link=f"/obcine/{municipality_slug(str(municipality_df['municipality'].iloc[0]))}",
        context={
            "region": str(latest_df["statistical_region"].mode().iloc[0])
            if "statistical_region" in latest_df.columns and not latest_df["statistical_region"].dropna().empty
            else None,
            "latest_year": latest_year,
            "transaction_count": int(len(latest_df)),
        },
    )


def _watchlist_feed_for_region(item: WatchlistItem, df=None) -> WatchlistFeedItemResponse:
    if df is None:
        df = _prepare_market_df()
    if df is None or df.empty:
        return WatchlistFeedItemResponse(
            id=f"watchlist:{item.id}",
            entity_type=item.entity_type,
            entity_key=item.entity_key,
            display_label=item.display_label,
            link=f"/regije?tab=drilldown&region={item.entity_key}",
        )

    frame = _viewer_frame(df)
    region_df = frame[frame["statistical_region"].map(lambda value: labels_match(value, item.entity_key))]
    if region_df.empty:
        return WatchlistFeedItemResponse(
            id=f"watchlist:{item.id}",
            entity_type=item.entity_type,
            entity_key=item.entity_key,
            display_label=item.display_label,
            link=f"/regije?tab=drilldown&region={item.entity_key}",
        )

    years = sorted([str(year) for year in region_df["_year"].dropna().unique().tolist()])
    latest_year = years[-1] if years else None
    previous_year = years[-2] if len(years) > 1 else None
    latest_df = region_df[region_df["_year"].astype(str) == latest_year] if latest_year else region_df
    previous_df = region_df[region_df["_year"].astype(str) == previous_year] if previous_year else region_df.iloc[0:0]
    previous_count = len(previous_df)
    trend_value = ((len(latest_df) - previous_count) / previous_count) * 100 if previous_count > 0 else None

    return WatchlistFeedItemResponse(
        id=f"watchlist:{item.id}",
        entity_type=item.entity_type,
        entity_key=item.entity_key,
        display_label=item.display_label,
        headline_value=_round_or_none(latest_df["_price_per_m2"].dropna().median()),
        headline_label="median_price_per_m2",
        trend_value=_round_or_none(trend_value, 1),
        trend_label="volume_delta_pct",
        link=f"/regije?tab=drilldown&region={item.entity_key}",
        context={
            "latest_year": latest_year,
            "transaction_count": int(len(latest_df)),
            "municipalities": int(latest_df["_municipality_slug"].nunique())
            if "_municipality_slug" in latest_df.columns
            else 0,
        },
    )


@router.get("/workspaces", response_model=list[SavedWorkspaceResponse])
async def list_workspaces(
    page: str | None = Query(None),
    pinned: bool | None = Query(None),
    limit: int | None = Query(None, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Workspace).where(Workspace.user_id == user.id)
    if page:
        stmt = stmt.where(Workspace.page == page)
    if pinned is not None:
        stmt = stmt.where(Workspace.pinned == pinned)
    stmt = stmt.order_by(Workspace.pinned.desc(), Workspace.updated_at.desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return [_workspace_to_response(item) for item in result.scalars().all()]


@router.post("/workspaces", response_model=SavedWorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: Request,
    body: WorkspaceCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = Workspace(
        user_id=user.id,
        name=body.name,
        scope=body.scope,
        page=body.page,
        filters_json=json.dumps(body.filters, ensure_ascii=True),
        tab=body.tab,
        sort=body.sort,
        columns_json=json.dumps(body.columns, ensure_ascii=True),
        pinned=body.pinned,
    )
    db.add(item)
    await db.flush()
    await _record_activity(
        db,
        user_id=user.id,
        scope="admin" if user.role.value == "admin" else "viewer",
        category="workspace_created",
        title=f"Saved workspace: {body.name}",
        body=f"{body.page} workspace saved",
        link=f"/{body.page}" if not body.page.startswith("/") else body.page,
        payload={"workspace_id": item.id, "page": body.page},
    )
    await db.commit()
    await db.refresh(item)
    await invalidate_request_caches(request, prefixes=("cache:activity:", "cache:workbench:"))
    return _workspace_to_response(item)


@router.get("/workspaces/{workspace_id}", response_model=SavedWorkspaceResponse)
async def get_workspace(
    workspace_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await db.get(Workspace, workspace_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    return _workspace_to_response(item)


@router.patch("/workspaces/{workspace_id}", response_model=SavedWorkspaceResponse)
async def update_workspace(
    request: Request,
    workspace_id: int,
    body: WorkspaceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await db.get(Workspace, workspace_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")

    payload = body.model_dump(exclude_unset=True)
    if "name" in payload:
        item.name = payload["name"]
    if "scope" in payload:
        item.scope = payload["scope"]
    if "page" in payload:
        item.page = payload["page"]
    if "filters" in payload:
        item.filters_json = json.dumps(payload["filters"] or {}, ensure_ascii=True)
    if "tab" in payload:
        item.tab = payload["tab"]
    if "sort" in payload:
        item.sort = payload["sort"]
    if "columns" in payload:
        item.columns_json = json.dumps(payload["columns"] or [], ensure_ascii=True)
    if "pinned" in payload:
        item.pinned = bool(payload["pinned"])

    await _record_activity(
        db,
        user_id=user.id,
        scope="admin" if user.role.value == "admin" else "viewer",
        category="workspace_updated",
        title=f"Updated workspace: {item.name}",
        body=f"{item.page} workspace refreshed",
        link=f"/{item.page}" if not item.page.startswith("/") else item.page,
        payload={"workspace_id": item.id, "page": item.page},
    )
    await db.commit()
    await db.refresh(item)
    await invalidate_request_caches(request, prefixes=("cache:activity:", "cache:workbench:"))
    return _workspace_to_response(item)


@router.delete("/workspaces/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    request: Request,
    workspace_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await db.get(Workspace, workspace_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Workspace not found")
    await _record_activity(
        db,
        user_id=user.id,
        scope="admin" if user.role.value == "admin" else "viewer",
        category="workspace_deleted",
        title=f"Removed workspace: {item.name}",
        body=f"{item.page} workspace deleted",
        payload={"workspace_id": item.id, "page": item.page},
    )
    await db.delete(item)
    await db.commit()
    await invalidate_request_caches(request, prefixes=("cache:activity:", "cache:workbench:"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/watchlists", response_model=list[WatchlistItemResponse])
async def list_watchlists(
    entity_type: str | None = Query(None),
    limit: int | None = Query(None, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(WatchlistItem).where(WatchlistItem.user_id == user.id)
    if entity_type:
        stmt = stmt.where(WatchlistItem.entity_type == entity_type)
    stmt = stmt.order_by(WatchlistItem.created_at.desc())
    if limit is not None:
        stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return [_watchlist_to_response(item) for item in result.scalars().all()]


@router.post("/watchlists", response_model=WatchlistItemResponse, status_code=status.HTTP_201_CREATED)
async def create_watchlist_item(
    request: Request,
    body: WatchlistCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = await db.execute(
        select(WatchlistItem).where(
            WatchlistItem.user_id == user.id,
            WatchlistItem.entity_type == body.entity_type,
            WatchlistItem.entity_key == body.entity_key,
        )
    )
    found = existing.scalar_one_or_none()
    if found is not None:
        return _watchlist_to_response(found)

    item = WatchlistItem(
        user_id=user.id,
        entity_type=body.entity_type,
        entity_key=body.entity_key,
        display_label=body.display_label,
        metadata_json=json.dumps(body.metadata, ensure_ascii=True),
    )
    db.add(item)
    await db.flush()
    await _record_activity(
        db,
        user_id=user.id,
        scope="admin" if user.role.value == "admin" else "viewer",
        category="watchlist_added",
        title=f"Added to watchlist: {body.display_label}",
        body=f"Tracking {body.entity_type}",
        link=body.metadata.get("link") if isinstance(body.metadata, dict) else None,
        payload={"watchlist_id": item.id, "entity_type": body.entity_type, "entity_key": body.entity_key},
    )
    await db.commit()
    await db.refresh(item)
    await invalidate_request_caches(request, prefixes=("cache:activity:", "cache:workbench:"))
    return _watchlist_to_response(item)


@router.delete("/watchlists/{watchlist_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_watchlist_item(
    request: Request,
    watchlist_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = await db.get(WatchlistItem, watchlist_id)
    if item is None or item.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Watchlist item not found")
    await _record_activity(
        db,
        user_id=user.id,
        scope="admin" if user.role.value == "admin" else "viewer",
        category="watchlist_removed",
        title=f"Removed from watchlist: {item.display_label}",
        body=f"Stopped tracking {item.entity_type}",
        payload={"watchlist_id": item.id, "entity_type": item.entity_type, "entity_key": item.entity_key},
    )
    await db.delete(item)
    await db.commit()
    await invalidate_request_caches(request, prefixes=("cache:activity:", "cache:workbench:"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/watchlists/feed", response_model=list[WatchlistFeedItemResponse])
async def watchlist_feed(
    limit: int = Query(24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(WatchlistItem)
        .where(WatchlistItem.user_id == user.id)
        .order_by(WatchlistItem.created_at.desc())
        .limit(limit)
    )
    items = result.scalars().all()
    output: list[WatchlistFeedItemResponse] = []
    market_df = None
    if any(item.entity_type in {"municipality", "region"} for item in items):
        market_df = _prepare_market_df()
    for item in items:
        if item.entity_type == "municipality":
            output.append(_watchlist_feed_for_municipality(item, market_df))
        elif item.entity_type == "region":
            output.append(_watchlist_feed_for_region(item, market_df))
        else:
            output.append(
                WatchlistFeedItemResponse(
                    id=f"watchlist:{item.id}",
                    entity_type=item.entity_type,
                    entity_key=item.entity_key,
                    display_label=item.display_label,
                )
            )
    return output

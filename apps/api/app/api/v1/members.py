from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import AdminContext, get_admin_context
from app.core.errors import not_found
from app.db.session import get_db
from app.repositories.licenses import MemberRepository
from app.schemas.member import MemberChannelIdentityOut, MemberChannelUpdate, MemberOut
from app.services.licenses import LicenseService
from app.services.projects import MemberChannelService, ProjectService
from app.services.serializers import member_out

router = APIRouter(prefix="/projects/{project_id}/members", tags=["members"])


def _member_or_404(db: Session, project_id: uuid.UUID, member_id: uuid.UUID):
    member = MemberRepository.get(db, member_id, lock=True)
    if member is None or member.project_id != project_id:
        raise not_found("درخواست اتصال یافت نشد.")
    return member


@router.get("", response_model=list[MemberOut])
def list_members(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> list[MemberOut]:
    ProjectService.get(db, project_id)
    return [member_out(member) for member in MemberRepository.list_for_project(db, project_id)]


@router.post("/{member_id}/approve", response_model=MemberOut)
def approve_member(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> MemberOut:
    member = _member_or_404(db, project_id, member_id)
    LicenseService.approve_member(db, member=member, actor=ctx.actor)
    db.refresh(member)
    return member_out(member)


@router.post("/{member_id}/revoke", response_model=MemberOut)
def revoke_member(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> MemberOut:
    member = _member_or_404(db, project_id, member_id)
    LicenseService.revoke_member(db, member=member, actor=ctx.actor)
    db.refresh(member)
    return member_out(member)


@router.get("/{member_id}/channels", response_model=list[MemberChannelIdentityOut])
def list_member_channels(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: AdminContext = Depends(get_admin_context),
) -> list[MemberChannelIdentityOut]:
    member = _member_or_404(db, project_id, member_id)
    return [
        MemberChannelIdentityOut.model_validate(row)
        for row in MemberChannelService.list_for_member(db, member.id)
    ]


@router.put("/{member_id}/channels/{channel}", response_model=MemberChannelIdentityOut)
def save_member_channel(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    channel: str,
    payload: MemberChannelUpdate,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> MemberChannelIdentityOut:
    member = _member_or_404(db, project_id, member_id)
    row = MemberChannelService.upsert(
        db,
        member=member,
        channel=channel,
        external_id=payload.external_id,
        label=payload.label,
        actor=ctx.actor,
    )
    db.commit()
    return MemberChannelIdentityOut.model_validate(row)


@router.delete("/{member_id}/channels/{channel}", status_code=204)
def delete_member_channel(
    project_id: uuid.UUID,
    member_id: uuid.UUID,
    channel: str,
    db: Session = Depends(get_db),
    ctx: AdminContext = Depends(get_admin_context),
) -> Response:
    member = _member_or_404(db, project_id, member_id)
    MemberChannelService.delete(db, member=member, channel=channel, actor=ctx.actor)
    db.commit()
    return Response(status_code=204)

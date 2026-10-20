from __future__ import annotations

from fastapi.testclient import TestClient

from tests.helpers import approve_first_member, create_project, last_message, telegram_update


def test_archive_stops_bot_and_restore_brings_it_back(
    admin_client: TestClient, mock_adapter
) -> None:
    project = create_project(admin_client)
    telegram_update(admin_client, telegram_id=930001, text=project["license_code"])
    approve_first_member(admin_client, project["id"])

    archived = admin_client.post(f"/api/v1/projects/{project['id']}/archive")
    assert archived.status_code == 200, archived.text
    body = archived.json()
    assert body["archived_at"] is not None
    assert body["status"] == "inactive"

    listing = admin_client.get("/api/v1/projects").json()
    assert project["id"] not in [item["id"] for item in listing["items"]]
    with_archived = admin_client.get("/api/v1/projects", params={"include_archived": True}).json()
    assert project["id"] in [item["id"] for item in with_archived["items"]]

    # The bot refuses access: the membership is no longer usable.
    telegram_update(admin_client, telegram_id=930001, callback_data="0:ann")
    assert "فعال نیست" in last_message(mock_adapter)["text"]

    double = admin_client.post(f"/api/v1/projects/{project['id']}/archive")
    assert double.status_code == 409

    restored = admin_client.post(f"/api/v1/projects/{project['id']}/restore")
    assert restored.status_code == 200
    assert restored.json()["archived_at"] is None
    telegram_update(admin_client, telegram_id=930001, callback_data="0:ann")
    assert (
        "اطلاعیه" in last_message(mock_adapter)["text"]
        or "هنوز اطلاعیه" in last_message(mock_adapter)["text"]
    )


def test_delete_requires_exact_name_confirmation(admin_client: TestClient) -> None:
    project = create_project(admin_client, name="پروژه حذف شدنی")
    wrong = admin_client.delete(
        f"/api/v1/projects/{project['id']}", params={"confirm": "نام اشتباه"}
    )
    assert wrong.status_code == 422
    assert admin_client.get(f"/api/v1/projects/{project['id']}").status_code == 200

    deleted = admin_client.delete(
        f"/api/v1/projects/{project['id']}", params={"confirm": "پروژه حذف شدنی"}
    )
    assert deleted.status_code == 204
    assert admin_client.get(f"/api/v1/projects/{project['id']}").status_code == 404
    # The audit trail survives the deletion with a null project reference.
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.audit import AuditLog

    with SessionLocal() as db:
        rows = db.scalars(select(AuditLog).where(AuditLog.action == "project.deleted")).all()
        assert len(rows) == 1
        assert rows[0].project_id is None
        assert rows[0].context["name"] == "پروژه حذف شدنی"


def test_demo_purge_only_removes_demo_flagged_projects(admin_client: TestClient) -> None:
    real = create_project(admin_client, name="پروژه واقعی")
    demo = create_project(admin_client, name="پروژه نمایشی")

    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models.project import Project

    with SessionLocal() as db:
        row = db.scalar(select(Project).where(Project.id == __import__("uuid").UUID(demo["id"])))
        row.is_demo = True
        db.commit()

    wrong = admin_client.post("/api/v1/projects/demo-purge", params={"confirm": "yes"})
    assert wrong.status_code == 422

    purged = admin_client.post("/api/v1/projects/demo-purge", params={"confirm": "DEMO"})
    assert purged.status_code == 200, purged.text
    assert purged.json()["deleted"] == 1
    assert admin_client.get(f"/api/v1/projects/{demo['id']}").status_code == 404
    assert admin_client.get(f"/api/v1/projects/{real['id']}").status_code == 200

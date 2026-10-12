import io
from pathlib import Path
from uuid import uuid4

import pandas as pd
from fastapi.testclient import TestClient
from PIL import Image
from reportlab.pdfgen import canvas
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.rate_limit import limiter
from app.core.security import create_access_token
from app.main import app
from app.models.analysis import Analysis
from app.models.dataset import Dataset
from app.models.user import User
from app.services import file_service
from app.services.file_service import read_file_as_dataframe, save_and_read_file

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
client = TestClient(app)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


def setup_function():
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    limiter.reset()
    app.dependency_overrides[get_db] = override_get_db


def teardown_function():
    app.dependency_overrides.clear()


def _headers(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user_id))}"}


def _user(email: str = "dataset@example.com") -> int:
    with TestSession() as db:
        user = User(
            name="Dataset User",
            email=email,
            password_hash="unused",
            is_verified=True,
        )
        db.add(user)
        db.commit()
        return user.id


def _csv_bytes() -> bytes:
    dataframe = pd.DataFrame({
        "email": ["amina@example.test", "other@example.test"],
        "amount": [10, 25],
    })
    return dataframe.to_csv(index=False).encode("utf-8")


def _xlsx_bytes() -> bytes:
    output = io.BytesIO()
    pd.DataFrame({"name": ["A", "B"], "score": [1, 2]}).to_excel(output, index=False)
    return output.getvalue()


def _pdf_bytes() -> bytes:
    output = io.BytesIO()
    document = canvas.Canvas(output)
    document.drawString(72, 720, "Quarterly sales report")
    document.save()
    return output.getvalue()


def _docx_bytes() -> bytes:
    from docx import Document

    output = io.BytesIO()
    document = Document()
    document.add_paragraph("Quarterly sales report")
    document.save(output)
    return output.getvalue()


def _image_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (20, 20), color="white").save(output, format="PNG")
    return output.getvalue()


def test_file_service_reads_csv_xlsx_pdf_and_docx(tmp_path, monkeypatch):
    monkeypatch.setattr(file_service, "UPLOAD_DIR", tmp_path)

    csv_path, csv_data = save_and_read_file("sales.csv", _csv_bytes())
    xlsx_path, xlsx_data = save_and_read_file("sales.xlsx", _xlsx_bytes())
    pdf_path, pdf_data = save_and_read_file("report.pdf", _pdf_bytes())
    docx_path, docx_data = save_and_read_file("report.docx", _docx_bytes())

    assert csv_path.parent == tmp_path
    assert list(csv_data.columns) == ["email", "amount"]
    assert len(xlsx_data) == 2
    assert list(pdf_data["content"]) == ["Quarterly sales report"]
    assert "Quarterly sales report" in docx_data.iloc[0]["content"]
    assert file_service.get_document_page_count(pdf_path) == 1
    assert file_service.get_document_page_count(docx_path) == 1


def test_file_service_reads_images_with_mocked_ocr(tmp_path, monkeypatch):
    monkeypatch.setattr(file_service, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(file_service, "_ocr_image", lambda _image: "OCR extracted text")

    image_path, dataframe = save_and_read_file("scan.png", _image_bytes())

    assert image_path.exists()
    assert dataframe.iloc[0]["content"] == "OCR extracted text"


def test_file_service_rejects_unsupported_empty_and_malformed_files(tmp_path, monkeypatch):
    monkeypatch.setattr(file_service, "UPLOAD_DIR", tmp_path)

    cases = [
        ("notes.txt", b"hello", "Unsupported file format."),
        ("empty.csv", b"", None),
        ("broken.xlsx", b"not an xlsx file", None),
    ]
    for filename, content, message in cases:
        try:
            save_and_read_file(filename, content)
        except ValueError as error:
            if message is not None:
                assert message in str(error)
        else:
            raise AssertionError(f"{filename} should have been rejected")

    assert list(tmp_path.iterdir()) == []


def test_upload_returns_preview_profile_and_pii_report(tmp_path, monkeypatch):
    user_id = _user()
    monkeypatch.setattr(file_service, "UPLOAD_DIR", tmp_path)

    response = client.post(
        "/files/upload",
        headers=_headers(user_id),
        files=[("files", ("sales.csv", _csv_bytes(), "text/csv"))],
    )

    assert response.status_code == 200
    uploaded = response.json()[0]
    assert uploaded["filename"] == "sales.csv"
    assert uploaded["row_count"] == 2
    assert uploaded["column_count"] == 2
    assert uploaded["column_names"] == ["email", "amount"]
    assert len(uploaded["preview"]) == 2
    assert uploaded["profile"]["row_count"] == 2
    assert uploaded["pii_report"]["columns"][0]["category"] == "email"
    assert uploaded["file_size_bytes"] == len(_csv_bytes())

    with TestSession() as db:
        dataset = db.query(Dataset).one()
        assert Path(dataset.file_path).exists()


def test_upload_rejects_empty_missing_and_unsupported_files_without_persisting(tmp_path, monkeypatch):
    user_id = _user()
    monkeypatch.setattr(file_service, "UPLOAD_DIR", tmp_path)

    empty = client.post(
        "/files/upload",
        headers=_headers(user_id),
        files=[("files", ("empty.csv", b"", "text/csv"))],
    )
    unsupported = client.post(
        "/files/upload",
        headers=_headers(user_id),
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    )
    missing_name = client.post(
        "/files/upload",
        headers=_headers(user_id),
        files=[("files", ("", b"hello", "application/octet-stream"))],
    )

    assert empty.status_code == 400
    assert unsupported.status_code == 400
    assert missing_name.status_code == 422
    with TestSession() as db:
        assert db.query(Dataset).count() == 0
    assert list(tmp_path.iterdir()) == []


def test_upload_rolls_back_previous_files_when_a_later_file_fails(tmp_path, monkeypatch):
    user_id = _user()
    monkeypatch.setattr(file_service, "UPLOAD_DIR", tmp_path)

    response = client.post(
        "/files/upload",
        headers=_headers(user_id),
        files=[
            ("files", ("valid.csv", _csv_bytes(), "text/csv")),
            ("files", ("broken.xlsx", b"broken", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")),
        ],
    )

    assert response.status_code == 400
    with TestSession() as db:
        assert db.query(Dataset).count() == 0
    assert list(tmp_path.iterdir()) == []


def test_preview_and_pii_preferences_are_persisted(tmp_path, monkeypatch):
    user_id = _user()
    monkeypatch.setattr(file_service, "UPLOAD_DIR", tmp_path)
    uploaded = client.post(
        "/files/upload",
        headers=_headers(user_id),
        files=[("files", ("sales.csv", _csv_bytes(), "text/csv"))],
    ).json()[0]
    dataset_id = uploaded["id"]

    preferences = client.put(
        f"/files/{dataset_id}/pii-preferences",
        headers=_headers(user_id),
        json={"preferences": {"email": "exclude"}},
    )
    preview = client.get(f"/files/{dataset_id}/preview", headers=_headers(user_id))
    unknown = client.put(
        f"/files/{dataset_id}/pii-preferences",
        headers=_headers(user_id),
        json={"preferences": {"amount": "mask"}},
    )

    assert preferences.status_code == 200
    assert preferences.json()["preferences"] == {"email": "exclude"}
    assert preview.status_code == 200
    assert preview.json()["pii_preferences"] == {"email": "exclude"}
    assert unknown.status_code == 422


def test_dataset_endpoints_enforce_ownership_and_missing_files(tmp_path, monkeypatch):
    owner_id = _user("owner@example.com")
    other_id = _user("other@example.com")
    monkeypatch.setattr(file_service, "UPLOAD_DIR", tmp_path)
    path = tmp_path / "owned.csv"
    path.write_bytes(_csv_bytes())

    with TestSession() as db:
        dataset = Dataset(
            user_id=owner_id,
            filename="owned.csv",
            file_path=str(path),
            file_type="csv",
            row_count=2,
            column_count=2,
        )
        db.add(dataset)
        db.commit()
        dataset_id = dataset.id

    assert client.get(f"/files/{dataset_id}/preview", headers=_headers(other_id)).status_code == 403
    assert client.delete(f"/files/{dataset_id}", headers=_headers(other_id)).status_code == 404
    path.unlink()
    assert client.get(f"/files/{dataset_id}/preview", headers=_headers(owner_id)).status_code == 404


def test_dataset_delete_rejects_paths_outside_upload_directory(tmp_path, monkeypatch):
    user_id = _user()
    upload_dir = tmp_path / "uploads"
    upload_dir.mkdir()
    outside_path = tmp_path / "outside.csv"
    outside_path.write_bytes(_csv_bytes())
    monkeypatch.setattr(file_service, "UPLOAD_DIR", upload_dir)

    with TestSession() as db:
        dataset = Dataset(
            user_id=user_id,
            filename="outside.csv",
            file_path=str(outside_path),
            file_type="csv",
            row_count=2,
            column_count=2,
        )
        db.add(dataset)
        db.commit()
        dataset_id = dataset.id

    response = client.delete(f"/files/{dataset_id}", headers=_headers(user_id))

    assert response.status_code == 400
    assert outside_path.exists()
    with TestSession() as db:
        assert db.get(Dataset, dataset_id) is not None


def test_dataset_delete_cascade_soft_deletes_active_analyses(tmp_path, monkeypatch):
    user_id = _user()
    monkeypatch.setattr(file_service, "UPLOAD_DIR", tmp_path)
    path = tmp_path / "owned.csv"
    path.write_bytes(_csv_bytes())

    with TestSession() as db:
        dataset = Dataset(
            user_id=user_id,
            filename="owned.csv",
            file_path=str(path),
            file_type="csv",
            row_count=2,
            column_count=2,
        )
        db.add(dataset)
        db.flush()
        analysis = Analysis(
            user_id=user_id,
            dataset_id=dataset.id,
            question="Question",
            answer="Answer",
            result_type="text",
        )
        db.add(analysis)
        db.commit()
        dataset_id = dataset.id
        analysis_id = analysis.id

    conflict = client.delete(f"/files/{dataset_id}", headers=_headers(user_id))
    deleted = client.delete(f"/files/{dataset_id}?cascade=true", headers=_headers(user_id))

    assert conflict.status_code == 409
    assert deleted.status_code == 204
    assert not path.exists()
    with TestSession() as db:
        assert db.get(Dataset, dataset_id) is None
        assert db.get(Analysis, analysis_id).deleted_at is not None

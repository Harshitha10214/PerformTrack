import hashlib
import hmac
import os
import re
import unicodedata
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, quote, unquote, urlsplit

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.database import get_db
from app.models import CheckIn, Employee, Evidence, Feedback, Goal, KeyResult, Review
from app.schemas.evidence import EvidenceResponse, EvidenceTargetType, PaginatedEvidence
from app.services.audit import set_audit_actor
from app.services.record_ids import next_evidence_id

router = APIRouter(tags=["evidence"])

MAX_FILE_SIZE = 10 * 1024 * 1024
MAX_FILENAME_LENGTH = 150
_ALLOWED_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
_SAFE_FILENAME = re.compile(r"^[\w][\w .()-]*$", re.UNICODE)
_EVIDENCE_ID = re.compile(r"^EVD-\d{6}$")


def _storage_root() -> Path:
    configured = Path(settings.evidence_storage_dir)
    if not configured.is_absolute():
        configured = Path(__file__).resolve().parents[2] / configured
    return configured.resolve()


def _evidence_query():
    return select(Evidence).options(
        selectinload(Evidence.employee),
        selectinload(Evidence.key_result).selectinload(KeyResult.goal),
        selectinload(Evidence.checkin),
        selectinload(Evidence.feedback),
        selectinload(Evidence.review),
    )


def _target_type(item: Evidence) -> EvidenceTargetType:
    if item.key_result_id is not None:
        return "key_result"
    if item.checkin_id is not None:
        return "checkin"
    if item.feedback_id is not None:
        return "feedback"
    return "review"


def _filename_from_uri(uri: str) -> str:
    name = PurePosixPath(unquote(urlsplit(uri).path)).name
    return name or "Evidence attachment"


def _size_from_uri(uri: str) -> int | None:
    raw_size = parse_qs(urlsplit(uri).query).get("size", [None])[0]
    try:
        return int(raw_size) if raw_size is not None else None
    except ValueError:
        return None


def _response(item: Evidence) -> EvidenceResponse:
    if item.key_result is not None:
        goal = item.key_result.goal
        target_type: EvidenceTargetType = "key_result"
        linked_record_id = item.key_result.id
        linked_record_label = f"{goal.title} ({goal.id}) / {item.key_result.title} ({item.key_result.id})"
    elif item.checkin is not None:
        target_type = "checkin"
        linked_record_id = item.checkin.id
        linked_record_label = f"Check-in {item.checkin.id} ({item.checkin.checkin_date})"
    elif item.feedback is not None:
        target_type = "feedback"
        linked_record_id = item.feedback.id
        linked_record_label = f"Feedback {item.feedback.id}"
    elif item.review is not None:
        target_type = "review"
        linked_record_id = item.review.id
        linked_record_label = f"Review {item.review.id}"
    else:
        raise HTTPException(status_code=500, detail="Evidence has no valid linked record.")

    return EvidenceResponse(
        id=item.id,
        employee_id=item.employee_id,
        employee_name=f"{item.employee.first_name} {item.employee.last_name}",
        target_type=target_type,
        linked_record_id=linked_record_id,
        linked_record_label=linked_record_label,
        file_name=_filename_from_uri(item.uri),
        uri=item.uri,
        media_type=item.media_type,
        size_bytes=_size_from_uri(item.uri),
        sha256=item.sha256,
        description=item.description,
        downloadable=urlsplit(item.uri).scheme == "local-evidence",
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _validate_filename(filename: str) -> str:
    normalized = unicodedata.normalize("NFC", filename)
    if (
        not normalized
        or len(normalized) > MAX_FILENAME_LENGTH
        or normalized in {".", ".."}
        or ".." in normalized
        or "/" in normalized
        or "\\" in normalized
        or not _SAFE_FILENAME.fullmatch(normalized)
    ):
        raise HTTPException(status_code=422, detail="The filename is invalid.")
    if normalized.split(".", 1)[0].upper() in {
        "CON", "PRN", "AUX", "NUL",
        *(f"COM{index}" for index in range(1, 10)),
        *(f"LPT{index}" for index in range(1, 10)),
    }:
        raise HTTPException(status_code=422, detail="The filename is invalid.")
    return normalized


def _validate_file_content(filename: str, declared_type: str | None, content: bytes) -> str:
    extension = Path(filename).suffix.lower()
    media_type = _ALLOWED_MEDIA_TYPES.get(extension)
    if media_type is None:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a PDF, text, PNG, or JPEG file.",
        )
    supplied_type = (declared_type or "").split(";", 1)[0].strip().lower()
    if supplied_type and supplied_type != "application/octet-stream" and supplied_type != media_type:
        raise HTTPException(status_code=415, detail="The file type does not match its filename.")
    if not content:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    if extension == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The file content is not a valid PDF.")
    if extension == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=415, detail="The file content is not a valid PNG image.")
    if extension in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=415, detail="The file content is not a valid JPEG image.")
    if extension == ".txt":
        try:
            content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=415, detail="Text files must use UTF-8 encoding.") from exc
        if b"\x00" in content:
            raise HTTPException(status_code=415, detail="The text file contains invalid binary data.")
    return media_type


def _validate_target(
    db: Session,
    employee_id: str,
    target_type: EvidenceTargetType,
    target_id: str,
) -> dict[str, str | None]:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=422, detail="employee_id must reference an existing employee.")

    linked_fields: dict[str, str | None] = {
        "key_result_id": None,
        "checkin_id": None,
        "feedback_id": None,
        "review_id": None,
    }
    if target_type == "key_result":
        linked = db.scalar(
            select(KeyResult).options(selectinload(KeyResult.goal)).where(KeyResult.id == target_id)
        )
        linked_employee_id = linked.goal.employee_id if linked is not None else None
        field = "key_result_id"
    elif target_type == "checkin":
        linked = db.get(CheckIn, target_id)
        linked_employee_id = linked.employee_id if linked is not None else None
        field = "checkin_id"
    elif target_type == "feedback":
        linked = db.get(Feedback, target_id)
        linked_employee_id = linked.subject_employee_id if linked is not None else None
        field = "feedback_id"
    else:
        linked = db.get(Review, target_id)
        linked_employee_id = linked.employee_id if linked is not None else None
        field = "review_id"

    if linked is None:
        raise HTTPException(status_code=422, detail="The linked performance record does not exist.")
    if linked_employee_id != employee_id:
        raise HTTPException(
            status_code=422,
            detail="The linked performance record must belong to the selected employee.",
        )
    linked_fields[field] = target_id
    return linked_fields


def _commit_upload(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="The evidence conflicts with a database constraint.") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="The evidence could not be saved.") from None


def _stored_file_path(item: Evidence) -> Path:
    parsed_uri = urlsplit(item.uri)
    if parsed_uri.scheme != "local-evidence" or parsed_uri.netloc != item.id:
        raise HTTPException(status_code=404, detail="No uploaded file is available for this evidence record.")
    filename = _validate_filename(_filename_from_uri(item.uri))
    if Path(filename).suffix.lower() not in _ALLOWED_MEDIA_TYPES:
        raise HTTPException(status_code=404, detail="No uploaded file is available for this evidence record.")
    root = _storage_root()
    path = (root / item.id).resolve()
    if path.parent != root or not path.is_file():
        raise HTTPException(status_code=404, detail="The evidence file was not found.")
    return path


@router.get("/evidence", response_model=PaginatedEvidence)
def list_evidence(
    search: str | None = None,
    target_type: EvidenceTargetType | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedEvidence:
    query = select(Evidence).join(Employee)
    predicates = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        predicates.append(
            or_(
                Evidence.id.ilike(term),
                Evidence.description.ilike(term),
                Evidence.uri.ilike(term),
                Evidence.key_result_id.ilike(term),
                Evidence.checkin_id.ilike(term),
                Evidence.feedback_id.ilike(term),
                Evidence.review_id.ilike(term),
                Employee.first_name.ilike(term),
                Employee.last_name.ilike(term),
            )
        )
    if target_type == "key_result":
        predicates.append(Evidence.key_result_id.is_not(None))
    elif target_type == "checkin":
        predicates.append(Evidence.checkin_id.is_not(None))
    elif target_type == "feedback":
        predicates.append(Evidence.feedback_id.is_not(None))
    elif target_type == "review":
        predicates.append(Evidence.review_id.is_not(None))
    if predicates:
        query = query.where(*predicates)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = db.scalars(
        _evidence_query()
        .where(Evidence.id.in_(query.with_only_columns(Evidence.id).scalar_subquery()))
        .order_by(Evidence.created_at.desc(), Evidence.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PaginatedEvidence(
        items=[_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/evidence/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(evidence_id: str, db: Session = Depends(get_db)) -> EvidenceResponse:
    if not _EVIDENCE_ID.fullmatch(evidence_id):
        raise HTTPException(status_code=404, detail="Evidence not found.")
    item = db.scalar(_evidence_query().where(Evidence.id == evidence_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Evidence not found.")
    return _response(item)


@router.post("/evidence", response_model=EvidenceResponse, status_code=201)
async def upload_evidence(
    employee_id: str = Form(...),
    target_type: EvidenceTargetType = Form(...),
    target_id: str = Form(...),
    description: str = Form(..., max_length=4000),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> EvidenceResponse:
    content = await file.read(MAX_FILE_SIZE + 1)
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="The file exceeds the 10 MB upload limit.")
    filename = _validate_filename(file.filename or "")
    media_type = _validate_file_content(filename, file.content_type, content)
    normalized_description = description.strip()
    if not normalized_description:
        raise HTTPException(status_code=422, detail="description cannot be blank.")
    linked_fields = _validate_target(db, employee_id, target_type, target_id)
    evidence_id = next_evidence_id(db)
    uri = f"local-evidence://{evidence_id}/{quote(filename, safe='')}?size={len(content)}"
    item = Evidence(
        id=evidence_id,
        employee_id=employee_id,
        **linked_fields,
        uri=uri,
        media_type=media_type,
        sha256=hashlib.sha256(content).hexdigest(),
        description=normalized_description,
    )

    root = _storage_root()
    path = root / evidence_id
    created_file = False
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        created_file = True
        with os.fdopen(descriptor, "wb") as stored_file:
            stored_file.write(content)
    except OSError as exc:
        if created_file:
            path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="The evidence file could not be stored.") from exc

    try:
        set_audit_actor(db, employee_id)
        db.add(item)
        db.flush()
        _commit_upload(db)
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    except IntegrityError:
        db.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=409, detail="The evidence conflicts with a database constraint.") from None
    except SQLAlchemyError:
        db.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="The evidence could not be saved.") from None
    except OSError as exc:
        db.rollback()
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=503, detail="The evidence file could not be stored.") from exc

    saved_item = db.scalar(_evidence_query().where(Evidence.id == evidence_id))
    if saved_item is None:
        raise HTTPException(status_code=500, detail="The uploaded evidence could not be retrieved.")
    return _response(saved_item)


@router.get("/evidence/{evidence_id}/file")
def download_evidence_file(evidence_id: str, db: Session = Depends(get_db)) -> Response:
    if not _EVIDENCE_ID.fullmatch(evidence_id):
        raise HTTPException(status_code=404, detail="Evidence not found.")
    item = db.get(Evidence, evidence_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Evidence not found.")
    path = _stored_file_path(item)
    try:
        stored_size = path.stat().st_size
        if stored_size > MAX_FILE_SIZE or _size_from_uri(item.uri) != stored_size:
            raise HTTPException(status_code=409, detail="The stored evidence size does not match its metadata.")
        content = path.read_bytes()
    except OSError as exc:
        raise HTTPException(status_code=503, detail="The evidence file could not be read.") from exc
    actual_checksum = hashlib.sha256(content).hexdigest()
    if item.sha256 is None or not hmac.compare_digest(actual_checksum, item.sha256):
        raise HTTPException(status_code=409, detail="The stored evidence checksum does not match its metadata.")
    if len(content) != stored_size:
        raise HTTPException(status_code=409, detail="The stored evidence size does not match its metadata.")
    filename = _filename_from_uri(item.uri)
    return Response(
        content=content,
        media_type=item.media_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )

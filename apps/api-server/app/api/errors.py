from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError


def translate_integrity_error(_: IntegrityError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="database integrity error",
    )


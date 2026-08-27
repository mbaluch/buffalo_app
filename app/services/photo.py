import io

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.livestock import Livestock, LivestockPhoto

ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB
THUMBNAIL_SIZE = (300, 300)


def generate_thumbnail(data: bytes, mime_type: str) -> bytes:
    img = Image.open(io.BytesIO(data))
    img.thumbnail(THUMBNAIL_SIZE, Image.LANCZOS)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


async def upload_photo(
    livestock: Livestock,
    data: bytes,
    mime_type: str,
    original_filename: str,
    uploader_id: int,
    make_primary: bool,
    db: AsyncSession,
) -> LivestockPhoto:
    if mime_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Unsupported image type: {mime_type}")
    if len(data) > MAX_FILE_SIZE:
        raise ValueError("File exceeds 5 MB limit")

    thumbnail = generate_thumbnail(data, mime_type)

    if make_primary:
        # Demote any existing primary
        for p in livestock.photos:
            p.is_primary = False

    display_order = len(livestock.photos)
    photo = LivestockPhoto(
        livestock_id=livestock.id,
        data=data,
        thumbnail_data=thumbnail,
        mime_type=mime_type,
        original_filename=original_filename,
        file_size_bytes=len(data),
        is_primary=make_primary or display_order == 0,
        display_order=display_order,
        uploaded_by=uploader_id,
    )
    db.add(photo)
    await db.commit()
    return photo


async def delete_photo(photo_id: int, livestock: Livestock, db: AsyncSession) -> None:
    result = await db.execute(
        select(LivestockPhoto).where(
            LivestockPhoto.id == photo_id,
            LivestockPhoto.livestock_id == livestock.id,
        )
    )
    photo = result.scalar_one_or_none()
    if not photo:
        return

    was_primary = photo.is_primary
    await db.delete(photo)
    await db.flush()

    if was_primary and livestock.photos:
        livestock.photos[0].is_primary = True

    await db.commit()

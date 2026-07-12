"""Registry explorer API (spec §9): entities with domains, headers, key states."""
import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.models import Entity
from app.schemas import EntityDetailOut, EntityOut, err, ok

router = APIRouter(prefix="/api/registry", tags=["registry"])


@router.get("/entities")
def list_entities(db: Session = Depends(get_db)) -> dict:
    entities = (
        db.execute(
            select(Entity).options(selectinload(Entity.keys)).order_by(Entity.name)
        )
        .scalars()
        .all()
    )
    return ok([EntityOut.model_validate(e) for e in entities])


@router.get("/entities/{entity_id}")
def get_entity(entity_id: uuid.UUID, db: Session = Depends(get_db)):
    entity = db.get(
        Entity,
        entity_id,
        options=[
            selectinload(Entity.keys),
            selectinload(Entity.domains),
            selectinload(Entity.sms_headers),
        ],
    )
    if entity is None:
        return JSONResponse(status_code=404, content=err("not_found", "No such entity."))
    return ok(EntityDetailOut.model_validate(entity))

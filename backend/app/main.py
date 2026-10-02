from fastapi import FastAPI

from app.routers.contacts import router as contacts_router
from app.routers.tags import router as tags_router


app = FastAPI(title="Contact Manager API")
app.include_router(contacts_router)
app.include_router(tags_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

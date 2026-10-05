from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.contacts import router as contacts_router
from app.routers.tags import router as tags_router


app = FastAPI(title="Contact Manager API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_frontend_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
)
app.include_router(contacts_router)
app.include_router(tags_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

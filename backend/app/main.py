from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.contacts import router as contacts_router
from app.routers.tags import router as tags_router


app = FastAPI(title="Contact Manager API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_methods=["GET", "POST", "DELETE"],
)
app.include_router(contacts_router)
app.include_router(tags_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}

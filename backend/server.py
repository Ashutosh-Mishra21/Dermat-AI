from fastapi import FastAPI, APIRouter, HTTPException, staticfiles
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from skin_analysis import analyze_skin
from amazon_service import search_products, get_bestsellers

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")


# MongoDB connection
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 🚀 Startup logic (optional)
    print("App starting...")

    yield  # <-- app runs here

    # 🛑 Shutdown logic
    print("Closing MongoDB connection...")
    client.close()


app = FastAPI(title="DermaSense AI Backend", lifespan=lifespan)
api_router = APIRouter(prefix="/api")


# ---------- Existing models ----------
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StatusCheckCreate(BaseModel):
    client_name: str


@api_router.get("/")
async def root():
    return {"message": "DermaSense AI backend running"}


@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_obj = StatusCheck(**input.model_dump())
    await db.status_checks.insert_one(status_obj.model_dump())
    return status_obj


@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**s) for s in status_checks]


# ---------- Skin analysis ----------
class QuizPayload(BaseModel):
    skintype: Optional[str] = None
    fitz: Optional[str] = None
    concerns: List[str] = []
    severity: Optional[str] = None
    sun: Optional[str] = None
    sleep: Optional[float] = None
    stress: Optional[str] = None
    diet: Optional[str] = None
    cleanser: Optional[str] = None
    currentActives: List[str] = []
    allergies: Optional[str] = None
    pregnancy: Optional[str] = None
    image: Optional[str] = None  # data URL or base64 string


@api_router.post("/analyze-skin")
async def analyze_skin_endpoint(payload: QuizPayload) -> Dict[str, Any]:
    quiz = payload.model_dump(exclude={"image"})
    image_b64 = payload.image
    # Basic sanity limit to avoid huge upload blobs (~8MB base64)
    if image_b64 and len(image_b64) > 12_000_000:
        raise HTTPException(status_code=413, detail="Image too large")
    result = await analyze_skin(quiz, image_base64=image_b64)
    return result


# ---------- Amazon products ----------
class ProductMatch(BaseModel):
    query: str
    matchedActive: Optional[str] = ""
    targetConcern: Optional[str] = ""
    category: Optional[str] = ""
    tier: Optional[str] = ""


class ProductQueryPayload(BaseModel):
    # Either send `queries` (list of strings) OR `matches` (rich objects). If both,
    # `matches` wins. Keeping `queries` for backwards-compat.
    queries: Optional[List[str]] = None
    matches: Optional[List[ProductMatch]] = None


@api_router.post("/products-search")
async def products_search(payload: ProductQueryPayload) -> Dict[str, Any]:
    rich_matches: List[Dict[str, Any]] = []
    if payload.matches:
        rich_matches = [m.model_dump() for m in payload.matches]
    elif payload.queries:
        rich_matches = [{"query": q} for q in payload.queries]

    if not rich_matches:
        return {"products": []}

    rich_matches = rich_matches[:12]
    products = await search_products(rich_matches)
    return {"products": products}


@api_router.get("/bestsellers")
async def bestsellers_endpoint() -> Dict[str, Any]:
    """Curated list of popular skincare products on Amazon.in (no analysis required)."""
    products = await get_bestsellers()
    return {"products": products}


@api_router.get("/config")
async def get_config() -> Dict[str, bool]:
    """Let the frontend know which integrations are configured."""
    return {
        "siliconflow": bool(os.environ.get("SILICONFLOW_API_KEY", "").strip()),
        "openrouter": bool(os.environ.get("OPENROUTER_API_KEY", "").strip()),
        "amazon": bool(os.environ.get("OPENWEB_NINJA_API_KEY", "").strip()),
    }
app.include_router(api_router)

# Serve the static DermaSense site (HTML/CSS/JS) at the root path.
# Use an absolute path so it works regardless of the current working directory.
_STATIC_DIR = (ROOT_DIR / ".." / "frontend" / "public" / "dermasense").resolve()
if _STATIC_DIR.is_dir():
    app.mount(
        "/",
        staticfiles.StaticFiles(directory=str(_STATIC_DIR), html=True),
        name="frontend",
    )
else:
    logging.getLogger(__name__).warning(
        "Static directory not found at %s — frontend will not be served by FastAPI.",
        _STATIC_DIR,
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://127.0.0.1:5500"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

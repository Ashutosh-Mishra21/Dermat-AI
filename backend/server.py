from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime

from skin_analysis import analyze_skin
from amazon_service import search_products


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

# MongoDB connection
mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI(title="DermaSense AI Backend")
api_router = APIRouter(prefix="/api")


# ---------- Existing models ----------
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StatusCheckCreate(BaseModel):
    client_name: str


@api_router.get("/")
async def root():
    return {"message": "DermaSense AI backend running"}


@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_obj = StatusCheck(**input.dict())
    await db.status_checks.insert_one(status_obj.dict())
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
    quiz = payload.dict(exclude={"image"})
    image_b64 = payload.image
    # Basic sanity limit to avoid huge upload blobs (~8MB base64)
    if image_b64 and len(image_b64) > 12_000_000:
        raise HTTPException(status_code=413, detail="Image too large")
    result = await analyze_skin(quiz, image_base64=image_b64)
    return result


# ---------- Amazon products ----------
class ProductQueryPayload(BaseModel):
    queries: List[str]


@api_router.post("/products-search")
async def products_search(payload: ProductQueryPayload) -> Dict[str, Any]:
    if not payload.queries:
        return {"products": []}
    # Limit to a reasonable number
    queries = payload.queries[:12]
    products = await search_products(queries)
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

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()

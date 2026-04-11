import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from gpu_utils import log_device_info
from routes.answer import router as answer_router
from routes.stream import router as stream_router
from routes.call import router as call_router
from routes.api import router as api_router
from routes.voices import router as voices_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://45.195.83.136:5173", "http://45.195.83.136:3000", "http://45.195.83.136:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(answer_router)
app.include_router(stream_router)
app.include_router(call_router)
app.include_router(api_router)
app.include_router(voices_router)


@app.on_event("startup")
async def startup():
    log_device_info()
    init_db()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

import os
import time
import uuid
from contextlib import asynccontextmanager


from main.middleware.redis_limit_middleware import RedisLimitMiddleware

from loguru import logger
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

import redis.asyncio as redis
from pydantic import BaseModel



redis_client = redis.Redis(host="localhost", port=6379, db=0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = redis.Redis(host="localhost", port=6379, db=0)
    try:
        await app.state.redis.ping()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise e
    yield
    await app.state.redis.close()
    logger.info("Redis connection closed")


app = FastAPI(title="Rate Limiter Application", description="Rate Limiter Application", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RedisLimitMiddleware, limit=5, window=60)







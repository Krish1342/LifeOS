import asyncio
import logging
import os

import pymongo
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

logger = logging.getLogger("lifeos.db")


class MongoDB:
    """Async MongoDB client wrapper with automatic indexing and connection management."""

    _client: AsyncIOMotorClient | None = None
    _db: AsyncIOMotorDatabase | None = None
    _loop: asyncio.AbstractEventLoop | None = None

    @classmethod
    def get_uri(cls) -> str:
        return os.getenv("MONGODB_URI", "mongodb://localhost:27017")

    @classmethod
    def get_db_name(cls) -> str:
        return os.getenv("MONGODB_DB_NAME", "lifeos")

    @classmethod
    def get_client(cls) -> AsyncIOMotorClient:
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if cls._client is None or cls._loop != current_loop or (current_loop and current_loop.is_closed()):
            uri = cls.get_uri()
            cls._client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=1000)
            cls._loop = current_loop
            cls._db = None
        return cls._client

    @classmethod
    def get_database(cls) -> AsyncIOMotorDatabase:
        client = cls.get_client()
        if cls._db is None:
            cls._db = client[cls.get_db_name()]
        return cls._db

    @classmethod
    async def init_indexes(cls) -> None:
        """Create required unique and query indexes for all collections."""
        try:
            db = cls.get_database()
            # 1. users
            await db.users.create_index([("email", pymongo.ASCENDING)], unique=True)

            # 2. oauth_tokens
            await db.oauth_tokens.create_index(
                [("user_id", pymongo.ASCENDING), ("service", pymongo.ASCENDING)],
                unique=True
            )

            # 3. tasks
            await db.tasks.create_index([("task_id", pymongo.ASCENDING)], unique=True)
            await db.tasks.create_index([("user_id", pymongo.ASCENDING), ("status", pymongo.ASCENDING)])
            await db.tasks.create_index([("user_id", pymongo.ASCENDING), ("due_date", pymongo.ASCENDING)])

            # 4. agent_runs
            await db.agent_runs.create_index([("user_id", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)])
            await db.agent_runs.create_index([("a2a_context_id", pymongo.ASCENDING)])

            # 5. user_config
            await db.user_config.create_index(
                [("user_id", pymongo.ASCENDING), ("config_key", pymongo.ASCENDING)],
                unique=True
            )
            logger.info("MongoDB indexes successfully initialized")
        except Exception as e:
            logger.warning(f"Could not initialize MongoDB indexes (will retry when DB is available): {e}")

    @classmethod
    def close(cls) -> None:
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            cls._db = None
            cls._loop = None

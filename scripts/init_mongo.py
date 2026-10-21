import asyncio
import os
import sys

from dotenv import load_dotenv

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from lifeos.shared.db.mongo import MongoDB


async def main():
    print("Testing MongoDB connection...")
    uri = MongoDB.get_uri()
    db_name = MongoDB.get_db_name()
    print(f"Target Database: {db_name} via {uri.split('@')[-1] if '@' in uri else uri}")

    try:
        client = MongoDB.get_client()
        # Verify server ping
        await client.admin.command('ping')
        print("MongoDB connection verified successfully!")

        print("Initializing collections and indexes...")
        await MongoDB.init_indexes()
        print("Initialization complete! Ready for LifeOS multi-agent operations.")
    except Exception as e:
        print(f"Could not connect to MongoDB: {e}")
        print("Note: If using MongoDB Atlas, check your network whitelist (0.0.0.0/0) and credentials in .env")


if __name__ == "__main__":
    asyncio.run(main())

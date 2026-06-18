import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from db.database import engine, AsyncSessionLocal
from db.models import Subject

async def test_delete():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Subject))
        subject = result.scalar_one_or_none()
        if subject:
            print(f"Found subject: {subject.name} - {subject.id}")
            try:
                await db.delete(subject)
                await db.commit()
                print("Deleted successfully!")
            except Exception as e:
                print(f"Failed to delete: {e.__class__.__name__} - {e}")
        else:
            print("No subjects found.")

if __name__ == "__main__":
    asyncio.run(test_delete())

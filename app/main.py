# app/main.py
import sys
from pathlib import Path
from fastapi import FastAPI

# Add the project root to sys.path to make imports work
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

# Import routers
from app.routers import books, sync

app = FastAPI(
    title="Calibre Sync API",
    description="API for synchronizing Calibre libraries to external devices",
    version="0.1.0"
)

# Include routers
app.include_router(books.router)
app.include_router(sync.router)

@app.get("/")
async def root():
    return {"message": "Welcome to Calibre Sync API"}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
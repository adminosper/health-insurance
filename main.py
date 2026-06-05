from fastapi import FastAPI

# Import models to ensure they are registered with SQLAlchemy's metadata
from src.database.connection import Base, engine
from src.models import claims as claim_models
from src.models import plans as plan_models
from src.models import policies as policy_models
from src.models import rules as rule_models

app = FastAPI(title="Claims Processing System API")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Claims Processing System API"}

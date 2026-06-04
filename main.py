from fastapi import FastAPI

app = FastAPI(title="Claims Processing System API")

@app.get("/")
def read_root():
    return {"message": "Welcome to the Claims Processing System API"}

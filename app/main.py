from fastapi import FastAPI

from app.oauth import router as oauth_router

app=FastAPI()

app.include_router(oauth_router)

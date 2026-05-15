from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import stock, screener, watchlist, news

app = FastAPI(title="MonkeyTrade API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(stock.router)
app.include_router(screener.router)
app.include_router(watchlist.router)
app.include_router(news.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}

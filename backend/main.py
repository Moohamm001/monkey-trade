from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import stock, screener, watchlist, news, orderflow, whale, quant, forwardtest, bot, portfolio

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
app.include_router(orderflow.router)
app.include_router(whale.router)
app.include_router(quant.router)
app.include_router(forwardtest.router)
app.include_router(bot.router)
app.include_router(portfolio.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}

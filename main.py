from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from core import get_sorted_prices

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://srithedesigner.github.io"],
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"], 
)

class PriceRequest(BaseModel):
    country: str
    product: str

@app.post("/get-prices")
async def get_prices(request: PriceRequest):
    try:
        result = await get_sorted_prices(request.country, request.product)
        return {"sorted_prices": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
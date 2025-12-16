# main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import uvicorn

app = FastAPI()

class Item(BaseModel):
    id: int
    name: str
    price: float

db: List[Item] = []

@app.get("/")
async def root():
    return {"status": "ok"}

@app.get("/items", response_model=List[Item])
async def get_items():
    return db

@app.get("/items/{item_id}", response_model=Item)
async def get_item(item_id: int):
    for item in db:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="Item missing")

@app.post("/items", response_model=Item)
async def create_item(item: Item):
    if any(i.id == item.id for i in db):
        raise HTTPException(status_code=400, detail="Duplicate id")
    db.append(item)
    return item

@app.delete("/items/{item_id}")
async def delete_item(item_id: int):
    for i, item in enumerate(db):
        if item.id == item_id:
            db.pop(i)
            return {"deleted": item_id}
    raise HTTPException(status_code=404, detail="Item missing")
if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


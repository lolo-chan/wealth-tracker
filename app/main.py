from fastapi import FastAPI
from .database import engine, Base
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from datetime import date
from decimal import Decimal
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy import func
from .database import engine, Base, get_db
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from . import models
from fastapi.middleware.cors import CORSMiddleware
import os
import httpx
from .config import settings

origins = os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")


class SnapshotCreate(BaseModel):
    snapshot_date: date
    asset_name: str
    balance: Decimal

# Create all tables that don't exist yet
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Wealth Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_voo_inr_value():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    async with httpx.AsyncClient(headers=headers, timeout=10) as client:
        # VOO price
        r = await client.get("https://query1.finance.yahoo.com/v8/finance/chart/VOO?range=1d&interval=1d")
        r.raise_for_status()
        price = r.json()["chart"]["result"][0]["meta"]["regularMarketPrice"]

        # USD→INR
        rate_r = await client.get("https://api.frankfurter.dev/v2/rate/USD/INR")
        rate = rate_r.json()["rate"]

    fixed_inr = settings.voo_units * price * rate
    return fixed_inr, rate



@app.get("/")
def root():
    return {"message": "Wealth Tracker backend is running"}


@app.post("/snapshots")
def create_snapshot(payload: SnapshotCreate, db: Session = Depends(get_db)):
    snapshot = models.Snapshot(
        snapshot_date=payload.snapshot_date,
        asset_name=payload.asset_name,
        balance=payload.balance,
    )
    db.add(snapshot)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="A snapshot for this asset on this date already exists. Please update the existing snapshot instead."
        )
    
    db.refresh(snapshot)
    return {
        "id": snapshot.id,
        "snapshot_date": snapshot.snapshot_date,
        "asset_name": snapshot.asset_name,
        "balance": snapshot.balance,
    }


@app.get("/snapshots")
def list_snapshots(
    asset_name: Optional[str] = None,
    snapshot_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Snapshot)

    if asset_name:
        query = query.filter(models.Snapshot.asset_name == asset_name)
    if snapshot_date:
        query = query.filter(models.Snapshot.snapshot_date == snapshot_date)

    snapshots = query.order_by(models.Snapshot.snapshot_date.desc()).all()

    return [
        {
            "id": s.id,
            "snapshot_date": s.snapshot_date,
            "asset_name": s.asset_name,
            "balance": s.balance,
        }
        for s in snapshots
    ]


@app.post("/snapshots/bulk")
async def create_snapshots_bulk(payloads: List[SnapshotCreate], db: Session = Depends(get_db)):
    fixed_inr, rate = await get_voo_inr_value()

    snapshots = []
    for payload in payloads:
        balance = payload.balance
        if payload.asset_name == "US Market":
            groww_usd = float(payload.balance)
            groww_inr = groww_usd * rate

            balance = Decimal(str(round(fixed_inr + groww_inr, 2)))

        snapshot = models.Snapshot(
            snapshot_date=payload.snapshot_date,
            asset_name=payload.asset_name,
            balance=balance,
        )
        db.add(snapshot)
        snapshots.append(snapshot)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="A snapshot for this asset on this date already exists. Please update the existing snapshot instead."
        )

    for s in snapshots:
        db.refresh(s)

    return [
        {
            "id": s.id,
            "snapshot_date": s.snapshot_date,
            "asset_name": s.asset_name,
            "balance": s.balance,
        }
        for s in snapshots
    ]


@app.get("/snapshots/summary")
def get_summary(
    snapshot_date: date,
    db: Session = Depends(get_db),
):
    total = (
        db.query(func.sum(models.Snapshot.balance))
        .filter(models.Snapshot.snapshot_date == snapshot_date)
        .scalar()
    )

    return {
        "snapshot_date": snapshot_date,
        "total_balance": total or 0,
    }


class SnapshotUpdate(BaseModel):
    balance: Decimal


@app.patch("/snapshots/{snapshot_id}")
def update_snapshot(
    snapshot_id: int,
    payload: SnapshotUpdate,
    db: Session = Depends(get_db),
):
    snapshot = db.query(models.Snapshot).filter(models.Snapshot.id == snapshot_id).first()
    if not snapshot:
        return {"error": "Snapshot not found"}

    snapshot.balance = payload.balance
    db.commit()
    db.refresh(snapshot)

    return {
        "id": snapshot.id,
        "snapshot_date": snapshot.snapshot_date,
        "asset_name": snapshot.asset_name,
        "balance": snapshot.balance,
    }


@app.delete("/snapshots/{snapshot_id}")
def delete_snapshot(snapshot_id: int, db: Session = Depends(get_db)):
    snapshot = db.query(models.Snapshot).filter(models.Snapshot.id == snapshot_id).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    db.delete(snapshot)
    db.commit()
    return {"message": "Snapshot deleted"}


@app.get("/price/voo")
async def get_voo_price():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(headers=headers, timeout=10) as client:
        r = await client.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/VOO?range=1d&interval=1d"
        )
        r.raise_for_status()
        data = r.json()
        price = data["chart"]["result"][0]["meta"]["regularMarketPrice"]
    return {
        "price_usd": price,
        "units": settings.voo_units,
    }
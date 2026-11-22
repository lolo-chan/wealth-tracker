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


class SnapshotCreate(BaseModel):
    snapshot_date: date
    asset_name: str
    balance: Decimal

# Create all tables that don't exist yet
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Wealth Tracker API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
def create_snapshots_bulk(payloads: List[SnapshotCreate], db: Session = Depends(get_db)):
    snapshots = []
    for payload in payloads:
        snapshot = models.Snapshot(
            snapshot_date=payload.snapshot_date,
            asset_name=payload.asset_name,
            balance=payload.balance,
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
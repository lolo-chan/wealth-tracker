from sqlalchemy import Column, Integer, String, Date, Numeric, UniqueConstraint
from .database import Base

class Snapshot(Base):
    __tablename__ = "snapshots"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    asset_name = Column(String, nullable=False)
    balance = Column(Numeric(15, 2), nullable=False)

    __table_args__ = (
        UniqueConstraint("snapshot_date", "asset_name", name="uq_date_asset"),
    )
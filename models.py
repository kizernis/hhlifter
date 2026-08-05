from sqlalchemy import Column, Integer, String, DateTime, Boolean
from datetime import datetime
from database import Base

class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    hh_resume_id = Column(String, unique=True)
    last_updated = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)
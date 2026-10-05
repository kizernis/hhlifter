from worker import lift_all_resumes_task
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
import models
from database import SessionLocal, engine
from loguru import logger

logger.add("logs/api.log", rotation="10 MB", level="INFO")

# logger.info("--- Создаю таблицы в базе данных ---")
# models.Base.metadata.create_all(bind=engine)
# logger.success("--- Таблицы созданы (если их не было) ---")

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
async def root():
    return {"message": "Бэкенд трекера запущен!"}

@app.post("/add_resume")
async def add_resume(name: str, hh_resume_id: str, db: Session = Depends(get_db)):
    new_resume = models.Resume(name=name, hh_resume_id=hh_resume_id)
    db.add(new_resume)
    db.commit()
    db.refresh(new_resume)
    return {"status": "Resume added", "id": new_resume.id, "name": new_resume.name}

@app.get("/get_resumes")
async def get_resumes(db: Session = Depends(get_db)):
    resumes = db.query(models.Resume).all()
    return {"resumes": resumes}

@app.post("/lift_resumes/")
async def lift_resumes():
    lift_all_resumes_task.delay() # type: ignore
    return {"status": "Task sent to worker"}

from worker import lift_resume_task
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
import models
from database import SessionLocal, engine

# При старте приложения создаем таблицы в базе данных (если их еще нет)
print("--- Создаю таблицы в базе данных ---")
models.Base.metadata.create_all(bind=engine)
print("--- Таблицы созданы (если их не было) ---")

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

@app.post("/lift_resume/{resume_id}")
async def lift_resume(resume_id: int, db: Session = Depends(get_db)):
    resume = db.query(models.Resume).filter(models.Resume.id == resume_id).first()
    if not resume:
        return {"error": "Resume not found"}
    
    # Отправляем задачу в Celery (фоном)
    # .delay() — это магия Celery, которая кидает задачу в Redis и сразу возвращает управление
    lift_resume_task.delay(resume.name, resume.hh_resume_id) # type: ignore
    
    return {"status": "Task sent to worker", "resume": resume.name}

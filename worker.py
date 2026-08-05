import os
import asyncio
from celery import Celery
from patchright.async_api import async_playwright, expect
from config import settings
from celery.schedules import crontab
from database import SessionLocal, engine
import models

# models.Base.metadata.create_all(bind=engine)

celery_app = Celery("worker", broker=settings.redis_url, backend=settings.redis_url)

async def run_hh_lift(resume_name, resume_hh_id):
    async with async_playwright() as p:
        # ПРОВЕРКА: Если мы в Докере, путь будет /app/browser_cache
        # Если в Windows — просто browser_cache в папке проекта
        is_docker = os.path.exists("/.dockerenv")
        user_data_dir = "/app/browser_cache" if is_docker else os.path.join(os.getcwd(), "browser_cache")

        # Настройки для Докера (без них Chrome не заведется)
        docker_args = [
            '--no-sandbox', 
            '--disable-setuid-sandbox', 
            '--disable-dev-shm-usage'
        ] if is_docker else []

        context = None
        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                channel='chrome', slow_mo=0,
                headless=is_docker,
                no_viewport=True,
                chromium_sandbox=not is_docker, # для запуска в Windows?
                args=docker_args,
                ignore_default_args=['--disable-blink-features=AutomationControlled'],
            )

            page = await context.new_page()
            await page.route('**/*', lambda route: route.abort() if route.request.resource_type == 'image' or route.request.resource_type == 'video' else route.continue_())
            print(f"--- Иду на HH для резюме {resume_name} ---")
            
            # await page.goto("https://hh.ru/resume/361c6939ff02951bd20039ed1f6d735a324e65") # Программист
            # await page.goto("https://hh.ru/resume/b2fdb5ecff0cf5b16f0039ed1f474f4c7a5a41") # Техподдержка
            await page.goto(f"https://hh.ru/resume/{resume_hh_id}", wait_until="domcontentloaded")

            btn_enter = page.get_by_role("main").get_by_role("button", name="Войти")
            if await btn_enter.is_visible():
                print("--- Аутентификация в HH ---")
                await btn_enter.click()
                await page.get_by_role("button", name="Войти").click()
                await page.get_by_text("Почта").first.click()
                await page.get_by_role("textbox").fill(settings.hh_login)
                await page.get_by_role("button", name="Войти с паролем").click()
                await page.get_by_role("textbox").fill(settings.hh_password)
                await page.get_by_role("button", name="Войти", exact=True).click()

            # ... после перехода на страницу резюме ...

            selector_yes = 'button[data-qa="resume-update-button"]'
            selector_no = 'a[data-qa="resumeservice-button__renewresume"]'
            await expect(page.locator(f'{selector_yes}, {selector_no}')).to_be_visible()

            # 1. Проверяем кнопку обновления
            btn_update = page.locator(selector_yes)
            if await btn_update.is_visible():
                print(f"--- Кнопка найдена! Поднимаю резюме {resume_name} ---")
                # await btn_update.click()
                # Можно добавить проверку на появление сообщения "Резюме обновлено"
                # Обновим время в базе (позже сделаем через SQLAlchemy)
            else:
                print(f"--- Кнопка обновления не найдена для {resume_name} ---")
                # 2. Пытаемся понять, когда можно будет поднять
                # Ищем текст "Можно сегодня в..."
                info_text = page.locator('span[data-qa="cell-text-content"]')
                # На странице может быть несколько таких спанов, нам нужен тот, где есть время
                all_texts = await info_text.all_text_contents()
                for text in all_texts:
                    if "Можно сегодня в" in text or "Можно завтра в" in text:
                        print(f"--- Инфо: {text} ---")
                        # Тут можно распарсить время через регулярку или сплит
            
            await page.wait_for_timeout(2000) # Дадим время на анимацию

            await page.close()
        except Exception as e:
            print(f"!!! Ошибка в работе бота: {e}")
        finally:
            if context:
                await context.close()
                print("--- Контекст браузера закрыт ---")

@celery_app.task
def lift_resume_task(resume_name, resume_hh_id):
    # Запускаем асинхронную функцию в синхронном Celery
    asyncio.run(run_hh_lift(resume_name, resume_hh_id))


@celery_app.task
def check_all_resumes_task():
    """Задача, которая проверяет все активные резюме в базе"""
    db = SessionLocal()
    try:
        resumes = db.query(models.Resume).filter(models.Resume.is_active == True).all()
        for resume in resumes:
            # Запускаем поднятие для каждого резюме
            # .delay() отправит их в очередь, и они будут выполняться один за другим
            lift_resume_task.delay(resume.name, resume.hh_resume_id) # type: ignore
    finally:
        db.close()

# Настраиваем расписание "будильника"
celery_app.conf.beat_schedule = {
    "check-every-30-minutes": {
        "task": "worker.check_all_resumes_task",
        "schedule": crontab(minute="*/1"), # каждые 30 минут
    },
}
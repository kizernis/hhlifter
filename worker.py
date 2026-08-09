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

async def login_to_hh(page):
    print("--- Аутентификация в HH ---")
    await page.get_by_role("button", name="Войти").click()
    await page.get_by_text("Почта").first.click()
    await page.get_by_role("textbox").fill(settings.hh_login)
    await page.get_by_role("button", name="Войти с паролем").click()
    await page.get_by_role("textbox").fill(settings.hh_password)
    await page.get_by_role("button", name="Войти", exact=True).click()

async def lift_single_page(page, resume_hh_id, resume_name):
    url = f"https://hh.ru/resume/{resume_hh_id}"
    await page.goto(url, wait_until="domcontentloaded")
    
    btn_enter = page.get_by_role("main").get_by_role("button", name="Войти")
    if await btn_enter.is_visible():
        await btn_enter.click()
        await login_to_hh(page)

    selector_yes = 'button[data-qa="resume-update-button"]'
    selector_no = 'a[data-qa="resumeservice-button__renewresume"]'
    
    try:
        await expect(page.locator(f'{selector_yes}, {selector_no}')).to_be_visible(timeout=10000)
        btn_update = page.locator(selector_yes)
        
        if await btn_update.is_visible():
            print(f"!!! Поднимаю резюме {resume_name}")
            # await btn_update.click()
            await page.wait_for_timeout(2000)
        else:
            info_text = page.locator('span[data-qa="cell-text-content"]')
            # На странице может быть несколько таких спанов, нам нужен тот, где есть время
            all_texts = await info_text.all_text_contents()
            for text in all_texts:
                if "Можно сегодня в" in text or "Можно завтра в" in text:
                    print(f"--- Инфо: {text} ---")
                    # Тут можно распарсить время через регулярку или сплит
    except Exception as e:
        print(f"Ошибка на странице {resume_name}: {e}")

async def run_mass_lift(resumes):
    async with async_playwright() as p:
        is_docker = os.path.exists("/.dockerenv")
        user_data_dir = "/app/browser_cache" if is_docker else os.path.join(os.getcwd(), "browser_cache")

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

            await context.tracing.start(screenshots=True, snapshots=True, sources=True)

            scout_page = await context.new_page()
            try:
                print(f"--- Разведка: проверяю логин на примере {resumes[0].name} ---")
                await lift_single_page(scout_page, resumes[0].hh_resume_id, resumes[0].name)
            finally:
                await scout_page.close()

            # async with asyncio.TaskGroup() as tg:
            #     for res in resumes[1:]:
            #         tg.create_task(process_resume_in_parallel(context, res))

            # Создаем список задач для всех оставшихся резюме
            tasks = []
            for res in resumes[1:]:
                tasks.append(process_resume_in_parallel(context, res))
            
            # Запускаем все задачи одновременно и ждем их выполнения
            # *tasks — это "распаковка" списка в аргументы функции
            await asyncio.gather(*tasks)
        finally:
            if context is not None:
                await context.tracing.stop(path="traces/mass_lift_report.zip")
                await context.close()

async def process_resume_in_parallel(context, res_data):
    """Вспомогательная функция для TaskGroup"""
    page = await context.new_page()
    try:
        # Блокировка картинок для скорости
        # await page.route('**/*', lambda r: r.abort() if r.request.resource_type in ['image', 'media'] else r.continue_())
        await lift_single_page(page, res_data.hh_resume_id, res_data.name)
    except Exception as e:
        print(f"Ошибка в параллельном потоке {res_data.name}: {e}")
    finally:
        await page.close()

@celery_app.task
def lift_all_resumes_task():
    """Задача, которая поднимает все активные резюме в базе"""
    db = SessionLocal()
    try:
        resumes = db.query(models.Resume).filter(models.Resume.is_active == True).all()
        if resumes:
            asyncio.run(run_mass_lift(resumes))
    finally:
        db.close()

# Настраиваем расписание "будильника"
celery_app.conf.beat_schedule = {
    "check-every-30-minutes": {
        "task": "worker.lift_all_resumes_task",
        "schedule": crontab(minute="*/5"), # каждые 30 минут
    },
}
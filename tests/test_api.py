from fastapi.testclient import TestClient
from main import app

# Создаем тестового клиента, который умеет делать запросы к нашему приложению
client = TestClient(app)


def test_read_root():
    """Тест 1: Проверяем, что главная страница отвечает 200 OK и отдает приветствие"""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()


def test_get_resumes_endpoint():
    """Тест 2: Проверяем, что эндпоинт получения резюме возвращает список"""
    response = client.get("/get_resumes")
    assert response.status_code == 200

    data = response.json()
    assert "resumes" in data
    assert isinstance(data["resumes"], list)
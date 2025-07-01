import os
from datetime import datetime

RESULTS_DIR = "results"

def save_debate_result(query: str, content: str):
    """
    Сохраняет результат дебатов в markdown файл в папке RESULTS_DIR.
    Имя файла генерируется на основе текущей даты/времени и части запроса.
    """
    # Создаем папку для результатов, если её нет
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # Формируем имя файла
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    # Очищаем запрос для использования в имени файла
    safe_query = "".join(c for c in query if c.isalnum() or c in (' ', '_')).strip()
    safe_query = safe_query.replace(' ', '_')[:50] # Обрезаем до 50 символов
    
    filename = f"{timestamp}_{safe_query}.md"
    filepath = os.path.join(RESULTS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    
    print(f"✅ Результаты дебатов сохранены в: {filepath}")

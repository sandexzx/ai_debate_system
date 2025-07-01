#!/usr/bin/env python3
"""
AI Debate System - Система дебатов между ИИ агентами

Этот скрипт запускает систему, где несколько ИИ моделей спорят между собой
по заданному вопросу, а судья оценивает их аргументы и выносит вердикт.

Использование:
    python main.py "Стоит ли внедрять 4-дневную рабочую неделю?"
    python main.py --interactive  # Интерактивный режим
    python main.py --demo         # Демо с примерами

Автор: Твой любимый AI сеньор 🚀
"""

import asyncio
import argparse
import sys
from datetime import datetime
from typing import Optional

# Импорты наших модулей
from config import Config
from models.api_client import ModelManager
from agents.orchestrator import DebateOrchestrator

class DebateApp:
    """Главное приложение для управления дебатами"""
    
    def __init__(self):
        self.model_manager: Optional[ModelManager] = None
        self.orchestrator: Optional[DebateOrchestrator] = None
    
    async def __aenter__(self):
        """Async context manager для инициализации"""
        self.model_manager = ModelManager(Config.MODELS)
        await self.model_manager.__aenter__()
        
        self.orchestrator = DebateOrchestrator(self.model_manager)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрываем соединения при выходе"""
        if self.model_manager:
            await self.model_manager.__aexit__(exc_type, exc_val, exc_tb)
    
    async def run_single_debate(self, query: str) -> str:
        """Запускает один дебат и возвращает результат"""
        if not self.orchestrator:
            raise RuntimeError("Приложение не инициализировано")
        
        print(f"🎯 Запускаем дебаты: {query}")
        print("=" * 80)
        
        result = await self.orchestrator.run_quick_debate(query)
        return result
    
    async def interactive_mode(self):
        """Интерактивный режим для множественных запросов"""
        print("🎭 СИСТЕМА ДЕБАТОВ МЕЖДУ ИИ")
        print("Введите ваш вопрос, и AI агенты проведут дебаты!")
        print("Команды: 'exit' - выход, 'help' - помощь, 'sessions' - список сессий")
        print("=" * 80)
        
        while True:
            try:
                query = input("\n💬 Ваш вопрос: ").strip()
                
                if query.lower() in ['exit', 'quit', 'выход']:
                    print("👋 До свидания!")
                    break
                elif query.lower() == 'help':
                    self._show_help()
                    continue
                elif query.lower() == 'sessions':
                    self._show_sessions()
                    continue
                elif not query:
                    print("❌ Пустой запрос. Попробуйте еще раз.")
                    continue
                
                print(f"\n🚀 Обрабатываем: {query}")
                result = await self.run_single_debate(query)
                print(f"\n{result}")
                
            except KeyboardInterrupt:
                print("\n\n👋 Прерывание пользователем. До свидания!")
                break
            except Exception as e:
                print(f"\n❌ Ошибка: {e}")
                print("Попробуйте еще раз или введите 'exit' для выхода.")
    
    async def demo_mode(self):
        """Демонстрационный режим с примерами"""
        demo_queries = [
            "Стоит ли внедрять 4-дневную рабочую неделю?",
            "Нужно ли разрешить удаленную работу во всех компаниях?", 
            "Полезен ли искусственный интеллект для образования?",
            "Стоит ли запретить использование смартфонов в школах?"
        ]
        
        print("🎪 ДЕМО РЕЖИМ - Примеры дебатов")
        print("Сейчас проведем несколько демонстрационных дебатов")
        print("=" * 80)
        
        for i, query in enumerate(demo_queries, 1):
            print(f"\n🎯 ДЕМО {i}/{len(demo_queries)}: {query}")
            
            try:
                result = await self.run_single_debate(query)
                print(f"\n{result}")
                
                # Пауза между демо для читабельности
                if i < len(demo_queries):
                    print(f"\n⏳ Пауза 3 секунды перед следующим демо...")
                    await asyncio.sleep(3)
                    
            except Exception as e:
                print(f"❌ Ошибка в демо {i}: {e}")
        
        print(f"\n🎉 Демо завершено! Проведено {len(demo_queries)} дебатов.")
    
    def _show_help(self):
        """Показывает справку по командам"""
        help_text = """
📖 СПРАВКА ПО КОМАНДАМ:

Основные команды:
• Просто введите ваш вопрос - система запустит дебаты
• 'exit' или 'quit' - выйти из программы  
• 'help' - показать эту справку
• 'sessions' - показать список проведенных дебатов

Примеры хороших вопросов для дебатов:
• "Стоит ли внедрять 4-дневную рабочую неделю?"
• "Полезен ли ИИ для образования?"
• "Нужно ли запретить криптовалюты?"
• "Стоит ли переходить на электромобили?"

Система автоматически:
✓ Фильтрует слишком простые вопросы
✓ Улучшает формулировку запроса
✓ Проводит 3 раунда дебатов между экспертами
✓ Выносит итоговый вердикт через ИИ-судью
"""
        print(help_text)
    
    def _show_sessions(self):
        """Показывает список проведенных сессий"""
        if not self.orchestrator:
            print("❌ Оркестратор не инициализирован")
            return
        
        sessions = self.orchestrator.list_sessions()
        
        if not sessions:
            print("📝 Пока не проведено ни одного дебата")
            return
        
        print(f"📊 ПРОВЕДЕННЫЕ ДЕБАТЫ ({len(sessions)}):")
        print("-" * 50)
        
        for session_id in sessions[-10:]:  # Показываем последние 10
            summary = self.orchestrator.get_session_summary(session_id)
            if summary:
                print(f"{summary}\n")

async def main():
    """Главная функция приложения"""
    
    # Настройка аргументов командной строки
    parser = argparse.ArgumentParser(
        description="AI Debate System - Дебаты между ИИ агентами",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python main.py "Стоит ли внедрять 4-дневную рабочую неделю?"
  python main.py --interactive
  python main.py --demo
        """
    )
    
    parser.add_argument(
        "query", 
        nargs="?", 
        help="Вопрос для дебатов"
    )
    
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Запустить в интерактивном режиме"
    )
    
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="Запустить в режиме отладки с детальными логами"
    )
    
    args = parser.parse_args()
    
    # Проверяем наличие API ключей для OpenRouter
    missing_keys = []
    if not Config.OPENROUTER_API_KEY or Config.OPENROUTER_API_KEY == "your-openrouter-key":
        missing_keys.append("OPENROUTER_API_KEY")
    
    if missing_keys:
        print("❌ Отсутствуют API ключи для OpenRouter:")
        for key in missing_keys:
            print(f"   • {key}")
        print("\nУстановите переменную окружения:")
        print("   export OPENROUTER_API_KEY='ваш-ключ-openrouter'")
        print("Или измените значение в config.py")
        sys.exit(1)
    
    # Запускаем приложение
    try:
        async with DebateApp() as app:
            
            if args.debug:
                # Режим отладки - используем асинхронную функцию
                if args.query:
                    from debug_utils import async_debug_run
                    await async_debug_run(args.query)
                else:
                    print("❌ В режиме отладки нужно указать запрос")
                    print("Пример: python main.py --debug 'Ваш вопрос'")
            elif args.demo:
                await app.demo_mode()
            elif args.interactive:
                await app.interactive_mode()
            elif args.query:
                result = await app.run_single_debate(args.query)
                print(result)
            else:
                # Если нет аргументов, запускаем интерактивный режим
                await app.interactive_mode()
                
    except KeyboardInterrupt:
        print("\n👋 Программа прервана пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Запускаем основную функцию в asyncio event loop
    asyncio.run(main())
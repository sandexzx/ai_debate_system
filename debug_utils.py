"""
Утилиты для отладки системы дебатов.
Помогают понять, что происходит между агентами и как передаются данные.
"""

import json
from typing import Dict, Any
from datetime import datetime
from agents.debater import DebateContext
from agents.orchestrator import DebateSession

class DebugLogger:
    """Логгер для отладки процесса дебатов"""
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.logs = []
    
    def log_step(self, step: str, data: Any = None):
        """Логирует шаг выполнения с данными"""
        if self.verbose:
            print(f"🐛 DEBUG: {step}")
            if data:
                print(f"   Data: {str(data)[:200]}...")
        
        self.logs.append({
            "step": step,
            "data": data,
            "timestamp": "now"  # В реальности можно добавить datetime
        })
    
    def show_context_state(self, context: DebateContext, title: str = "Context State"):
        """Показывает текущее состояние контекста дебатов"""
        print(f"\n📋 {title}")
        print("=" * 50)
        print(f"Query: {context.query}")
        print(f"Current Round: {context.current_round}")
        print(f"Arguments History: {len(context.arguments_history)} rounds")
        
        for round_num, arguments in context.arguments_history.items():
            print(f"  Round {round_num}: {list(arguments.keys())}")
            for role, arg in arguments.items():
                print(f"    {role}: {len(arg)} chars - {arg[:100]}...")
        
        print(f"Scores History: {len(context.scores_history)} rounds")
        for round_num, scores in context.scores_history.items():
            print(f"  Round {round_num}: {scores}")
        
        print("=" * 50)
    
    def show_session_summary(self, session: DebateSession):
        """Показывает детальную сводку по сессии"""
        print(f"\n📊 SESSION SUMMARY: {session.session_id}")
        print("=" * 60)
        print(f"Status: {session.status}")
        print(f"Original Query: {session.original_query}")
        print(f"Enhanced Query: {session.enhanced_query}")
        
        if session.context:
            print(f"\nContext Data:")
            print(f"  Total rounds in history: {len(session.context.arguments_history)}")
            print(f"  Total chars in all arguments: {self._count_total_chars(session.context)}")
        
        print(f"\nResults per round:")
        for i, result in enumerate(session.results, 1):
            print(f"  Round {i}: Winner = {result.winner}")
            print(f"    Scores: {[(role, score.total) for role, score in result.scores.items()]}")
        
        if session.final_verdict:
            print(f"\nFinal Verdict Preview:")
            print(f"  {session.final_verdict[:300]}...")
        
        print("=" * 60)
    
    def _count_total_chars(self, context: DebateContext) -> int:
        """Подсчитывает общее количество символов в аргументах"""
        total = 0
        for round_args in context.arguments_history.values():
            for arg in round_args.values():
                total += len(arg)
        return total
    
    def export_session_to_file(self, session: DebateSession, filename: str = None):
        """Экспортирует полную сессию в JSON файл для анализа"""
        if not filename:
            filename = f"debug_session_{session.session_id}.json"
        
        # Собираем данные для экспорта
        export_data = {
            "session_id": session.session_id,
            "original_query": session.original_query,
            "enhanced_query": session.enhanced_query,
            "status": session.status,
            "start_time": str(session.start_time),
            "end_time": str(session.end_time) if session.end_time else None,
            "context": self._serialize_context(session.context) if session.context else None,
            "results": self._serialize_results(session.results),
            "final_verdict": session.final_verdict
        }
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            print(f"📁 Session exported to: {filename}")
        except Exception as e:
            print(f"❌ Error exporting session: {e}")
    
    def _serialize_context(self, context: DebateContext) -> Dict[str, Any]:
        """Сериализует контекст в словарь для JSON"""
        return {
            "query": context.query,
            "current_round": context.current_round,
            "arguments_history": context.arguments_history,
            "scores_history": context.scores_history,
            "judge_feedback": context.judge_feedback
        }
    
    def _serialize_results(self, results) -> list:
        """Сериализует результаты раундов"""
        serialized = []
        for result in results:
            serialized.append({
                "winner": result.winner,
                "scores": {role: {
                    "logic": score.logic,
                    "evidence": score.evidence,
                    "refutation": score.refutation,
                    "practicality": score.practicality,
                    "total": score.total
                } for role, score in result.scores.items()},
                "feedback": result.feedback,
                "recommendations": result.recommendations
            })
        return serialized

# Глобальный экземпляр для удобства использования
debug_logger = DebugLogger()

def show_round_arguments(context: DebateContext, round_num: int):
    """Удобная функция для показа аргументов конкретного раунда"""
    if round_num not in context.arguments_history:
        print(f"❌ Раунд {round_num} не найден в истории")
        return
    
    print(f"\n🗣️ АРГУМЕНТЫ РАУНДА {round_num}")
    print("=" * 60)
    
    arguments = context.arguments_history[round_num]
    for role, argument in arguments.items():
        role_name = {"D1": "PRO (За)", "D2": "CONTRA (Против)", "D3": "ALTERNATIVE (Альтернатива)"}.get(role, role)
        print(f"\n{role} - {role_name}:")
        print("-" * 40)
        print(argument)
    
    print("=" * 60)

async def async_debug_run(query: str):
    """Асинхронный запуск дебатов с максимальной отладочной информацией"""
    from config import Config
    from models.api_client import ModelManager
    from agents.orchestrator import DebateOrchestrator
    from token_tracker import token_tracker
    
    # Создаем специальный session_id для отладки
    debug_session_id = f"debug_{query[:20].replace(' ', '_')}_{datetime.now().strftime('%H%M%S')}"
    
    async with ModelManager(Config.MODELS, session_id=debug_session_id) as manager:
        orchestrator = DebateOrchestrator(manager)
        
        print("🐛 Запуск дебатов в отладочном режиме")
        debug_logger.log_step("Starting debug debate", {"query": query})
        
        session = await orchestrator.run_debate(query, session_id=debug_session_id)
        
        debug_logger.show_session_summary(session)
        
        if session.context:
            debug_logger.show_context_state(session.context, "Final Context State")
            
            # Показываем аргументы каждого раунда
            for round_num in session.context.arguments_history.keys():
                show_round_arguments(session.context, round_num)
        
        # Показываем детальную статистику токенов
        if session.token_stats:
            print("\n" + "="*80)
            print(session.token_stats)
        
        # Экспортируем детальную статистику токенов
        if token_tracker:
            token_export_result = token_tracker.export_session_usage(debug_session_id)
            print(f"\n{token_export_result}")
        
        # Экспортируем полную сессию для анализа
        debug_logger.export_session_to_file(session)
        
        return session

def quick_debug_run(query: str):
    """
    УСТАРЕВШАЯ функция - оставлена для совместимости.
    Используйте async_debug_run() внутри уже существующего event loop'а.
    """
    print("⚠️ Внимание: quick_debug_run устарела. Используйте async_debug_run().")
    
    import asyncio
    
    # Проверяем, есть ли уже запущенный event loop
    try:
        loop = asyncio.get_running_loop()
        print("❌ Обнаружен активный event loop. Используйте async_debug_run() вместо quick_debug_run().")
        return None
    except RuntimeError:
        # Нет активного loop'а, можно создать новый
        return asyncio.run(async_debug_run(query))
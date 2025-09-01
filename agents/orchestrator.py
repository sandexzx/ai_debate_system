import asyncio
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime

from agents.gatekeeper import Gatekeeper  
from agents.debater import ProDebater, ContraDebater, AlternativeDebater, DebateContext
from agents.judge import Judge, RoundResult
from config import Config
from token_tracker import token_tracker

@dataclass
class DebateSession:
    """Полная сессия дебатов с метаданными и статистикой токенов"""
    session_id: str
    original_query: str
    enhanced_query: str
    start_time: datetime
    end_time: Optional[datetime] = None
    context: Optional[DebateContext] = None
    results: List[RoundResult] = field(default_factory=list)
    final_verdict: Optional[str] = None
    status: str = "pending"  # pending, running, completed, failed
    token_stats: Optional[str] = None  # Отчет по токенам

class DebateOrchestrator:
    """
    Главный оркестратор системы дебатов.
    Координирует работу всех агентов и управляет жизненным циклом дебатов.
    """
    
    def __init__(self, model_manager):
        """
        Инициализирует оркестратор со всеми необходимыми агентами.
        
        Каждый агент имеет свою роль:
        - Gatekeeper: фильтрует запросы  
        - ProDebater: аргументирует "за"
        - ContraDebater: аргументирует "против"
        - AlternativeDebater: предлагает альтернативы
        - Judge: оценивает и выносит вердикты
        """
        self.model_manager = model_manager
        
        # Инициализируем всех агентов
        self.gatekeeper = Gatekeeper(model_manager)
        self.pro_debater = ProDebater(model_manager)
        self.contra_debater = ContraDebater(model_manager)
        self.alternative_debater = AlternativeDebater(model_manager)
        self.judge = Judge(model_manager)
        
        # Маппинг агентов для удобного доступа
        self.debaters = {
            "D1": self.pro_debater,
            "D2": self.contra_debater, 
            "D3": self.alternative_debater
        }
        
        # История сессий (в реальном приложении можно сохранять в БД)
        self.sessions: Dict[str, DebateSession] = {}
    
    async def run_debate(
        self,
        query: str,
        session_id: Optional[str] = None,
        override_query: Optional[str] = None,
        known_enhanced: Optional[str] = None,
        skip_enhance: bool = False,
        skip_gatekeeper: bool = False,
        on_update: Optional[Callable[[str, Dict], None]] = None,
    ) -> DebateSession:
        """
        Запускает полный цикл дебатов для заданного запроса.
        
        Этапы дебатов:
        1. Фильтрация запроса через Gatekeeper
        2. Улучшение формулировки запроса
        3. Проведение 3 раундов дебатов
        4. Оценка каждого раунда судьей
        5. Вынесение итогового вердикта
        
        Args:
            query: Исходный запрос пользователя
            session_id: Опциональный ID сессии для отслеживания
            
        Returns:
            DebateSession: Полный результат дебатов
        """
        
        # Создаем новую сессию
        if not session_id:
            session_id = f"debate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        session = DebateSession(
            session_id=session_id,
            original_query=query,
            enhanced_query="",
            start_time=datetime.now()
        )
        
        self.sessions[session_id] = session
        
        try:
            print(f"🎭 Начинаем дебаты для сессии: {session_id}")
            session.status = "running"
            
            # Этап 1: Проверяем запрос через швейцара (если не пропускаем)
            if not skip_gatekeeper:
                should_debate, rejection_reason = await self.gatekeeper.should_debate(query)
            else:
                should_debate, rejection_reason = True, None
            
            if not should_debate:
                session.status = "rejected"
                session.final_verdict = f"❌ Запрос отклонен: {rejection_reason}"
                session.end_time = datetime.now()
                return session
            
            print("✅ Запрос прошел фильтрацию")
            
            # Этап 2: Улучшаем формулировку запроса
            if skip_enhance and known_enhanced is not None:
                enhanced_query = known_enhanced
            else:
                enhanced_query = await self.gatekeeper.get_enhanced_query(query)
            session.enhanced_query = enhanced_query

            print(f"📝 Запрос улучшен: {enhanced_query}")
            if on_update:
                on_update("enhanced_query", {"enhanced_query": enhanced_query})

            # Какой запрос использовать в дебатах
            debate_query = override_query or enhanced_query
            
            # Этап 3: Инициализируем контекст дебатов
            session.context = DebateContext(
                query=debate_query,
                current_round=1,
                arguments_history={},
                scores_history={},
                judge_feedback={},
                summaries={},
            )
            
            # Этап 4: Проводим раунды дебатов
            for round_num in range(1, Config.DEBATE_ROUNDS + 1):
                print(f"\n🥊 Раунд {round_num}/{Config.DEBATE_ROUNDS}")
                
                session.context.current_round = round_num
                round_result = await self._conduct_round(session.context, on_update=on_update)
                session.results.append(round_result)
                
                # Обновляем контекст результатами раунда
                self._update_context_with_results(session.context, round_result)
                
                print(f"🏆 Победитель раунда: {round_result.winner}")
                
                # Небольшая пауза между раундами для стабильности API
                await asyncio.sleep(1)
            
            # Этап 5: Итоговый вердикт от судьи
            print("\n⚖️ Формируем итоговый вердикт...")
            session.final_verdict = await self.judge.final_verdict(session.context)
            if on_update and session.final_verdict:
                on_update("final_verdict", {"final_verdict": session.final_verdict})
            
            # Этап 6: Генерируем отчет по токенам и затратам
            if token_tracker:
                session.token_stats = token_tracker.format_session_report(session_id)
                print(f"\n💰 Отчет по токенам готов")
                if on_update and session.token_stats:
                    on_update("token_stats", {"token_stats": session.token_stats})
            
            session.status = "completed"
            session.end_time = datetime.now()
            
            print(f"✅ Дебаты завершены! Время: {session.end_time - session.start_time}")
            
        except Exception as e:
            print(f"❌ Ошибка в дебатах: {e}")
            session.status = "failed"
            session.final_verdict = f"Техническая ошибка: {str(e)}"
            session.end_time = datetime.now()
        
        return session
    
    async def _conduct_round(self, context: DebateContext, on_update: Optional[Callable[[str, Dict], None]] = None) -> RoundResult:
        """
        Проводит один раунд дебатов между всеми участниками.
        
        Порядок выступлений:
        1. D1 (Pro) - сторонник
        2. D2 (Contra) - противник  
        3. D3 (Alternative) - альтернативщик
        4. Judge - оценка раунда
        
        Args:
            context: Текущий контекст дебатов
            
        Returns:
            RoundResult: Результат раунда с оценками и победителем
        """
        
        round_arguments = {}
        
        # Собираем аргументы от всех участников последовательно для поэтапного отображения
        print("  🗣️ Собираем аргументы участников...")
        
        # Проходим участников по порядку: D1, D2, D3
        for role in ["D1", "D2", "D3"]:
            debater = self.debaters[role]
            
            # Генерируем аргумент участника
            try:
                argument = await self._get_debater_argument(debater, context, role)
                round_arguments[role] = argument
                print(f"    ✓ {role}: {len(argument)} символов")
                
                # Отправляем аргумент в интерфейс
                if on_update:
                    on_update("argument", {"round": context.current_round, "role": role, "text": argument})
                
                # Генерируем саммари для этого аргумента
                try:
                    if hasattr(self.model_manager, "summarize"):
                        summary = await self.model_manager.summarize(argument)
                        if summary:
                            # Отправляем саммари в интерфейс
                            if on_update:
                                on_update("summary", {"round": context.current_round, "role": role, "summary": summary})
                except Exception:
                    pass  # Саммари не критично
                    
            except Exception as e:
                argument = f"[Техническая ошибка при генерации аргумента: {str(e)}]"
                round_arguments[role] = argument
                print(f"    ❌ {role}: ошибка - {str(e)}")
                
                # Отправляем даже ошибочный аргумент
                if on_update:
                    on_update("argument", {"round": context.current_round, "role": role, "text": argument})
        
        # ВАЖНО: Сохраняем аргументы в контекст ДО оценки судьи
        context.arguments_history[context.current_round] = round_arguments
        
        # Оцениваем раунд через судью
        print("  ⚖️ Судья оценивает раунд...")
        round_result = await self.judge.evaluate_round(context, round_arguments)
        if on_update and round_result and hasattr(round_result, "feedback"):
            on_update("judge", {"round": context.current_round, "feedback": round_result.feedback, "scores": {role: score.total for role, score in round_result.scores.items()}, "winner": round_result.winner})
        
        return round_result
    
    async def _get_debater_argument(self, debater, context: DebateContext, role: str) -> str:
        """
        Получает аргумент от конкретного участника с обработкой ошибок.
        Используется в качестве таски для параллельного выполнения.
        """
        try:
            return await debater.generate_argument(context)
        except Exception as e:
            # В случае ошибки возвращаем заглушку
            return f"[{role}] Технические трудности при генерации аргумента: {str(e)}"
    
    def _update_context_with_results(self, context: DebateContext, round_result: RoundResult):
        """
        Обновляет контекст дебатов результатами последнего раунда.
        Добавляет оценки и фидбек судьи.
        
        ВАЖНО: Аргументы уже должны быть сохранены в context.arguments_history
        в методе _conduct_round, поэтому здесь мы только добавляем оценки.
        """
        
        round_num = context.current_round
        
        # Обновляем историю очков
        context.scores_history[round_num] = {
            role: score.total for role, score in round_result.scores.items()
        }
        
        # Обновляем фидбек судьи
        context.judge_feedback[round_num] = round_result.feedback
    
    def get_session_summary(self, session_id: str) -> Optional[str]:
        """
        Возвращает краткую сводку по сессии дебатов.
        Полезно для быстрого просмотра результатов.
        """
        
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        summary_parts = [
            f"📋 СВОДКА ДЕБАТОВ #{session_id}",
            f"📝 Запрос: {session.original_query}",
            f"⏱️ Статус: {session.status}",
            f"🕐 Время: {session.start_time.strftime('%H:%M:%S')}"
        ]
        
        if session.end_time:
            duration = session.end_time - session.start_time
            summary_parts.append(f"⌛ Длительность: {duration.total_seconds():.1f}s")
        
        if session.results:
            summary_parts.append(f"🥊 Раундов: {len(session.results)}")
            
            # Показываем победителей раундов
            winners = [result.winner for result in session.results]
            winners_count = {role: winners.count(role) for role in set(winners)}
            winners_str = ", ".join([f"{role}: {count}" for role, count in winners_count.items()])
            summary_parts.append(f"🏆 Победы: {winners_str}")
        
        if session.final_verdict:
            # Берем первые 200 символов вердикта
            verdict_preview = session.final_verdict[:200] + "..." if len(session.final_verdict) > 200 else session.final_verdict
            summary_parts.append(f"⚖️ Вердикт: {verdict_preview}")
        
        return "\n".join(summary_parts)
    
    def get_detailed_session(self, session_id: str) -> Optional[DebateSession]:
        """Возвращает полную детальную информацию о сессии"""
        return self.sessions.get(session_id)
    
    def list_sessions(self) -> List[str]:
        """Возвращает список всех ID сессий"""
        return list(self.sessions.keys())
    
    async def run_quick_debate(self, query: str) -> str:
        """
        Быстрый метод для простого использования - запускает дебаты и возвращает результат.
        Удобно для интеграции в другие приложения.
        
        Args:
            query: Запрос пользователя
            
        Returns:
            str: Итоговый результат дебатов в текстовом формате
        """
        
        session = await self.run_debate(query)
        
        if session.status == "rejected":
            return session.final_verdict
        elif session.status == "failed":
            return f"❌ Ошибка: {session.final_verdict}"
        elif session.status == "completed":
            # Формируем красивый отчет
            report_parts = [
                f"🎯 РЕЗУЛЬТАТ ДЕБАТОВ",
                f"📝 Вопрос: {session.original_query}",
                ""
            ]
            
            # Добавляем краткую сводку по раундам
            if session.results:
                report_parts.append("📊 СВОДКА ПО РАУНДАМ:")
                for i, result in enumerate(session.results, 1):
                    winner_scores = result.scores[result.winner]
                    report_parts.append(f"  Раунд {i}: {result.winner} ({winner_scores.total} баллов)")
                report_parts.append("")
            
            # Добавляем итоговый вердикт
            if session.final_verdict:
                report_parts.append(session.final_verdict)
            
            return "\n".join(report_parts)
        else:
            return f"⏳ Дебаты в процессе... (статус: {session.status})"

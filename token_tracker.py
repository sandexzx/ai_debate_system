"""
Система подсчета токенов и расчета стоимости для дебатов.
Помогает понимать экономику системы и оптимизировать затраты.
"""

import tiktoken
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
import json

@dataclass
class TokenUsage:
    """Информация об использовании токенов для одного запроса"""
    model_name: str
    role: str  # gatekeeper, debater_pro, judge, etc.
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: float
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class SessionTokenStats:
    """Статистика токенов для всей сессии дебатов"""
    session_id: str
    total_requests: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    usage_by_role: Dict[str, List[TokenUsage]] = field(default_factory=dict)
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

class TokenTracker:
    """
    Основной класс для отслеживания использования токенов и расчета стоимости.
    
    Поддерживает разные модели через OpenRouter с их pricing.
    """
    
    def __init__(self):
        # Примерные цены OpenRouter (может меняться, проверяйте актуальные)
        # Цены указаны за 1K токенов в USD
        self.pricing = {
            "google/gemini-2.5-flash": {
                "input": 0.0003,   # $0.30 per 1M input tokens -> $0.0003 per 1K input tokens
                "output": 0.0025     # $2.50 per 1M output tokens -> $0.0025 per 1K output tokens
            },
            "anthropic/claude-sonnet-4": {
                "input": 0.003,   # $3 per 1M input tokens -> $0.003 per 1K input tokens
                "output": 0.015     # $15 per 1M output tokens -> $0.015 per 1K output tokens
            },
            "openai/gpt-4o-mini-2024-07-18": {
                "input": 0.00015,  # $0.15 per 1M input tokens -> $0.00015 per 1K input tokens
                "output": 0.00060   # $0.60 per 1M output tokens -> $0.00060 per 1K output tokens
            },
            "google/gemini-2.5-pro": {
                "input": 0.00125,  # $1.25 per 1M input tokens -> $0.00125 per 1K input tokens
                "output": 0.010     # $10 per 1M output tokens -> $0.010 per 1K output tokens
            },
            "openai/o3": {
                "input": 0.002,    # $2 per 1M input tokens -> $0.002 per 1K input tokens
                "output": 0.008      # $8 per 1M output tokens -> $0.008 per 1K output tokens
            },
            "openai/gpt-4.1": {
                "input": 0.002,    # $2 per 1M input tokens -> $0.002 per 1K input tokens
                "output": 0.008      # $8 per 1M output tokens -> $0.008 per 1K output tokens
            }
        }
        
        # Для подсчета токенов используем tiktoken (приблизительно)
        try:
            self.encoder = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding
        except:
            self.encoder = None
        
        # Активные сессии
        self.sessions: Dict[str, SessionTokenStats] = {}
    
    def estimate_tokens(self, text: str) -> int:
        """
        Приблизительный подсчет токенов в тексте.
        
        Для точного подсчета нужны специфичные для модели энкодеры,
        но это дает хорошую оценку для планирования затрат.
        """
        if self.encoder:
            return len(self.encoder.encode(text))
        else:
            # Fallback: примерно 4 символа = 1 токен для европейских языков
            return len(text) // 4
    
    def calculate_cost(self, model_id: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Рассчитывает стоимость запроса на основе использованных токенов"""
        
        if model_id not in self.pricing:
            # Если модели нет в pricing, используем gemini-2.5-flash как default
            model_id = "google/gemini-2.5-flash"
        
        pricing = self.pricing[model_id]
        
        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
    
    def start_session(self, session_id: str) -> SessionTokenStats:
        """Начинает новую сессию отслеживания"""
        session = SessionTokenStats(session_id=session_id)
        self.sessions[session_id] = session
        return session
    
    def log_request(self, session_id: str, model_id: str, role: str, 
                   prompt_text: str, completion_text: str) -> TokenUsage:
        """
        Логирует использование токенов для одного запроса.
        
        Args:
            session_id: ID сессии дебатов
            model_id: ID модели (например, "google/gemini-2.5-flash")
            role: Роль агента (gatekeeper, debater_pro, judge, etc.)
            prompt_text: Текст промпта
            completion_text: Текст ответа модели
        """
        
        # Подсчитываем токены
        prompt_tokens = self.estimate_tokens(prompt_text)
        completion_tokens = self.estimate_tokens(completion_text)
        total_tokens = prompt_tokens + completion_tokens
        
        # Рассчитываем стоимость
        cost = self.calculate_cost(model_id, prompt_tokens, completion_tokens)
        
        # Создаем запись об использовании
        usage = TokenUsage(
            model_name=model_id,
            role=role,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            estimated_cost=cost
        )
        
        # Обновляем статистику сессии
        if session_id not in self.sessions:
            self.start_session(session_id)
        
        session = self.sessions[session_id]
        session.total_requests += 1
        session.total_prompt_tokens += prompt_tokens
        session.total_completion_tokens += completion_tokens
        session.total_tokens += total_tokens
        session.total_cost += cost
        
        # Группируем по ролям
        if role not in session.usage_by_role:
            session.usage_by_role[role] = []
        session.usage_by_role[role].append(usage)
        
        return usage
    
    def finish_session(self, session_id: str):
        """Завершает сессию отслеживания"""
        if session_id in self.sessions:
            self.sessions[session_id].end_time = datetime.now()
    
    def get_session_stats(self, session_id: str) -> Optional[SessionTokenStats]:
        """Возвращает статистику по сессии"""
        return self.sessions.get(session_id)
    
    def format_session_report(self, session_id: str) -> str:
        """Форматирует красивый отчет по использованию токенов в сессии"""
        
        session = self.get_session_stats(session_id)
        if not session:
            return f"❌ Сессия {session_id} не найдена"
        
        # Вычисляем длительность
        duration = ""
        if session.end_time:
            delta = session.end_time - session.start_time
            duration = f"{delta.total_seconds():.1f}s"
        else:
            duration = "в процессе"
        
        # Формируем отчет
        report_parts = [
            f"💰 ОТЧЕТ ПО ТОКЕНАМ И ЗАТРАТАМ",
            f"📊 Сессия: {session_id}",
            f"⏱️ Длительность: {duration}",
            f"",
            f"📈 ОБЩАЯ СТАТИСТИКА:",
            f"• Всего запросов: {session.total_requests}",
            f"• Входящие токены: {session.total_prompt_tokens:,}",
            f"• Исходящие токены: {session.total_completion_tokens:,}",
            f"• Общий объем: {session.total_tokens:,} токенов",
            f"• Оценочная стоимость: ${session.total_cost:.4f}",
            f""
        ]
        
        # Разбивка по ролям
        if session.usage_by_role:
            report_parts.append("🎭 РАЗБИВКА ПО РОЛЯМ:")
            
            role_names = {
                "gatekeeper": "🚪 Швейцар",
                "debater_pro": "✅ Сторонник", 
                "debater_contra": "❌ Противник",
                "debater_alternative": "🔄 Альтернативщик",
                "judge": "⚖️ Судья"
            }
            
            for role, usages in session.usage_by_role.items():
                role_name = role_names.get(role, role)
                total_tokens = sum(u.total_tokens for u in usages)
                total_cost = sum(u.estimated_cost for u in usages)
                
                report_parts.append(f"• {role_name}: {len(usages)} запросов, "
                                  f"{total_tokens:,} токенов, ${total_cost:.4f}")
        
        # Эффективность
        if session.total_tokens > 0:
            cost_per_1k_tokens = (session.total_cost / session.total_tokens) * 1000
            report_parts.extend([
                f"",
                f"💡 ЭФФЕКТИВНОСТЬ:",
                f"• Стоимость за 1K токенов: ${cost_per_1k_tokens:.4f}",
                f"• Токенов в секунду: {session.total_tokens / max(1, delta.total_seconds() if session.end_time else 1):.1f}" if session.end_time else ""
            ])
        
        return "\n".join(report_parts)
    
    def export_session_usage(self, session_id: str, filename: str = None) -> str:
        """Экспортирует детальную статистику использования в JSON"""
        
        session = self.get_session_stats(session_id)
        if not session:
            return f"❌ Сессия {session_id} не найдена"
        
        if not filename:
            filename = f"token_usage_{session_id}.json"
        
        # Подготавливаем данные для экспорта
        export_data = {
            "session_id": session.session_id,
            "summary": {
                "total_requests": session.total_requests,
                "total_prompt_tokens": session.total_prompt_tokens,
                "total_completion_tokens": session.total_completion_tokens,
                "total_tokens": session.total_tokens,
                "total_cost": session.total_cost,
                "start_time": str(session.start_time),
                "end_time": str(session.end_time) if session.end_time else None
            },
            "detailed_usage": {}
        }
        
        # Детальная информация по каждой роли
        for role, usages in session.usage_by_role.items():
            export_data["detailed_usage"][role] = [
                {
                    "model_name": u.model_name,
                    "prompt_tokens": u.prompt_tokens,
                    "completion_tokens": u.completion_tokens,
                    "total_tokens": u.total_tokens,
                    "estimated_cost": u.estimated_cost,
                    "timestamp": str(u.timestamp)
                }
                for u in usages
            ]
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            return f"📁 Статистика токенов экспортирована в: {filename}"
        except Exception as e:
            return f"❌ Ошибка экспорта: {e}"

# Глобальный трекер для использования в системе
token_tracker = TokenTracker()

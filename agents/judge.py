import re
from typing import Dict, Tuple, Optional
from models.prompts import PromptTemplates
from agents.debater import DebateContext
from dataclasses import dataclass

@dataclass
class RoundScore:
    """Оценка одного участника за раунд"""
    logic: int          # Логичность аргументов (0-10)
    evidence: int       # Фактическая база (0-10)  
    refutation: int     # Опровержение оппонентов (0-10)
    practicality: int   # Практическая применимость (0-10)
    
    @property
    def total(self) -> int:
        return self.logic + self.evidence + self.refutation + self.practicality

@dataclass  
class RoundResult:
    """Результат оценки раунда"""
    scores: Dict[str, RoundScore]  # {role: RoundScore}
    winner: str                    # Победитель раунда
    feedback: str                  # Обратная связь от судьи
    recommendations: str           # Рекомендации на следующий раунд

class Judge:
    """
    Агент-судья, который оценивает качество аргументов в дебатах.
    Выставляет баллы, определяет победителей раундов и формулирует итоговые решения.
    """
    
    def __init__(self, model_manager):
        self.model_manager = model_manager
        self.model_name = "judge"
        
        # Регулярные выражения для парсинга оценок
        self.score_pattern = re.compile(r'D([123]).*?(\d+)\+(\d+)\+(\d+)\+(\d+)\s*=\s*(\d+)')
        self.winner_pattern = re.compile(r'ПОБЕДИТЕЛЬ РАУНДА:\s*D([123])')
    
    async def evaluate_round(self, context: DebateContext, round_arguments: Dict[str, str]) -> RoundResult:
        """
        Оценивает раунд дебатов и возвращает результат с баллами и победителем.
        
        Args:
            context: Контекст дебатов с полной историей
            round_arguments: Аргументы текущего раунда {role: argument}
            
        Returns:
            RoundResult: Полный результат оценки раунда
        """
        
        # Обновляем контекст текущими аргументами
        temp_context = self._update_context_with_arguments(context, round_arguments)
        
        # Формируем промпт для судьи
        judge_prompt = PromptTemplates.get_judge_prompt(
            query=context.query,
            round_num=context.current_round,
            arguments=temp_context.arguments_history,
            is_final=False
        )
        
        messages = [{"role": "user", "content": judge_prompt}]
        
        try:
            # Получаем оценку от модели-судьи
            response = await self.model_manager.query_model(
                model_name=self.model_name,
                messages=messages,
                system_prompt=PromptTemplates.JUDGE_SYSTEM
            )
            
            # Парсим ответ судьи
            return self._parse_judge_response(response, round_arguments)
            
        except Exception as e:
            print(f"Ошибка при оценке раунда: {e}")
            # Возвращаем базовую оценку в случае ошибки
            return self._get_fallback_evaluation(round_arguments)
    
    async def final_verdict(self, context: DebateContext) -> str:
        """
        Выносит итоговый вердикт по всем дебатам и формулирует рекомендацию.
        
        Args:
            context: Полный контекст всех дебатов
            
        Returns:
            str: Итоговый вердикт и рекомендация пользователю
        """
        
        # Формируем промпт для финального решения
        final_prompt = PromptTemplates.get_judge_prompt(
            query=context.query,
            round_num=0,  # Не важно для финала
            arguments=context.arguments_history,
            is_final=True
        )
        
        messages = [{"role": "user", "content": final_prompt}]
        
        try:
            # Получаем итоговое решение
            verdict = await self.model_manager.query_model(
                model_name=self.model_name,
                messages=messages,
                system_prompt=PromptTemplates.JUDGE_SYSTEM
            )
            
            return self._format_final_verdict(verdict, context)
            
        except Exception as e:
            print(f"Ошибка при вынесении вердикта: {e}")
            return self._get_fallback_verdict(context)
    
    def _update_context_with_arguments(self, context: DebateContext, round_arguments: Dict[str, str]) -> DebateContext:
        """
        Обновляет контекст новыми аргументами раунда.
        
        ВАЖНО: Этот метод создает ВРЕМЕННУЮ копию контекста только для генерации
        промпта судьи. Реальное обновление контекста происходит в orchestrator.
        """
        updated_history = context.arguments_history.copy()
        updated_history[context.current_round] = round_arguments
        
        return DebateContext(
            query=context.query,
            current_round=context.current_round,
            arguments_history=updated_history,
            scores_history=context.scores_history,
            judge_feedback=context.judge_feedback,
            summaries=context.summaries
        )
    
    def _parse_judge_response(self, response: str, round_arguments: Dict[str, str]) -> RoundResult:
        """
        Парсит ответ судьи и извлекает оценки, победителя и фидбек.
        Использует регулярные выражения для надежного извлечения данных.
        """
        
        scores = {}
        
        # Извлекаем оценки для каждого участника
        score_matches = self.score_pattern.findall(response)
        
        for match in score_matches:
            role_num, logic, evidence, refutation, practicality, total = match
            role = f"D{role_num}"
            
            scores[role] = RoundScore(
                logic=int(logic),
                evidence=int(evidence), 
                refutation=int(refutation),
                practicality=int(practicality)
            )
        
        # Если не удалось распарсить оценки, ставим базовые
        if not scores:
            scores = self._generate_fallback_scores(round_arguments)
        
        # Извлекаем победителя раунда
        winner_match = self.winner_pattern.search(response)
        if winner_match:
            winner = f"D{winner_match.group(1)}"
        else:
            # Определяем победителя по наивысшему баллу
            winner = max(scores.keys(), key=lambda role: scores[role].total, default="D1")
        
        # Извлекаем рекомендации
        recommendations = self._extract_recommendations(response)
        
        return RoundResult(
            scores=scores,
            winner=winner,
            feedback=response,
            recommendations=recommendations
        )
    
    def _generate_fallback_scores(self, round_arguments: Dict[str, str]) -> Dict[str, RoundScore]:
        """Генерирует базовые оценки, если парсинг не удался"""
        scores = {}
        
        for role in round_arguments.keys():
            # Базовые оценки 6-8 баллов по каждому критерию
            scores[role] = RoundScore(
                logic=7,
                evidence=6, 
                refutation=6,
                practicality=7
            )
        
        return scores
    
    def _extract_recommendations(self, response: str) -> str:
        """Извлекает рекомендации из ответа судьи"""
        
        # Ищем секцию с рекомендациями
        rec_patterns = [
            r'РЕКОМЕНДАЦИИ.*?:(.*?)(?=\n\n|\Z)',
            r'РЕКОМЕНДАЦИИ НА СЛЕДУЮЩИЙ РАУНД:(.*?)(?=\n\n|\Z)',
            r'что улучшить.*?:(.*?)(?=\n\n|\Z)'
        ]
        
        for pattern in rec_patterns:
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return "Продолжайте в том же духе, усиливая аргументацию."
    
    def _format_final_verdict(self, verdict: str, context: DebateContext) -> str:
        """Форматирует итоговый вердикт для красивого вывода"""
        
        # Добавляем статистику дебатов
        stats = self._calculate_debate_stats(context)
        
        formatted = f"""
🏛️ ИТОГОВЫЙ ВЕРДИКТ ДЕБАТОВ 🏛️

{verdict}

📊 СТАТИСТИКА ДЕБАТОВ:
• Всего раундов: {len(context.arguments_history)}
• Участников: {len(set().union(*[args.keys() for args in context.arguments_history.values()]))}
• Общий объем аргументов: ~{stats['total_chars']} символов

{stats['winners_summary']}
"""
        return formatted
    
    def _calculate_debate_stats(self, context: DebateContext) -> Dict:
        """Вычисляет статистику дебатов"""
        
        total_chars = 0
        round_winners = []
        
        # Подсчитываем статистику по раундам  
        for round_num, arguments in context.arguments_history.items():
            total_chars += sum(len(arg) for arg in arguments.values())
            
            # Определяем победителя раунда по очкам (если есть)
            if round_num in context.scores_history:
                scores = context.scores_history[round_num]
                winner = max(scores.keys(), key=lambda k: scores[k])
                round_winners.append(winner)
        
        # Формируем сводку победителей
        if round_winners:
            winners_count = {role: round_winners.count(role) for role in set(round_winners)}
            winners_summary = "🏆 Победы по раундам: " + ", ".join([f"{role}: {count}" for role, count in winners_count.items()])
        else:
            winners_summary = ""
        
        return {
            'total_chars': total_chars,
            'winners_summary': winners_summary
        }
    
    def _get_fallback_evaluation(self, round_arguments: Dict[str, str]) -> RoundResult:
        """Базовая оценка в случае ошибки"""
        
        scores = self._generate_fallback_scores(round_arguments)
        winner = list(round_arguments.keys())[0] if round_arguments else "D1"
        
        return RoundResult(
            scores=scores,
            winner=winner,
            feedback="Техническая ошибка при оценке раунда",
            recommendations="Продолжайте аргументацию"
        )
    
    def _get_fallback_verdict(self, context: DebateContext) -> str:
        """Базовый вердикт в случае ошибки"""
        
        return f"""
🏛️ ИТОГОВЫЙ ВЕРДИКТ (резервный режим)

ЗАПРОС: {context.query}

К сожалению, произошла техническая ошибка при формировании итогового вердикта.
Все участники дебатов представили ценные аргументы по данному вопросу.

РЕКОМЕНДАЦИЯ: Рассмотрите все представленные точки зрения при принятии решения.
"""

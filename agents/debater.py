# agents/debater.py - Агенты-спорщики
from typing import Dict, List, Optional
from models.prompts import PromptTemplates
from dataclasses import dataclass

@dataclass
class DebateContext:
    """Контекст дебатов - вся история аргументов и оценок"""
    query: str
    current_round: int
    arguments_history: Dict[int, Dict[str, str]]  # {round: {role: argument}}
    scores_history: Dict[int, Dict[str, int]]     # {round: {role: score}}
    judge_feedback: Dict[int, str]                # {round: feedback}

class BaseDebater:
    """
    Базовый класс для всех участников дебатов.
    Содержит общую логику построения аргументов и взаимодействия с контекстом.
    """
    
    def __init__(self, model_manager, model_name: str, role: str, system_prompt: str):
        self.model_manager = model_manager
        self.model_name = model_name
        self.role = role
        self.system_prompt = system_prompt
        
        # Маппинг ролей для обращения к оппонентам
        self.role_mapping = {
            "D1": "PRO",
            "D2": "CONTRA", 
            "D3": "ALTERNATIVE"
        }
    
    async def generate_argument(self, context: DebateContext) -> str:
        """
        Генерирует аргумент для текущего раунда на основе контекста дебатов.
        
        Args:
            context: Полный контекст дебатов с историей аргументов
            
        Returns:
            str: Сгенерированный аргумент
        """
        
        # Строим контекст из предыдущих раундов
        context_str = self._build_context_string(context)
        
        # Формируем промпт для текущего раунда
        user_prompt = PromptTemplates.get_debater_prompt(
            role=self.role,
            query=context.query,
            round_num=context.current_round,
            context=context_str
        )
        
        messages = [{"role": "user", "content": user_prompt}]
        
        try:
            # Генерируем аргумент
            argument = await self.model_manager.query_model(
                model_name=self.model_name,
                messages=messages,
                system_prompt=self.system_prompt
            )
            
            # Обрезаем до лимита символов и очищаем
            argument = self._clean_argument(argument)
            return argument
            
        except Exception as e:
            # В случае ошибки возвращаем базовый ответ
            return self._get_fallback_argument(context)
    
    def _build_context_string(self, context: DebateContext) -> str:
        """
        Строит строку контекста из предыдущих раундов для подачи в промпт.
        Включает аргументы оппонентов и фидбек судьи.
        """
        if context.current_round == 1:
            return "Это первый раунд дебатов. История аргументов пуста."
        
        context_parts = []
        
        # Добавляем историю предыдущих раундов
        for round_num in range(1, context.current_round):
            context_parts.append(f"\n=== РАУНД {round_num} ===")
            
            # Аргументы участников
            if round_num in context.arguments_history:
                round_args = context.arguments_history[round_num]
                for role, argument in round_args.items():
                    role_name = self.role_mapping.get(role, role)
                    context_parts.append(f"\n{role} ({role_name}): {argument}")
            
            # Оценка судьи
            if round_num in context.judge_feedback:
                context_parts.append(f"\nОЦЕНКА СУДЬИ: {context.judge_feedback[round_num]}")
            
            # Счет раунда
            if round_num in context.scores_history:
                scores = context.scores_history[round_num]
                score_str = ", ".join([f"{role}: {score}" for role, score in scores.items()])
                context_parts.append(f"СЧЕТ: {score_str}")
        
        return "\n".join(context_parts)
    
    def _clean_argument(self, argument: str) -> str:
        """Очищает и обрезает аргумент до нужного формата"""
        
        # Убираем лишние переносы и пробелы
        argument = argument.strip()
        
        # Обрезаем до максимальной длины
        max_length = 1000
        if len(argument) > max_length:
            # Обрезаем по последнему предложению, которое помещается
            sentences = argument.split('.')
            truncated = ""
            for sentence in sentences:
                if len(truncated + sentence + ".") <= max_length:
                    truncated += sentence + "."
                else:
                    break
            argument = truncated if truncated else argument[:max_length] + "..."
        
        return argument
    
    def _get_fallback_argument(self, context: DebateContext) -> str:
        """Возвращает базовый аргумент в случае ошибки API"""
        role_name = self.role_mapping.get(self.role, self.role)
        return f"[{role_name}] Технические трудности при генерации аргумента. Придерживаюсь своей позиции по вопросу: {context.query}"

class ProDebater(BaseDebater):
    """Агент-сторонник, который поддерживает основную идею"""
    
    def __init__(self, model_manager):
        super().__init__(
            model_manager=model_manager,
            model_name="debater_pro",
            role="D1",
            system_prompt=PromptTemplates.DEBATER_PRO_SYSTEM
        )

class ContraDebater(BaseDebater):
    """Агент-противник, который критикует основную идею"""
    
    def __init__(self, model_manager):
        super().__init__(
            model_manager=model_manager,
            model_name="debater_contra", 
            role="D2",
            system_prompt=PromptTemplates.DEBATER_CONTRA_SYSTEM
        )

class AlternativeDebater(BaseDebater):
    """Агент-альтернативщик, который предлагает третий путь"""
    
    def __init__(self, model_manager):
        super().__init__(
            model_manager=model_manager,
            model_name="debater_alternative",
            role="D3", 
            system_prompt=PromptTemplates.DEBATER_ALTERNATIVE_SYSTEM
        )
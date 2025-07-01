# agents/gatekeeper.py - Фильтрация запросов
from typing import Tuple, Optional
from models.prompts import PromptTemplates

class Gatekeeper:
    """
    Агент-швейцар, который решает стоит ли запрос серьезного обсуждения.
    Фильтрует тривиальные вопросы и пропускает только достойные дебатов.
    """
    
    def __init__(self, model_manager):
        self.model_manager = model_manager
        self.model_name = "gatekeeper"
    
    async def should_debate(self, query: str) -> Tuple[bool, Optional[str]]:
        """
        Определяет, нужны ли дебаты для данного запроса.
        
        Args:
            query: Запрос пользователя
            
        Returns:
            Tuple[bool, Optional[str]]: (нужны_дебаты, причина_отклонения)
        """
        
        # Собираем сообщения для модели
        messages = [
            {
                "role": "user", 
                "content": PromptTemplates.GATEKEEPER_USER.format(query=query)
            }
        ]
        
        try:
            # Запрашиваем решение у модели-швейцара
            response = await self.model_manager.query_model(
                model_name=self.model_name,
                messages=messages,
                system_prompt=PromptTemplates.GATEKEEPER_SYSTEM
            )
            
            # Парсим ответ модели
            response = response.strip()
            
            if response.startswith("PASS"):
                return True, None
            elif response.startswith("REJECT"):
                # Извлекаем причину отклонения
                reason = response.replace("REJECT:", "").strip()
                return False, reason
            else:
                # Если формат ответа неожиданный, считаем что нужны дебаты
                # Лучше перестраховаться и запустить дискуссию
                return True, None
                
        except Exception as e:
            # В случае ошибки тоже пропускаем - безопаснее
            print(f"Ошибка в Gatekeeper: {e}")
            return True, None
    
    async def get_enhanced_query(self, original_query: str) -> str:
        """
        Дополнительный метод - улучшает формулировку запроса для дебатов.
        Это опциональная фича, которая может сделать дискуссию более фокусированной.
        """
        
        enhancement_prompt = f"""
Перефразируй этот запрос так, чтобы он лучше подходил для экспертных дебатов:

Исходный запрос: "{original_query}"

Сделай формулировку:
- Более конкретной и фокусированной
- Подходящей для аргументированной дискуссии  
- Провоцирующей разные точки зрения

Верни только улучшенную формулировку, без объяснений.
"""
        
        messages = [{"role": "user", "content": enhancement_prompt}]
        
        try:
            enhanced = await self.model_manager.query_model(
                model_name=self.model_name,
                messages=messages,
                system_prompt="Ты эксперт по формулировке вопросов для дебатов."
            )
            
            # Возвращаем улучшенную версию, если она разумная
            enhanced = enhanced.strip().strip('"')
            if len(enhanced) > 10 and len(enhanced) < 500:
                return enhanced
            else:
                return original_query
                
        except:
            # Если что-то пошло не так, возвращаем оригинал
            return original_query
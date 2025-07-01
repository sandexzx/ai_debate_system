import os
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class ModelConfig:
    """Конфигурация для конкретной модели"""
    name: str
    api_key: str
    base_url: str
    model_id: str
    max_tokens: int = 4000
    temperature: float = 0.7
    # Новые поля для OpenRouter
    site_url: Optional[str] = None
    site_name: Optional[str] = None

class Config:
    """Главный конфиг всей системы"""
    
    # API ключ для OpenRouter - засунь свой сюда
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "your-openrouter-key")
    
    # Базовая конфигурация OpenRouter
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    
    # Конфигурации моделей для дебатов
    # Сейчас все используют gemini-2.5-flash через OpenRouter
    MODELS = {
        "gatekeeper": ModelConfig(
            name="gatekeeper",
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            model_id="google/gemini-2.5-flash",
            temperature=0.3  # Более строгий для фильтрации
        ),
        
        "debater_pro": ModelConfig(
            name="debater_pro", 
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            model_id="google/gemini-2.5-flash",
            temperature=0.8  # Более креативный для споров
        ),
        
        "debater_contra": ModelConfig(
            name="debater_contra",
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            model_id="google/gemini-2.5-flash",
            temperature=0.8
        ),
        
        "debater_alternative": ModelConfig(
            name="debater_alternative",
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            model_id="google/gemini-2.5-flash",
            temperature=0.9  # Самый креативный для альтернатив
        ),
        
        "judge": ModelConfig(
            name="judge",
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            model_id="google/gemini-2.5-flash",
            temperature=0.4  # Более объективный
        )
    }
    
    # Настройки дебатов
    DEBATE_ROUNDS = 3
    MAX_ARGUMENT_LENGTH = 1000
    TIMEOUT_SECONDS = 30
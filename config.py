import os
from dataclasses import dataclass
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# Загружаем переменные из .env файла при каждом импорте
load_dotenv()

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
    
    # API ключ для neuroAPI
    NEUROAPI_API_KEY = os.getenv("NEUROAPI_API_KEY", "your-neuroapi-key")
    
    # Базовая конфигурация OpenRouter
    OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
    
    # Базовая конфигурация neuroAPI
    NEUROAPI_BASE_URL = "https://neuroapi.host/v1"
    
    # Флаг для выбора провайдера: 'openrouter' или 'neuroapi'
    PROVIDER = os.getenv("PROVIDER", "neuroapi")
    
    # Конфигурации моделей для дебатов
    # Сейчас все используют gemini-2.5-flash через OpenRouter
    MODELS = {
        "gatekeeper": ModelConfig(
            name="gatekeeper",
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            model_id="openai/gpt-4o-mini-2024-07-18",
            temperature=0.3  # Более строгий для фильтрации
        ),
        
        "debater_pro": ModelConfig(
            name="debater_pro", 
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            model_id="google/gemini-2.5-pro",
            temperature=0.8  # Более креативный для споров
        ),
        
        "debater_contra": ModelConfig(
            name="debater_contra",
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            model_id="anthropic/claude-sonnet-4",
            temperature=0.8
        ),
        
        "debater_alternative": ModelConfig(
            name="debater_alternative",
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            model_id="openai/gpt-4.1",
            temperature=0.9  # Самый креативный для альтернатив
        ),
        
        "judge": ModelConfig(
            name="judge",
            api_key=OPENROUTER_API_KEY,
            base_url=OPENROUTER_BASE_URL,
            model_id="anthropic/claude-sonnet-4",
            temperature=0.4  # Более объективный
        )
    }
    
    # Конфигурации моделей для neuroAPI (используем gpt-5-thinking-all)
    NEUROAPI_MODELS = {
        "gatekeeper": ModelConfig(
            name="gatekeeper",
            api_key=NEUROAPI_API_KEY,
            base_url=NEUROAPI_BASE_URL,
            model_id="gpt-5-thinking-all",
            temperature=0.3
        ),
        
        "debater_pro": ModelConfig(
            name="debater_pro", 
            api_key=NEUROAPI_API_KEY,
            base_url=NEUROAPI_BASE_URL,
            model_id="gpt-5-thinking-all",
            temperature=0.8
        ),
        
        "debater_contra": ModelConfig(
            name="debater_contra",
            api_key=NEUROAPI_API_KEY,
            base_url=NEUROAPI_BASE_URL,
            model_id="gpt-5-thinking-all",
            temperature=0.8
        ),
        
        "debater_alternative": ModelConfig(
            name="debater_alternative",
            api_key=NEUROAPI_API_KEY,
            base_url=NEUROAPI_BASE_URL,
            model_id="gpt-5-thinking-all",
            temperature=0.9
        ),
        
        "judge": ModelConfig(
            name="judge",
            api_key=NEUROAPI_API_KEY,
            base_url=NEUROAPI_BASE_URL,
            model_id="gpt-5-thinking-all",
            temperature=0.4
        )
    }
    
    @classmethod
    def get_models(cls):
        """Возвращает конфигурацию моделей в зависимости от выбранного провайдера"""
        if cls.PROVIDER == "neuroapi":
            return cls.NEUROAPI_MODELS
        else:
            return cls.MODELS
    
    # Настройки дебатов
    DEBATE_ROUNDS = 3
    MAX_ARGUMENT_LENGTH = 1000
    TIMEOUT_SECONDS = 120  # Увеличено для тяжелых моделей типа gpt-5
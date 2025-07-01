import asyncio
import aiohttp
import json
from typing import Dict, Any, Optional
from config import ModelConfig

class APIClient:
    """Универсальный клиент для работы с разными API LLM"""
    
    def __init__(self, config: ModelConfig):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager - создаем сессию"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрываем сессию при выходе"""
        if self.session:
            await self.session.close()
    
    def _build_headers(self) -> Dict[str, str]:
        """Строим заголовки в зависимости от провайдера"""
        headers = {"Content-Type": "application/json"}
        
        # Для OpenRouter используем OpenAI-совместимый формат
        if "openrouter.ai" in self.config.base_url:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
            
            # Добавляем специальные заголовки OpenRouter для рейтингов
            if self.config.site_url:
                headers["HTTP-Referer"] = self.config.site_url
            if self.config.site_name:
                headers["X-Title"] = self.config.site_name
                
        elif "openai" in self.config.base_url:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        elif "anthropic" in self.config.base_url:
            headers["x-api-key"] = self.config.api_key
            headers["anthropic-version"] = "2023-06-01"
        elif "deepseek" in self.config.base_url:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        
        return headers
    
    def _build_payload(self, messages: list, system_prompt: str = "") -> Dict[str, Any]:
        """Формируем payload для разных провайдеров"""
        
        # Для OpenRouter и обычного OpenAI используем одинаковый формат
        if "openrouter.ai" in self.config.base_url or "openai" in self.config.base_url:
            all_messages = []
            if system_prompt:
                all_messages.append({"role": "system", "content": system_prompt})
            all_messages.extend(messages)
            
            payload = {
                "model": self.config.model_id,
                "messages": all_messages,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
            
        elif "anthropic" in self.config.base_url:
            # Claude формат (оставляем для будущего использования)
            payload = {
                "model": self.config.model_id,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "messages": messages
            }
            if system_prompt:
                payload["system"] = system_prompt
        else:
            # Fallback к OpenAI-совместимому формату для других провайдеров
            all_messages = []
            if system_prompt:
                all_messages.append({"role": "system", "content": system_prompt})
            all_messages.extend(messages)
            
            payload = {
                "model": self.config.model_id,
                "messages": all_messages,
                "max_tokens": self.config.max_tokens,
                "temperature": self.config.temperature
            }
        
        return payload
    
    async def chat_completion(self, messages: list, system_prompt: str = "") -> str:
        """Основной метод для получения ответа от модели"""
        if not self.session:
            raise RuntimeError("APIClient не инициализирован. Используй async with.")
        
        headers = self._build_headers()
        payload = self._build_payload(messages, system_prompt)
        
        # Определяем endpoint в зависимости от провайдера
        if "anthropic" in self.config.base_url:
            endpoint = f"{self.config.base_url}/messages"
        else:
            # Для OpenRouter, OpenAI и других OpenAI-совместимых провайдеров
            endpoint = f"{self.config.base_url}/chat/completions"
        
        try:
            async with self.session.post(
                endpoint, 
                headers=headers, 
                json=payload
            ) as response:
                
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"API Error {response.status}: {error_text}")
                
                data = await response.json()
                
                # Парсим ответ в зависимости от провайдера
                if "anthropic" in self.config.base_url:
                    # Формат ответа Claude
                    return data["content"][0]["text"]
                else:
                    # Формат ответа OpenAI/OpenRouter и других совместимых провайдеров
                    return data["choices"][0]["message"]["content"]
                    
        except asyncio.TimeoutError:
            raise Exception(f"Timeout при запросе к {self.config.name}")
        except Exception as e:
            raise Exception(f"Ошибка при запросе к {self.config.name}: {str(e)}")

class ModelManager:
    """Менеджер для управления несколькими моделями"""
    
    def __init__(self, models_config: Dict[str, ModelConfig]):
        self.models_config = models_config
        self.clients: Dict[str, APIClient] = {}
    
    async def __aenter__(self):
        """Инициализируем всех клиентов"""
        for name, config in self.models_config.items():
            client = APIClient(config)
            await client.__aenter__()
            self.clients[name] = client
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрываем всех клиентов"""
        for client in self.clients.values():
            await client.__aexit__(exc_type, exc_val, exc_tb)
    
    async def query_model(self, model_name: str, messages: list, system_prompt: str = "") -> str:
        """Запрос к конкретной модели"""
        if model_name not in self.clients:
            raise ValueError(f"Модель {model_name} не найдена")
        
        return await self.clients[model_name].chat_completion(messages, system_prompt)
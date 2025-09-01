import asyncio
import aiohttp
import json
from typing import Dict, Any, Optional
from config import ModelConfig
from token_tracker import token_tracker

class APIClient:
    """Универсальный клиент для работы с разными API LLM"""
    
    def __init__(self, config: ModelConfig, session_id: str = None, role: str = "unknown"):
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        # Добавляем параметры для трекинга токенов
        self.session_id = session_id
        self.role = role
    
    async def __aenter__(self):
        """Async context manager - создаем сессию"""
        # Увеличиваем таймауты для тяжелых моделей типа gpt-5
        timeout_seconds = 120 if "neuroapi.host" in self.config.base_url else 30
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=timeout_seconds)
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
                
        # Для neuroAPI используем OpenAI-совместимый формат
        elif "neuroapi.host" in self.config.base_url:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
                
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
        
        # Для OpenRouter, neuroAPI и обычного OpenAI используем одинаковый формат
        if ("openrouter.ai" in self.config.base_url or 
            "neuroapi.host" in self.config.base_url or 
            "openai" in self.config.base_url):
            
            all_messages = []
            if system_prompt:
                all_messages.append({"role": "system", "content": system_prompt})
            all_messages.extend(messages)
            
            payload = {
                "model": self.config.model_id,
                "messages": all_messages,
                "temperature": self.config.temperature
            }
            
            # Для neuroAPI не добавляем max_tokens, так как это может вызвать ошибку 500
            if "neuroapi.host" not in self.config.base_url:
                payload["max_tokens"] = self.config.max_tokens
            
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
        """Основной метод для получения ответа от модели с трекингом токенов"""
        if not self.session:
            raise RuntimeError("APIClient не инициализирован. Используй async with.")
        
        headers = self._build_headers()
        payload = self._build_payload(messages, system_prompt)
        
        # Формируем полный текст промпта для подсчета токенов
        full_prompt = self._build_full_prompt_text(messages, system_prompt)
        
        # Определяем endpoint
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
                    completion_text = data["content"][0]["text"]
                else:
                    # Формат ответа OpenAI/OpenRouter/neuroAPI и других совместимых провайдеров
                    completion_text = data["choices"][0]["message"]["content"]
                
                # Логируем использование токенов, если включен трекинг
                if self.session_id and token_tracker:
                    token_tracker.log_request(
                        session_id=self.session_id,
                        model_id=self.config.model_id,
                        role=self.role,
                        prompt_text=full_prompt,
                        completion_text=completion_text
                    )
                
                return completion_text
                    
        except asyncio.TimeoutError:
            raise Exception(f"Timeout при запросе к {self.config.name}")
        except Exception as e:
            raise Exception(f"Ошибка при запросе к {self.config.name}: {str(e)}")
    
    def _build_full_prompt_text(self, messages: list, system_prompt: str = "") -> str:
        """
        Строит полный текст промпта для подсчета токенов.
        Это приблизительная реконструкция того, что видит модель.
        """
        prompt_parts = []
        
        if system_prompt:
            prompt_parts.append(f"System: {system_prompt}")
        
        for message in messages:
            role = message.get("role", "unknown")
            content = message.get("content", "")
            prompt_parts.append(f"{role.capitalize()}: {content}")
        
        return "\n\n".join(prompt_parts)

class ModelManager:
    """Менеджер для управления несколькими моделями с поддержкой трекинга токенов"""
    
    def __init__(self, models_config: Dict[str, ModelConfig], session_id: str = None):
        self.models_config = models_config
        self.clients: Dict[str, APIClient] = {}
        self.session_id = session_id
    
    async def __aenter__(self):
        """Инициализируем всех клиентов с информацией о сессии"""
        for name, config in self.models_config.items():
            client = APIClient(config, session_id=self.session_id, role=name)
            await client.__aenter__()
            self.clients[name] = client
        
        # Запускаем отслеживание токенов для сессии
        if self.session_id and token_tracker:
            token_tracker.start_session(self.session_id)
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Закрываем всех клиентов и завершаем отслеживание"""
        for client in self.clients.values():
            await client.__aexit__(exc_type, exc_val, exc_tb)
        
        # Завершаем отслеживание токенов
        if self.session_id and token_tracker:
            token_tracker.finish_session(self.session_id)
    
    async def query_model(self, model_name: str, messages: list, system_prompt: str = "") -> str:
        """Запрос к конкретной модели с автоматическим трекингом токенов"""
        if model_name not in self.clients:
            raise ValueError(f"Модель {model_name} не найдена")
        
        return await self.clients[model_name].chat_completion(messages, system_prompt)
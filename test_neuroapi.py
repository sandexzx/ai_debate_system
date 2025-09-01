#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работоспособности neuroAPI провайдера
"""

import asyncio
import os
from config import Config, ModelConfig
from models.api_client import APIClient

async def test_neuroapi():
    """Тестируем базовый запрос к neuroAPI"""
    print("🧪 ТЕСТИРУЕМ NEUROAPI")
    print("=" * 50)
    
    # Проверяем наличие API ключа
    if not Config.NEUROAPI_API_KEY or Config.NEUROAPI_API_KEY == "your-neuroapi-key":
        print("❌ NEUROAPI_API_KEY не установлен!")
        print("Установите переменную: export NEUROAPI_API_KEY='ваш-ключ'")
        return False
    
    print(f"✅ API ключ найден: {Config.NEUROAPI_API_KEY[:10]}...")
    print(f"🌐 Base URL: {Config.NEUROAPI_BASE_URL}")
    
    # Создаем тестовую конфигурацию (используем gpt-5-thinking-all)
    test_config = ModelConfig(
        name="test_neuro",
        api_key=Config.NEUROAPI_API_KEY,
        base_url=Config.NEUROAPI_BASE_URL,
        model_id="gpt-5-thinking-all",
        temperature=0.7
    )
    
    print(f"🤖 Модель: {test_config.model_id}")
    print()
    
    # Тестируем соединение
    try:
        async with APIClient(test_config, session_id="test_session", role="test") as client:
            print("🔄 Отправляем тестовый запрос...")
            
            test_messages = [
                {"role": "user", "content": "Привет! Ответь одним словом: работает ли neuroAPI?"}
            ]
            
            response = await client.chat_completion(test_messages)
            
            print("✅ УСПЕХ! Получен ответ:")
            print(f"📝 {response}")
            print()
            
            return True
            
    except Exception as e:
        print(f"❌ ОШИБКА при тестировании neuroAPI:")
        print(f"   {str(e)}")
        return False

async def test_all_models():
    """Тестируем все модели из конфигурации neuroAPI"""
    print("🧪 ТЕСТИРУЕМ ВСЕ МОДЕЛИ NEUROAPI")
    print("=" * 50)
    
    if not Config.NEUROAPI_API_KEY or Config.NEUROAPI_API_KEY == "your-neuroapi-key":
        print("❌ NEUROAPI_API_KEY не установлен!")
        return False
    
    neuro_models = Config.NEUROAPI_MODELS
    successful_tests = 0
    
    for model_name, model_config in neuro_models.items():
        print(f"\n🤖 Тестируем {model_name}...")
        
        try:
            async with APIClient(model_config, session_id=f"test_{model_name}", role=model_name) as client:
                test_messages = [
                    {"role": "user", "content": f"Привет от {model_name}! Ответь кратко."}
                ]
                
                response = await client.chat_completion(test_messages)
                print(f"   ✅ {model_name}: {response[:100]}...")
                successful_tests += 1
                
        except Exception as e:
            print(f"   ❌ {model_name}: {str(e)}")
    
    print(f"\n📊 РЕЗУЛЬТАТ: {successful_tests}/{len(neuro_models)} моделей работают")
    return successful_tests == len(neuro_models)

async def test_vs_openrouter():
    """Сравниваем ответы neuroAPI и OpenRouter"""
    print("🧪 СРАВНИВАЕМ NEUROAPI VS OPENROUTER")
    print("=" * 50)
    
    # Проверяем ключи
    if not Config.NEUROAPI_API_KEY or Config.NEUROAPI_API_KEY == "your-neuroapi-key":
        print("❌ NEUROAPI_API_KEY не установлен!")
        return
        
    if not Config.OPENROUTER_API_KEY or Config.OPENROUTER_API_KEY == "your-openrouter-key":
        print("❌ OPENROUTER_API_KEY не установлен!")
        return
    
    # Конфигурации для сравнения
    neuro_config = ModelConfig(
        name="neuro_test",
        api_key=Config.NEUROAPI_API_KEY,
        base_url=Config.NEUROAPI_BASE_URL,
        model_id="gpt-5-thinking-all",
        temperature=0.7
    )
    
    openrouter_config = ModelConfig(
        name="openrouter_test",
        api_key=Config.OPENROUTER_API_KEY,
        base_url=Config.OPENROUTER_BASE_URL,
        model_id="openai/gpt-4o-mini-2024-07-18",
        temperature=0.7
    )
    
    test_question = "Объясни в двух предложениях, что такое машинное обучение?"
    
    print(f"❓ Вопрос: {test_question}")
    print()
    
    # Тестируем neuroAPI
    try:
        async with APIClient(neuro_config) as neuro_client:
            print("🔄 neuroAPI отвечает...")
            neuro_response = await neuro_client.chat_completion([
                {"role": "user", "content": test_question}
            ])
            print(f"🧠 neuroAPI (gpt-5): {neuro_response}")
    except Exception as e:
        print(f"❌ neuroAPI ошибка: {e}")
    
    print()
    
    # Тестируем OpenRouter
    try:
        async with APIClient(openrouter_config) as or_client:
            print("🔄 OpenRouter отвечает...")
            or_response = await or_client.chat_completion([
                {"role": "user", "content": test_question}
            ])
            print(f"🔄 OpenRouter (gpt-4o-mini): {or_response}")
    except Exception as e:
        print(f"❌ OpenRouter ошибка: {e}")

async def main():
    """Главная функция тестирования"""
    print("🚀 ТЕСТИРОВАНИЕ NEUROAPI ИНТЕГРАЦИИ")
    print("=" * 60)
    print()
    
    # Базовый тест
    basic_success = await test_neuroapi()
    
    if basic_success:
        print("\n" + "=" * 60)
        
        # Тест всех моделей
        all_models_success = await test_all_models()
        
        print("\n" + "=" * 60)
        
        # Сравнительный тест
        await test_vs_openrouter()
        
        print("\n" + "=" * 60)
        print("🎉 ТЕСТИРОВАНИЕ ЗАВЕРШЕНО!")
        
        if all_models_success:
            print("✅ Все тесты пройдены успешно!")
        else:
            print("⚠️ Некоторые тесты завершились с ошибками")
    else:
        print("\n❌ Базовый тест не пройден. Проверьте настройки API.")

if __name__ == "__main__":
    asyncio.run(main())
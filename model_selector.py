"""
Модуль для выбора модели при старте системы дебатов.
Позволяет пользователю выбрать единую модель для всех ролей
или использовать кастомные настройки из config.py
"""

import sys
from typing import Dict, Optional, Tuple
from dataclasses import replace
from config import Config, ModelConfig
from token_tracker import token_tracker


class ModelSelector:
    """Класс для интерактивного выбора модели"""
    
    def __init__(self):
        # Модели с ценами из token_tracker
        self.available_models = {
            "google/gemini-2.5-flash-lite-preview-06-17": "Gemini 2.5 Flash Lite (самая дешевая)",
            "google/gemini-2.5-flash": "Gemini 2.5 Flash (быстрая и дешевая)",
            "anthropic/claude-sonnet-4": "Claude Sonnet 4 (качественная)",
            "openai/gpt-4o-mini-2024-07-18": "GPT-4o Mini (экономичная)",
            "google/gemini-2.5-pro": "Gemini 2.5 Pro (продвинутая)",
            "openai/o3": "OpenAI o3 (новая)",
            "openai/gpt-4.1": "GPT-4.1 (стабильная)"
        }
        
        # Проверяем, что все модели есть в pricing
        self.pricing = token_tracker.pricing
    
    def show_model_menu(self) -> Tuple[bool, Optional[str]]:
        """
        Показывает меню выбора модели.
        
        Returns:
            Tuple[bool, Optional[str]]: (use_custom, selected_model)
            - use_custom: True если выбраны кастомные настройки
            - selected_model: ID выбранной модели или None для кастома
        """
        print("🤖 ВЫБОР МОДЕЛИ ДЛЯ ДЕБАТОВ")
        print("=" * 60)
        print()
        
        # Показываем доступные модели с ценами
        print("📋 Доступные модели (с ценами за 1K токенов):")
        print()
        
        model_options = []
        for i, (model_id, description) in enumerate(self.available_models.items(), 1):
            pricing = self.pricing.get(model_id, {"input": 0, "output": 0})
            input_cost = pricing["input"] * 1000  # переводим в USD за 1K токенов
            output_cost = pricing["output"] * 1000
            
            print(f"{i}. {description}")
            print(f"   Модель: {model_id}")
            print(f"   Цена: ${input_cost:.4f} (вход) / ${output_cost:.4f} (выход)")
            print()
            
            model_options.append(model_id)
        
        # Опция для кастомных настроек
        custom_option = len(model_options) + 1
        print(f"{custom_option}. Кастомные настройки (разные модели для разных ролей)")
        print("   Использует модели из config.py:")
        for role, model_config in Config.MODELS.items():
            print(f"   • {role}: {model_config.model_id}")
        print()
        
        # Запрашиваем выбор пользователя
        while True:
            try:
                choice = input(f"Выберите опцию (1-{custom_option}): ").strip()
                
                if not choice:
                    print("❌ Пожалуйста, введите номер опции")
                    continue
                
                choice_num = int(choice)
                
                if 1 <= choice_num <= len(model_options):
                    selected_model = model_options[choice_num - 1]
                    model_name = self.available_models[selected_model]
                    
                    print(f"✅ Выбрана модель: {model_name}")
                    print(f"   Все роли будут использовать: {selected_model}")
                    return False, selected_model
                
                elif choice_num == custom_option:
                    print("✅ Выбраны кастомные настройки")
                    print("   Каждая роль будет использовать свою модель из config.py")
                    return True, None
                
                else:
                    print(f"❌ Неверный выбор. Введите число от 1 до {custom_option}")
                    
            except ValueError:
                print("❌ Пожалуйста, введите число")
            except KeyboardInterrupt:
                print("\n👋 Выход из программы")
                sys.exit(0)
    
    def create_unified_config(self, model_id: str) -> Dict[str, ModelConfig]:
        """
        Создает конфигурацию, где все роли используют одну модель.
        
        Args:
            model_id: ID модели для всех ролей
            
        Returns:
            Dict[str, ModelConfig]: Обновленная конфигурация моделей
        """
        unified_models = {}
        
        # Базовые настройки температуры для разных ролей
        role_temperatures = {
            "gatekeeper": 0.3,      # Строгий для фильтрации
            "debater_pro": 0.8,     # Креативный для споров
            "debater_contra": 0.8,  # Креативный для споров
            "debater_alternative": 0.9,  # Самый креативный для альтернатив
            "judge": 0.4           # Объективный для судейства
        }
        
        # Создаем конфигурацию для каждой роли
        for role in Config.MODELS.keys():
            base_config = Config.MODELS[role]
            
            unified_models[role] = replace(
                base_config,
                model_id=model_id,
                temperature=role_temperatures.get(role, 0.7)
            )
        
        return unified_models
    
    def get_model_configuration(self) -> Dict[str, ModelConfig]:
        """
        Получает итоговую конфигурацию моделей на основе выбора пользователя.
        
        Returns:
            Dict[str, ModelConfig]: Конфигурация моделей для использования
        """
        use_custom, selected_model = self.show_model_menu()
        
        if use_custom:
            print("🔧 Используем кастомные настройки из config.py")
            return Config.MODELS
        else:
            print(f"🎯 Настраиваем все роли на модель: {selected_model}")
            return self.create_unified_config(selected_model)


def select_models() -> Dict[str, ModelConfig]:
    """
    Главная функция для выбора моделей при старте приложения.
    
    Returns:
        Dict[str, ModelConfig]: Выбранная конфигурация моделей
    """
    selector = ModelSelector()
    return selector.get_model_configuration()


if __name__ == "__main__":
    # Тестирование модуля
    print("🧪 Тестирование модуля выбора моделей")
    config = select_models()
    
    print("\n📊 Итоговая конфигурация:")
    for role, model_config in config.items():
        print(f"• {role}: {model_config.model_id} (temp: {model_config.temperature})")
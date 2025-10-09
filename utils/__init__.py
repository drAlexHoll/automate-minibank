"""
Test Utils Module
================

Утилиты для тестового фреймворка:
- API клиенты (базовый и расширенный)
- Хелперы для общих операций
- Генераторы тестовых данных
"""

try:
    # Попробуем относительные импорты для pytest
    from .api_client import MiniBankAPIClient, APIResponse
    from .helpers import (
        retry_on_failure,
        generate_random_string,
        generate_random_email,
        generate_random_phone,
        create_unique_user_data,
        create_unique_account_data,
        create_transfer_data
    )
except ImportError:
    # Используем абсолютные импорты для прямого использования
    from utils.api_client import MiniBankAPIClient, APIResponse
    from utils.helpers import (
        retry_on_failure,
        generate_random_string,
        generate_random_email,
        generate_random_phone,
        create_unique_user_data,
        create_unique_account_data,
        create_transfer_data
    )

__all__ = [
    # API Clients
    'MiniBankAPIClient',
    'APIResponse',
    
    # Helpers
    'retry_on_failure',
    'generate_random_string',
    'generate_random_email', 
    'generate_random_phone',
    'create_unique_user_data',
    'create_unique_account_data',
    'create_transfer_data'
] 
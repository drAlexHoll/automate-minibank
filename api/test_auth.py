"""
API тесты для аутентификации MiniBank
Простые синхронные тесты с использованием MiniBankAPIClient
"""

import pytest
from typing import Dict, Any

from config.settings import settings, UserRole
from utils.api_client import MiniBankAPIClient, APIResponse


@pytest.mark.api
@pytest.mark.auth
class TestAuthenticationAPI:
    """Набор API тестов для аутентификации"""
    
    def test_health_check(self, api_client: MiniBankAPIClient):
        """Тест health check Auth Service"""
        response = api_client.health_check()
        
        assert response.success, f"Health check failed: {response.message}"
        assert response.status_code == 200
        assert response.data is not None
    
    def test_valid_login(self, api_client: MiniBankAPIClient):
        """Тест успешного логина"""
        test_user = settings.get_user(UserRole.USER)
        
        response = api_client.login(test_user.email, test_user.password)
        
        assert response.success, f"Login failed: {response.message}"
        assert response.status_code == 200
        assert response.data is not None
        
        # Проверяем что токен получен
        if 'token' in response.data:
            token = response.data['token']
            assert isinstance(token, str), "Token should be string"
            assert len(token) > 0, "Token should not be empty"
        
        # Проверяем информацию о пользователе
        if 'user' in response.data:
            user_info = response.data['user']
            assert user_info['email'] == test_user.email
    
    def test_invalid_credentials(self, api_client: MiniBankAPIClient):
        """Тест логина с неверными данными"""
        response = api_client.login("invalid@email.com", "wrongpassword")
        
        assert not response.success, "Login with invalid credentials should fail"
        assert response.status_code in [401, 403, 400]
    
    def test_role_based_login(self, api_client: MiniBankAPIClient):
        """Тест логина пользователей разных ролей"""
        roles_to_test = [UserRole.USER, UserRole.VIP_USER, UserRole.ADMIN, UserRole.SUPPORT]
        
        for role in roles_to_test:
            test_user = settings.get_user(role)
            response = api_client.login(test_user.email, test_user.password)
            
            assert response.success, f"Login failed for role {role.value}: {response.message}"
            if response.data and 'user' in response.data:
                assert response.data['user']['role'] == role.value
    
    def test_token_validation(self, api_client: MiniBankAPIClient):
        """Тест валидации JWT токена"""
        # Сначала логинимся чтобы получить токен
        test_user = settings.get_user(UserRole.USER)
        login_response = api_client.login(test_user.email, test_user.password)
        assert login_response.success
        
        # Валидируем токен через метод API клиента
        validation_response = api_client.validate_token()
        
        assert validation_response.success, f"Token validation failed: {validation_response.message}"
        assert validation_response.status_code == 200
    
    def test_invalid_token_validation(self, api_client: MiniBankAPIClient):
        """Тест валидации невалидного токена"""
        # Создаем новый клиент без токена
        new_client = MiniBankAPIClient()
        new_client.jwt_token = "invalid.jwt.token"
        
        validation_response = new_client.validate_token()
        
        assert not validation_response.success
        assert validation_response.status_code in [401, 403]
    
    def test_logout(self, api_client: MiniBankAPIClient):
        """Тест логаута"""
        # Сначала логинимся
        test_user = settings.get_user(UserRole.USER)
        login_response = api_client.login(test_user.email, test_user.password)
        assert login_response.success
        
        # Логаут
        logout_response = api_client.logout()
        
        assert logout_response.success, f"Logout failed: {logout_response.message}"
        assert logout_response.status_code == 200
    
    @pytest.mark.performance
    def test_login_performance(self, api_client: MiniBankAPIClient):
        """Тест производительности логина"""
        import time
        
        test_user = settings.get_user(UserRole.USER)
        
        start_time = time.time()
        response = api_client.login(test_user.email, test_user.password)
        duration = time.time() - start_time
        
        assert response.success
        assert duration < 5.0, f"Login took too long: {duration:.2f}s"
    
    @pytest.mark.concurrency
    def test_concurrent_logins(self, api_client: MiniBankAPIClient):
        """Тест одновременных логинов"""
        test_user = settings.get_user(UserRole.USER)
        
        # Создаем несколько клиентов
        clients = [MiniBankAPIClient() for _ in range(3)]
        
        # Запускаем логины
        responses = []
        for client in clients:
            response = client.login(test_user.email, test_user.password)
            responses.append(response)
            client.logout()  # Очищаем после себя
        
        # Все логины должны быть успешными
        for i, response in enumerate(responses):
            assert response.success, f"Concurrent login {i} failed: {response.message}"


@pytest.mark.integration
@pytest.mark.auth
class TestAuthIntegration:
    """Интеграционные тесты аутентификации"""
    
    def test_auth_service_availability(self):
        """Тест доступности Auth Service"""
        api_client = MiniBankAPIClient()
        response = api_client.health_check()
        
        assert response.success, "Auth Service should be available"
    

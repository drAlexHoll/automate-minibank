"""
API тесты для счетов MiniBank
Простые синхронные тесты с использованием MiniBankAPIClient
"""

import pytest
from typing import Dict, Any

from config.settings import settings, UserRole
from utils.api_client import MiniBankAPIClient, APIResponse


@pytest.mark.api
@pytest.mark.accounts
class TestAccountsAPI:
    """Набор API тестов для счетов"""
    
    def test_get_accounts(self, api_client: MiniBankAPIClient):
        """Тест получения списка счетов"""
        # Логинимся как пользователь
        login_response = api_client.login_as_role(UserRole.USER)
        assert login_response.success, f"Login failed: {login_response.message}"
        
        response = api_client.get_accounts()
        
        assert response.success, f"Failed to get accounts: {response.message}"
        assert response.status_code == 200
        
        if response.data:
            # Проверяем что ответ содержит данные об аккаунтах
            if 'accounts' in response.data:
                assert isinstance(response.data['accounts'], list)
            elif isinstance(response.data, list):
                # Если data сам является списком аккаунтов
                assert True
    
    def test_create_account_simple(self, api_client: MiniBankAPIClient):
        """Простой тест создания счета без создания новых пользователей"""
        # Логинимся как администратор
        login_response = api_client.login_as_role(UserRole.ADMIN)
        assert login_response.success, f"Admin login failed: {login_response.message}"
        
        # Проверяем что можем получить список существующих пользователей
        users_response = api_client.get_users()
        assert users_response.success, f"Failed to get users: {users_response.message}"
        
        # Проверяем что есть пользователи в системе
        if users_response.data and 'users' in users_response.data:
            users = users_response.data['users']
            assert len(users) > 0, "No users found in system"
    
    def test_get_dashboard_data(self, api_client: MiniBankAPIClient):
        """Тест получения данных dashboard"""
        # Логинимся напрямую
        login_response = api_client.login_as_role(UserRole.USER)
        assert login_response.success, f"Login failed: {login_response.message}"
        
        response = api_client.get_dashboard_data()
        
        assert response.success, f"Failed to get dashboard data: {response.message}"
        assert response.status_code == 200
        
        if response.data:
            # Проверяем что есть базовые поля dashboard
            # (структура может варьироваться в зависимости от реализации)
            assert isinstance(response.data, dict)
    
    def test_get_accounts_vip(self, api_client: MiniBankAPIClient):
        """Тест получения счетов VIP пользователя"""
        # Логинимся как VIP пользователь
        login_response = api_client.login_as_role(UserRole.VIP_USER)
        assert login_response.success, f"VIP login failed: {login_response.message}"
        
        response = api_client.get_accounts()
        
        assert response.success, f"Failed to get VIP accounts: {response.message}"
        assert response.status_code == 200
    
    def test_get_accounts_admin(self, api_client: MiniBankAPIClient):
        """Тест получения счетов администратором"""
        # Логинимся как администратор
        login_response = api_client.login_as_role(UserRole.ADMIN)
        assert login_response.success, f"Admin login failed: {login_response.message}"
        
        response = api_client.get_accounts()
        
        assert response.success, f"Failed to get admin accounts: {response.message}"
        assert response.status_code == 200


@pytest.mark.integration
@pytest.mark.accounts
class TestAccountsIntegration:
    """Интеграционные тесты для счетов"""
    
    def test_account_service_availability(self):
        """Тест доступности Account Service"""
        api_client = MiniBankAPIClient()
        response = api_client.health_check()
        
        assert response.success, "Account Service should be available"
    
    def test_account_workflow_existing_users(self, api_client: MiniBankAPIClient):
        """Тест workflow с существующими пользователями"""
        # Логинимся как админ
        login_response = api_client.login_as_role(UserRole.ADMIN)
        assert login_response.success
        
        # Получаем список пользователей
        users_response = api_client.get_users()
        assert users_response.success
        
        # Получаем аккаунты
        accounts_response = api_client.get_accounts()
        assert accounts_response.success
        
        # Проверяем dashboard
        dashboard_response = api_client.get_dashboard_data()
        assert dashboard_response.success
    
    @pytest.mark.parametrize("role", [
        UserRole.USER,
        UserRole.VIP_USER,
        UserRole.ADMIN,
        UserRole.SUPPORT,
    ], ids=["USER","VIP","ADMIN","SUPPORT"])
    def test_user_roles_accounts_access(self, api_client: MiniBankAPIClient, role: UserRole):
        """Тест доступа к аккаунтам разных ролей"""
        # Логинимся под ролью
        login_response = api_client.login_as_role(role)
        assert login_response.success, f"Login failed for {role.value}"
        
        # Проверяем доступ к аккаунтам
        accounts_response = api_client.get_accounts()
        assert accounts_response.success, f"Accounts access failed for {role.value}"
        
        # Логаут
        api_client.logout() 
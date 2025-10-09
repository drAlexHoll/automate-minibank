"""
API тесты для переводов MiniBank
Простые синхронные тесты с использованием MiniBankAPIClient
"""

import pytest
from typing import Dict, Any
from decimal import Decimal

from config.settings import settings, UserRole
from utils.api_client import MiniBankAPIClient, APIResponse


@pytest.mark.api
@pytest.mark.transfers
class TestTransfersAPI:
    """Набор API тестов для переводов"""
    
    def test_get_transfer_limits(self, api_client: MiniBankAPIClient):
        """Тест получения лимитов переводов"""
        # Логинимся как пользователь
        login_response = api_client.login_as_role(UserRole.USER)
        assert login_response.success, f"Login failed: {login_response.message}"
        
        response = api_client.get_transfer_limits()
        
        assert response.success, f"Failed to get transfer limits: {response.message}"
        assert response.status_code == 200
        
        if response.data:
            # Проверяем что есть информация о лимитах
            # Структура может варьироваться в зависимости от реализации
            assert isinstance(response.data, dict)
    
    def test_get_transfers(self, api_client: MiniBankAPIClient):
        """Тест получения списка переводов"""
        # Логинимся как пользователь
        login_response = api_client.login_as_role(UserRole.USER)
        assert login_response.success, f"Login failed: {login_response.message}"
        
        response = api_client.get_transfers()
        
        assert response.success, f"Failed to get transfers: {response.message}"
        assert response.status_code == 200
        
        if response.data:
            # Проверяем что ответ содержит данные о переводах
            if 'transfers' in response.data:
                assert isinstance(response.data['transfers'], list)
            elif isinstance(response.data, list):
                # Если data сам является списком переводов
                assert True
    
    def test_transfers_admin_access(self, api_client: MiniBankAPIClient):
        """Тест доступа к переводам администратором"""
        # Логинимся как администратор
        login_response = api_client.login_as_role(UserRole.ADMIN)
        assert login_response.success, f"Admin login failed: {login_response.message}"
        
        response = api_client.get_transfers()
        
        assert response.success, f"Failed to get admin transfers: {response.message}"
        assert response.status_code == 200
    
    def test_transfers_vip_access(self, api_client: MiniBankAPIClient):
        """Тест доступа к переводам VIP пользователя"""
        # Логинимся как VIP пользователь
        login_response = api_client.login_as_role(UserRole.VIP_USER)
        assert login_response.success, f"VIP login failed: {login_response.message}"
        
        response = api_client.get_transfers()
        
        assert response.success, f"Failed to get VIP transfers: {response.message}"
        assert response.status_code == 200

    def test_create_internal_transfer_between_own_accounts(self, user_with_two_accounts, api_client: MiniBankAPIClient):
        """Тест создания внутреннего перевода между собственными счетами через API"""
        test_data = user_with_two_accounts
        credentials = test_data["credentials"]
        source_account = test_data["source_account"]
        target_account = test_data["target_account"]
        
        # Логинимся под тестовым пользователем
        login_response = api_client.login(credentials["email"], credentials["password"])
        assert login_response.success, f"Login failed: {login_response.message}"
        
        # Создаем перевод
        transfer_amount = 50
        transfer_data = {
            "fromAccountId": source_account["id"],
            "toAccountId": target_account["id"],
            "amount": transfer_amount,
            "description": "API Test: Internal transfer"
        }
        
        # Выполняем перевод
        response = api_client.create_transfer(transfer_data)
        assert response.success, f"Transfer failed: {response.message}"
        assert response.status_code == 201
        
        # Проверяем ключевые данные
        data = response.data
        transfer = data["transfer"]
        
        assert transfer["from_account_id"] == source_account["id"]
        assert transfer["to_account_id"] == target_account["id"] 
        assert float(transfer["amount"]) == transfer_amount
        assert transfer["status"] == "COMPLETED"
        assert "reference_number" in transfer
        assert transfer["reference_number"].startswith("TXN")
        
        # Проверяем комиссию для внутреннего перевода
        assert data["feeInfo"]["amount"] == 0
        assert data["feeInfo"]["type"] == "INTERNAL"
        
        # Проверяем что балансы обновились
        updated_balances = data["updatedBalances"]
        assert source_account["id"] in updated_balances
        assert target_account["id"] in updated_balances
        
        print(f"✅ Перевод выполнен: {transfer['reference_number']}, сумма: {transfer_amount}")


@pytest.mark.integration
@pytest.mark.transfers
class TestTransfersIntegration:
    """Интеграционные тесты для переводов"""
    
    def test_transfer_service_availability(self):
        """Тест доступности Transfer Service"""
        api_client = MiniBankAPIClient()
        response = api_client.health_check()
        
        assert response.success, "Transfer Service should be available"
    
    def test_transfer_workflow_existing_users(self, api_client: MiniBankAPIClient):
        """Тест workflow переводов с существующими пользователями"""
        # Логинимся как пользователь
        login_response = api_client.login_as_role(UserRole.USER)
        assert login_response.success
        
        # Получаем лимиты переводов
        limits_response = api_client.get_transfer_limits()
        assert limits_response.success
        
        # Получаем список переводов
        transfers_response = api_client.get_transfers()
        assert transfers_response.success
    
    @pytest.mark.parametrize("role", [
        UserRole.USER,
        UserRole.VIP_USER,
        UserRole.ADMIN,
        UserRole.SUPPORT,
    ], ids=["USER","VIP","ADMIN","SUPPORT"])
    def test_user_roles_transfers_access(self, api_client: MiniBankAPIClient, role: UserRole):
        """Тест доступа к переводам разных ролей"""
        # Логинимся под ролью
        login_response = api_client.login_as_role(role)
        assert login_response.success, f"Login failed for {role.value}"
        
        # Проверяем доступ к переводам
        transfers_response = api_client.get_transfers()
        assert transfers_response.success, f"Transfers access failed for {role.value}"
        
        # Проверяем доступ к лимитам
        limits_response = api_client.get_transfer_limits()
        assert limits_response.success, f"Transfer limits access failed for {role.value}"
        
        # Логаут
        api_client.logout() 
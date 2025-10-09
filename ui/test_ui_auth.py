"""
UI тесты аутентификации MiniBank
Логин и логаут через пользовательский интерфейс
"""

import pytest

from config.settings import settings, UserRole
from utils.api_client import MiniBankAPIClient
from ui.pages.login_page import LoginPage
from ui.pages.dashboard_page import DashboardPage


@pytest.mark.ui
@pytest.mark.auth
class TestUIAuthentication:
    """UI тесты аутентификации"""
    
    def test_successful_login(self, driver, api_client: MiniBankAPIClient):
        """Тест успешного логина пользователя через UI"""
        # Переходим на страницу логина
        login_page = LoginPage(driver)
        login_page.navigate_to()
        
        # Проверяем что страница загрузилась
        login_page.assert_page_loaded()
        
        # Логинимся как обычный пользователь
        test_user = settings.get_user(UserRole.USER)
        login_page.login(test_user.email, test_user.password)
        
        # Проверяем что попали на dashboard
        dashboard_page = DashboardPage(driver)
        dashboard_page.assert_page_loaded()
    

    def test_successful_logout(self, driver, api_client: MiniBankAPIClient):
        """Тест успешного логаута через UI"""
        # Сначала логинимся через UI
        login_page = LoginPage(driver)
        login_page.navigate_to()
        login_page.assert_page_loaded()
        
        test_user = settings.get_user(UserRole.USER)
        login_page.login(test_user.email, test_user.password)
        
        # Проверяем что попали на dashboard
        dashboard_page = DashboardPage(driver)
        dashboard_page.assert_page_loaded()
        
        # Выходим из системы
        dashboard_page.logout()
        
        # Проверяем что попали на страницу логина
        login_page.assert_page_loaded()
        
 

    def test_login_with_vip_user(self, driver):
        """Тест логина VIP пользователя"""
        login_page = LoginPage(driver)
        login_page.navigate_to()
        login_page.assert_page_loaded()
        
        vip_user = settings.get_user(UserRole.VIP_USER)
        login_page.login(vip_user.email, vip_user.password)
        
        dashboard_page = DashboardPage(driver)
        dashboard_page.assert_page_loaded()
        
        current_url = driver.current_url
        assert "dashboard" in current_url.lower(), f"VIP user not on dashboard: {current_url}" 
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


    def test_basic_login(self, driver):
        """Тест логина USER пользователя"""
        login_page = LoginPage(driver)
        login_page.navigate_to()
        login_page.assert_page_loaded()

        simple_user = settings.get_user(UserRole.USER)
        login_page.login(simple_user.email, simple_user.password)

        #Проверяем, что попали на Dashboard
        dashboard_page = DashboardPage(driver)
        dashboard_page.assert_page_loaded()

        #Проверяем, что URL верный
        current_url = driver.current_url
        assert "dashboard" in current_url.lower(), f"SIMPLE user not on dashboard: {current_url}"


    def test_login_logout_flow(self,driver, api_client: MiniBankAPIClient):
        """Тест логаута USER пользователя"""
        login_page = LoginPage(driver)
        login_page.navigate_to()
        login_page.assert_page_loaded()

        simple_user = settings.get_user(UserRole.USER)
        login_page.login(simple_user.email, simple_user.password)

        dashboard_page = DashboardPage(driver)
        dashboard_page.assert_page_loaded()

        current_url = driver.current_url
        assert "dashboard" in current_url.lower(), f"SIMPLE user not on dashboard: {current_url}"

        dashboard_page.logout()
        login_page.assert_page_loaded()
        login_url = driver.current_url
        assert "login" in login_url.lower(), f"SIMPLE user not on login: {login_url} page"


    def test_login_with_wrong_password(self, driver):
        """Тест с вводом невалидных данных при авторизации USER пользователя"""
        login_page = LoginPage(driver)
        login_page.navigate_to()
        login_page.assert_page_loaded()

        #Определяю USER пользователя
        simple_user = settings.get_user(UserRole.USER)
        login_page.enter_email(simple_user.email)

        #Добавляю неверные цифры к паролю
        login_page.enter_password(simple_user.password+"123")
        login_page.click_submit()

        #Проверяю, что всплывающее окно с ошибкой появилось на экране
        login_page.assert_error_visible()

        #Проверяю, что мы остались на странице Login
        assert "login" in login_page.get_page_title().lower(), f"SIMPLE user not on login: {login_page.get_page_title()} page"
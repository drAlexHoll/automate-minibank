"""
Страница входа для автотестов MiniBank
Реализует действия и проверки экрана аутентификации

Структура:
- Селекторы страницы (data-testid для стабильности)
- Реализация абстрактных методов BasePage (загрузка/заголовок)
- Действия высокого уровня (login / ввод полей)
- Проверки состояния (ошибка/отсутствие ошибки)
"""

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from typing import Optional
import structlog

from .base_page import BasePage

logger = structlog.get_logger(__name__)


class LoginPage(BasePage):
    """Объект страницы входа"""

    def __init__(self, driver: webdriver.Remote):
        super().__init__(driver)

        # Селекторы элементов страницы
        self.selectors = {
            "login_form": '[data-testid="login-form"]',
            "email_input": '[data-testid="email-input"]',
            "password_input": '[data-testid="password-input"]',
            "submit_button": '[data-testid="submit-button"]',
            "error_message": '[data-testid="error-message"]',
            "loading_indicator": '[data-testid="loading-indicator"]'
        }

    # ---------------------------------------------------------------------
    # Реализация абстрактных методов
    # ---------------------------------------------------------------------
    def is_loaded(self) -> bool:
        """Проверяет загружена ли страница входа"""
        return self.is_element_immediately_visible(self.selectors["login_form"])

    def wait_until_loaded(self) -> None:
        """Ожидает полной загрузки страницы входа"""
        self.wait_for_element(self.selectors["login_form"])

    def get_page_title(self) -> str:
        return "Login"

    # ---------------------------------------------------------------------
    # Действия на странице
    # ---------------------------------------------------------------------
    def enter_email(self, email: str) -> None:
        """Вводит email в поле ввода"""
        self.fill_input(self.selectors["email_input"], email)

    def enter_password(self, password: str) -> None:
        """Вводит пароль в поле ввода"""
        self.fill_input(self.selectors["password_input"], password)

    def click_submit(self) -> None:
        """Нажимает кнопку входа и ожидает смены URL"""
        current_url = self.driver.current_url
        self.click_element(self.selectors["submit_button"])
        
        # Ждем смены URL (успешный логин)
        try:
            self.wait_for_url_change(current_url)
        except TimeoutException:
            # Проверяем может есть ошибка логина
            if self.is_element_immediately_visible(self.selectors["error_message"]):
                self.logger.warning("Login failed - error message visible")
            else:
                self.logger.warning("URL did not change after login attempt")

    def login(self, email: str, password: str) -> None:
        """Выполняет полную последовательность входа"""
        self.logger.info(f"Logging in with user: {email}")
        self.enter_email(email)
        self.enter_password(password)
        self.click_submit()

    # ---------------------------------------------------------------------
    # Проверки состояния
    # ---------------------------------------------------------------------
    def assert_error_visible(self, message: Optional[str] = None) -> None:
        """Ожидает появления ошибки, затем проверяет её"""
        self.wait_for_element(self.selectors["error_message"])
        
        if message:
            element = self.find_element(self.selectors["error_message"])
            actual_text = element.text
            assert message in actual_text, f"Expected error message '{message}' not found in '{actual_text}'"
        self.logger.info("Login error displayed as expected")

    def assert_no_error(self) -> None:
        """Проверяет отсутствие ошибки на странице"""
        assert not self.is_element_immediately_visible(self.selectors["error_message"]), "Unexpected error message visible" 
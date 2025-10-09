"""
Страница дашборда для автотестов MiniBank
Обеспечивает навигацию по разделам и базовые проверки состояния

Структура:
- Селекторы ключевых элементов (greeting, overview, balances)
- Реализация абстрактных методов BasePage (загрузка)
- Методы навигации по тексту кнопок
- Вспомогательные проверки (балансы, ошибки)
"""

from selenium import webdriver
from typing import Optional
import structlog
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from .base_page import BasePage

logger = structlog.get_logger(__name__)


class DashboardPage(BasePage):
    """Объект страницы дашборда"""

    def __init__(self, driver: webdriver.Remote):
        super().__init__(driver)

        # Селекторы элементов страницы
        self.selectors.update({
            "overview_section": '[data-testid="dashboard-overview"]',
            "greeting": '[data-testid="dashboard-greeting"]',
            "error": '[data-testid="dashboard-error"]',
            "loading": '[data-testid="dashboard-loading"]',
            "content_grid": '[data-testid="dashboard-content"]',
            "total_balance_card": '[data-testid="total-balance-card"]',
            "total_balance_amount": '[data-testid="total-balance-amount"]',
            "checking_balance": '[data-testid="checking-balance"]',
            "savings_balance": '[data-testid="savings-balance"]',
            "accounts_count": '[data-testid="accounts-count"]',
        })

    # ------------------------------------------------------------------
    # Реализация абстрактных методов
    # ------------------------------------------------------------------
    def is_loaded(self) -> bool:
        """Быстрая проверка загрузки дашборда"""
        dashboard_indicators = [
            '[data-testid="dashboard-overview"]',
            '[data-testid="dashboard-greeting"]', 
            'nav',
            'main'
        ]
        for indicator in dashboard_indicators:
            if self.is_element_immediately_visible(indicator):
                return True
        return False

    def wait_until_loaded(self) -> None:
        """Ожидает полной загрузки дашборда"""
        self.wait_for_element(self.selectors["greeting"])

    def get_page_title(self) -> str:
        return "Dashboard"

    # ------------------------------------------------------------------
    # Методы навигации (по тексту кнопок)
    # ------------------------------------------------------------------
    def open_overview(self):
        self.click_element_by_text("button", "Overview")

    def open_accounts(self):
        self.click_element_by_text("button", "Accounts")

    def open_transfers(self):
        self.click_element_by_text("button", "Transfers")

    def open_transactions(self):
        self.click_element_by_text("button", "History")

    def open_notifications(self):
        self.click_element_by_text("button", "Notifications")

    def open_users(self):
        self.click_element_by_text("button", "Users")

    def logout(self):
        # На больших экранах текст 'Logout', на маленьких — символ стрелки
        try:
            self.click_element_by_text("button", "Logout", partial=False)
        except Exception:
            self.click_element_by_text("button", "↗")

    # ------------------------------------------------------------------
    # Вспомогательные проверки
    # ------------------------------------------------------------------
    def assert_section_loaded(self, section_key: str):
        """Проверяет загрузку секции дашборда"""
        assert self.is_element_visible(self.selectors[section_key]), f"Section {section_key} not visible"

    def get_total_balance(self) -> str:
        """Получает общий баланс"""
        return self.get_text(self.selectors["total_balance_amount"])

    def get_accounts_count(self) -> int:
        """Получает количество счетов"""
        count_text = self.get_text(self.selectors["accounts_count"])
        try:
            return int(count_text.split()[-1])
        except ValueError:
            return 0

    def has_error(self) -> bool:
        """Проверяет наличие ошибки на дашборде"""
        return self.is_element_visible(self.selectors["error"]) 
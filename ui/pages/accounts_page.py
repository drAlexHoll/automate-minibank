"""
Страница счетов для автотестов MiniBank
Обрабатывает действия по управлению счетами
"""

from typing import List

import structlog
from selenium import webdriver

from .base_page import BasePage

logger = structlog.get_logger(__name__)


class AccountsPage(BasePage):
    """Объект страницы счетов"""

    def __init__(self, driver: webdriver.Remote):
        super().__init__(driver)

        # Селекторы элементов страницы
        self.selectors.update({
            "page_title": 'h2',
            "create_button": '[data-testid="create-account-button"]',
            "create_form": '[data-testid="create-account-form"]',
            "user_select": '[data-testid="user-select"]',
            "account_type_select": '[data-testid="account-type-select"]',
            "initial_balance_input": '[data-testid="initial-balance-input"]',
            "submit_create": '[data-testid="submit-create-account"]',
            "cancel_create": '[data-testid="cancel-create-account"]',
            "accounts_grid": '[data-testid="accounts-grid"]',
            "account_card": '[data-testid^="account-card-"]',
            "details_button": '[data-testid^="details-button-"]',
            "delete_button": '[data-testid^="delete-button-"]',
            "no_accounts": '[data-testid="no-accounts-message"]',
            "error_message": '[data-testid="error-message"]'
        })

    # --------------------------------------------------------------------
    # Реализация абстрактных методов
    # --------------------------------------------------------------------
    def is_loaded(self) -> bool:
        """Проверяет загружена ли страница счетов"""
        return self.is_element_immediately_visible(self.selectors["page_title"])

    def wait_until_loaded(self) -> None:
        """Ожидает полной загрузки страницы счетов"""
        self.wait_for_element(self.selectors["page_title"])

    def get_page_title(self) -> str:
        return "Accounts"

    # --------------------------------------------------------------------
    # Действия на странице
    # --------------------------------------------------------------------
    def open_create_form(self):
        """Открывает форму создания счета"""
        self.click_element(self.selectors["create_button"])
        self.wait_for_element(self.selectors["create_form"])

    def create_account(self, account_type: str = "CHECKING", initial_balance: float = 0.0, user_id: str = None):
        """Создает новый счет"""
        self.open_create_form()

        # Выбираем пользователя если админ
        if user_id and self.is_element_visible(self.selectors["user_select"], timeout=1):
            self.select_option(self.selectors["user_select"], user_id)

        # Выбираем тип счета
        self.select_option(self.selectors["account_type_select"], account_type)

        # Заполняем начальный баланс если поле видимо
        if initial_balance > 0 and self.is_element_visible(self.selectors["initial_balance_input"], timeout=1):
            self.fill_input(self.selectors["initial_balance_input"], str(initial_balance))

        self.click_element(self.selectors["submit_create"])
        self.wait_for_loading_to_complete()

    def submit_create(self):
        """Создание счета"""
        self.click_element(self.selectors["submit_create"])

    def cancel_create(self):
        """Отменяет создание счета"""
        self.click_element(self.selectors["cancel_create"])

    def get_account_cards(self) -> List[str]:
        """Получает текстовое содержимое всех карточек счетов"""
        cards = self.find_elements(self.selectors["account_card"])
        return [card.text for card in cards]

    def get_account_cards_count(self) -> int:
        """Возвращает количество карточек счетов на странице"""
        return len(self.find_elements(self.selectors["account_card"]))

    def get_account_cards_numbers(self) -> List[str]:
        """Возвращаем список номеров счетов из карточек"""
        account_cards = self.get_account_cards()
        account_numbers = []

        for text in account_cards:
            lines = [line.strip() for line in text.split("\n") if line.strip()]

            possible_numbers = [line for line in lines if line.replace(" ", "").isdigit()]
            if len(possible_numbers):
                account_numbers.append(possible_numbers[0])

        return account_numbers

    def get_newest_account_number(self) -> str:
        """Получает номер последнего созданного счёта"""
        account_numbers = self.get_account_cards_numbers()
        if not account_numbers:
            raise ValueError("Не найдено ни одного счета на странице")
        return account_numbers[0]

    def delete_account(self, account_id: str):
        """Удаляет счет по ID"""
        delete_selector = f'[data-testid="delete-button-{account_id}"]'
        self.click_element(delete_selector)
        self.handle_alert(True)
        self.wait_for_loading_to_complete()

    def show_details(self, account_id: str):
        """Показывает детали конкретного счета"""
        details_selector = f'[data-testid="details-button-{account_id}"]'
        self.click_element(details_selector)
        self.wait_for_loading_to_complete()

    # --------------------------------------------------------------------
    # Проверки состояния
    # --------------------------------------------------------------------
    def assert_account_exists(self, account_id: str):
        """Проверяет существование счета с заданным ID"""
        account_selector = f'[data-testid="account-card-{account_id}"]'
        assert self.is_element_visible(account_selector), f"Account {account_id} not found"

    def assert_no_accounts(self):
        """Проверяет отображение сообщения об отсутствии счетов"""
        assert self.is_element_visible(self.selectors["no_accounts"]), "Expected no accounts message"

    def assert_error_message(self, message: str = None):
        """Проверяет отображение сообщения об ошибке"""
        assert self.is_element_visible(self.selectors["error_message"]), "Error message not visible"

        if message:
            error_text = self.get_text(self.selectors["error_message"])
            assert message in error_text, f"Expected '{message}' in error text '{error_text}'"

    def assert_create_button(self):
        """Проверяет видимость кнопки создания нового счет"""
        assert self.is_element_visible(self.selectors["create_button"]), "Expected create button not visible"

    def assert_user_select_visible(self):
        """Проверяет видимость поля для выбора пользователя"""
        assert self.is_element_immediately_visible(self.selectors["user_select"]), "Expected user select visible"

    def assert_user_select_not_visible(self):
        """Проверяет, что у пользователя нет видимости поля для выбора пользователя"""
        assert not self.is_element_immediately_visible(
            self.selectors["user_select"]), "Expected user select not visible"

    def assert_user_initial_balance_visible(self):
        """Проверяет видимость поля для установки начального баланса"""
        assert self.is_element_immediately_visible(
            self.selectors["initial_balance_input"]), "Expected user initial_balance_input visible"

    def assert_user_initial_balance_not_visible(self):
        """Проверяет, что у пользователя нет видимости поля установки начального баланса"""
        assert not self.is_element_immediately_visible(
            self.selectors["initial_balance_input"]), "Expected user initial_balance_input not visible"

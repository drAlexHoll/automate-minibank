"""
Страница управление пользователями для автотестов MiniBank

"""

from typing import List

import structlog
from selenium import webdriver

from .base_page import BasePage

logger = structlog.get_logger(__name__)


class UsersPage(BasePage):
    """Объект страницы управления пользователями"""

    def __init__(self, driver: webdriver.Remote):
        super().__init__(driver)

        # Селекторы элементов страницы
        self.selectors.update({
            "page_title": '//h1[normalize-space()="User Management"]',
            "table": "//div[div[normalize-space()='Name']]/parent::div",

            "create_button": '//button[normalize-space()="+ Create User"]',
            "cancel_create_button": '//button[normalize-space()="Cancel"]',
            "create_user_button": '//button[normalize-space()="Create User"]',
            "update_button": '//button[normalize-space()="Update User"]',
            "edit_button_by_email": "//div[./div[normalize-space()='{email}']]//button[normalize-space()='Edit']",

            "create_form": '//h2[normalize-space()="Create New User"]',
            "create_form_title": 'h2',

            "first_name_input": '[name="firstName"]',
            "last_name_input": '[name="lastName"]',
            "email_input": '[name="email"]',
            "password_input": '[name="password"]',

            "role_select": '[name="role"]',
        })

    # --------------------------------------------------------------------
    # Реализация абстрактных методов
    # --------------------------------------------------------------------

    def is_loaded(self) -> bool:
        """Проверяет загружена ли страница управление пользователями"""
        return self.is_element_immediately_visible(self.selectors["page_title"])

    def wait_until_loaded(self) -> None:
        """Ожидает полной загрузки страницы управления пользователями"""
        self.wait_for_element(self.selectors["table"])

    def wait_until_form_create_closed(self):
        """Ждем, когда форма создания пользователя закроется"""
        self.wait_for_condition(
            lambda: not self.is_element_immediately_visible(self.selectors["create_form"]),
            timeout=1)

    def get_page_title(self) -> str:
        """Получение заголовка страницы"""
        return self.get_text(self.selectors["page_title"])

    def _get_users(self) -> list[dict]:
        """Получение всех пользователей из таблицы"""
        return self.get_div_table_data(self.selectors["table"])

    # --------------------------------------------------------------------
    # Действия на странице
    # --------------------------------------------------------------------

    def get_all_users(self) -> List[dict]:
        """Возвращает всех пользователей в таблице"""
        return self._get_users()

    def find_user_by_email(self, email: str) -> dict:
        """Поиск пользователя в таблице по Email"""
        users = self._get_users()
        for user in users:
            if user.get("Email") == email:
                return user
        return None

    def open_create_form(self):
        """Открывает форму создания пользователя"""
        self.click_element(self.selectors["create_button"])
        self.wait_for_element(self.selectors["create_form_title"])

    def create_new_user(self, user_data: dict, user_role: str) -> None:
        """Создание нового пользователя"""
        self.open_create_form()

        self.fill_input(self.selectors["first_name_input"], user_data["firstName"])
        self.fill_input(self.selectors["last_name_input"], user_data["lastName"])
        self.fill_input(self.selectors["email_input"], user_data["email"])
        self.fill_input(self.selectors["password_input"], user_data["password"])

        self.select_option(self.selectors["role_select"], user_role)
        self.submit_create_new_user()
        self.wait_until_form_create_closed()

    def submit_create_new_user(self):
        """Подтверждение создания нового пользователя"""
        self.click_element(self.selectors["create_user_button"])

    def submit_update_user(self):
        """Подтверждение обновления данных у пользователя"""
        self.click_element(self.selectors["update_button"])

    def cancel_create_new_user(self):
        """Отмена создания нового пользователя"""
        self.click_element(self.selectors["cancel_create_button"])

    def open_edit_button_for_email(self, email: str) -> None:
        """Открываем кнопку Edit у конкретного пользователя"""
        self.click_element(self.selectors["edit_button_by_email"].format(email=email))
        self.wait_for_element(self.selectors["update_button"])

    # --------------------------------------------------------------------
    # Проверки состояния
    # --------------------------------------------------------------------

    def assert_has_users(self) -> None:
        """Проверяет есть ли в таблице хотя бы один пользователь"""
        users = self._get_users()
        assert len(users) > 0, "В таблице нет ни одного пользователя"

    # --------------------------------------------------------------------
    # Валидация формы
    # --------------------------------------------------------------------

    def get_required_fields_validation_messages(self) -> dict:
        """Возвращает сообщения валидации для всех обязательных полей"""

        required_inputs = [
            self.selectors["first_name_input"],
            self.selectors["last_name_input"],
            self.selectors["email_input"],
            self.selectors["password_input"],
        ]

        messages = {}
        for locator in required_inputs:
            msg = self.get_attribute(locator, "validationMessage")
            if msg:
                messages[locator] = msg.strip()
        return messages

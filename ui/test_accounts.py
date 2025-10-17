"""
UI тесты для раздела со счетами пользователей

"""

import pytest
from config.settings import settings, UserRole
from ui.pages.accounts_page import AccountsPage
from ui.pages.dashboard_page import DashboardPage
from ui.pages.login_page import LoginPage
from utils.api_client import MiniBankAPIClient


@pytest.mark.ui
@pytest.mark.accounts
class TestUIAccounts:
    """UI тесты для раздела со счетами (account_page)"""

    def test_view_user_accounts(self, driver, login_as):
        """Тест просмотра счетов пользователя (USER)"""

        # Авторизуемся за пользователя USER
        auth_as_user = login_as(UserRole.USER)

        # Открываем вкладку 💳 Accounts
        auth_as_user.open_accounts()

        account_page = AccountsPage(driver)
        account_page.assert_page_loaded()

        # Определяем в переменную все счета пользователя
        accounts = account_page.get_account_cards()

        # Проверяем, что количество счетов больше 0
        assert len(accounts) > 0, "У пользователя нет ни одного счета"

        # Выводим информацию по первому счету
        print(f"Первый счет: {accounts[0]}")

    def test_user_account_permissions(self, driver, login_as, api_client):
        """Проверка прав для пользователя USER"""
        # Авторизуемся за пользователя USER
        auth_as_user = login_as(UserRole.USER)

        # Открываем вкладку 💳 Accounts
        auth_as_user.open_accounts()

        account_page = AccountsPage(driver)
        account_page.assert_page_loaded()

        # Проверяем, что кнопка есть кнопка создания счетов
        account_page.assert_create_button()

        # Получаю из UI номера счетов
        accounts = account_page.get_account_cards()
        accounts_numbers = [line.split("\n")[2].strip() for line in
                            accounts]  # Использую листкомпрехеншинс, где забираю из полученного ответа только номера счетов

        # Получаю из API все счета пользователя
        api_client.login_as_role(UserRole.USER)
        api_get_accounts = api_client.get_accounts().data["accounts"]
        api_account_numbers = [account["account_number"] for account in api_get_accounts]

        # Проверяем, что видны только собственные счета
        for account in accounts_numbers:
            assert account in api_account_numbers, f"У пользователя есть чужой счет {account}"

        # Открываю форму создания счета
        account_page.open_create_form()

        # Проверяем, что в форме НЕТ поля выбора пользователя
        account_page.assert_user_select_no_visible()

        # Проверяем, что в форме НЕТ поля установки начального баланса
        account_page.assert_user_initial_balance_no_visible()

    def test_admin_account_permissions(self, driver, login_as):
        """Проверка прав для пользователя ADMIN"""
        # Авторизуемся за пользователя USER
        auth_as_admin = login_as(UserRole.ADMIN)

        # Открываем вкладку 💳 Accounts
        auth_as_admin.open_accounts()

        account_page = AccountsPage(driver)
        account_page.assert_page_loaded()

        # Проверяем, что кнопка есть кнопка создания счетов
        account_page.assert_create_button()

        # Открываю форму создания счета
        account_page.open_create_form()

        # Проверяем, что в форме ЕСТЬ поля выбора пользователя
        account_page.assert_user_select_visible()

        # Проверяем, что в форме ЕСТЬ поля установки начального баланса
        account_page.assert_user_initial_balance_visible()

        # Закрываем форму создания счета
        account_page.cancel_create()

    def test_create_basic_account(self, driver, logged_in_admin, login_as):
        """Проверка создания счета пользователем ADMIN"""

        # Авторизуемся за пользователя ADMIN
        auth_as_admin = login_as(UserRole.ADMIN)
        auth_as_admin.open_accounts()

        # Открываем вкладку 💳 Accounts
        account_page = AccountsPage(driver)
        account_page.assert_page_loaded()

        # Узнаем, сколько счетов было ДО создания нового счета
        accounts_before_create = len(account_page.find_elements(account_page.selectors["account_card"]))

        # Заполняем данные счета и создаем
        account_page.create_account(
            account_type="CHECKING",
            initial_balance=333,
            user_id=logged_in_admin["id"]
        )

        # Узнаем, сколько стало счетов ПОСЛЕ создания счета
        account_page.wait_for_element_count(account_page.selectors["account_card"], accounts_before_create + 1)
        accounts_after_create = len(account_page.find_elements(account_page.selectors["account_card"]))

        # Проверяем, что счет создался
        assert accounts_after_create == accounts_before_create + 1, "Новый счет не создался"

        # Забираем account_card нового счёта
        get_all_accounts_card = account_page.get_account_cards()
        split_to_only_cards_numbers = [line.split("\n")[4].strip() for line in
                                       get_all_accounts_card]  # Использую листкомпрехеншинс, где забираю из полученного ответа только номера счетов
        new_cards_number = split_to_only_cards_numbers[0]  # Забираю account_card_number с нового созданного счета

        # Обновляем страницу
        account_page.refresh_page()

        # Открываем вкладку 💳 Accounts
        auth_as_admin.open_accounts()

        # Проверяем, что новый счет есть среди остальных

        assert new_cards_number in split_to_only_cards_numbers, f"Счет {new_cards_number[0]} не найден в UI"

    def test_create_basic_account_api(self, driver, logged_in_admin, login_as, make_account_for_user):
        """Проверка, что счёт, созданный через API отображается в UI"""

        # Подготовка данных через фикстуру make_account_for_user
        created_new_account = make_account_for_user(user_id=logged_in_admin["id"], initial_balance=222,
                                                    account_type="SAVINGS")
        account_number = created_new_account["account"]["account_number"]

        # Авторизуемся за пользователя ADMIN
        auth_as_admin = login_as(UserRole.ADMIN)
        auth_as_admin.open_accounts()

        account_page = AccountsPage(driver)
        account_page.assert_page_loaded()

        # Проверяем, через UI что счет создался
        get_all_accounts_card = account_page.get_account_cards()
        assert any(account_number in card for card in get_all_accounts_card), f"Счет {account_number} не найден в UI"

    def test_create_account_with_empty_fields(self, driver, login_as, logged_in_admin):
        """Проверка создания счета с пустыми полями"""

        # Авторизуемся за пользователя ADMIN
        auth_as_admin = login_as(UserRole.ADMIN)
        auth_as_admin.open_accounts()

        # Открываем вкладку 💳 Accounts
        account_page = AccountsPage(driver)
        account_page.assert_page_loaded()

        # Узнаем, сколько счетов было ДО создания нового счета
        accounts_before_create = len(account_page.find_elements(account_page.selectors["account_card"]))

        # Заполняем данные счета
        account_page.open_create_form()

        # Нажимаем кнопку создать счет
        account_page.submit_create()

        # Получаем локатор поля выбора пользователя
        user_select = account_page.selectors["user_select"]

        # Считываем нативное сообщение браузера о валидации (если поле не заполнено)
        message = account_page.get_attribute(user_select, "validationMessage")

        # Проверяем, что сообщение о валидации появилось
        assert message and message.strip() != "", "Ожидается сообщение о необходимости выбрать пользователя"

        # Проверяем, что количество счетов не изменилось
        accounts_after_create = len(account_page.find_elements(account_page.selectors["account_card"]))
        assert accounts_after_create == accounts_before_create, f"Количество счетов изменилось: было {accounts_after_create}, стало {accounts_before_create}"

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

    def test_view_accounts_roles(self, driver, account_page_as_role, role):
        """Тест просмотра счетов ролей"""

        account_page = account_page_as_role
        accounts = account_page.get_account_cards()

        # Проверяем, что количество счетов больше 0
        assert accounts, f"Для роли {role.value} не отображаются счета"
        print(f"[{role.value}] Первый счет: {accounts[0]}")

    @pytest.mark.parametrize(
        "role, expect_user_select, expect_initial_balance",
        [
            (UserRole.ADMIN, True, True),
            (UserRole.USER, False, False),
            (UserRole.VIP_USER, False, False),
            (UserRole.SUPPORT, True, True),
        ],
        ids=[
            "ADMIN", "USER", "VIP_USER", "SUPPORT",
        ]
    )
    def test_user_account_permissions(self, driver, api_client, account_page_as_role, role, expect_user_select,
                                      expect_initial_balance):
        """Проверка прав для пользователя USER"""

        account_page = account_page_as_role

        # Получаю из UI номера счетов
        accounts_numbers = account_page.get_account_cards_numbers()

        # Получаю из API все счета пользователя
        api_client.login_as_role(role)
        api_get_accounts = api_client.get_accounts().data["accounts"]
        api_account_numbers = [account["account_number"] for account in api_get_accounts]

        # Проверяем, что видны только собственные счета
        for account in accounts_numbers:
            assert account in api_account_numbers, f"У пользователя есть чужой счет {account}"

        # Открываю форму создания счета
        account_page.open_create_form()

        # Проверяем видимость полей
        if expect_user_select:
            account_page.assert_user_select_visible()
        else:
            account_page.assert_user_select_not_visible()

        if expect_initial_balance:
            account_page.assert_user_initial_balance_visible()
        else:
            account_page.assert_user_initial_balance_not_visible()

    def test_create_basic_account(self, driver, logged_in_admin, login_as, checking_account_data):
        """Проверка создания счета пользователем ADMIN"""

        # Авторизуемся за пользователя ADMIN
        auth_as_admin = login_as(UserRole.ADMIN)
        auth_as_admin.open_accounts()

        # Открываем вкладку 💳 Account
        account_page = AccountsPage(driver)
        account_page.assert_page_loaded()

        # Узнаем, сколько счетов было ДО создания нового счета
        accounts_before_create = account_page.get_account_cards_count()

        # Заполняем данные счета и создаем
        account_page.create_account(**checking_account_data, user_id=logged_in_admin["id"])

        # Узнаем, сколько стало счетов ПОСЛЕ создания счета
        account_page.wait_for_element_count(account_page.selectors["account_card"], accounts_before_create + 1)
        accounts_after_create = account_page.get_account_cards_count()

        # Проверяем, что счет создался
        assert accounts_after_create == accounts_before_create + 1, "Новый счет не создался"

        # Забираем account_card нового счёта
        numbers = account_page.get_account_cards_numbers()
        new_cards_number = account_page.get_newest_account_number()

        # Обновляем страницу
        account_page.refresh_page()

        # Открываем вкладку 💳 Accounts
        auth_as_admin.open_accounts()

        # Проверяем, что новый счет есть среди остальных
        assert new_cards_number in numbers, f"Счет {new_cards_number} не найден в UI"

    def test_create_basic_account_api(self, driver, logged_in_admin, login_as, make_account_for_user,
                                      savings_account_data):
        """Проверка, что счёт, созданный через API отображается в UI"""

        # Подготовка данных через фикстуру make_account_for_user
        created_new_account = make_account_for_user(user_id=logged_in_admin["id"], **savings_account_data)
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
        accounts_before_create = account_page.get_account_cards_count()

        account_page.open_create_form()
        account_page.submit_create()

        # Получаем локатор поля выбора пользователя
        user_select = account_page.selectors["user_select"]

        # Считываем нативное сообщение браузера о валидации (если поле не заполнено)
        message = account_page.get_attribute(user_select, "validationMessage")

        # Проверяем, что сообщение о валидации появилось
        assert message and message.strip() != "", "Ожидается сообщение о необходимости выбрать пользователя"

        # Проверяем, что количество счетов не изменилось
        accounts_after_create = account_page.get_account_cards_count()
        assert accounts_after_create == accounts_before_create, f"Количество счетов изменилось: было {accounts_after_create}, стало {accounts_before_create}"

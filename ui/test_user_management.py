"""
UI тесты

"""

import pytest
import structlog
from config.settings import settings, UserRole
from ui.pages.dashboard_page import DashboardPage
from ui.pages.login_page import LoginPage
from ui.pages.users_page import UsersPage
from utils.api_client import MiniBankAPIClient
from utils.helpers import create_unique_user_data as create_user_data

logger = structlog.get_logger(__name__)


@pytest.mark.ui
@pytest.mark.users_management
class TestUsersManagement:
    """UI тесты для раздела управления пользователями (users)"""

    def test_admin_can_view_users(self, driver, open_user_page_as_admin):
        """Проверка, что администратор может просматривать список пользователей"""

        user_page = open_user_page_as_admin
        user_page.assert_has_users()
        user_count = len(user_page.get_all_users())
        logger.info("User count on page", count=user_count)

    @pytest.mark.parametrize(
        "role",
        [
            "ADMIN",
            "USER",
            "VIP_USER",
            "SUPPORT",
        ],
        ids=[
            "Create ADMIN account",
            "Create USER account",
            "Create VIP_USER account",
            "Create SUPPORT account",
        ]
    )
    def test_create_basic_user(self, driver, open_user_page_as_admin, role, api_client, user_teardown):
        """Создание пользователя под админом"""

        user_page = open_user_page_as_admin
        user_data = create_user_data()
        user_page.create_new_user(user_data, role)

        # Записываем созданный email для последующего удаления
        user_teardown["email"] = user_data["email"]

        # Находим пользователя в списке пользователей
        assert user_page.find_user_by_email(user_data['email']), f"В таблице нет пользователя: {user_data['email']}"

        # Удостоверяемся через back, что пользователь создался в системе
        login_response = api_client.login(email=user_data['email'], password=user_data['password'])
        assert login_response.status_code == 200, f"Не удалось авторизоваться под пользователем: {user_data['email']} / {user_data['password']}\n Статус: {login_response.status_code}"

    @pytest.mark.parametrize(
        "role, expected"
        , [
            (UserRole.ADMIN, True),
            (UserRole.USER, False),
            (UserRole.SUPPORT, True),
            (UserRole.VIP_USER, False)
        ],
        ids=[
            "Check ADMIN role",
            "Check USER role",
            "Check SUPPORT role",
            "Check VIP_USER role"
        ]
    )
    def test_user_management_button_visibility_by_role(self, driver, login_as, role, expected):
        """Проверяем различные роли на наличие кнопки Users"""
        user = login_as(role)

        actual_visibility = user.has_button_user_management()
        assert actual_visibility == expected, f"Для роли {role.value} ожидалось видимость кнопки Users: {expected}, но получено: {actual_visibility}"

    def test_create_new_user_without_data(self, driver, open_user_page_as_admin):
        """Создание пользователя без заполнения данных"""

        user_page = open_user_page_as_admin
        user_page.open_create_form()
        user_page.submit_create_new_user()

        message_input = user_page.get_required_fields_validation_messages()

        assert message_input, "Ожидалось сообщение о валидации обязательных полей"
        assert user_page.is_element_visible(
            user_page.selectors["create_form"]), "Форма создания пользователя закрылась, хотя поля не заполнены"

    def test_create_and_edit_user(self, driver, open_user_page_as_admin, user_teardown):
        """Создание пользователя и изменение информации через UI кнопку Edit"""
        user_page = open_user_page_as_admin

        origin_user = create_user_data()
        user_page.create_new_user(origin_user, user_role="USER")

        user_teardown["email"] = origin_user["email"]
        assert user_page.find_user_by_email(origin_user["email"]), f"Нет пользователя: {origin_user['email']}"

        # Добавляем _udp к имени и фамилии
        upd_first_name = origin_user["firstName"] + "_upd"
        upd_last_name = origin_user["lastName"] + "_upd"
        upd_role = "VIP_USER"

        # Открываем edit у пользователя и обновляем данные
        user_page.open_edit_button_for_email(origin_user["email"])
        user_page.fill_input(user_page.selectors["first_name_input"], upd_first_name)
        user_page.fill_input(user_page.selectors["last_name_input"], upd_last_name)
        user_page.select_option(user_page.selectors["role_select"], upd_role)
        user_page.submit_update_user()

        # Собираем обновленные данные для проверки
        upd_user = user_page.find_user_by_email(origin_user["email"])
        actual_name = upd_user.get("Name")
        expected_results = f"{upd_first_name} {upd_last_name}"

        # Проверяем, что данные у пользователя обновленные
        assert upd_user, f"Пользователь с новыми данными не найден: {origin_user['email']}"
        assert actual_name == expected_results, f"Имя в таблице: {actual_name}, ожидали: {expected_results}"
        assert upd_user["Role"] == upd_role, f"Роль в таблице: {upd_user.get('Role')}, ожидали: {upd_role}"

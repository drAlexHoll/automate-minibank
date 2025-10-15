import pytest

from config.settings import settings, UserRole


@pytest.mark.api
@pytest.mark.auth
class TestMyAuth:
    def test_my_first_api_login(self, api_client):
        """Мой первый API тест логина"""

        # Подготовка данных
        simple_user = settings.get_user(UserRole.USER)

        # Выполнение запроса
        login_response = api_client.login(simple_user.email, simple_user.password)

        # Проверки
        assert login_response.success
        assert login_response.status_code == 200, f"Неверный статус код: {login_response.status_code}"

        data = login_response.data

        # Проверка, что в ответе есть токен и пользователь
        assert "token" in data and data["token"], "Отсутствует токен"
        assert "user" in data and data["user"], "Отсутствует пользователь"

        # Проверка данных пользователя
        user_data = data["user"]

        # email и role соответствует переданному в запрос
        assert user_data[
                   "email"] == simple_user.email, f"Email не совпадает: {user_data['email']} != {simple_user.email}"
        assert user_data["role"] == UserRole.USER.value, f"Неверная роль: {user_data['role']} != {UserRole.USER.value}"

    def test_login_wrong_password(self, api_client):
        """Тест с передачей неверного пароля в запросе"""

        # Подготовка данных
        simple_user = settings.get_user(UserRole.USER)

        # Выполнение запроса
        login_response = api_client.login(simple_user.email, simple_user.password + "123")

        # Проверка ответа
        assert login_response.success is False, f"Статус ответа: {login_response.success}"
        assert login_response.status_code in [401, 403], f"Статус код: {login_response.status_code}"

        data = login_response.data

        # Проверка, что токен в ответе отсутствует
        assert "token" not in data, f"В ответе присутствует токен: {data['token']}"

    def test_already_logged_in_user(self, logged_in_user, api_client):
        """Тест с уже залогиненным пользователем"""

        # Подготовка данных
        simple_user = settings.get_user(UserRole.USER)
        auth_response = api_client.get_current_user()

        # Проверяем, что пользователь USER авторизовался
        assert auth_response["email"] == simple_user.email, f"Авторизован не пользователь: {simple_user.email}"

    def test_token_validation(self, logged_in_user, api_client):
        """Тест на валидацию токена"""

        # Проверяем валидацию токена
        validation_token = api_client.validate_token()

        assert validation_token.success, f"Валидация токена не прошла: {validation_token.message}"
        assert validation_token.status_code == 200

    def test_login_different_roles(self, api_client, role):
        """Тест логина разных ролей через параметризацию"""

        # Подготовка данных
        user = settings.get_user(role)

        # Выполнение запроса
        login_response = api_client.login(user.email, user.password)

        assert login_response.status_code == 200, f"Неверный статус-код: {login_response.status_code}"

        # Извлекаем информацию о пользователе
        user_data = login_response.data["user"]

        # email и role соответствует переданному в запрос
        assert user_data["role"] == role.value, f"Неверная роль: {user_data['role']} != {role.value}"
        assert user_data["email"] == user.email, f"Email не совпадает: {user_data['email']} != {user.email}"

    @pytest.mark.parametrize("email, password, expected_status", [
        ("", "password123", 400),
        ("user@bank.test", "", 400),
        ("email@email.ru", "password123", 401),
        ("user@bank.test", "123456", 401),
        pytest.param("", "", 400, marks=pytest.mark.skip(reason="Проверка избыточна и покрывается предыдущими"))

    ], ids=[
        "Test with empty email",
        "Test with empty password",
        "Test with wrong email",
        "Test with wrong password",
        "(SKIP) Test with empty email and password"
    ])
    def test_login_errors(self, api_client, email, password, expected_status):
        """Параметризированный тест ошибок логина"""

        # Выполнение запроса
        login_response = api_client.login(email, password)

        # Проверка ответа
        assert login_response.success is False, f"Статус ответа: {login_response.success}"
        assert login_response.status_code == expected_status, f"Статус код: {login_response.status_code}"

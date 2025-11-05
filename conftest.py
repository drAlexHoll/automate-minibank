"""
Конфигурация pytest для MiniBank Test Framework

Структура файла:
- СИСТЕМНЫЕ НАСТРОЙКИ И ЛОГИРОВАНИЕ
- ХУКИ PYTEST И ДОП. ОПЦИИ
- UI ФИКСТУРЫ (WebDriver, ожидания)
- API ФИКСТУРЫ (клиент и логин под ролями)
- ДАННЫЕ ДЛЯ ТЕСТОВ (готовые сценарии создания данных)
- ФАБРИКИ ДАННЫХ (гибкие генераторы пользователей/счетов)
"""

import base64
import os
import re
import sys
from pathlib import Path
from typing import Generator, Dict, Any, Callable

import pytest
import structlog
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.support.ui import WebDriverWait

from ui.pages.accounts_page import AccountsPage
from ui.pages.dashboard_page import DashboardPage
from ui.pages.login_page import LoginPage
from ui.pages.transfers_page import TransfersPage
from ui.pages.users_page import UsersPage
from utils.helpers import delete_user_by_email

# ──────────────────────────────────────────────────────────────────────────────
# СИСТЕМНЫЕ НАСТРОЙКИ И ЛОГИРОВАНИЕ
# ──────────────────────────────────────────────────────────────────────────────
# Обеспечиваем absolute-импорты модулей tests (config, utils, ui)

SENSITIVE_KEYS = {
    "password", "currentPassword", "newPassword",
    "token", "access_token", "refresh_token",
    "authorization", "Authorization", "api_key", "Api-Key"
}

_RE_PASSWORD = re.compile(
    r'(\[[^\]]*password[^\]]*\].*?with:\s*)(["\']?)([^"\']+)(\2)',
    re.IGNORECASE,
)


def _redact_string(s: str) -> str:
    """Маскирует значение пароля в строке лога"""
    return _RE_PASSWORD.sub(r'\1"******"', s)


def _redact(obj):
    """Рекурсивно маскирует чувствительные данные в объектах (dict, list, str)"""
    if obj is None:
        return None
    if isinstance(obj, dict):
        return {k: ("******" if k in SENSITIVE_KEYS else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        t = type(obj)
        return t(_redact(v) for v in obj)
    if isinstance(obj, str):
        return _redact_string(obj)
    return obj


def censor_processor(logger, method_name, event_dict):
    """Обрабатывает события structlog и маскирует секреты перед записью в логи"""
    # Рекурсивно маскируем поля события, включая вложенные dict/list
    return {k: _redact(v) for k, v in event_dict.items()}


PROJECT_TESTS_DIR = Path(__file__).parent
SCREENSHOTS_DIR = PROJECT_TESTS_DIR / "screenshots"
REPORTS_DIR = PROJECT_TESTS_DIR / "reports"
if str(PROJECT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_TESTS_DIR))

from config.settings import settings, UserRole
from utils.api_client import MiniBankAPIClient

# Конфигурация структурированного логирования для лучшего вывода тестов
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        censor_processor,
        structlog.processors.JSONRenderer()

    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (локальные)
# ──────────────────────────────────────────────────────────────────────────────

def _get_browser_options(browser_name: str, headless: bool = True):
    """Получить опции браузера (минимально необходимый набор)."""
    if browser_name.lower() == "chrome":
        options = ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-features=PasswordLeakDetection,PasswordManagerOnboarding")
        options.add_experimental_option(
            "prefs",
            {
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False,
                "autofill.profile_enabled": False,
                "autofill.credit_card_enabled": False,
            }
        )
        return options
    elif browser_name.lower() == "firefox":
        options = FirefoxOptions()
        if headless:
            options.add_argument("--headless")
        return options
    elif browser_name.lower() == "edge":
        options = EdgeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        return options
    else:
        raise ValueError(f"Неподдерживаемый браузер: {browser_name}")


def _create_webdriver(browser_name: str, headless: bool = True):
    """Создать экземпляр WebDriver с использованием Selenium Manager."""
    browser_name = browser_name.lower()

    if browser_name == "chromium":
        browser_name = "chrome"

    if browser_name == "chrome":
        options = _get_browser_options("chrome", headless)
        driver = webdriver.Chrome(options=options)
    elif browser_name == "firefox":
        options = _get_browser_options("firefox", headless)
        driver = webdriver.Firefox(options=options)
    elif browser_name == "edge":
        options = _get_browser_options("edge", headless)
        driver = webdriver.Edge(options=options)
    else:
        raise ValueError(f"Неподдерживаемый браузер: {browser_name}")

    driver.implicitly_wait(0)
    driver.set_page_load_timeout(settings.browser_config.page_load_timeout)

    return driver


def _capture_screenshot_bytes(driver) -> bytes:
    """Снять скриншот надёжно: сначала через CDP (Chrome/Edge), затем обычным методом."""
    # Попробовать дождаться полной загрузки документа (до 2 сек)
    try:
        WebDriverWait(driver, 2).until(lambda d: d.execute_script("return document.readyState") == "complete")
    except Exception:
        pass
    try:
        driver.execute_script("window.scrollTo(0,0)")
    except Exception:
        pass

    # CDP для Chromium-браузеров
    try:
        if hasattr(driver, "execute_cdp_cmd"):
            data = driver.execute_cdp_cmd("Page.captureScreenshot", {
                "format": "png",
                "fromSurface": True,
                "captureBeyondViewport": True,
            })
            if data and isinstance(data, dict) and data.get("data"):
                return base64.b64decode(data["data"])
    except Exception as e:
        logger.warning(f"CDP screenshot failed: {e}")

    # Fallback на стандартный API
    try:
        return driver.get_screenshot_as_png()
    except Exception as e:
        logger.warning(f"Standard screenshot failed: {e}")
        return b""


# ──────────────────────────────────────────────────────────────────────────────
# ХУКИ PYTEST И ДОП. ОПЦИИ
# ──────────────────────────────────────────────────────────────────────────────

def pytest_sessionstart(session):
    """Подготовка директорий перед стартом сессии (скриншоты/репорты)."""
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """При провале UI теста делаем скриншот и HTML-дамп и прикрепляем к Allure."""
    outcome = yield
    rep = outcome.get_result()

    if rep.when == "call":
        item._rep_call_failed = rep.failed

    if rep.when != "call" or not rep.failed:
        return

    driver = getattr(item, "_driver", None)
    if not driver or not settings.browser_config.screenshot_on_failure:
        return

    # Гарантируем наличие каталога
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    test_name = item.name.replace("/", "_")
    screenshot_path = SCREENSHOTS_DIR / f"{test_name}.png"
    html_path = SCREENSHOTS_DIR / f"{test_name}.html"

    # Сохранить скриншот (CDP -> fallback)
    try:
        png_bytes = _capture_screenshot_bytes(driver)
        if png_bytes:
            with open(screenshot_path, "wb") as f:
                f.write(png_bytes)
    except Exception as e:
        logger.warning(f"Не удалось сохранить скриншот: {e}")

    # Сохранить HTML
    try:
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(driver.page_source or "")
    except Exception as e:
        logger.warning(f"Не удалось сохранить HTML: {e}")

    # Прикрепление в Allure
    try:
        import allure
        from allure_commons.types import AttachmentType
        if screenshot_path.exists():
            with open(screenshot_path, "rb") as f:
                allure.attach(f.read(), name=f"Screenshot - {test_name}", attachment_type=AttachmentType.PNG)
        if html_path.exists():
            with open(html_path, "r", encoding="utf-8") as f:
                allure.attach(f.read(), name=f"Page Source - {test_name}", attachment_type=AttachmentType.TEXT)
    except Exception as e:
        logger.warning(f"Не удалось прикрепить артефакты к Allure: {e}")


def pytest_addoption(parser):
    """CLI-опции фреймворка для выбора браузера и режима."""
    parser.addoption(
        "--browser-headed",
        action="store_true",
        default=False,
        help="Запустить тесты в обычном режиме (с видимым браузером)",
    )
    parser.addoption(
        "--ui-browser",
        action="store",
        default=None,
        help="Выбрать браузер для UI: chrome|firefox|edge",
    )


# ──────────────────────────────────────────────────────────────────────────────
# UI ФИКСТУРЫ
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def driver(request) -> Generator[webdriver.Remote, None, None]:
    """Создать экземпляр WebDriver для UI тестов."""
    cli_browser = request.config.getoption("--ui-browser")
    headed = request.config.getoption("--browser-headed")

    browser_name = cli_browser or settings.browser_config.browser
    headless = settings.browser_config.headless and (not headed)

    driver_instance = _create_webdriver(browser_name, headless)

    if not headless:
        try:
            driver_instance.set_window_size(
                settings.browser_config.window_width, settings.browser_config.window_height
            )
        except Exception:
            pass

    request.node._driver = driver_instance

    yield driver_instance

    try:
        driver_instance.quit()
    except Exception as e:
        logger.warning(f"Ошибка при закрытии WebDriver: {e}")


@pytest.fixture(scope="function")
def wait(driver) -> WebDriverWait:
    """Явные ожидания для текущего драйвера с таймаутом из настроек."""
    return WebDriverWait(driver, settings.browser_config.element_wait_timeout)


# ──────────────────────────────────────────────────────────────────────────────
# API ФИКСТУРЫ (клиент и быстрый логин ролей)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def api_client() -> Generator[MiniBankAPIClient, None, None]:
    """Инициализирует MiniBankAPIClient и выполняет logout/cleanup после теста (если авторизован)."""
    client = MiniBankAPIClient()
    yield client
    if client.is_authenticated():
        client.logout()


@pytest.fixture(scope="function")
def logged_in_user(api_client: MiniBankAPIClient) -> Dict[str, Any]:
    """Быстрый логин под обычным пользователем и возврат текущего пользователя."""
    login_response = api_client.login_as_role(UserRole.USER)
    if not login_response.success:
        pytest.skip(f"Не удалось залогиниться как пользователь: {login_response.message}")
    return api_client.get_current_user()


@pytest.fixture(scope="function")
def logged_in_vip(api_client: MiniBankAPIClient) -> Dict[str, Any]:
    """Быстрый логин под VIP и возврат текущего пользователя."""
    login_response = api_client.login_as_role(UserRole.VIP_USER)
    if not login_response.success:
        pytest.skip(f"Не удалось залогиниться как VIP: {login_response.message}")
    return api_client.get_current_user()


@pytest.fixture(scope="function")
def logged_in_admin(api_client: MiniBankAPIClient) -> Dict[str, Any]:
    """Быстрый логин под администратором и возврат текущего пользователя."""
    login_response = api_client.login_as_role(UserRole.ADMIN)
    if not login_response.success:
        pytest.skip(f"Не удалось залогиниться как админ: {login_response.message}")
    return api_client.get_current_user()


@pytest.fixture(scope="function")
def logged_in_support(api_client: MiniBankAPIClient) -> Dict[str, Any]:
    """Быстрый логин под поддержкой и возврат текущего пользователя."""
    login_response = api_client.login_as_role(UserRole.SUPPORT)
    if not login_response.success:
        pytest.skip(f"Не удалось залогиниться как поддержка: {login_response.message}")
    return api_client.get_current_user()


# ──────────────────────────────────────────────────────────────────────────────
# ДАННЫЕ ДЛЯ ТЕСТОВ (готовые сценарии)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def test_user_data(api_client: MiniBankAPIClient) -> Dict[str, Any]:
    """Создаёт тестового пользователя (role=USER) с одним счётом (initialBalance=0)."""
    admin_login = api_client.login_as_role(UserRole.ADMIN)
    if not admin_login.success:
        pytest.skip(f"Не удалось залогиниться как админ: {admin_login.message}")
    test_data = api_client.create_test_user_with_account(UserRole.USER)
    logger.info(f"Создан тестовый пользователь для UI теста: {test_data['user']['email']}")
    return test_data


@pytest.fixture(scope="function")
def user_with_two_accounts(api_client: MiniBankAPIClient):
    """Создаёт пользователя с двумя счетами: CHECKING(1000) и SAVINGS(0), выполняет вход этим пользователем."""
    admin_login = api_client.login_as_role(UserRole.ADMIN)
    if not admin_login.success:
        pytest.fail(f"Не удалось залогиниться как админ: {admin_login.message}")

    from utils.helpers import create_unique_user_data

    user_data = create_unique_user_data()
    if "uniqueId" in user_data:
        del user_data["uniqueId"]

    user_data.update({
        "role": "USER",
        "password": "TestPassword123!"
    })

    user_response = api_client.create_user(user_data)
    if not user_response.success:
        pytest.fail(f"Не удалось создать пользователя: {user_response.message}")

    user = user_response.data["user"]

    account1_data = {
        "userId": user["id"],
        "accountType": "CHECKING",
        "initialBalance": 1000
    }

    account1_response = api_client.create_account(account1_data)
    if not account1_response.success:
        pytest.fail(f"Не удалось создать первый счет: {account1_response.message}")

    account1_id = account1_response.data["account"]["id"]
    print(f"✅ Создан исходный счет ID: {account1_id}")

    account2_data = {
        "userId": user["id"],
        "accountType": "SAVINGS"
    }

    account2_response = api_client.create_account(account2_data)
    if not account2_response.success:
        pytest.fail(f"Не удалось создать второй счет: {account2_response.message}")

    account2_id = account2_response.data["account"]["id"]
    print(f"✅ Создан целевой счет ID: {account2_id}")

    user_login = api_client.login(user["email"], "TestPassword123!")
    if not user_login.success:
        pytest.fail(f"Не удалось залогиниться как пользователь: {user_login.message}")

    accounts_response = api_client.get_accounts()
    if not accounts_response.success:
        pytest.fail(f"Не удалось получить счета пользователя: {accounts_response.message}")

    user_accounts = accounts_response.data.get("accounts", [])

    account1 = None
    account2 = None

    for acc in user_accounts:
        if acc["id"] == account1_id:
            account1 = acc
        elif acc["id"] == account2_id:
            account2 = acc

    if not account1 or not account2:
        pytest.fail("Не удалось найти созданные счета в списке счетов пользователя")

    print(f"✅ Обновлены счета с user_id: {account1['user_id']}")

    yield {
        "user": user,
        "credentials": {
            "email": user["email"],
            "password": "TestPassword123!"
        },
        "source_account": account1,
        "target_account": account2,
        "accounts": [account1, account2]
    }

    from utils.helpers import delete_user_by_email
    delete_user_by_email(api_client, user["email"])


# ──────────────────────────────────────────────────────────────────────────────
# ФАБРИКИ ДАННЫХ (гибкие генераторы пользователей/счетов)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="function")
def make_user_with_account(api_client: MiniBankAPIClient) -> Callable[[UserRole, float, str], Dict[str, Any]]:
    """
    Фабрика: создать пользователя заданной роли с одним счётом и указанным балансом.

    Возвращает функцию: (role, initial_balance, account_type) -> dict с ключами
      - user, credentials, account
    Пример:
      data = make_user_with_account(UserRole.USER, 200.0, "CHECKING")
    """

    def _creator(role: UserRole = UserRole.USER, initial_balance: float = 0.0, account_type: str = "CHECKING") -> Dict[
        str, Any]:
        # Нужны админские права для создания пользователей/счетов
        admin_login = api_client.login_as_role(UserRole.ADMIN)
        if not admin_login.success:
            pytest.fail(f"Не удалось залогиниться как админ: {admin_login.message}")

        from utils.helpers import create_unique_user_data
        user_payload = create_unique_user_data()
        user_payload.pop("uniqueId", None)
        password = "TestPassword123!"
        user_payload.update({
            "role": role.value,
            "password": password,
        })
        u_res = api_client.create_user(user_payload)
        if not u_res.success:
            pytest.fail(f"Не удалось создать пользователя: {u_res.message}")
        user = u_res.data["user"]

        acc_payload = {
            "userId": user["id"],
            "accountType": account_type,
            "initialBalance": float(initial_balance) if initial_balance else 0.0,
        }
        a_res = api_client.create_account(acc_payload)
        if not a_res.success:
            pytest.fail(f"Не удалось создать счёт: {a_res.message}")
        account = a_res.data["account"]

        return {
            "user": user,
            "credentials": {"email": user["email"], "password": password},
            "account": account,
        }

    return _creator


@pytest.fixture(scope="function")
def make_account_for_user(api_client: MiniBankAPIClient) -> Callable[[str, float, str], Dict[str, Any]]:
    """
    Фабрика: создать дополнительный счёт для существующего пользователя.

    Возвращает функцию: (user_id, initial_balance, account_type) -> dict с ключом account
    Пример:
      acc = make_account_for_user(user_id, 500.0, "SAVINGS")
    """

    def _creator(user_id: str, initial_balance: float = 0.0, account_type: str = "CHECKING") -> Dict[str, Any]:
        # Создание счетов доступно админу
        admin_login = api_client.login_as_role(UserRole.ADMIN)
        if not admin_login.success:
            pytest.fail(f"Не удалось залогиниться как админ: {admin_login.message}")

        acc_payload = {
            "userId": user_id,
            "accountType": account_type,
            "initialBalance": float(initial_balance) if initial_balance else 0.0,
        }
        a_res = api_client.create_account(acc_payload)
        if not a_res.success:
            pytest.fail(f"Не удалось создать счёт: {a_res.message}")
        return {"account": a_res.data["account"]}

    return _creator


# ──────────────────────────────────────────────────────────────────────────────
# ОБЩИЕ ФИКСТУРЫ для UI и API тестов
# ──────────────────────────────────────────────────────────────────────────────

ROLES = [
    (UserRole.USER, "Login as USER"),
    (UserRole.ADMIN, "Login as ADMIN"),
    (UserRole.VIP_USER, "Login as VIP_USER"),
    (UserRole.SUPPORT, "Login as SUPPORT"),
]


@pytest.fixture(params=ROLES, ids=[r[1] for r in ROLES])
def role(request):
    return request.param[0]


@pytest.fixture(scope="function")
def login_as(driver):
    """Хелпер для логина под любой ролью в ПО"""

    def _login(role):
        # Переходим на страницу логина
        login_page = LoginPage(driver)
        login_page.navigate_to()

        # Проверяем, что страница загрузилась
        login_page.assert_page_loaded()

        # Логинимся как пользователь с переданной ролью
        user = settings.get_user(role)
        login_page.login(user.email, user.password)

        # Проверяем что попали на dashboard
        dashboard_page = DashboardPage(driver)
        dashboard_page.assert_page_loaded()

        current_url = driver.current_url
        assert "dashboard" in current_url.lower(), f"{user.role} user not on dashboard: {current_url}"

        return dashboard_page

    return _login


@pytest.fixture(scope="function")
def account_page_as_role(driver, login_as, role):
    """Логинимся под ролью и открывает страницу счетов"""
    auth_as_user = login_as(role)
    auth_as_user.open_accounts()
    account_page = AccountsPage(driver)
    account_page.assert_page_loaded()
    account_page.assert_create_button()

    return account_page


@pytest.fixture
def checking_account_data():
    return {"account_type": "CHECKING", "initial_balance": 333}


@pytest.fixture
def savings_account_data():
    return {"account_type": "SAVINGS", "initial_balance": 222}


@pytest.fixture
def open_user_page_as_admin(driver, login_as):
    """Хеплер с логином под админом и открытие страницы user management"""

    auth_as_admin = login_as(UserRole.ADMIN)
    auth_as_admin.open_users()

    user_page = UsersPage(driver)
    user_page.wait_until_loaded()

    return user_page


@pytest.fixture(scope="function")
def user_teardown(api_client):
    """Фикстура по хранению данных созданного пользователя в случае сбоя и удалению в конце теста"""
    state = {"email": None}

    yield state
    email = state.get("email")

    if email:
        delete_user_by_email(api_client, email)


@pytest.fixture(scope="function")
def transfers_page_as_user(driver, user_with_two_accounts):
    """Логин под тестовым пользователем и открытие страницы Transfers"""
    creds = user_with_two_accounts["credentials"]
    src_id = user_with_two_accounts["source_account"]["id"]

    # UI логин
    login_page = LoginPage(driver)
    login_page.navigate_to()
    login_page.assert_page_loaded()
    login_page.login(creds["email"], creds["password"])

    # Основная страница (dashboard) и переход на Transfers
    dashboard_page = DashboardPage(driver)
    dashboard_page.assert_page_loaded()
    dashboard_page.open_transfers()

    transfers_page = TransfersPage(driver)
    transfers_page.wait_until_loaded()
    transfers_page.wait_for_accounts_loaded(src_id)

    # Проверки основных элементов форм
    transfers_page.assert_form_elements_visible()
    return {
        **user_with_two_accounts,
        "transfers_page": transfers_page,
    }


def _get_balance(api_client, source_account: str, target_account: str) -> tuple[float, float]:
    """Возвращает текущие балансы исходного и целевого счетов через API"""
    account_response = api_client.get_accounts()
    assert account_response.success, f"Не удалось получить счета: {account_response.message}"

    accounts = account_response.data["accounts"]
    source_after = float(next((a["balance"] for a in accounts if a["id"] == source_account), None))
    target_after = float(next((a["balance"] for a in accounts if a["id"] == target_account), None))
    return source_after, target_after


def assert_balance_delta(api_client, source_account: str, target_account: str, source_before: float,
                         target_before: float, delta: float) -> None:
    """Проверяет изменение балансов после перевода и логирует результаты"""
    source_after, target_after = _get_balance(api_client, source_account, target_account)
    assert source_after == source_before - delta, f"Баланс отправителя: ожидалось {source_before - delta}, получено {source_after}"
    assert target_after == target_before + delta, f"Баланс получателя: ожидалось {target_before + delta}, получено {target_after}"
    logger.info("Transfer completed",
                source_before=source_before,
                source_after=source_after,
                target_before=target_before,
                target_after=target_after,
                amount=delta)

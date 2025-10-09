"""
UI тесты переводов MiniBank
Переводы между счетами через пользовательский интерфейс
"""

import pytest
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

from config.settings import settings, UserRole
from utils.api_client import MiniBankAPIClient
from ui.pages.login_page import LoginPage
from ui.pages.dashboard_page import DashboardPage
from ui.pages.transfers_page import TransfersPage


@pytest.mark.ui
@pytest.mark.transfers
def test_access_transfers_page(driver):
    """Тест доступа к странице переводов"""
    login_page = LoginPage(driver)
    login_page.navigate_to()
    login_page.assert_page_loaded()
    
    vip_user = settings.get_user(UserRole.VIP_USER)
    login_page.login(vip_user.email, vip_user.password)
    
    dashboard_page = DashboardPage(driver)
    dashboard_page.assert_page_loaded()
    dashboard_page.open_transfers()
    
    transfers_page = TransfersPage(driver)
    transfers_page.assert_page_loaded()
    
    assert transfers_page.is_element_visible("transfer_form"), "Transfers page not loaded properly"


@pytest.mark.ui  
@pytest.mark.transfers
def test_transfer_form_elements(driver):
    """Тест наличия элементов формы перевода"""
    login_page = LoginPage(driver)
    login_page.navigate_to()
    
    vip_user = settings.get_user(UserRole.VIP_USER)
    login_page.login(vip_user.email, vip_user.password)
    
    dashboard_page = DashboardPage(driver)
    dashboard_page.assert_page_loaded()
    dashboard_page.open_transfers()
    
    transfers_page = TransfersPage(driver)
    transfers_page.assert_page_loaded()
    
    assert transfers_page.is_element_visible("transfer_form"), "Transfer form not visible"
    
    try:
        transfers_page.enter_description("Test transfer description")
    except Exception as e:
        import structlog
        structlog.get_logger(__name__).info(f"Description field not present or not interactable: {e}")


@pytest.mark.ui
@pytest.mark.transfers  
def test_internal_transfer_between_own_accounts(driver, user_with_two_accounts):
    """Тест внутреннего перевода между собственными счетами пользователя"""
    test_data = user_with_two_accounts
    credentials = test_data["credentials"]
    source_account = test_data["source_account"]
    target_account = test_data["target_account"]

    # Вход через UI
    login_page = LoginPage(driver)
    login_page.navigate_to()
    login_page.assert_page_loaded()
    login_page.login(credentials["email"], credentials["password"])
    
    # Переходим к переводам
    dashboard_page = DashboardPage(driver)
    dashboard_page.assert_page_loaded()
    dashboard_page.open_transfers()
    
    transfers_page = TransfersPage(driver)
    transfers_page.assert_page_loaded()
    
    # Выполняем перевод
    transfer_amount = 50.0
    description = "UI Test: Transfer between own accounts"
    
    transfers_page.create_internal_transfer(
        from_account=source_account["id"],
        to_account=target_account["id"],
        amount=transfer_amount,
        description=description
    )
    
    # Проверяем успешность перевода через PageObject (стабильные селекторы)
    transfers_page.assert_success_message()

    # Проверяем, что форма остается функциональной
    assert transfers_page.is_element_immediately_visible("transfer_form"), "Форма перевода должна оставаться видимой после перевода" 
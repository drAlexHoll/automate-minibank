"""
Страница переводов для автотестов MiniBank
Управление переводами: выбор счетов, суммы, подтверждение и проверка результата

Структура:
- Селекторы формы, полей и сообщений
- Реализация абстрактных методов BasePage
- Действия высокого уровня (создание внутреннего перевода)
- Вспомогательные ожидания (опции select)
- Проверки состояния (успех/ошибка)
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Optional
import structlog
import time
from selenium.webdriver.support.ui import Select

from .base_page import BasePage

logger = structlog.get_logger(__name__)


class TransfersPage(BasePage):
    """Объект страницы переводов"""

    def __init__(self, driver: webdriver.Remote):
        super().__init__(driver)

        # Селекторы элементов страницы
        self.selectors.update({
            "page_container": '[data-testid="transfers-page"]',
            "transfer_form": '[data-testid="transfer-form"]', 
            "from_account_select": '[data-testid="from-account-select"]',
            "to_account_select": '[data-testid="to-account-select"]',
            "amount_input": '[data-testid="amount-input"]',
            "description_input": '[data-testid="description-input"]',
            "submit_button": 'button[type="submit"]',
            "success_message": '[class*="success"], [role="alert"]',
            "error_message": '[class*="error"], [role="alert"]',
            "my_account_button": '[data-testid="transfer-type-my-account"]'
        })

    # ------------------------------------------------------------------
    # Реализация абстрактных методов  
    # ------------------------------------------------------------------
    def is_loaded(self) -> bool:
        """Проверяет загружена ли страница переводов"""
        return self.is_element_immediately_visible(self.selectors["page_container"])

    def wait_until_loaded(self) -> None:
        """Ожидает полной загрузки страницы переводов"""
        self.wait_for_element(self.selectors["transfer_form"])

    def get_page_title(self) -> str:
        return "Transfers"

    # ----------------------------------------------------------------
    # Вспомогательные методы
    # ----------------------------------------------------------------
    def _wait_for_select_option(self, select_selector: str, option_value: str, timeout: Optional[int] = None) -> None:
        """Ожидает, пока в select появится option с нужным value (устраняет гонки при загрузке)."""
        timeout = timeout or self.timeout
        end_time = time.time() + timeout
        last_len = -1
        while time.time() < end_time:
            try:
                select_el = self.wait_for_element(select_selector, timeout=timeout)
                options = select_el.find_elements(By.TAG_NAME, "option")
                if len(options) != last_len:
                    self.logger.debug(f"Найдено опций в select {select_selector}: {len(options)}")
                    last_len = len(options)
                for opt in options:
                    val = opt.get_attribute("value")
                    if val == option_value:
                        return
            except Exception:
                pass
            time.sleep(0.2)
        raise AssertionError(f"В select {select_selector} не появилась опция со значением value='{option_value}' за {timeout}с")

    # ----------------------------------------------------------------
    # Действия на странице
    # ----------------------------------------------------------------
    def select_from_account(self, account_id: str):
        """Выбирает исходный счёт."""
        self._wait_for_select_option(self.selectors["from_account_select"], account_id)
        from_select = self.wait_for_element(self.selectors["from_account_select"])
        select = Select(from_select)
        select.select_by_value(account_id)

    def select_to_account(self, account_id: str):
        """Выбирает целевой счёт."""
        self._wait_for_select_option(self.selectors["to_account_select"], account_id)
        to_select = self.wait_for_element(self.selectors["to_account_select"])
        select = Select(to_select)
        select.select_by_value(account_id)

    def enter_amount(self, amount: float):
        """Вводит сумму перевода."""
        self.fill_input(self.selectors["amount_input"], str(amount))

    def enter_description(self, description: str):
        """Вводит описание перевода."""
        self.fill_input(self.selectors["description_input"], description)

    def create_internal_transfer(self, from_account: str, to_account: str, amount: float, description: str = ""):
        """Создает внутренний перевод между собственными счетами."""
        try:
            self.click_element(self.selectors["my_account_button"])
        except:
            pass  # Кнопка может уже быть выбрана
        
        self.select_from_account(from_account)
        self.select_to_account(to_account)
        self.enter_amount(amount)
        if description:
            self.enter_description(description)
        self.submit_transfer()

    def submit_transfer(self):
        """Отправляет форму перевода."""
        self.click_element(self.selectors["submit_button"])

    def wait_for_transfer_result(self) -> dict:
        """
        Ожидает результат выполнения перевода.
        Возвращает словарь со статусом и деталями (успех/ошибка и индикаторы).
        """
        result = {
            "success": False,
            "message": "",
            "transfer_info_visible": False,
            "remaining_limits_visible": False
        }
        try:
            transfer_info = self.wait_for_element_by_text("*", "Transfer Information")
            if transfer_info:
                result["transfer_info_visible"] = True
                self.logger.info("Transfer Information block appeared")
                try:
                    remaining_limits = self.wait_for_element_by_text("*", "Remaining Limits")
                    if remaining_limits:
                        result["remaining_limits_visible"] = True
                        self.logger.info("Remaining Limits block appeared")
                except:
                    pass
                success_indicators = [
                    "Transfer completed", "successfully", "Success", 
                    "INTERNAL", "Fee Amount: $0.00"
                ]
                for indicator in success_indicators:
                    try:
                        if self.wait_for_element_by_text("*", indicator, timeout=2):
                            result["success"] = True
                            result["message"] = f"Success indicator found: {indicator}"
                            self.logger.info(f"Transfer success detected: {indicator}")
                            break
                    except:
                        continue
                if not result["success"]:
                    error_indicators = ["Transfer failed", "error", "not found", "insufficient", "failed"]
                    for indicator in error_indicators:
                        try:
                            if self.wait_for_element_by_text("*", indicator, timeout=1):
                                result["message"] = f"Error detected: {indicator}"
                                self.logger.warning(f"Transfer error detected: {indicator}")
                                break
                        except:
                            continue
                if not result["message"]:
                    result["message"] = "Transfer result appeared but status unclear"
        except Exception as e:
            result["message"] = f"Transfer result not detected: {e}"
            self.logger.error(f"Failed to detect transfer result: {e}")
        return result

    # ----------------------------------------------------------------
    # Проверки состояния
    # ----------------------------------------------------------------
    def assert_success_message(self):
        """Проверяет отображение сообщения об успехе."""
        if self.is_element_visible(self.selectors["success_message"]):
            return
        success_texts = ["Transfer completed", "successfully", "Success"]
        for text in success_texts:
            try:
                self.wait_for_element_by_text("*", text, timeout=2)
                return
            except:
                continue
        raise AssertionError("Success message not found after transfer")

    def assert_error_message(self):
        """Проверяет отображение сообщения об ошибке."""
        if self.is_element_visible(self.selectors["error_message"]):
            return
        error_texts = ["error", "failed", "invalid", "required"]
        for text in error_texts:
            try:
                self.wait_for_element_by_text("*", text, timeout=2)
                return
            except:
                continue
        raise AssertionError("Error message not visible") 
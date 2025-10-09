"""
Базовый класс страницы для автотестов MiniBank
Предоставляет общую функциональность для всех Page Object с устойчивыми стратегиями поиска локаторов

Структура:
- Базовые поля и селекторы (общие селекторы)
- Абстрактные методы (загрузка/ожидание/заголовок)
- Поиск и ожидания элементов (CSS/XPath/ID/class)
- Действия (клик, ввод, выбор, скролл, hover, double-click)
- Проверки (видимость, текст, количество элементов, URL/заголовок)
- Вспомогательные утилиты (скриншот, история, модалки, алерты)
"""

import re
from typing import Optional, List, Dict, Any, Union
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException
from abc import ABC, abstractmethod
import structlog

from config.settings import settings
from utils.helpers import wait_for_condition, retry_on_failure

logger = structlog.get_logger(__name__)


class BasePage(ABC):
    """
    Базовый класс для всех объектов страниц приложения MiniBank.
    Реализует устойчивые стратегии поиска локаторов и общие операции со страницами.
    """

    def __init__(self, driver: webdriver.Remote):
        self.driver = driver
        self.settings = settings
        self.timeout = settings.browser_config.element_wait_timeout
        self.wait = WebDriverWait(driver, self.timeout)
        self.logger = logger.bind(page=self.__class__.__name__)
        
        # Словарь селекторов конкретной страницы (может быть расширен в подклассах)
        self.selectors: dict[str, str] = {}

        # Общие селекторы, используемые на нескольких страницах
        self.common_selectors = {
            # Навигация и макет
            "loading_indicator": '[data-testid="loading-indicator"], .loading, [class*="loading"]',
            "error_message": '[data-testid="error-message"], .error, [class*="error"]',
            "success_message": '[data-testid="success-message"], .success, [class*="success"]',
            
            # Кнопки и элементы форм
            "submit_button": '[data-testid="submit-button"], button[type="submit"], .submit-btn',
            "cancel_button": '[data-testid="cancel-button"], button[aria-label="Cancel"]',
            "save_button": '[data-testid="save-button"], button[aria-label="Save"]',
            "delete_button": '[data-testid="delete-button"], button[aria-label="Delete"]',
            
            # Модальные окна и диалоги
            "modal": '[data-testid="modal"], .modal, [role="dialog"]',
            "modal_close": '[data-testid="modal-close"], .modal-close, button[aria-label="Close"]',
            "confirm_dialog": '[data-testid="confirm-dialog"], .confirm-dialog',
            
            # Таблицы и списки
            "table": '[data-testid="table"], table',
            "table_row": '[data-testid="table-row"], tr',
            "table_cell": '[data-testid="table-cell"], td',
            
            # Элементы форм
            "form": '[data-testid="form"], form',
            "input": 'input',
            "select": 'select',
            "textarea": 'textarea',
            
            # Тема и настройки
            "theme_toggle": '[data-testid="theme-toggle"]',
            "notification_bell": '[data-testid="notification-bell"]',
            
            # Элементы дашборда
            "dashboard_greeting": '[data-testid="dashboard-greeting"]',
            "dashboard_overview": '[data-testid="dashboard-overview"]',
            "total_balance_card": '[data-testid="total-balance-card"]',
        }
    
    # Абстрактные методы, которые должен определить каждый Page Object
    @abstractmethod
    def is_loaded(self) -> bool:
        """Проверяет полную загрузку страницы — без явных ожиданий."""
        pass
    
    @abstractmethod  
    def wait_until_loaded(self) -> None:
        """Ожидает полной загрузки страницы."""
        pass
    
    @abstractmethod
    def get_page_title(self) -> str:
        """Идентификатор/заголовок страницы (для удобства проверок)."""
        pass

    
    def is_element_immediately_visible(self, selector: str) -> bool:
        """Проверяет видимость элемента БЕЗ ожидания"""
        try:
            by, locator = self._get_by_and_locator(selector)
            element = self.driver.find_element(by, locator)
            return element.is_displayed()
        except:
            return False
    
    def wait_for_url_change(self, current_url: str) -> None:
        """Ожидает изменения URL с текущего"""
        WebDriverWait(self.driver, self.timeout).until(
            lambda driver: driver.current_url != current_url
        )
        self.logger.info(f"URL changed from {current_url} to {self.driver.current_url}")
    
    def navigate_to(self, path: str = "") -> None:
        """Переходит на конкретный путь страницы"""
        url = self.settings.get_page_url(path)
        self.logger.info(f"Navigating to: {url}")
        self.driver.get(url)
    
    def wait_for_load_state(self, state: str = "complete", timeout: Optional[int] = None) -> None:
        """Ожидает достижения страницей определенного состояния загрузки"""
        timeout = timeout or self.timeout
        wait = WebDriverWait(self.driver, timeout)
        
        # Ждем готовности документа
        wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
    
    def wait_for_element(self, selector: str, timeout: Optional[int] = None) -> webdriver.remote.webelement.WebElement:
        """Ожидает видимости элемента с интеллектуальным разрешением селектора"""
        timeout = timeout or self.timeout
        wait = WebDriverWait(self.driver, timeout)
        by, locator = self._get_by_and_locator(selector)
        element = wait.until(EC.visibility_of_element_located((by, locator)))
        return element
    
    def find_element_by_text(self, tag: str, text: str, partial: bool = True) -> webdriver.remote.webelement.WebElement:
        """Находит элемент по текстовому содержимому используя XPath"""
        if partial:
            xpath = f"//{tag}[contains(text(), '{text}')]"
        else:
            xpath = f"//{tag}[text()='{text}']"
        
        return self.driver.find_element(By.XPATH, xpath)
    
    def find_elements_by_text(self, tag: str, text: str, partial: bool = True) -> List[webdriver.remote.webelement.WebElement]:
        """Находит элементы по текстовому содержимому используя XPath"""
        if partial:
            xpath = f"//{tag}[contains(text(), '{text}')]"
        else:
            xpath = f"//{tag}[text()='{text}']"
        
        return self.driver.find_elements(By.XPATH, xpath)
    
    def wait_for_element_by_text(self, tag: str, text: str, partial: bool = True, timeout: Optional[int] = None) -> webdriver.remote.webelement.WebElement:
        """Ожидает элемент по текстовому содержимому используя XPath"""
        timeout = timeout or self.timeout
        wait = WebDriverWait(self.driver, timeout)
        
        if partial:
            xpath = f"//{tag}[contains(text(), '{text}')]"
        else:
            xpath = f"//{tag}[text()='{text}']"
        
        return wait.until(EC.visibility_of_element_located((By.XPATH, xpath)))
    
    def click_element_by_text(self, tag: str, text: str, partial: bool = True, timeout: Optional[int] = None) -> None:
        """Кликает элемент по его текстовому содержимому"""
        timeout = timeout or self.timeout
        wait = WebDriverWait(self.driver, timeout)
        
        if partial:
            xpath = f"//{tag}[contains(text(), '{text}')]"
        else:
            xpath = f"//{tag}[text()='{text}']"
        
        element = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
        element.click()
        self.logger.info(f"Clicked element by text: {tag} containing '{text}'")

    def _get_by_and_locator(self, selector: str) -> tuple[By, str]:
        """Преобразует CSS селектор в соответствующую стратегию By"""
        # Проверяем селекторы конкретной страницы
        if selector in self.selectors:
            selector = self.selectors[selector]
        
        # Проверяем общие селекторы
        elif selector in self.common_selectors:
            selector = self.common_selectors[selector]
        
        # Определяем подходящую стратегию By
        if selector.startswith('//'):
            return By.XPATH, selector
        elif selector.startswith('[data-testid='):
            return By.CSS_SELECTOR, selector
        elif selector.startswith('#'):
            return By.ID, selector[1:]
        elif selector.startswith('.') and ' ' not in selector and '[' not in selector:
            return By.CLASS_NAME, selector[1:]
        else:
            return By.CSS_SELECTOR, selector
    
    def find_element(self, selector: str) -> webdriver.remote.webelement.WebElement:
        """Находит элемент используя интеллектуальное разрешение селектора"""
        by, locator = self._get_by_and_locator(selector)
        return self.driver.find_element(by, locator)
    
    def find_elements(self, selector: str) -> List[webdriver.remote.webelement.WebElement]:
        """Находит несколько элементов используя интеллектуальное разрешение селектора"""
        by, locator = self._get_by_and_locator(selector)
        return self.driver.find_elements(by, locator)
    
    def click_element(self, selector: str, timeout: Optional[int] = None) -> None:
        """Кликает элемент с ожиданием и обработкой ошибок"""
        timeout = timeout or self.timeout
        wait = WebDriverWait(self.driver, timeout)
        by, locator = self._get_by_and_locator(selector)
        
        # Ждем кликабельности элемента
        element = wait.until(EC.element_to_be_clickable((by, locator)))
        element.click()
        self.logger.info(f"Clicked element: {selector}")
    
    def fill_input(self, selector: str, value: str, timeout: Optional[int] = None) -> None:
        """Заполняет поле ввода значением"""
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, timeout)
        
        # Очищаем и заполняем поле
        element.clear()
        element.send_keys(value)
        
        # Проверяем установленное значение
        actual_value = element.get_attribute("value")
        assert actual_value == value, f"Expected value '{value}', got '{actual_value}'"
        self.logger.info(f"Filled input {selector} with: {value}")
    
    def select_option(self, selector: str, value: str, timeout: Optional[int] = None) -> None:
        """Выбирает опцию из выпадающего списка"""
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, timeout)
        select = Select(element)
        
        # Пытаемся выбрать по значению, затем по видимому тексту
        try:
            select.select_by_value(value)
        except NoSuchElementException:
            select.select_by_visible_text(value)
        
        self.logger.info(f"Selected option {value} in: {selector}")
    
    def get_text(self, selector: str, timeout: Optional[int] = None) -> str:
        """Получает текстовое содержимое элемента"""
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, timeout)
        return element.text
    
    def get_attribute(self, selector: str, attribute: str, timeout: Optional[int] = None) -> Optional[str]:
        """Получает значение атрибута элемента"""
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, timeout)
        return element.get_attribute(attribute)
    
    def is_element_visible(self, selector: str, timeout: Optional[int] = None) -> bool:
        """Проверяет видимость элемента"""
        timeout = timeout or self.timeout
        try:
            wait = WebDriverWait(self.driver, timeout)
            by, locator = self._get_by_and_locator(selector)
            wait.until(EC.visibility_of_element_located((by, locator)))
            return True
        except TimeoutException:
            return False
    
    def is_element_enabled(self, selector: str, timeout: Optional[int] = None) -> bool:
        """Проверяет доступность элемента"""
        timeout = timeout or self.timeout
        try:
            element = self.wait_for_element(selector, timeout)
            return element.is_enabled()
        except TimeoutException:
            return False
    
    def wait_for_text(self, selector: str, expected_text: str, timeout: Optional[int] = None) -> None:
        """Ожидает появления определенного текста в элементе"""
        timeout = timeout or self.timeout
        wait = WebDriverWait(self.driver, timeout)
        by, locator = self._get_by_and_locator(selector)
        wait.until(EC.text_to_be_present_in_element((by, locator), expected_text))
    
    def wait_for_element_count(self, selector: str, count: int, timeout: Optional[int] = None) -> None:
        """Ожидает определенного количества элементов"""
        timeout = timeout or self.timeout
        wait = WebDriverWait(self.driver, timeout)
        by, locator = self._get_by_and_locator(selector)
        
        def element_count_is(driver):
            elements = driver.find_elements(by, locator)
            return len(elements) == count
        
        wait.until(element_count_is)
    
    def scroll_to_element(self, selector: str) -> None:
        """Прокручивает к элементу"""
        element = self.find_element(selector)
        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
        self.logger.info(f"Scrolled to element: {selector}")
    
    def hover_element(self, selector: str) -> None:
        """Наводит курсор на элемент"""
        element = self.wait_for_element(selector)
        actions = ActionChains(self.driver)
        actions.move_to_element(element).perform()
        self.logger.info(f"Hovered over element: {selector}")
    
    def double_click_element(self, selector: str) -> None:
        """Двойной клик по элементу"""
        element = self.wait_for_element(selector)
        actions = ActionChains(self.driver)
        actions.double_click(element).perform()
        self.logger.info(f"Double clicked element: {selector}")
    
    def wait_for_loading_to_complete(self, timeout: Optional[int] = None) -> None:
        """Ожидает исчезновения индикаторов загрузки"""
        timeout = timeout or self.timeout
        try:
            elements = self.driver.find_elements(By.CSS_SELECTOR, '.loading, .spinner, [data-loading="true"]')
            if elements:
                WebDriverWait(self.driver, timeout).until(
                    lambda d: not d.find_elements(By.CSS_SELECTOR, '.loading, .spinner, [data-loading="true"]')
                )
        except:
            pass  # Игнорируем ошибки
    
    def wait_for_network_idle(self, timeout: Optional[int] = None) -> None:
        """Ожидает завершения сетевой активности (эвристика)"""
        timeout = timeout or self.timeout
        # Простой хак: ждём завершения загрузки документа и отсутствие активных fetch/XHR
        wait = WebDriverWait(self.driver, timeout)
        try:
            wait.until(lambda d: d.execute_script("return document.readyState") == "complete")
            wait.until(lambda d: d.execute_script("return (window.__activeRequests__||0)") == 0)
        except Exception:
            # Если app не инжектит счётчик запросов — ограничимся readyState
            pass
    
    def take_screenshot(self, name: str = "screenshot") -> str:
        """Делает скриншот и возвращает путь"""
        screenshot_path = f"screenshots/{name}_{self.__class__.__name__}.png"
        self.driver.save_screenshot(screenshot_path)
        self.logger.info(f"Screenshot saved: {screenshot_path}")
        return screenshot_path
    
    def get_current_url(self) -> str:
        """Получает текущий URL страницы"""
        return self.driver.current_url
    
    def get_page_title_text(self) -> str:
        """Получает заголовок страницы из браузера"""
        return self.driver.title
    
    def refresh_page(self) -> None:
        """Обновляет текущую страницу"""
        self.driver.refresh()
        self.wait_for_load_state()
        self.logger.info("Page refreshed")
    
    def go_back(self) -> None:
        """Возвращается назад в истории браузера"""
        self.driver.back()
        self.wait_for_load_state()
        self.logger.info("Navigated back")
    
    def go_forward(self) -> None:
        """Переходит вперед в истории браузера"""
        self.driver.forward()
        self.wait_for_load_state()
        self.logger.info("Navigated forward")
    
    def close_modals(self) -> None:
        """Закрывает любые открытые модальные окна или диалоги"""
        modal_selectors = [
            '[data-testid="modal-close"]',
            '.modal-close',
            'button[aria-label="Close"]',
            '.close-btn'
        ]
        
        for selector in modal_selectors:
            try:
                if self.is_element_visible(selector, timeout=1):
                    self.click_element(selector)
                    self.logger.info(f"Closed modal using: {selector}")
                    break
            except:
                continue
    
    def handle_alert(self, accept: bool = True) -> None:
        """Обрабатывает диалог браузера"""
        try:
            alert = self.driver.switch_to.alert
            if accept:
                alert.accept()
            else:
                alert.dismiss()
            self.logger.info(f"Alert {'accepted' if accept else 'dismissed'}")
        except:
            self.logger.info("No alert present")
    
    def get_table_data(self, table_selector: str) -> List[Dict[str, str]]:
        """Извлекает данные из таблицы"""
        table = self.wait_for_element(table_selector)
        
        # Получаем заголовки
        headers = []
        try:
            header_cells = table.find_elements(By.CSS_SELECTOR, 'thead th, thead td')
            for cell in header_cells:
                headers.append(cell.text.strip())
        except NoSuchElementException:
            # Если нет thead, пытаемся получить первую строку как заголовки
            try:
                first_row = table.find_element(By.CSS_SELECTOR, 'tr')
                header_cells = first_row.find_elements(By.TAG_NAME, 'td')
                for cell in header_cells:
                    headers.append(cell.text.strip())
            except:
                pass
        
        # Получаем строки
        rows = []
        try:
            body_rows = table.find_elements(By.CSS_SELECTOR, 'tbody tr')
            if not body_rows:  # Если нет tbody, получаем все строки кроме первой
                all_rows = table.find_elements(By.TAG_NAME, 'tr')
                body_rows = all_rows[1:] if len(all_rows) > 1 else all_rows
            
            for row in body_rows:
                cells = row.find_elements(By.TAG_NAME, 'td')
                row_data = {}
                for i, cell in enumerate(cells):
                    if i < len(headers):
                        row_data[headers[i]] = cell.text.strip()
                    else:
                        row_data[f'column_{i}'] = cell.text.strip()
                rows.append(row_data)
        except:
            pass
        
        return rows
    
    def wait_for_condition(self, condition_func, timeout: Optional[int] = None, interval: int = 1) -> bool:
        """Ожидает выполнения пользовательского условия"""
        timeout = timeout or self.timeout
        return wait_for_condition(condition_func, timeout * 1000, interval * 1000)
    
    def retry_action(self, action_func, max_retries: int = 3, delay: int = 1) -> Any:
        """Повторяет действие при неудаче"""
        return retry_on_failure(action_func, max_retries, delay * 1000)
    
    def assert_page_loaded(self) -> None:
        """Проверяет полную загрузку страницы"""
        if not self.is_loaded():
            # Если страница не готова - ждем её загрузки  
            self.wait_until_loaded()
        
        # Дополнительная проверка после ожидания
        assert self.is_loaded(), f"{self.__class__.__name__} is not fully loaded"
        self.logger.info(f"Page {self.__class__.__name__} loaded successfully")
    
    def assert_url_contains(self, url_part: str) -> None:
        """Проверяет что текущий URL содержит определенную часть"""
        current_url = self.get_current_url()
        assert url_part in current_url, f"URL '{current_url}' does not contain '{url_part}'"
    
    def assert_title_contains(self, title_part: str) -> None:
        """Проверяет что заголовок страницы содержит определенный текст"""
        title = self.get_page_title_text()
        assert title_part in title, f"Title '{title}' does not contain '{title_part}'"
    
    def send_keys(self, selector: str, keys: str) -> None:
        """Отправляет клавиши в элемент"""
        element = self.wait_for_element(selector)
        element.send_keys(keys)
        self.logger.info(f"Sent keys '{keys}' to element: {selector}")
    
    def press_key(self, selector: str, key: str) -> None:
        """Нажимает определенную клавишу на элементе"""
        element = self.wait_for_element(selector)
        if hasattr(Keys, key.upper()):
            key_constant = getattr(Keys, key.upper())
            element.send_keys(key_constant)
        else:
            element.send_keys(key)
        self.logger.info(f"Pressed key '{key}' on element: {selector}")
    
    def clear_input(self, selector: str) -> None:
        """Очищает поле ввода"""
        element = self.wait_for_element(selector)
        element.clear()
        self.logger.info(f"Cleared input: {selector}") 
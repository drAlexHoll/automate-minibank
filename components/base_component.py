"""
Base Component class for MiniBank Test Framework
Provides common functionality for reusable UI components
"""

from typing import Optional, List, Dict, Any
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import structlog

from ..config.settings import settings
from ..utils.helpers import wait_for_condition, retry_on_failure


logger = structlog.get_logger(__name__)


class BaseComponent:
    """
    Base class for reusable UI components in MiniBank application
    Handles common component operations with stable locator strategies
    """

    def __init__(self, driver: webdriver.Remote, root_selector: str = ""):
        self.driver = driver
        self.root_selector = root_selector
        self.settings = settings
        self.timeout = settings.browser_config.timeout / 1000  # Convert ms to seconds
        self.wait = WebDriverWait(driver, self.timeout)
        self.logger = logger.bind(component=self.__class__.__name__)
        
        # Root element
        self.root = None
        if root_selector:
            try:
                by, locator = self._get_by_and_locator(root_selector)
                self.root = self.driver.find_element(by, locator)
            except NoSuchElementException:
                self.logger.warning(f"Root element not found: {root_selector}")
    
    def _get_by_and_locator(self, selector: str) -> tuple[By, str]:
        """Convert CSS selector to appropriate By strategy"""
        # Determine the appropriate By strategy
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
    
    def find_element(self, selector: str, relative_to_root: bool = True) -> webdriver.remote.webelement.WebElement:
        """
        Find element with intelligent selector resolution
        
        Args:
            selector: CSS selector or data-testid
            relative_to_root: Whether to search relative to component root
            
        Returns:
            WebElement: Selenium WebElement object
        """
        by, locator = self._get_by_and_locator(selector)
        
        # Use root context if available and requested
        if relative_to_root and self.root:
            return self.root.find_element(by, locator)
        else:
            return self.driver.find_element(by, locator)
    
    def find_elements(self, selector: str, relative_to_root: bool = True) -> List[webdriver.remote.webelement.WebElement]:
        """Find multiple elements relative to root or driver"""
        by, locator = self._get_by_and_locator(selector)
        
        if relative_to_root and self.root:
            return self.root.find_elements(by, locator)
        else:
            return self.driver.find_elements(by, locator)
    
    def wait_for_component_visible(self, timeout: Optional[int] = None) -> None:
        """Wait for component to be visible"""
        if self.root:
            timeout = timeout or self.timeout
            wait = WebDriverWait(self.driver, timeout)
            wait.until(EC.visibility_of(self.root))
            self.logger.info(f"Component {self.__class__.__name__} is visible")
    
    def wait_for_component_hidden(self, timeout: Optional[int] = None) -> None:
        """Wait for component to be hidden"""
        if self.root:
            timeout = timeout or self.timeout
            wait = WebDriverWait(self.driver, timeout)
            wait.until(EC.invisibility_of_element(self.root))
            self.logger.info(f"Component {self.__class__.__name__} is hidden")
    
    def is_visible(self) -> bool:
        """Check if component is visible"""
        if self.root:
            return self.root.is_displayed()
        return True
    
    def is_enabled(self) -> bool:
        """Check if component is enabled"""
        if self.root:
            return self.root.is_enabled()
        return True
    
    def click(self, selector: str = "", timeout: Optional[int] = None) -> None:
        """
        Click element within component
        
        Args:
            selector: Element selector (empty for root element)
            timeout: Wait timeout
        """
        timeout = timeout or self.timeout
        wait = WebDriverWait(self.driver, timeout)
        
        if selector:
            by, locator = self._get_by_and_locator(selector)
            if self.root:
                element = wait.until(EC.element_to_be_clickable(self.root.find_element(by, locator)))
            else:
                element = wait.until(EC.element_to_be_clickable((by, locator)))
        else:
            element = self.root
        
        if element:
            element.click()
            self.logger.info(f"Clicked {selector or 'root'} in {self.__class__.__name__}")
    
    def fill(self, selector: str, value: str, timeout: Optional[int] = None) -> None:
        """Fill input field within component"""
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, timeout)
        
        element.clear()
        element.send_keys(value)
        
        # Verify the value was set
        actual_value = element.get_attribute("value")
        assert actual_value == value, f"Expected value '{value}', got '{actual_value}'"
        self.logger.info(f"Filled {selector} with '{value}' in {self.__class__.__name__}")
    
    def select_option(self, selector: str, value: str, timeout: Optional[int] = None) -> None:
        """Select option from dropdown within component"""
        timeout = timeout or self.timeout
        element = self.wait_for_element(selector, timeout)
        select = Select(element)
        
        try:
            select.select_by_value(value)
        except NoSuchElementException:
            select.select_by_visible_text(value)
        
        self.logger.info(f"Selected option '{value}' in {selector} in {self.__class__.__name__}")
    
    def wait_for_element(self, selector: str, timeout: Optional[int] = None) -> webdriver.remote.webelement.WebElement:
        """Wait for element to be visible within component"""
        timeout = timeout or self.timeout
        wait = WebDriverWait(self.driver, timeout)
        by, locator = self._get_by_and_locator(selector)
        
        if self.root:
            # Wait for element relative to root
            wait.until(EC.visibility_of(self.root))
            element = self.root.find_element(by, locator)
            wait.until(EC.visibility_of(element))
            return element
        else:
            return wait.until(EC.visibility_of_element_located((by, locator)))
    
    def get_text(self, selector: str = "", timeout: Optional[int] = None) -> str:
        """Get text content of element within component"""
        if selector:
            element = self.wait_for_element(selector, timeout)
        else:
            element = self.root
        
        return element.text if element else ""
    
    def get_attribute(self, selector: str, attribute: str, timeout: Optional[int] = None) -> Optional[str]:
        """Get attribute value of element within component"""
        element = self.wait_for_element(selector, timeout)
        return element.get_attribute(attribute)
    
    def is_element_visible(self, selector: str, timeout: Optional[int] = None) -> bool:
        """Check if element is visible within component"""
        timeout = timeout or self.timeout
        try:
            element = self.wait_for_element(selector, timeout)
            return element.is_displayed()
        except (TimeoutException, NoSuchElementException):
            return False
    
    def is_element_enabled(self, selector: str, timeout: Optional[int] = None) -> bool:
        """Check if element is enabled within component"""
        timeout = timeout or self.timeout
        try:
            element = self.wait_for_element(selector, timeout)
            return element.is_enabled()
        except (TimeoutException, NoSuchElementException):
            return False
    
    def hover(self, selector: str = "") -> None:
        """Hover over element within component"""
        if selector:
            element = self.wait_for_element(selector)
        else:
            element = self.root
        
        if element:
            actions = ActionChains(self.driver)
            actions.move_to_element(element).perform()
            self.logger.info(f"Hovered over {selector or 'root'} in {self.__class__.__name__}")
    
    def right_click(self, selector: str = "") -> None:
        """Right click element within component"""
        if selector:
            element = self.wait_for_element(selector)
        else:
            element = self.root
        
        if element:
            actions = ActionChains(self.driver)
            actions.context_click(element).perform()
            self.logger.info(f"Right clicked {selector or 'root'} in {self.__class__.__name__}")
    
    def drag_and_drop(self, source_selector: str, target_selector: str) -> None:
        """Drag and drop within component"""
        source = self.find_element(source_selector)
        target = self.find_element(target_selector)
        
        actions = ActionChains(self.driver)
        actions.drag_and_drop(source, target).perform()
        self.logger.info(f"Dragged {source_selector} to {target_selector} in {self.__class__.__name__}")
    
    def take_screenshot(self, name: str = "") -> str:
        """Take screenshot of component"""
        if not name:
            name = f"{self.__class__.__name__}_screenshot"
        
        if self.root:
            screenshot_path = f"screenshots/{name}.png"
            self.root.screenshot(screenshot_path)
            self.logger.info(f"Component screenshot saved: {screenshot_path}")
            return screenshot_path
        else:
            # Take full page screenshot if no root element
            screenshot_path = f"screenshots/{name}.png"
            self.driver.save_screenshot(screenshot_path)
            return screenshot_path
    
    def assert_visible(self) -> None:
        """Assert that component is visible"""
        if self.root:
            assert self.root.is_displayed(), f"Component {self.__class__.__name__} is not visible"
            self.logger.info(f"Component {self.__class__.__name__} is visible")
    
    def assert_hidden(self) -> None:
        """Assert that component is hidden"""
        if self.root:
            assert not self.root.is_displayed(), f"Component {self.__class__.__name__} is visible but should be hidden"
            self.logger.info(f"Component {self.__class__.__name__} is hidden")
    
    def assert_enabled(self) -> None:
        """Assert that component is enabled"""
        if self.root:
            assert self.root.is_enabled(), f"Component {self.__class__.__name__} is not enabled"
            self.logger.info(f"Component {self.__class__.__name__} is enabled")
    
    def assert_disabled(self) -> None:
        """Assert that component is disabled"""
        if self.root:
            assert not self.root.is_enabled(), f"Component {self.__class__.__name__} is enabled but should be disabled"
            self.logger.info(f"Component {self.__class__.__name__} is disabled")
    
    def assert_contains_text(self, expected_text: str) -> None:
        """Assert that component contains specific text"""
        if self.root:
            actual_text = self.root.text
            assert expected_text in actual_text, f"Component {self.__class__.__name__} does not contain text '{expected_text}'. Actual: '{actual_text}'"
            self.logger.info(f"Component {self.__class__.__name__} contains text: {expected_text}")
    
    def assert_has_attribute(self, attribute: str, value: str) -> None:
        """Assert that component has specific attribute value"""
        if self.root:
            actual_value = self.root.get_attribute(attribute)
            assert actual_value == value, f"Component {self.__class__.__name__} attribute {attribute} is '{actual_value}', expected '{value}'"
            self.logger.info(f"Component {self.__class__.__name__} has {attribute}={value}")
    
    def assert_has_class(self, class_name: str) -> None:
        """Assert that component has specific CSS class"""
        if self.root:
            classes = self.root.get_attribute("class") or ""
            assert class_name in classes.split(), f"Component {self.__class__.__name__} does not have class: {class_name}"
            self.logger.info(f"Component {self.__class__.__name__} has class: {class_name}")
    
    def wait_for_animation_complete(self, timeout: Optional[int] = None) -> None:
        """Wait for CSS animations to complete"""
        timeout = timeout or 2  # Default 2 seconds for animations
        
        if self.root:
            # Wait for element to be stable (no animation)
            wait = WebDriverWait(self.driver, timeout)
            wait.until(EC.visibility_of(self.root))
            # Additional wait for animations to complete
            import time
            time.sleep(0.5)
            self.logger.info(f"Animation completed for {self.__class__.__name__}")
    
    def get_bounding_box(self) -> Optional[Dict[str, float]]:
        """Get component bounding box"""
        if self.root:
            size = self.root.size
            location = self.root.location
            return {
                'x': location['x'],
                'y': location['y'],
                'width': size['width'],
                'height': size['height']
            }
        return None
    
    def is_in_viewport(self) -> bool:
        """Check if component is in viewport"""
        if self.root:
            return self.root.is_displayed()
        return False
    
    def focus(self) -> None:
        """Focus on component"""
        if self.root:
            actions = ActionChains(self.driver)
            actions.move_to_element(self.root).click().perform()
            self.logger.info(f"Focused on {self.__class__.__name__}")
    
    def blur(self) -> None:
        """Remove focus from component"""
        if self.root:
            # Click elsewhere to remove focus
            self.driver.find_element(By.TAG_NAME, "body").click()
            self.logger.info(f"Blurred {self.__class__.__name__}")
    
    def press_key(self, key: str) -> None:
        """Press key on component"""
        if self.root:
            if hasattr(Keys, key.upper()):
                key_constant = getattr(Keys, key.upper())
                self.root.send_keys(key_constant)
            else:
                self.root.send_keys(key)
            self.logger.info(f"Pressed key '{key}' on {self.__class__.__name__}")
    
    def type_text(self, text: str, delay: int = 100) -> None:
        """Type text into component with delay"""
        if self.root:
            import time
            for char in text:
                self.root.send_keys(char)
                time.sleep(delay / 1000)  # Convert ms to seconds
            self.logger.info(f"Typed '{text}' into {self.__class__.__name__}")
    
    def clear_input(self, selector: str = "") -> None:
        """Clear input field within component"""
        if selector:
            element = self.wait_for_element(selector)
        else:
            element = self.root
        
        if element:
            element.clear()
            self.logger.info(f"Cleared {selector or 'root'} in {self.__class__.__name__}")
    
    def get_inner_html(self) -> str:
        """Get inner HTML of component"""
        if self.root:
            return self.root.get_attribute("innerHTML")
        return ""
    
    def get_inner_text(self) -> str:
        """Get inner text of component"""
        if self.root:
            return self.root.text
        return ""
    
    def scroll_into_view(self) -> None:
        """Scroll component into view"""
        if self.root:
            self.driver.execute_script("arguments[0].scrollIntoView(true);", self.root)
            self.logger.info(f"Scrolled {self.__class__.__name__} into view")
    
    def wait_for_text_change(self, initial_text: str, timeout: Optional[int] = None) -> None:
        """Wait for component text to change from initial value"""
        timeout = timeout or self.timeout
        wait = WebDriverWait(self.driver, timeout)
        
        if self.root:
            wait.until(lambda driver: self.root.text != initial_text)
            self.logger.info(f"Text changed in {self.__class__.__name__}")
    
    def get_css_property(self, property_name: str) -> str:
        """Get CSS property value of component"""
        if self.root:
            return self.root.value_of_css_property(property_name)
        return "" 
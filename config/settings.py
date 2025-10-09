"""
Configuration management for MiniBank Test Framework
Supports environment-specific settings, test stand configuration, and tenant management
"""

import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Environment(Enum):
    """Available testing environments"""
    LOCAL = "local"
    DEV = "dev"
    TEST = "test"
    STAGE = "stage"
    PROD = "prod"


class UserRole(Enum):
    """User roles for testing"""
    USER = "USER"
    VIP_USER = "VIP_USER"
    SUPPORT = "SUPPORT"
    ADMIN = "ADMIN"


@dataclass
class TestUser:
    """Test user configuration"""
    email: str
    password: str
    role: UserRole
    first_name: str
    last_name: str
    is_active: bool = True


@dataclass
class BrowserConfig:
    """Browser configuration for Selenium WebDriver"""
    browser: str = "chrome"
    headless: bool = True
    window_width: int = 1920
    window_height: int = 1080
    screenshot_on_failure: bool = True
    # Selenium-specific timeouts (оптимизированы для скорости)
    implicit_wait: int = 1  # Default 1 second - оставляем
    page_load_timeout: int = 5  # Уменьшено с 10 до 5 секунд для SPA 
    element_wait_timeout: int = 3  # Уменьшено с 5 до 3 секунд


@dataclass
class APIConfig:
    """API configuration for backend integration"""
    base_url: str
    timeout: int = 30
    retry_count: int = 2  # Reduced from 3
    retry_delay: int = 1


@dataclass
class TestDataConfig:
    """Test data management configuration"""
    cleanup_after_test: bool = True
    cleanup_after_suite: bool = True
    data_isolation: bool = True


class Settings:
    """Main configuration class for the test framework"""
    
    def __init__(self):
        # По умолчанию локальная среда для удобного старта разработчика
        self.environment = Environment(os.getenv("TEST_ENV", "local"))
        self.base_dir = Path(__file__).parent.parent
        self.config_dir = self.base_dir / "config"
        self.reports_dir = self.base_dir / "reports"
        
        # Load environment-specific configuration
        self._load_configuration()
    
    def _load_configuration(self):
        """Load configuration based on environment"""
        # Test stand configuration (без фатальных исключений — безопасные дефолты)
        self.test_stand_url = os.getenv("TEST_STAND_URL", "http://localhost:3000")
        self.tenant_name = os.getenv("TENANT_NAME", "tenant1")
        
        # Build full application URL
        self.app_url = f"{self.test_stand_url}/{self.tenant_name}"
        
        # Browser configuration (все из env, с современными дефолтами)
        self.browser_config = BrowserConfig(
            browser=os.getenv("BROWSER", "chrome"),
            headless=os.getenv("HEADLESS", "true").lower() == "true",
            window_width=int(os.getenv("WINDOW_WIDTH", "1920")),
            window_height=int(os.getenv("WINDOW_HEIGHT", "1080")),
            screenshot_on_failure=os.getenv("SCREENSHOT_ON_FAILURE", "true").lower() == "true",
            implicit_wait=int(os.getenv("IMPLICIT_WAIT", "0")),  # только явные ожидания
            page_load_timeout=int(os.getenv("PAGE_LOAD_TIMEOUT", "5")),  # синхронизировано с комментарием
            element_wait_timeout=int(os.getenv("ELEMENT_WAIT_TIMEOUT", "3"))  # синхронизировано с комментарием
        )
        
        # API configuration
        api_base_url = self._get_api_base_url()
        self.api_config = APIConfig(
            base_url=api_base_url,
            timeout=int(os.getenv("API_TIMEOUT", "30")),
            retry_count=int(os.getenv("API_RETRY_COUNT", "2")),
            retry_delay=int(os.getenv("API_RETRY_DELAY", "1"))
        )
        
        # Test data configuration
        self.test_data_config = TestDataConfig(
            cleanup_after_test=os.getenv("CLEANUP_AFTER_TEST", "true").lower() == "true",
            cleanup_after_suite=os.getenv("CLEANUP_AFTER_SUITE", "true").lower() == "true",
            data_isolation=os.getenv("DATA_ISOLATION", "true").lower() == "true"
        )
        
        # Test users configuration
        self.test_users = self._load_test_users()
    
    def _get_api_base_url(self) -> str:
        """Get API base URL based on environment"""
        if self.environment == Environment.LOCAL:
            return os.getenv("API_BASE_URL", "http://localhost:3001")
        else:
            # Для удалённых окружений используем тот же базовый URL, что и тест-стенд
            return f"{self.test_stand_url}/api"
    
    def _load_test_users(self) -> Dict[UserRole, TestUser]:
        """Load test users configuration from environment variables"""
        return {
            UserRole.USER: TestUser(
                email=os.getenv("TEST_USER_EMAIL", "user@bank.test"),
                password=os.getenv("TEST_USER_PASSWORD", "password123"),
                role=UserRole.USER,
                first_name=os.getenv("TEST_USER_FIRST_NAME", "Test"),
                last_name=os.getenv("TEST_USER_LAST_NAME", "User")
            ),
            UserRole.VIP_USER: TestUser(
                email=os.getenv("TEST_VIP_EMAIL", "vip@bank.test"),
                password=os.getenv("TEST_VIP_PASSWORD", "password123"),
                role=UserRole.VIP_USER,
                first_name=os.getenv("TEST_VIP_FIRST_NAME", "VIP"),
                last_name=os.getenv("TEST_VIP_LAST_NAME", "User")
            ),
            UserRole.SUPPORT: TestUser(
                email=os.getenv("TEST_SUPPORT_EMAIL", "support@bank.test"),
                password=os.getenv("TEST_SUPPORT_PASSWORD", "password123"),
                role=UserRole.SUPPORT,
                first_name=os.getenv("TEST_SUPPORT_FIRST_NAME", "Support"),
                last_name=os.getenv("TEST_SUPPORT_LAST_NAME", "User")
            ),
            UserRole.ADMIN: TestUser(
                email=os.getenv("TEST_ADMIN_EMAIL", "admin@bank.test"),
                password=os.getenv("TEST_ADMIN_PASSWORD", "password123"),
                role=UserRole.ADMIN,
                first_name=os.getenv("TEST_ADMIN_FIRST_NAME", "Admin"),
                last_name=os.getenv("TEST_ADMIN_LAST_NAME", "User")
            )
        }
    
    def get_user(self, role: UserRole) -> TestUser:
        """Get test user by role"""
        return self.test_users[role]
    
    def get_primary_test_roles(self) -> List[UserRole]:
        """Get primary roles for testing (USER and VIP_USER)"""
        return [UserRole.USER, UserRole.VIP_USER]
    
    def get_all_test_roles(self) -> List[UserRole]:
        """Get all available test roles"""
        return list(UserRole)
    
    def get_page_url(self, page_path: str = "") -> str:
        """Get full URL for a specific page"""
        if page_path.startswith("/"):
            page_path = page_path[1:]
        return f"{self.app_url}/{page_path}" if page_path else self.app_url
    
    def get_api_url(self, endpoint: str, relative: bool = False) -> str:
        """Get full or relative API URL for an endpoint"""
        # Ensure tenant and endpoint are included
        full_path = f"{self.tenant_name}/{endpoint.lstrip('/')}"
        
        if relative:
            # Used for httpx client which has a base_url set
            return f"/{full_path}"
        else:
            # Used for other cases like manual requests or direct browser access
            return f"{self.api_config.base_url}/{full_path}"
    
    def is_production(self) -> bool:
        """Check if running in production environment"""
        return self.environment == Environment.PROD
    
    def is_local(self) -> bool:
        """Check if running in local environment"""
        return self.environment == Environment.LOCAL
    
    def should_cleanup_data(self) -> bool:
        """Check if test data should be cleaned up"""
        return self.test_data_config.cleanup_after_test
    
    def should_use_existing_data(self) -> bool:
        """Check if existing test data should be used (opposite of cleanup)"""
        return not self.test_data_config.cleanup_after_test
    
    def __str__(self) -> str:
        """String representation of settings"""
        return f"""
MiniBank Test Framework Settings:
- Environment: {self.environment.value}
- Test Stand: {self.test_stand_url}
- Tenant: {self.tenant_name}
- App URL: {self.app_url}
- API URL: {self.api_config.base_url}
- Browser: {self.browser_config.browser}
- Headless: {self.browser_config.headless}
- Cleanup Data: {self.test_data_config.cleanup_after_test}
"""


# Global settings instance
settings = Settings() 
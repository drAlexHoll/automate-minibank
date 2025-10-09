"""
Вспомогательные утилиты для MiniBank Test Framework
Часто используемые операции: ожидания, ретраи, генерация данных, форматирование и валидация

Структура:
- ОЖИДАНИЯ И ПОВТОРЫ (wait/retry)
- ГЕНЕРАЦИЯ ДАННЫХ (строки, email, суммы, номера счетов)
- ФОРМАТИРОВАНИЕ И ВАЛИДАЦИЯ (валюта, email/телефон/сумма)
- ДАТЫ (прошлое/будущее)
- ФИЛЬТРЫ ДАННЫХ (отсев тестовых, индикаторы)
- ПРОСТЕЙШИЕ РАСЧЁТЫ (комиссии)
"""

import time
import random
import string
from typing import Any, Callable, Optional, Dict, List
from datetime import datetime, timedelta
import structlog
from faker import Faker

faker = Faker()

logger = structlog.get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# ОЖИДАНИЯ И ПОВТОРЫ
# ──────────────────────────────────────────────────────────────────────────────

def wait_for_condition(
    condition_func: Callable[[], bool], 
    timeout: int = 5000,   # 5 seconds default - configurable
    interval: int = 100    # 100ms polling for responsiveness
) -> bool:
    """
    Дождаться выполнения условия в течение заданного таймаута (миллисекунды).
    Возвращает True при успехе, иначе False.
    """
    start_time = time.time() * 1000
    end_time = start_time + timeout
    
    while time.time() * 1000 < end_time:
        try:
            if condition_func():
                return True
        except Exception as e:
            logger.debug(f"Condition check failed: {e}")
        time.sleep(interval / 1000)
    return False


def retry_on_failure(
    action_func: Callable[[], Any], 
    max_retries: int = 2,  # Reduced from 3
    delay: int = 500       # Reduced from 1000
) -> Any:
    """
    Повтор выполнения действия при ошибке (минимальная задержка, линейный backoff).
    Возбуждает последнюю ошибку после исчерпания попыток.
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return action_func()
        except Exception as e:
            last_exception = e
            if attempt == max_retries:
                logger.error(f"Action failed after {max_retries} retries: {e}")
                raise e
            sleep_time = (delay + (delay * attempt * 0.5)) / 1000
            logger.warning(f"Attempt {attempt + 1} failed, retrying in {sleep_time}s: {e}")
            time.sleep(sleep_time)

# ──────────────────────────────────────────────────────────────────────────────
# ГЕНЕРАЦИЯ ДАННЫХ
# ──────────────────────────────────────────────────────────────────────────────

def generate_random_string(length: int = 8, prefix: str = "") -> str:
    """Случайная строка с опциональным префиксом."""
    random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return f"{prefix}{random_chars}"


def generate_random_email(domain: str = "test.com") -> str:
    """Случайный email-адрес."""
    username = generate_random_string(8)
    return f"{username}@{domain}"


def generate_random_phone() -> str:
    """Случайный телефонный номер."""
    return f"+1{random.randint(2000000000, 9999999999)}"


def generate_random_amount(min_amount: float = 1.0, max_amount: float = 1000.0) -> float:
    """Случайная сумма с точностью до 2 знаков."""
    return round(random.uniform(min_amount, max_amount), 2)


def generate_account_number() -> str:
    """Случайный номер счёта."""
    return f"ACC{random.randint(100000000, 999999999)}"

# ──────────────────────────────────────────────────────────────────────────────
# ФОРМАТИРОВАНИЕ И ВАЛИДАЦИЯ
# ──────────────────────────────────────────────────────────────────────────────

def format_currency(amount: float, currency: str = "USD") -> str:
    """Форматирование суммы как валюты."""
    if currency == "USD":
        return f"${amount:,.2f}"
    return f"{amount:,.2f} {currency}"


def parse_currency(currency_str: str) -> float:
    """Парсинг валютной строки в число."""
    cleaned = currency_str.replace("$", "").replace(",", "").strip()
    return float(cleaned)


def generate_test_data_id(prefix: str = "test") -> str:
    """Генерация уникального ID тестовых данных."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_suffix = generate_random_string(4)
    return f"{prefix}_{timestamp}_{random_suffix}"


def validate_email_format(email: str) -> bool:
    """Проверка формата email."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_phone_format(phone: str) -> bool:
    """Проверка формата телефона (упрощённая)."""
    import re
    pattern = r'^\+?1?[0-9]{10,15}$'
    cleaned_phone = re.sub(r'[^\d+]', '', phone)
    return re.match(pattern, cleaned_phone) is not None


def validate_amount_format(amount_str: str) -> bool:
    """Проверка, что строка может быть распознана как сумма."""
    try:
        float(amount_str.replace("$", "").replace(",", ""))
        return True
    except:
        return False

# ──────────────────────────────────────────────────────────────────────────────
# ДАТЫ
# ──────────────────────────────────────────────────────────────────────────────

def get_future_date(days: int = 1) -> str:
    """Дата в будущем (YYYY-MM-DD)."""
    future_date = datetime.now() + timedelta(days=days)
    return future_date.strftime("%Y-%m-%d")


def get_past_date(days: int = 1) -> str:
    """Дата в прошлом (YYYY-MM-DD)."""
    past_date = datetime.now() - timedelta(days=days)
    return past_date.strftime("%Y-%m-%d")

# ──────────────────────────────────────────────────────────────────────────────
# ФИЛЬТРЫ ДАННЫХ
# ──────────────────────────────────────────────────────────────────────────────

def clean_test_data_prefix(data_list: List[Dict], prefix: str = "test_") -> List[Dict]:
    """Отфильтровать данные, начинающиеся с заданного префикса."""
    return [item for item in data_list if not str(item.get("email", "")).startswith(prefix)]


def is_test_data(item: Dict, test_indicators: List[str] = None) -> bool:
    """Эвристика: определить, что элемент похож на тестовые данные по индикаторам."""
    if test_indicators is None:
        test_indicators = ["test_", "automation_", "qa_", "temp_"]
    fields_to_check = ["email", "firstName", "lastName", "description", "uniqueId"]
    for field in fields_to_check:
        value = str(item.get(field, "")).lower()
        if any(indicator in value for indicator in test_indicators):
            return True
    return False

# ──────────────────────────────────────────────────────────────────────────────
# ПРОСТЕЙШИЕ РАСЧЁТЫ
# ──────────────────────────────────────────────────────────────────────────────

def calculate_fee(amount: float, fee_percentage: float = 0.05) -> float:
    """Посчитать комиссию как долю от суммы (округление до 2 знаков)."""
    return round(amount * fee_percentage, 2)


def wait_for_element_text_change(
    element_getter: Callable[[], str], 
    initial_text: str, 
    timeout: int = 10000
) -> bool:
    """Wait for element text to change from initial value"""
    def text_changed():
        current_text = element_getter()
        return current_text != initial_text
    
    return wait_for_condition(text_changed, timeout)


def wait_for_element_attribute_change(
    element_getter: Callable[[], Optional[str]], 
    initial_value: Optional[str], 
    timeout: int = 10000
) -> bool:
    """Wait for element attribute to change from initial value"""
    def attribute_changed():
        current_value = element_getter()
        return current_value != initial_value
    
    return wait_for_condition(attribute_changed, timeout)


def create_unique_user_data() -> Dict[str, Any]:
    """Create unique user data for testing"""
    unique_id = generate_test_data_id("user")
    return {
        "firstName": f"Test{generate_random_string(4)}",
        "lastName": f"User{generate_random_string(4)}",
        "email": generate_random_email(),
        # Phone omitted to avoid backend validation issues differing across environments
        "uniqueId": unique_id
    }


def create_unique_account_data() -> Dict[str, Any]:
    """Create minimal valid account data for creation endpoint."""
    return {
        "accountType": random.choice(["CHECKING", "SAVINGS"]),
        "initialBalance": 0.0,  # Explicitly set to 0 as per API requirements
    }


def create_transfer_data(
    from_account: str, 
    to_account: str, 
    amount: Optional[float] = None
) -> Dict[str, Any]:
    """Create transfer data for testing"""
    if amount is None:
        amount = generate_random_amount(1, 100)
    
    return {
        "fromAccountId": from_account,
        "toAccountId": to_account,
        "amount": amount,
        "description": f"Test transfer {generate_test_data_id()}",
        "currency": "USD"
    }


def format_date_for_display(date_str: str) -> str:
    """Format date string for display"""
    try:
        date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return date_obj.strftime("%Y-%m-%d %H:%M")
    except:
        return date_str


def mask_sensitive_data(data: str, mask_char: str = "*", visible_chars: int = 4) -> str:
    """Mask sensitive data keeping only last few characters visible"""
    if len(data) <= visible_chars:
        return mask_char * len(data)
    
    masked_part = mask_char * (len(data) - visible_chars)
    visible_part = data[-visible_chars:]
    return masked_part + visible_part


def safe_get_nested_value(data: Dict, path: str, default: Any = None) -> Any:
    """Safely get nested dictionary value using dot notation"""
    keys = path.split('.')
    current = data
    
    try:
        for key in keys:
            current = current[key]
        return current
    except (KeyError, TypeError):
        return default


def compare_lists_ignore_order(list1: List, list2: List) -> bool:
    """Compare two lists ignoring order"""
    return sorted(list1) == sorted(list2)


def deep_merge_dicts(dict1: Dict, dict2: Dict) -> Dict:
    """Deep merge two dictionaries"""
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    return result 
"""
MiniBank API Client для тестового фреймворка
Синхронный httpx‑клиент с поддержкой арендаторов, авторизации и вспомогательных доменных операций.

Структура:
- APIResponse (обёртка ответа)
- MiniBankAPIClient:
  - Базовая конфигурация/HTTP методы (get/post/put/delete)
  - Аутентификация (login/logout/validate/refresh)
  - Доменные методы (users/accounts/transfers/notifications)
  - Health‑проверки
  - Управление тестовыми данными (учёт созданных сущностей, cleanup)
  - Вспомогательные методы (состояние клиента)
"""

import httpx
import json
import time
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from enum import Enum
import structlog
from urllib.parse import urljoin

# Всегда используем абсолютные импорты для консистентности
from config.settings import settings, UserRole
from utils.helpers import (
    retry_on_failure, 
    generate_random_string,
    generate_random_email,
    generate_random_phone,
    create_unique_user_data,
    create_unique_account_data,
    create_transfer_data
)

logger = structlog.get_logger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Стандартизованная обёртка ответа API
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class APIResponse:
    """Стандартизованная обёртка ответа API."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    message: str = ""
    status_code: int = 200
    error_code: Optional[str] = None
    
    @classmethod
    def from_response(cls, response: httpx.Response) -> 'APIResponse':
        """Сформировать APIResponse из httpx.Response."""
        try:
            data = response.json()
        except:
            data = {"raw_response": response.text}
        
        return cls(
            success=response.status_code < 400,
            data=data,
            message=data.get('message', '') if isinstance(data, dict) else str(data),
            status_code=response.status_code,
            error_code=data.get('error_code') if isinstance(data, dict) else None
        )

# ──────────────────────────────────────────────────────────────────────────────
# Основной клиент MiniBank для тестов
# ──────────────────────────────────────────────────────────────────────────────

class MiniBankAPIClient:
    """
    Клиент для MiniBank: многоарендность, JWT‑авторизация, роли, ретраи, учёт тестовых данных.

    Возможности:
    - Автодобавление tenant‑префикса к путям (кроме /health)
    - Управление токеном, методы login/logout/validate/refresh
    - Высокоуровневые доменные вызовы (пользователи/счета/переводы/уведомления)
    - Учёт созданных сущностей для последующей очистки
    - Контекстный менеджер (cleanup/закрытие клиента)
    """
    
    def __init__(self, base_url: Optional[str] = None, tenant_name: Optional[str] = None):
        """
        Инициализация клиента.
        Args:
            base_url: Базовый URL API (по умолчанию из settings)
            tenant_name: Имя арендатора (по умолчанию из settings)
        """
        self.base_url = base_url or settings.api_config.base_url
        self.tenant_name = tenant_name or settings.tenant_name
        self.timeout = settings.api_config.timeout
        self.retry_count = settings.api_config.retry_count
        self.retry_delay = settings.api_config.retry_delay
        
        # Состояние авторизации
        self.jwt_token: Optional[str] = None
        self.current_user: Optional[Dict[str, Any]] = None
        self.tenant_info: Optional[Dict[str, Any]] = None
        
        # HTTP‑клиент
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            headers={
                "Content-Type": "application/json",
                "Accept": "*/*",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
            }
        )
        
        # Учёт тестовых данных
        self.created_test_data: Dict[str, List[str]] = {
            'users': [],
            'accounts': [],
            'transfers': [],
            'notifications': []
        }
        
        self.logger = logger.bind(client=self.__class__.__name__)
        self.logger.info(f"Initialized API client for tenant: {self.tenant_name}")
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup"""
        self.cleanup_test_data()
        self.logout()
        self.client.close()
    
    # ================================================================
    # Core HTTP Methods
    # ================================================================
    
    def _get_headers(self) -> Dict[str, str]:
        """Сформировать заголовки с токеном и контекстом арендатора."""
        headers = {}
        
        if self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"
        
        # Remove X-Tenant headers to match browser behavior
        # if self.tenant_info:
        #     headers["X-Tenant-ID"] = self.tenant_info["id"]
        #     headers["X-Tenant-Name"] = self.tenant_info["name"]
        
        return headers
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: Optional[float] = None,
        retry: Optional[bool] = None,
    ) -> APIResponse:
        """
        Make HTTP request с per-request timeout и ограниченными ретраями для идемпотентных методов.
        
        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint path
            data: Request body data
            params: Query parameters
            headers: Additional headers
            timeout: per-request timeout в секундах (по умолчанию settings.api_config.timeout)
            retry: включить ретраи (по умолчанию True только для GET)
        
        Returns:
            APIResponse: Standardized response wrapper
        """
        # Build full URL with tenant context
        if not endpoint.startswith('/'):
            endpoint = f'/{endpoint}'
        
        # Add tenant prefix for tenant-scoped endpoints
        # Only /health endpoints are global, everything else needs tenant prefix
        if not endpoint.startswith('/health') and self.tenant_name:
            endpoint = f'/{self.tenant_name}{endpoint}'
        
        # Prepare headers
        request_headers = self._get_headers()
        if headers:
            request_headers.update(headers)
        
        # Prepare request data
        json_data = data if data else None
        
        # Настройки ретраев
        is_idempotent = method.upper() == "GET"
        do_retry = retry if retry is not None else is_idempotent
        max_retries = self.retry_count if do_retry else 0
        base_delay = self.retry_delay
        per_request_timeout = timeout or self.timeout

        def single_attempt() -> APIResponse:
            self.logger.debug(f"Making {method} request to {endpoint}")
            self.logger.debug(f"Request headers: {request_headers}")
            if json_data:
                self.logger.debug(f"Request body: {json_data}")

            response = self.client.request(
                method=method,
                url=endpoint,
                json=json_data,
                params=params,
                headers=request_headers,
                timeout=per_request_timeout,
            )

            api_response = APIResponse.from_response(response)
            if not api_response.success:
                self.logger.warning(
                    f"Request failed: {method} {endpoint}",
                    status_code=api_response.status_code,
                    message=api_response.message,
                )
            return api_response

        # Ограниченные ретраи на 429/5xx/таймаут
        attempt = 0
        last_error: Optional[Exception] = None
        while True:
            try:
                result = single_attempt()
                if not do_retry:
                    return result
                # Повторяем только для 429/5xx
                if result.status_code in (429, 500, 502, 503, 504) and attempt < max_retries:
                    sleep_s = base_delay * (attempt + 1)
                    time.sleep(sleep_s)
                    attempt += 1
                    continue
                return result
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    sleep_s = base_delay * (attempt + 1)
                    time.sleep(sleep_s)
                    attempt += 1
                    continue
                self.logger.error(f"Request failed: {e}")
                return APIResponse(
                    success=False,
                    message=f"Request failed: {str(e)}",
                    status_code=500,
                )

    def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> APIResponse:
        """Make GET request"""
        return self._make_request("GET", endpoint, params=params, timeout=timeout)
    
    def post(self, endpoint: str, data: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> APIResponse:
        """Make POST request"""
        return self._make_request("POST", endpoint, data=data, timeout=timeout, retry=False)
    
    def put(self, endpoint: str, data: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None) -> APIResponse:
        """Make PUT request"""
        return self._make_request("PUT", endpoint, data=data, timeout=timeout, retry=False)
    
    def delete(self, endpoint: str, timeout: Optional[float] = None) -> APIResponse:
        """Make DELETE request"""
        return self._make_request("DELETE", endpoint, timeout=timeout, retry=False)
    
    # ================================================================
    # Authentication Methods
    # ================================================================
    
    def login(self, email: str, password: str) -> APIResponse:
        """
        Login with email and password
        
        Args:
            email: User email
            password: User password
            
        Returns:
            APIResponse: Login response with token and user info
        """
        self.logger.info(f"Logging in user: {email}")
        
        login_data = {
            "email": email,
            "password": password
        }
        
        response = self.post("/auth/login", login_data)
        
        if response.success and response.data:
            self.jwt_token = response.data.get("token")
            self.current_user = response.data.get("user")
            self.tenant_info = response.data.get("tenant")
            
            self.logger.info(
                f"Successfully logged in as {email}",
                role=self.current_user.get("role") if self.current_user else None
            )
        else:
            self.logger.error(f"Login failed for {email}: {response.message}")
        
        return response
    
    def login_as_role(self, role: UserRole) -> APIResponse:
        """
        Login using predefined test user for specific role
        
        Args:
            role: User role to login as
            
        Returns:
            APIResponse: Login response
        """
        test_user = settings.get_user(role)
        return self.login(test_user.email, test_user.password)
    
    def logout(self) -> APIResponse:
        """
        Logout current user
        
        Returns:
            APIResponse: Logout response
        """
        if not self.jwt_token:
            return APIResponse(success=True, message="Already logged out")
        
        self.logger.info("Logging out current user")
        
        response = self.post("/auth/logout")
        
        # Clear authentication state regardless of response
        self.jwt_token = None
        self.current_user = None
        self.tenant_info = None
        
        return response
    
    def validate_token(self) -> APIResponse:
        """
        Validate current JWT token
        
        Returns:
            APIResponse: Token validation response
        """
        if not self.jwt_token:
            return APIResponse(
                success=False,
                message="No token to validate"
            )
        
        return self.post("/auth/validate", {"token": self.jwt_token})
    
    def refresh_token(self) -> APIResponse:
        """
        Refresh JWT token
        
        Returns:
            APIResponse: Token refresh response
        """
        response = self.post("/auth/refresh")
        
        if response.success and response.data:
            self.jwt_token = response.data.get("token")
            self.logger.info("Token refreshed successfully")
        
        return response
    
    # ================================================================
    # User Management Methods
    # ================================================================
    
    def get_users(self, params: Optional[Dict[str, Any]] = None) -> APIResponse:
        """
        Get list of users (ADMIN/SUPPORT only)
        
        Args:
            params: Query parameters for filtering
            
        Returns:
            APIResponse: Users list response
        """
        return self.get("/users", params=params)
    
    def get_user(self, user_id: str) -> APIResponse:
        """
        Get user by ID
        
        Args:
            user_id: User ID
            
        Returns:
            APIResponse: User details response
        """
        return self.get(f"/users/{user_id}")
    
    def create_user(self, user_data: Dict[str, Any]) -> APIResponse:
        """
        Create new user (ADMIN only)
        
        Args:
            user_data: User creation data
            
        Returns:
            APIResponse: User creation response
        """
        response = self.post("/users", user_data)
        
        if response.success and response.data:
            user_id = response.data.get("user", {}).get("id")
            if user_id:
                self.created_test_data['users'].append(user_id)
                self.logger.info(f"Created user: {user_id}")
        
        return response
    
    def update_user(self, user_id: str, user_data: Dict[str, Any]) -> APIResponse:
        """
        Update user
        
        Args:
            user_id: User ID
            user_data: User update data
            
        Returns:
            APIResponse: User update response
        """
        return self.put(f"/users/{user_id}", user_data)
    
    def delete_user(self, user_id: str) -> APIResponse:
        """
        Delete user (ADMIN only)
        
        Args:
            user_id: User ID
            
        Returns:
            APIResponse: User deletion response
        """
        response = self.delete(f"/users/{user_id}")
        
        if response.success:
            # Remove from tracking
            if user_id in self.created_test_data['users']:
                self.created_test_data['users'].remove(user_id)
            self.logger.info(f"Deleted user: {user_id}")
        
        return response
    
    def change_password(self, user_id: str, new_password: str, current_password: str = "password123") -> APIResponse:
        """
        Change user password
        
        Args:
            user_id: User ID
            new_password: New password
            current_password: Current password (default for test users)
            
        Returns:
            APIResponse: Password change response
        """
        password_data = {
            "currentPassword": current_password,
            "newPassword": new_password
        }
        return self.put(f"/users/{user_id}/password", password_data)
    
    # ================================================================
    # Account Management Methods
    # ================================================================
    
    def get_accounts(self, params: Optional[Dict[str, Any]] = None) -> APIResponse:
        """
        Get list of accounts
        
        Args:
            params: Query parameters for filtering
            
        Returns:
            APIResponse: Accounts list response
        """
        return self.get("/accounts", params=params)
    
    def get_account(self, account_id: str) -> APIResponse:
        """
        Get account by ID
        
        Args:
            account_id: Account ID
            
        Returns:
            APIResponse: Account details response
        """
        return self.get(f"/accounts/{account_id}")
    
    def create_account(self, account_data: Dict[str, Any]) -> APIResponse:
        """
        Create new account
        
        Args:
            account_data: Account creation data
            
        Returns:
            APIResponse: Account creation response
        """
        response = self.post("/accounts", account_data)
        
        if response.success and response.data:
            account_id = response.data.get("account", {}).get("id")
            if account_id:
                self.created_test_data['accounts'].append(account_id)
                self.logger.info(f"Created account: {account_id}")
        
        return response
    
    def update_account(self, account_id: str, account_data: Dict[str, Any]) -> APIResponse:
        """
        Update account
        
        Args:
            account_id: Account ID
            account_data: Account update data
            
        Returns:
            APIResponse: Account update response
        """
        return self.put(f"/accounts/{account_id}", account_data)
    
    def delete_account(self, account_id: str) -> APIResponse:
        """
        Delete account
        
        Args:
            account_id: Account ID
            
        Returns:
            APIResponse: Account deletion response
        """
        response = self.delete(f"/accounts/{account_id}")
        
        if response.success:
            # Remove from tracking
            if account_id in self.created_test_data['accounts']:
                self.created_test_data['accounts'].remove(account_id)
            self.logger.info(f"Deleted account: {account_id}")
        
        return response
    
    def get_user_accounts(self, user_id: str) -> APIResponse:
        """
        Get accounts for specific user
        
        Args:
            user_id: User ID
            
        Returns:
            APIResponse: User accounts response
        """
        return self.get(f"/accounts/user/{user_id}")
    
    def get_account_balance(self, account_id: str) -> APIResponse:
        """
        Get account balance
        
        Args:
            account_id: Account ID
            
        Returns:
            APIResponse: Account balance response
        """
        return self.get(f"/accounts/{account_id}")
    
    def get_dashboard_data(self) -> APIResponse:
        """
        Get dashboard summary data
        
        Returns:
            APIResponse: Dashboard data response
        """
        return self.get("/accounts/dashboard")
    
    # ================================================================
    # Transfer and Transaction Methods
    # ================================================================
    
    def create_transfer(self, transfer_data: Dict[str, Any]) -> APIResponse:
        """
        Create money transfer
        
        Args:
            transfer_data: Transfer data
            
        Returns:
            APIResponse: Transfer creation response
        """
        # Creating a transfer triggers accounting, notifications and limits checks
        # on the backend which can occasionally exceed the default timeout. We
        # temporarily bump the timeout for this request.
        response = self.post("/transfers", transfer_data, timeout=90)
        
        if response.success and response.data:
            transfer_id = response.data.get("transaction", {}).get("id")
            if transfer_id:
                self.created_test_data['transfers'].append(transfer_id)
                self.logger.info(f"Created transfer: {transfer_id}")
        
        return response
    
    def get_transfers(self, params: Optional[Dict[str, Any]] = None) -> APIResponse:
        """
        Get list of transfers
        
        Args:
            params: Query parameters for filtering
            
        Returns:
            APIResponse: Transfers list response
        """
        return self.get("/transfers", params=params)
    
    def get_transfer(self, transfer_id: str) -> APIResponse:
        """
        Get transfer by ID
        
        Args:
            transfer_id: Transfer ID
            
        Returns:
            APIResponse: Transfer details response
        """
        return self.get(f"/transfers/{transfer_id}")
    
    def get_transfer_limits(self) -> APIResponse:
        """
        Get transfer limits for current user role
        
        Returns:
            APIResponse: Transfer limits response
        """
        return self.get("/transfers/limits")

    def get_fee_info(self) -> APIResponse:
        """Get global fee information (GET /transfers/fee-info)"""
        return self.get("/transfers/fee-info")

    def calculate_transfer_fee(self, transfer_data: Dict[str, Any]) -> APIResponse:
        """
        Calculate fee for specific transfer
        """
        # Some fee calculations may take longer than the default timeout. Temporarily
        # extend the client timeout so we do not abort the request prematurely.
        return self.post("/transfers/fee-info", transfer_data, timeout=90)
    
    def get_fee_rules(self) -> APIResponse:
        """
        Get current fee rules
        
        Returns:
            APIResponse: Fee rules response
        """
        return self.get("/transfers/fee-rules")
    
    def get_transactions(self, params: Optional[Dict[str, Any]] = None) -> APIResponse:
        """
        Get transaction history
        
        Args:
            params: Query parameters for filtering
            
        Returns:
            APIResponse: Transactions list response
        """
        return self.get("/transactions", params=params)
    
    def get_transaction(self, transaction_id: str) -> APIResponse:
        """
        Get transaction by ID
        
        Args:
            transaction_id: Transaction ID
            
        Returns:
            APIResponse: Transaction details response
        """
        return self.get(f"/transactions/{transaction_id}")
    
    def get_account_transactions(self, account_id: str, params: Optional[Dict[str, Any]] = None) -> APIResponse:
        """
        Get transactions for specific account
        
        Args:
            account_id: Account ID
            params: Query parameters for filtering
            
        Returns:
            APIResponse: Account transactions response
        """
        return self.get(f"/transactions/account/{account_id}", params=params)
    
    def export_transactions(self, params: Optional[Dict[str, Any]] = None) -> APIResponse:
        """
        Export transactions to file
        
        Args:
            params: Export parameters
            
        Returns:
            APIResponse: Export response
        """
        return self.get("/transactions/export", params=params)
    
    # ================================================================
    # Notification Methods
    # ================================================================
    
    def get_notifications(self, params: Optional[Dict[str, Any]] = None) -> APIResponse:
        """
        Get user notifications
        
        Args:
            params: Query parameters for filtering
            
        Returns:
            APIResponse: Notifications list response
        """
        return self.get("/notifications", params=params)
    
    def get_notification(self, notification_id: str) -> APIResponse:
        """
        Get notification by ID
        
        Args:
            notification_id: Notification ID
            
        Returns:
            APIResponse: Notification details response
        """
        return self.get(f"/notifications/{notification_id}")
    
    def mark_notification_read(self, notification_id: str) -> APIResponse:
        """
        Mark notification as read
        
        Args:
            notification_id: Notification ID
            
        Returns:
            APIResponse: Mark read response
        """
        return self.put(f"/notifications/{notification_id}/read")
    
    def mark_all_notifications_read(self) -> APIResponse:
        """
        Mark all notifications as read
        """
        return self.post("/notifications/mark-all-read")
    
    def delete_notification(self, notification_id: str) -> APIResponse:
        """
        Delete notification
        
        Args:
            notification_id: Notification ID
            
        Returns:
            APIResponse: Delete notification response
        """
        return self.delete(f"/notifications/{notification_id}")
    
    def get_unread_count(self) -> APIResponse:
        """
        Get unread notifications count
        
        Returns:
            APIResponse: Unread count response
        """
        return self.get("/notifications/unread-count")
    
    # ================================================================
    # Health Check Methods
    # ================================================================
    
    def health_check(self) -> APIResponse:
        """
        Basic health check (глобальный эндпоинт без tenant и без /api)
        """
        try:
            response = self.client.request(
                method="GET",
                url=f"{settings.test_stand_url}/health",
                timeout=self.timeout,
                headers={"Accept": "*/*"}
            )
            return APIResponse.from_response(response)
        except Exception as e:
            self.logger.error(f"Health check request failed: {e}")
            return APIResponse(success=False, message=str(e), status_code=500)
    
    def detailed_health_check(self) -> APIResponse:
        """
        Detailed health check (глобальный эндпоинт без tenant и без /api)
        """
        try:
            response = self.client.request(
                method="GET",
                url=f"{settings.test_stand_url}/health/detailed",
                timeout=self.timeout,
                headers={"Accept": "*/*"}
            )
            return APIResponse.from_response(response)
        except Exception as e:
            self.logger.error(f"Detailed health check request failed: {e}")
            return APIResponse(success=False, message=str(e), status_code=500)
    
    # ================================================================
    # Test Data Management Methods
    # ================================================================
    
    def create_test_user_with_account(self, role: UserRole = UserRole.USER) -> Dict[str, Any]:
        """
        Create test user with account for testing
        
        Args:
            role: User role
            
        Returns:
            Dict containing user, account, and credentials
        """
        # Generate unique test data
        user_data = create_unique_user_data()
        password = "TestPassword123!"
        
        # Remove uniqueId field as API doesn't accept it
        if "uniqueId" in user_data:
            del user_data["uniqueId"]
        
        # Add role and password
        user_data.update({
            "role": role.value,
            "password": password
        })
        
        # Create user
        user_response = self.create_user(user_data)
        if not user_response.success:
            raise Exception(f"Failed to create test user: {user_response.message}")
        
        user = user_response.data["user"]
        
        # Create account for user
        account_data = create_unique_account_data()
        account_data["userId"] = user["id"]
        
        account_response = self.create_account(account_data)
        if not account_response.success:
            raise Exception(f"Failed to create test account: {account_response.message}")
        
        account = account_response.data["account"]
        
        # Store credentials for login
        credentials = {
            "email": user["email"],
            "password": password
        }
        
        return {
            "user": user,
            "account": account,
            "credentials": credentials
        }
    
    def cleanup_test_data(self) -> None:
        """
        Clean up all created test data
        """
        self.logger.info("Starting test data cleanup")
        
        # Must be logged in as admin to delete data
        if not self.current_user or self.current_user.get("role") != "ADMIN":
            admin_login = self.login_as_role(UserRole.ADMIN)
            if not admin_login.success:
                self.logger.error("Cannot cleanup - failed to login as admin")
                return
        
        # Delete transfers (transactions)
        for transfer_id in self.created_test_data['transfers']:
            try:
                # Transfers are typically not deletable, just log
                self.logger.info(f"Transfer {transfer_id} created during test")
            except Exception as e:
                self.logger.warning(f"Could not process transfer {transfer_id}: {e}")
        
        # Delete accounts
        for account_id in self.created_test_data['accounts']:
            try:
                response = self.delete_account(account_id)
                if response.success:
                    self.logger.info(f"Deleted test account: {account_id}")
                else:
                    self.logger.warning(f"Could not delete account {account_id}: {response.message}")
            except Exception as e:
                self.logger.warning(f"Error deleting account {account_id}: {e}")
        
        # Delete users
        for user_id in self.created_test_data['users']:
            try:
                response = self.delete_user(user_id)
                if response.success:
                    self.logger.info(f"Deleted test user: {user_id}")
                else:
                    self.logger.warning(f"Could not delete user {user_id}: {response.message}")
            except Exception as e:
                self.logger.warning(f"Error deleting user {user_id}: {e}")
        
        # Clear tracking
        self.created_test_data = {
            'users': [],
            'accounts': [],
            'transfers': [],
            'notifications': []
        }
        
        self.logger.info("Test data cleanup completed")
    
    def get_test_data_summary(self) -> Dict[str, Any]:
        """
        Get summary of created test data
        
        Returns:
            Dict with test data summary
        """
        return {
            "users_created": len(self.created_test_data['users']),
            "accounts_created": len(self.created_test_data['accounts']),
            "transfers_created": len(self.created_test_data['transfers']),
            "notifications_created": len(self.created_test_data['notifications']),
            "total_items": sum(len(items) for items in self.created_test_data.values())
        }
    
    # ================================================================
    # Helper Methods
    # ================================================================
    
    def is_authenticated(self) -> bool:
        """
        Check if client is authenticated
        
        Returns:
            bool: True if authenticated
        """
        return self.jwt_token is not None
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """
        Get current authenticated user
        
        Returns:
            Current user data or None
        """
        return self.current_user
    
    def get_current_role(self) -> Optional[str]:
        """
        Get current user role
        
        Returns:
            Current user role or None
        """
        return self.current_user.get("role") if self.current_user else None
    
    def has_role(self, role: Union[str, UserRole]) -> bool:
        """
        Check if current user has specific role
        
        Args:
            role: Role to check
            
        Returns:
            bool: True if user has role
        """
        if isinstance(role, UserRole):
            role = role.value
        
        return self.get_current_role() == role
    
    def wait_for_condition(self, condition_func, timeout: int = 30, interval: int = 1) -> bool:
        """
        Wait for a condition to be met
        
        Args:
            condition_func: Function that returns True when condition is met
            timeout: Maximum time to wait in seconds
            interval: Check interval in seconds
            
        Returns:
            bool: True if condition was met
        """
        start_time = time.time()
        end_time = start_time + timeout
        
        while time.time() < end_time:
            try:
                if condition_func():
                    return True
            except Exception as e:
                self.logger.debug(f"Condition check failed: {e}")
            
            time.sleep(interval)
        
        return False
    
    def __str__(self) -> str:
        """String representation of API client"""
        user_info = f"user={self.current_user.get('email')}" if self.current_user else "not authenticated"
        return f"MiniBankAPIClient(tenant={self.tenant_name}, {user_info})" 
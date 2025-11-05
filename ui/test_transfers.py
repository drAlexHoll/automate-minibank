import pytest
import structlog
from conftest import assert_balance_delta, user_with_two_accounts
from ui.pages.dashboard_page import DashboardPage
from ui.pages.login_page import LoginPage
from ui.pages.transfers_page import TransfersPage

logger = structlog.get_logger(__name__)


class TestTransfers:
    """Тесты для страницы Transfers"""

    def test_transfer_form_elements(self, driver, transfers_page_as_user):
        """Тест для просмотра основных элементов на странице Transfers"""
        transfers_page = transfers_page_as_user["transfers_page"]

        transfers_page.assert_accounts_available(min_count=2)
        accounts_count = len(transfers_page.get_available_accounts())
        logger.info("Accounts count on page Transfers", count=accounts_count)

    def test_simple_transfer_between_accounts(self, driver, api_client, transfers_page_as_user):
        """Тест с успешным переводом ДС со счета на счет"""

        transfers_page = transfers_page_as_user["transfers_page"]
        source_account = transfers_page_as_user["source_account"]
        target_account = transfers_page_as_user["target_account"]

        # Записываем начальные балансы
        source_before = float(source_account["balance"])
        target_before = float(target_account["balance"])

        # Осуществляем перевод
        amount = 50
        transfers_page.make_transfer(
            from_account_id=source_account["id"],
            to_account_id=target_account["id"],
            amount=amount,
            description="UI автотест перевода"
        )

        # Проверяем, что появилось сообщение об успешном переводе
        transfers_page.assert_success_message()
        logger.info("Transfer completed",
                    from_balance_before=source_before,
                    to_balance_before=target_before,
                    amount=amount)

        # Проверяем актуальные балансы через API
        assert_balance_delta(api_client, source_account["id"], target_account["id"], source_before, target_before,
                             delta=amount)

    def test_transfer_insufficient_funds(self, api_client, transfers_page_as_user):
        """Тест переводом большой суммы"""

        transfers_page = transfers_page_as_user["transfers_page"]
        source_account = transfers_page_as_user["source_account"]
        target_account = transfers_page_as_user["target_account"]

        source_before = float(source_account["balance"])
        target_before = float(target_account["balance"])

        too_much = source_before + 500
        transfers_page.make_transfer(
            from_account_id=source_account["id"],
            to_account_id=target_account["id"],
            amount=too_much,
            description="UI автотест перевода"
        )
        transfers_page.assert_error_message()

        # Проверяем баланс (он не должен измениться)
        assert_balance_delta(api_client, source_account["id"], target_account["id"], source_before, target_before,
                             delta=0)

    @pytest.mark.parametrize(
        "amount",
        [0,
         -1000,
         "abc"],
        ids=["Transfer zero amount",
             "Transfer negative amount",
             "Transfer non-numeric amount"]
    )
    def test_invalid_amounts(self, transfers_page_as_user, amount):
        """Тест с вводом невалидных значений"""
        transfers_page = transfers_page_as_user["transfers_page"]
        source_account = transfers_page_as_user["source_account"]
        target_account = transfers_page_as_user["target_account"]

        transfers_page.make_transfer(
            from_account_id=source_account["id"],
            to_account_id=target_account["id"],
            amount=amount,
            description=f"UI автотест: invalid amount {amount}",
        )

        amount_input = transfers_page.selectors["amount_input"]
        validate_message = transfers_page.get_attribute(amount_input, "validationMessage")

        if validate_message:
            transfers_page.logger.info(f"Validation message: {validate_message}")
            return

        transfers_page.assert_error_message()

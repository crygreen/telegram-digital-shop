from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from aiogram import types

from price_list import EXAMPLE_PRICE_LIST, format_price_section, load_price_list
from test_card_payments import DB, MAIN, load_modules


class StarsPaymentsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.original_db = DB.DB_PATH
        self.original_bot = MAIN.bot
        self.telegram = SimpleNamespace(send_photo=AsyncMock(), send_video=AsyncMock(), send_invoice=AsyncMock())
        MAIN.bot = self.telegram
        DB.DB_PATH = str(Path(folder.name) / "test.db")
        DB.init_db()
        DB.add_product("Demo", 100, 60, "preview", "video-file", "video")
        self.product = DB.get_products()[0]

    async def asyncTearDown(self):
        DB.DB_PATH = self.original_db
        MAIN.bot = self.original_bot

    @staticmethod
    def callback(data, user=7):
        return SimpleNamespace(data=data, from_user=SimpleNamespace(id=user),
                               answer=AsyncMock(), message=SimpleNamespace(answer=AsyncMock()))

    async def test_demo_invoice_and_delivery_once(self):
        callback = self.callback(f"pay_stars_{self.product[0]}")
        await MAIN.process_pay_stars(callback)
        self.telegram.send_invoice.assert_not_awaited()
        keyboard = callback.message.answer.await_args.kwargs["reply_markup"]
        button = keyboard.inline_keyboard[0][0].callback_data
        order_id = button.split(":")[1]
        await MAIN.simulate_star_payment(self.callback(button, user=8))
        self.telegram.send_video.assert_not_awaited()
        await MAIN.simulate_star_payment(self.callback(button))
        await MAIN.simulate_star_payment(self.callback(button))
        self.telegram.send_video.assert_awaited_once()
        self.assertEqual(DB.get_star_order(order_id)["status"], "delivered")

    async def test_precheckout_validates_buyer_currency_and_snapshot_amount(self):
        with patch.object(MAIN, "STARS_MODE", "telegram_test"):
            await MAIN.process_pay_stars(self.callback(f"pay_stars_{self.product[0]}"))
            invoice = self.telegram.send_invoice.await_args.kwargs
            self.assertEqual(invoice["currency"], "XTR")
            with sqlite3.connect(DB.DB_PATH) as conn:
                conn.execute('UPDATE products SET price_stars = 99')
            conn.close()
            cases = [(8, "XTR", 60, False), (7, "RUB", 60, False),
                     (7, "XTR", 99, False), (7, "XTR", 60, True)]
            for user, currency, amount, expected in cases:
                query = SimpleNamespace(invoice_payload=invoice["payload"], currency=currency,
                                        total_amount=amount, id="query",
                                        from_user=SimpleNamespace(id=user), answer=AsyncMock())
                await MAIN.process_pre_checkout(query)
                self.assertIs(query.answer.await_args.kwargs["ok"], expected)
            query.id = "second-checkout"
            query.answer.reset_mock()
            await MAIN.process_pre_checkout(query)
            self.assertIs(query.answer.await_args.kwargs["ok"], False)

    async def test_successful_payment_is_routed_and_charge_is_unique(self):
        order_id = DB.create_star_order(7, self.product, "telegram_test")
        second_order = DB.create_star_order(7, self.product, "telegram_test")
        DB.authorize_star_checkout(order_id, 7, 60, "first")
        DB.authorize_star_checkout(second_order, 7, 60, "second")
        update = types.Update.model_validate({
            "update_id": 1, "message": {
                "message_id": 2, "date": 0,
                "chat": {"id": 7, "type": "private"},
                "from": {"id": 7, "is_bot": False, "first_name": "Test"},
                "successful_payment": {
                    "currency": "XTR", "total_amount": 60, "invoice_payload": f"star:{order_id}",
                    "telegram_payment_charge_id": "charge-1", "provider_payment_charge_id": "",
                }
            }
        })
        with patch.object(MAIN, "STARS_MODE", "telegram_test"):
            await MAIN.dp.feed_update(self.original_bot, update)
            await MAIN.dp.feed_update(self.original_bot, update)
        self.telegram.send_video.assert_awaited_once()
        self.assertEqual(DB.get_star_order(order_id)["status"], "delivered")
        self.assertEqual(DB.get_star_order(order_id)["charge_id"], "charge-1")
        self.assertFalse(DB.record_star_payment(second_order, 7, 60, "charge-1", "telegram_test"))

    async def test_delivery_failure_preserves_payment_for_admin_retry(self):
        order_id = DB.create_star_order(7, self.product, "demo")
        DB.record_star_payment(order_id, 7, 60, "test:charge", "demo")
        self.telegram.send_video.side_effect = RuntimeError("transport failure")
        with self.assertLogs(level="ERROR"):
            self.assertFalse(await MAIN.complete_star_delivery(order_id))
        self.assertEqual(DB.get_star_order(order_id)["charge_id"], "test:charge")
        self.assertEqual(DB.get_star_order(order_id)["status"], "delivery_failed")
        self.telegram.send_video.side_effect = None
        message = SimpleNamespace(from_user=SimpleNamespace(id=99), answer=AsyncMock())
        await MAIN.retry_stars_delivery(message, SimpleNamespace(args=order_id))
        self.assertEqual(DB.get_star_order(order_id)["status"], "delivered")

    async def test_test_mode_uses_dedicated_telegram_endpoint(self):
        _, app = load_modules("telegram_test")
        self.addAsyncCleanup(app.bot.session.close)
        self.assertIn("/test/", app.bot.session.api.api_url(app.bot.token, "getMe"))

    async def test_price_list_uses_safe_example_and_keeps_price_modifiers(self):
        data = load_price_list(EXAMPLE_PRICE_LIST)
        result = format_price_section(data["sections"][0])
        self.assertIn("от 92 ₽ / от 37 ⭐", result)
        self.assertIn("+11 ₽ / +3 ⭐", result)
        message = SimpleNamespace(answer=AsyncMock())
        with patch.object(MAIN, "PRICE_LIST", data):
            await MAIN.show_price_list(message)
        self.assertEqual(message.answer.await_count, 2)

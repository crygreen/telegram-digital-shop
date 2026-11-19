import ast
import asyncio
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import tempfile
import types
import unittest
from unittest.mock import AsyncMock, patch


ROOT = Path(__file__).resolve().parents[1]


def load_modules(stars_mode='demo'):
    # Load definitions without opening the real shop database or reading .env.
    tree = ast.parse((ROOT / 'database.py').read_text(encoding='utf-8'))
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name) and node.value.func.id == 'init_db'
    )]
    database = types.ModuleType('database')
    database.__file__ = str(ROOT / 'database.py')
    exec(compile(tree, database.__file__, 'exec'), database.__dict__)
    main = types.ModuleType('shopbot_test')
    main.__file__ = str(ROOT / 'main.py')
    with patch.dict('sys.modules', {'database': database}), patch('dotenv.load_dotenv'), patch.dict(
        os.environ, {'BOT_TOKEN': '123456:' + 'A' * 35, 'ADMIN_ID': '99', 'STARS_MODE': stars_mode}
    ):
        exec(compile((ROOT / 'main.py').read_text(encoding='utf-8'), main.__file__, 'exec'), main.__dict__)
    return database, main


DB, MAIN = load_modules()


class CardPaymentsTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory()
        DB.DB_PATH = str(Path(self.directory.name) / 'test.db')
        DB.init_db()
        DB.add_product('Demo product', 100, 60, 'preview', 'full')
        self.product = DB.get_products()[0]
        self.bot = types.SimpleNamespace(send_photo=AsyncMock(), send_document=AsyncMock(), send_message=AsyncMock())
        self.original_bot = MAIN.bot
        MAIN.bot = self.bot

    async def asyncTearDown(self):
        MAIN.bot = self.original_bot
        self.directory.cleanup()

    def order(self, user_id=7):
        return DB.create_card_order(user_id, self.product)

    def submit(self, order_id):
        return DB.submit_card_receipt(order_id, 7, 'receipt', 'photo')

    def callback(self, data, user_id=99):
        return types.SimpleNamespace(
            data=data, from_user=types.SimpleNamespace(id=user_id),
            answer=AsyncMock(), message=types.SimpleNamespace(answer=AsyncMock())
        )

    async def test_order_reuses_active_request_and_keeps_snapshot(self):
        order_id = self.order()
        self.assertEqual(order_id, self.order())
        with closing(sqlite3.connect(DB.DB_PATH)) as connection:
            with connection:
                connection.execute('UPDATE products SET price_rub = 999, full_photo_id = ?', ('changed',))
        order = DB.get_card_order(order_id)
        self.assertEqual(order['price_rub'], 100)
        self.assertEqual(order['full_photo_id'], 'full')

    async def test_receipt_is_owned_and_can_be_submitted_once(self):
        order_id = self.order()
        self.assertFalse(DB.submit_card_receipt(order_id, 8, 'receipt', 'photo'))
        self.assertTrue(self.submit(order_id))
        self.assertFalse(self.submit(order_id))
        DB.init_db()
        self.assertEqual(DB.get_card_order(order_id)['receipt_id'], 'receipt')

    async def test_approval_requires_receipt_and_admin(self):
        order_id = self.order()
        await MAIN.review_card_order(self.callback(f'card_approve:{order_id}'))
        self.bot.send_photo.assert_not_awaited()
        self.submit(order_id)
        await MAIN.review_card_order(self.callback(f'card_approve:{order_id}', 7))
        self.assertEqual(DB.get_card_order(order_id)['status'], 'submitted')
        self.bot.send_photo.assert_not_awaited()

    async def test_duplicate_approval_delivers_once(self):
        order_id = self.order()
        self.submit(order_id)
        await asyncio.gather(
            MAIN.review_card_order(self.callback(f'card_approve:{order_id}')),
            MAIN.review_card_order(self.callback(f'card_approve:{order_id}'))
        )
        self.assertEqual(self.bot.send_photo.await_count, 1)
        self.assertEqual(DB.get_card_order(order_id)['status'], 'delivered')

    async def test_failed_delivery_can_be_retried_by_admin(self):
        order_id = self.order()
        self.submit(order_id)
        self.bot.send_photo.side_effect = RuntimeError('simulated network failure')
        with self.assertLogs(level='ERROR'):
            await MAIN.review_card_order(self.callback(f'card_approve:{order_id}'))
        self.assertEqual(DB.get_card_order(order_id)['status'], 'delivery_failed')
        self.bot.send_photo.side_effect = None
        await MAIN.review_card_order(self.callback(f'card_retry:{order_id}'))
        self.assertEqual(DB.get_card_order(order_id)['status'], 'delivered')

    async def test_rejection_does_not_deliver(self):
        order_id = self.order()
        self.submit(order_id)
        await MAIN.review_card_order(self.callback(f'card_reject:{order_id}'))
        await MAIN.review_card_order(self.callback(f'card_approve:{order_id}'))
        self.bot.send_photo.assert_not_awaited()
        self.assertEqual(DB.get_card_order(order_id)['status'], 'rejected')

    async def test_receipt_photo_and_pdf_reach_admin(self):
        for receipt_type in ('photo', 'document'):
            order_id = self.order()
            state = types.SimpleNamespace(
                get_data=AsyncMock(return_value={'card_order_id': order_id}), clear=AsyncMock()
            )
            message = types.SimpleNamespace(
                from_user=types.SimpleNamespace(id=7), answer=AsyncMock(),
                photo=[types.SimpleNamespace(file_id='receipt')] if receipt_type == 'photo' else [],
                document=types.SimpleNamespace(file_id='pdf', mime_type='application/pdf', file_size=500)
            )
            await MAIN.receive_card_receipt(message, state)
            self.assertEqual(DB.get_card_order(order_id)['status'], 'submitted')
            DB.change_card_order_status(order_id, 'submitted', 'rejected')
        self.bot.send_photo.assert_awaited_once()
        self.bot.send_document.assert_awaited_once()

    async def test_invalid_receipt_keeps_input_open(self):
        state = types.SimpleNamespace(clear=AsyncMock(), get_data=AsyncMock())
        message = types.SimpleNamespace(photo=[], document=None, answer=AsyncMock())
        await MAIN.receive_card_receipt(message, state)
        state.clear.assert_not_awaited()
        state.get_data.assert_not_awaited()

    async def test_foreign_order_cannot_be_opened(self):
        order_id = self.order()
        state = types.SimpleNamespace(set_state=AsyncMock(), update_data=AsyncMock())
        await MAIN.request_card_receipt(self.callback(f'card_receipt:{order_id}', 8), state)
        state.set_state.assert_not_awaited()

    async def test_new_order_and_admin_queue(self):
        order_id = self.order()
        self.submit(order_id)
        self.assertEqual([order['id'] for order in DB.get_pending_card_orders()], [order_id])
        DB.change_card_order_status(order_id, 'submitted', 'delivered')
        self.assertNotEqual(self.order(), order_id)

    async def test_notification_failure_keeps_receipt_in_queue(self):
        order_id = self.order()
        state = types.SimpleNamespace(
            get_data=AsyncMock(return_value={'card_order_id': order_id}), clear=AsyncMock()
        )
        message = types.SimpleNamespace(
            from_user=types.SimpleNamespace(id=7), answer=AsyncMock(),
            photo=[types.SimpleNamespace(file_id='receipt')], document=None
        )
        self.bot.send_photo.side_effect = RuntimeError('simulated notification failure')
        with self.assertLogs(level='ERROR'):
            await MAIN.receive_card_receipt(message, state)
        self.assertEqual(DB.get_pending_card_orders()[0]['id'], order_id)
        self.assertEqual(DB.get_card_order(order_id)['receipt_id'], 'receipt')


if __name__ == '__main__':
    unittest.main()

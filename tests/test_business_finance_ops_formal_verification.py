"""Unit, local HTTP roundtrip, and Class-A formal verification tests for business-finance-ops."""
from __future__ import annotations

from decimal import Decimal
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import itertools
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'plugins/business-finance-ops/scripts'


def load_mod(name: str):
    spec = importlib.util.spec_from_file_location(f'bfo_{name}', SCRIPTS / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


init_workspace = load_mod('init_workspace')
fx_rates = load_mod('fx_rates')
ledger_engine = load_mod('ledger_engine')
anomaly_and_runway = load_mod('anomaly_and_runway')
build_boards = load_mod('build_boards')


class _MockFxHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = {'amount': 1.0, 'base': 'USD', 'date': '2026-11-24', 'rates': {'CNY': 7.0, 'EUR': 0.8}}
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode('utf-8'))

    def log_message(self, format, *args):
        return


class BusinessFinanceOpsFormalTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.ws = Path(self.tmp.name) / 'business-finance-ops'
        init_workspace.init_workspace(self.ws, base_currency='USD')

    def test_init_workspace_does_not_create_boards_and_seeds_flux_thresholds(self):
        """init_workspace must never pollute <data-dir> with boards/ and must seed fluxMinAbs/fluxMinPct."""
        self.assertFalse((self.ws / 'boards').exists())
        acct = json.loads((self.ws / 'accounts.json').read_text(encoding='utf-8'))
        self.assertEqual(acct['thresholds']['fluxMinAbs'], '100')
        self.assertEqual(acct['thresholds']['fluxMinPct'], '15')
        self.assertIn('costClassMap', acct)

        # Local preview --all --boards-root writes strictly to the preview directory
        preview_root = Path(self.tmp.name) / 'local-preview-boards'
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / 'build_boards.py'),
                str(self.ws),
                '--all',
                '--boards-root',
                str(preview_root),
                '--overwrite-templates',
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        out = json.loads(proc.stdout)
        self.assertEqual(len(out['projected']), 2)
        self.assertFalse((self.ws / 'boards').exists())
        self.assertTrue((preview_root / 'finance-overview-board/assets/data.json').is_file())
        self.assertTrue((preview_root / 'anomaly-audit-board/assets/data.json').is_file())

    def test_real_statement_parsers_stripe_alipay_wechat_ofx_csv_fx_and_boards(self):
        srv = ThreadingHTTPServer(('127.0.0.1', 0), _MockFxHandler)
        port = srv.server_address[1]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        self.addCleanup(srv.server_close)

        snap = fx_rates.update_fx_cache(self.ws, 'USD', symbols=['CNY', 'EUR'], api_base=f'http://127.0.0.1:{port}')
        self.assertEqual(snap['rates']['CNY'], '7.0')

        # 1. Stripe CSV
        stripe_csv = Path(self.tmp.name) / 'stripe.csv'
        stripe_csv.write_text(
            'id,Type,Amount,Fee,Net,Currency,Created (UTC),Description\n'
            'txn_001,charge,100.10,3.20,96.90,usd,2026-11-10 08:00:00,Pro subscription\n',
            encoding='utf-8',
        )
        r1 = ledger_engine.ingest_statement(self.ws, stripe_csv, fmt='stripe')
        self.assertEqual(r1['addedCount'], 2)  # gross inflow + explicit fee outflow
        # Re-ingesting exact same Stripe file must add 0
        self.assertEqual(ledger_engine.ingest_statement(self.ws, stripe_csv, fmt='stripe')['addedCount'], 0)

        # 2. Alipay CSV (GB18030 encoded with preamble lines + 不计收支 skip)
        alipay_csv = Path(self.tmp.name) / 'alipay.csv'
        alipay_text = (
            '支付宝交易记录明细查询\n'
            '账号:[test@example.com]\n'
            '---------------------------------\n'
            '交易时间,交易分类,交易对方,商品说明,收/支,金额,收/付款方式,交易状态,交易订单号\n'
            '2026-11-12 09:00:00,云计算,Aliyun,ECS服务器,支出,70.00,余额宝,交易成功,ALI2026111201\n'
            '2026-11-12 09:05:00,转账,自己,内部转入,不计收支,500.00,余额,交易成功,ALI2026111202\n'
        )
        alipay_csv.write_bytes(alipay_text.encode('gb18030'))
        r2 = ledger_engine.ingest_statement(self.ws, alipay_csv, fmt='alipay', tz_name='Asia/Shanghai')
        self.assertEqual(r2['addedCount'], 1)

        # 3. WeChat Pay CSV (UTF-8 BOM + preamble + ¥ prefix)
        wechat_csv = Path(self.tmp.name) / 'wechat.csv'
        wechat_text = (
            '微信支付账单明细\n'
            '----------------------\n'
            '交易时间,交易类型,交易对方,商品,收/支,金额(元),支付方式,当前状态,交易单号\n'
            '2026-11-13 10:00:00,商户消费,Tencent Cloud,对象存储,支出,¥140.00,零钱,支付成功,WX2026111301\n'
        )
        wechat_csv.write_bytes(b'\xef\xbb\xbf' + wechat_text.encode('utf-8'))
        r3 = ledger_engine.ingest_statement(self.ws, wechat_csv, fmt='wechat', tz_name='Asia/Shanghai')
        self.assertEqual(r3['addedCount'], 1)

        # 4. Bank OFX (SGML style, EUR)
        ofx_file = Path(self.tmp.name) / 'bank.ofx'
        ofx_file.write_text(
            '<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>EUR<BANKTRANLIST>\n'
            '<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261114120000<TRNAMT>-80.00<FITID>OFX-1<NAME>GitHub<MEMO>Team seats</STMTTRN>\n'
            '</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n',
            encoding='utf-8',
        )
        r4 = ledger_engine.ingest_statement(self.ws, ofx_file, fmt='ofx')
        self.assertEqual(r4['addedCount'], 1)

        # 5. Generic CSV (exact Decimal test: 0.10 + 0.20 = 0.30, no float drift)
        gen_csv = Path(self.tmp.name) / 'mercury.csv'
        gen_csv.write_text(
            'id,date,amount,currency,merchant,description\n'
            'm1,2026-11-15,-0.10,USD,Cloudflare,Micro usage 1\n'
            'm2,2026-11-16,-0.20,USD,Cloudflare,Micro usage 2\n',
            encoding='utf-8',
        )
        r5 = ledger_engine.ingest_statement(self.ws, gen_csv, fmt='csv')
        self.assertEqual(r5['addedCount'], 2)

        # Verify exact Decimal conversion & totals:
        # Inflow: 100.10 USD
        # Outflow: 3.20 (Stripe fee) + 70/7=10.00 (Aliyun) + 140/7=20.00 (Tencent) + 80/0.8=100.00 (GitHub) + 0.10 + 0.20 = 133.50 USD
        # Net: 100.10 - 133.50 = -33.40 USD
        report = anomaly_and_runway.analyze_workspace(self.ws, month='2026-11', write_report=True)
        self.assertEqual(report['summary']['inflowTotal'], '100.10')
        self.assertEqual(report['summary']['outflowTotal'], '133.50')
        self.assertEqual(report['summary']['netCashFlow'], '-33.40')
        self.assertEqual(report['spendByCategory']['cloud_infra'], '30.30')
        self.assertEqual(report['thresholds']['minRunwayMonths'], '6')

        b1 = build_boards.project_board(self.ws, 'finance-overview-board', self.ws / 'boards/finance-overview-board')
        b2 = build_boards.project_board(self.ws, 'anomaly-audit-board', self.ws / 'boards/anomaly-audit-board')
        b1_json = json.loads(b1.read_text(encoding='utf-8'))
        self.assertEqual(b1_json['summary']['netCashFlow'], '-33.40')
        self.assertEqual(b1_json['thresholds']['minRunwayMonths'], '6')
        self.assertEqual(json.loads(b2.read_text(encoding='utf-8'))['month'], '2026-11')

    def test_corrupted_ledger_jsonl_fails_closed_with_exact_file_and_line(self):
        """Malformed JSON or missing txHash in ledger.jsonl MUST fail closed in both library and CLI."""
        valid_row = {
            'txHash': 'ok1',
            'date': '2026-11-01',
            'timestamp': '2026-11-01T10:00:00Z',
            'direction': 'outflow',
            'amount': '10.00',
            'currency': 'USD',
            'merchant': 'AWS',
            'description': 'Compute',
            'category': 'cloud_infra',
            'sourceFile': 'aws.csv',
            'sourceLine': 2,
        }
        ledger_path = self.ws / 'ledger.jsonl'
        ledger_path.write_text(json.dumps(valid_row) + '\n{"txHash": "broken", bad json\n', encoding='utf-8')

        # Library-level fail-closed checks
        with self.assertRaises(anomaly_and_runway.LedgerCorruptionError) as ctx_a:
            anomaly_and_runway.analyze_workspace(self.ws, month='2026-11', write_report=False)
        self.assertEqual(ctx_a.exception.line, 2)
        self.assertEqual(Path(ctx_a.exception.path).resolve(), ledger_path.resolve())

        dummy_csv = Path(self.tmp.name) / 'dummy.csv'
        dummy_csv.write_text('id,date,amount,currency,merchant,description\nx1,2026-11-02,-5.00,USD,AWS,Test\n', encoding='utf-8')
        with self.assertRaises(ledger_engine.LedgerCorruptionError) as ctx_l:
            ledger_engine.ingest_statement(self.ws, dummy_csv, fmt='csv')
        self.assertEqual(ctx_l.exception.line, 2)
        self.assertEqual(Path(ctx_l.exception.path).resolve(), ledger_path.resolve())

        # CLI-level structured JSON stderr + non-zero exit code for both scripts
        for cmd in (
            [sys.executable, str(SCRIPTS / 'anomaly_and_runway.py'), str(self.ws), '--month', '2026-11'],
            [sys.executable, str(SCRIPTS / 'ledger_engine.py'), str(self.ws), '--file', str(dummy_csv), '--format', 'csv'],
        ):
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            self.assertNotEqual(proc.returncode, 0)
            err_payload = json.loads(proc.stderr)
            self.assertFalse(err_payload['ok'])
            self.assertEqual(err_payload['error']['code'], 'CORRUPTED_LEDGER_LINE')
            self.assertEqual(err_payload['error']['line'], 2)
            self.assertEqual(Path(err_payload['error']['file']).resolve(), ledger_path.resolve())

        # Missing txHash on a valid JSON object must also fail closed
        ledger_path.write_text(json.dumps(valid_row) + '\n{"amount": "5.00"}\n', encoding='utf-8')
        with self.assertRaises(anomaly_and_runway.LedgerCorruptionError) as ctx_missing:
            anomaly_and_runway.analyze_workspace(self.ws, month='2026-11', write_report=False)
        self.assertEqual(ctx_missing.exception.line, 2)

    def test_low_runway_triggers_on_recurring_only_even_when_base_is_cf_positive(self):
        """One-time windfall making base CF+ must still trigger low_runway when recurringOnly < minRunwayMonths."""
        acct = json.loads((self.ws / 'accounts.json').read_text(encoding='utf-8'))
        acct['cashBalances']['USD'] = '10000.00'
        acct['thresholds']['minRunwayMonths'] = '6'
        (self.ws / 'accounts.json').write_text(json.dumps(acct), encoding='utf-8')

        rows = [
            {'txHash': 'r1', 'date': '2026-11-05', 'timestamp': '2026-11-05T10:00:00Z', 'direction': 'inflow', 'amount': '2000.00', 'currency': 'USD', 'merchant': 'Stripe', 'description': 'MRR', 'category': 'revenue', 'costClass': 'recurring_revenue', 'sourceFile': 'nov.csv', 'sourceLine': 2},
            {'txHash': 'r2', 'date': '2026-11-06', 'timestamp': '2026-11-06T10:00:00Z', 'direction': 'inflow', 'amount': '5000.00', 'currency': 'USD', 'merchant': 'GrantOrg', 'description': 'One-time grant', 'category': 'one_time_revenue', 'costClass': 'one_time_revenue', 'sourceFile': 'nov.csv', 'sourceLine': 3},
            {'txHash': 'r3', 'date': '2026-11-10', 'timestamp': '2026-11-10T10:00:00Z', 'direction': 'outflow', 'amount': '4000.00', 'currency': 'USD', 'merchant': 'Payroll', 'description': 'Team', 'category': 'payroll', 'sourceFile': 'nov.csv', 'sourceLine': 4},
        ]
        (self.ws / 'ledger.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')

        rep = anomaly_and_runway.analyze_workspace(self.ws, month='2026-11', write_report=True)
        self.assertIsNone(rep['scenarios']['base']['runwayMonths'])  # base is CF+ (+3000)
        self.assertEqual(rep['scenarios']['recurringOnly']['runwayMonths'], '5.0')  # 10000 / 2000 = 5.0 < 6
        low_alerts = [a for a in rep['anomalies'] if a['type'] == 'low_runway']
        self.assertEqual(len(low_alerts), 1)
        self.assertEqual(low_alerts[0]['triggeredScenarios'], ['recurringOnly'])
        self.assertIn('recurringOnly', low_alerts[0]['summary'])
        self.assertEqual(rep['thresholds']['minRunwayMonths'], '6')

    def test_connector_format_timezone_inflow_rules_negative_stripe_fee_staging_and_manual_fx(self):
        """Verify --format connector, --timezone naive preservation, inflow rules, negative Stripe fee, --stage-out, and --set-rate."""
        # Manual non-ECB FX rate (e.g. TWD)
        snap = fx_rates.set_manual_rates(self.ws, 'USD', {'TWD': '32.0'}, date_str='2026-11-18')
        self.assertEqual(snap['rates']['TWD'], '32.0')
        self.assertEqual(snap['source'], 'manual')

        # Connector JSON with inflow matching category-rules.json (grant -> one_time_revenue) + foreign TWD outflow
        conn_file = Path(self.tmp.name) / 'connector.json'
        conn_file.write_text(
            json.dumps({
                'transactions': [
                    {
                        'id': 'conn_in_1',
                        'date': '2026-11-18 01:00:00',
                        'amount': '3000.00',
                        'currency': 'USD',
                        'merchant': 'Innovation Fund',
                        'description': 'Annual innovation grant',
                    },
                    {
                        'id': 'conn_out_1',
                        'date': '2026-11-18 02:30:00',
                        'amount': '-3200.00',
                        'currency': 'TWD',
                        'merchant': 'Taipei Supplier',
                        'description': 'Packaging materials',
                        'category': 'inventory',
                    },
                ],
            }),
            encoding='utf-8',
        )
        res_conn = ledger_engine.ingest_statement(self.ws, conn_file, fmt='connector', tz_name='Asia/Shanghai')
        self.assertEqual(res_conn['addedCount'], 2)

        # Stripe CSV with negative fee (refunded fee) staged first via --stage-out then merged via --format connector
        stripe_refund_csv = Path(self.tmp.name) / 'stripe-refund.csv'
        stripe_refund_csv.write_text(
            'id,Type,Amount,Fee,Net,Currency,Created (UTC),Description\n'
            'txn_ref_1,refund,-50.00,-1.50,-48.50,usd,2026-11-19 10:00:00,Customer refund\n',
            encoding='utf-8',
        )
        staged_path = Path(self.tmp.name) / 'staged-stripe.json'
        stage_res = ledger_engine.ingest_statement(self.ws, stripe_refund_csv, fmt='stripe', stage_out=staged_path)
        self.assertTrue(stage_res['staged'])
        self.assertEqual(stage_res['parsedCount'], 2)  # refund outflow + fee refund inflow
        # Staging must not have mutated ledger.jsonl yet (still only 2 rows from connector)
        self.assertEqual(len((self.ws / 'ledger.jsonl').read_text(encoding='utf-8').splitlines()), 2)

        merge_res = ledger_engine.ingest_statement(self.ws, staged_path, fmt='connector')
        self.assertEqual(merge_res['addedCount'], 2)

        rows = [json.loads(ln) for ln in (self.ws / 'ledger.jsonl').read_text(encoding='utf-8').splitlines() if ln.strip()]
        by_ext = {r['externalId']: r for r in rows}

        # Verify naive timestamp kept Asia/Shanghai local date & offset (not forced to UTC)
        self.assertEqual(by_ext['conn_in_1']['date'], '2026-11-18')
        self.assertEqual(by_ext['conn_in_1']['timestamp'], '2026-11-18T01:00:00+08:00')
        # Verify inflow rule matched one_time_revenue + costClass
        self.assertEqual(by_ext['conn_in_1']['category'], 'one_time_revenue')
        self.assertEqual(by_ext['conn_in_1']['costClass'], 'one_time_revenue')
        self.assertEqual(by_ext['conn_in_1']['sourceFormat'], 'connector')

        # Verify negative Stripe fee became inflow with one_time_revenue and preserved original stripe sourceFile/Line
        fee_refund = by_ext['txn_ref_1:fee']
        self.assertEqual(fee_refund['direction'], 'inflow')
        self.assertEqual(fee_refund['amount'], '1.50')
        self.assertEqual(fee_refund['category'], 'payment_fees')
        self.assertEqual(fee_refund['costClass'], 'one_time_revenue')
        self.assertEqual(fee_refund['sourceFormat'], 'stripe')
        self.assertEqual(fee_refund['sourceFile'], 'stripe-refund.csv')
        self.assertEqual(fee_refund['sourceLine'], 2)

        # Verify TWD converted accurately (3200 / 32.0 = 100.00 USD)
        rep = anomaly_and_runway.analyze_workspace(self.ws, month='2026-11', write_report=False)
        self.assertEqual(rep['spendByCategory']['inventory'], '100.00')
        self.assertEqual(rep['summary']['oneTimeInflow'], '3001.50')

    def test_configurable_cost_class_map_for_non_saas_business(self):
        """costClassMap in category-rules.json / accounts.json must override default SaaS cost classes."""
        rules_doc = json.loads((self.ws / 'category-rules.json').read_text(encoding='utf-8'))
        rules_doc['costClassMap'] = {
            'inventory': 'cogs',
            'shipping': 'cogs',
            'showroom_rent': 'fixed_opex',
            'pop_up_booth': 'variable_opex',
        }
        (self.ws / 'category-rules.json').write_text(json.dumps(rules_doc), encoding='utf-8')

        rows = [
            {'txHash': 'e1', 'date': '2026-11-05', 'timestamp': '2026-11-05T10:00:00Z', 'direction': 'inflow', 'amount': '10000.00', 'currency': 'USD', 'merchant': 'Shopify', 'description': 'Orders', 'category': 'revenue', 'sourceFile': 'shop.csv', 'sourceLine': 2},
            {'txHash': 'e2', 'date': '2026-11-06', 'timestamp': '2026-11-06T10:00:00Z', 'direction': 'outflow', 'amount': '3500.00', 'currency': 'USD', 'merchant': 'Factory', 'description': 'Batch 1', 'category': 'inventory', 'sourceFile': 'shop.csv', 'sourceLine': 3},
            {'txHash': 'e3', 'date': '2026-11-07', 'timestamp': '2026-11-07T10:00:00Z', 'direction': 'outflow', 'amount': '500.00', 'currency': 'USD', 'merchant': 'DHL', 'description': 'Freight', 'category': 'shipping', 'sourceFile': 'shop.csv', 'sourceLine': 4},
            {'txHash': 'e4', 'date': '2026-11-08', 'timestamp': '2026-11-08T10:00:00Z', 'direction': 'outflow', 'amount': '1200.00', 'currency': 'USD', 'merchant': 'Landlord', 'description': 'Rent', 'category': 'showroom_rent', 'sourceFile': 'shop.csv', 'sourceLine': 5},
            {'txHash': 'e5', 'date': '2026-11-09', 'timestamp': '2026-11-09T10:00:00Z', 'direction': 'outflow', 'amount': '800.00', 'currency': 'USD', 'merchant': 'Expo', 'description': 'Pop-up', 'category': 'pop_up_booth', 'sourceFile': 'shop.csv', 'sourceLine': 6},
        ]
        (self.ws / 'ledger.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')

        rep = anomaly_and_runway.analyze_workspace(self.ws, month='2026-11', write_report=False)
        self.assertEqual(rep['summary']['cogsTotal'], '4000.00')
        self.assertEqual(rep['summary']['grossProfit'], '6000.00')
        self.assertEqual(rep['summary']['grossMarginPct'], '60.0')
        self.assertEqual(rep['summary']['fixedOpexTotal'], '1200.00')
        self.assertEqual(rep['summary']['variableOpexTotal'], '800.00')

        # Fault injection: invalid costClassMap value must fail closed
        rules_doc['costClassMap']['inventory'] = 'bogus_class'
        (self.ws / 'category-rules.json').write_text(json.dumps(rules_doc), encoding='utf-8')
        with self.assertRaises(ValueError):
            anomaly_and_runway.analyze_workspace(self.ws, month='2026-11', write_report=False)

    def test_class_a_exhaustive_anomaly_matrix_and_missing_fx_fault_injection(self):
        """Class A exhaustive proof: all 2^4 combinations of duplicate, hike, budget breach, and low runway."""
        checked = 0
        for has_dup, has_hike, has_budget_breach, has_low_runway in itertools.product([False, True], repeat=4):
            checked += 1
            with tempfile.TemporaryDirectory() as td:
                tws = Path(td) / 'ws'
                init_workspace.init_workspace(tws, base_currency='USD')
                # Set cash balance: 500 if low runway else 500000
                acct = json.loads((tws / 'accounts.json').read_text(encoding='utf-8'))
                acct['cashBalances']['USD'] = '500.00' if has_low_runway else '500000.00'
                (tws / 'accounts.json').write_text(json.dumps(acct), encoding='utf-8')

                budgets = json.loads((tws / 'budgets.json').read_text(encoding='utf-8'))
                budgets['monthlyBudgets']['software_saas'] = '50.00' if has_budget_breach else '5000.00'
                (tws / 'budgets.json').write_text(json.dumps(budgets), encoding='utf-8')

                rows = [
                    # Historical SaaS vendor charges (Sep & Oct) to establish median = 100.00
                    {'txHash': 'h1', 'date': '2026-09-01', 'timestamp': '2026-09-01T10:00:00Z', 'direction': 'outflow', 'amount': '100.00', 'currency': 'USD', 'merchant': 'Figma', 'description': 'Seats', 'category': 'software_saas', 'sourceFile': 's.csv', 'sourceLine': 1},
                    {'txHash': 'h2', 'date': '2026-10-01', 'timestamp': '2026-10-01T10:00:00Z', 'direction': 'outflow', 'amount': '100.00', 'currency': 'USD', 'merchant': 'Figma', 'description': 'Seats', 'category': 'software_saas', 'sourceFile': 's.csv', 'sourceLine': 2},
                    # Current month charge (Nov): 150.00 (+50% hike) or 100.00 (flat)
                    {'txHash': 'h3', 'date': '2026-11-01', 'timestamp': '2026-11-01T10:00:00Z', 'direction': 'outflow', 'amount': '150.00' if has_hike else '100.00', 'currency': 'USD', 'merchant': 'Figma', 'description': 'Seats', 'category': 'software_saas', 'sourceFile': 's.csv', 'sourceLine': 3},
                ]
                if has_dup:
                    rows.append({'txHash': 'd1', 'date': '2026-11-10', 'timestamp': '2026-11-10T10:00:00Z', 'direction': 'outflow', 'amount': '49.00', 'currency': 'USD', 'merchant': 'Linear', 'description': 'Plan', 'category': 'software_saas', 'sourceFile': 's.csv', 'sourceLine': 4})
                    rows.append({'txHash': 'd2', 'date': '2026-11-11', 'timestamp': '2026-11-11T10:00:00Z', 'direction': 'outflow', 'amount': '49.00', 'currency': 'USD', 'merchant': 'Linear', 'description': 'Plan', 'category': 'software_saas', 'sourceFile': 's.csv', 'sourceLine': 5})

                (tws / 'ledger.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')
                rep = anomaly_and_runway.analyze_workspace(tws, month='2026-11', write_report=False)
                types = {a['type'] for a in rep['anomalies']}
                self.assertEqual('duplicate_charge' in types, has_dup)
                self.assertEqual('vendor_price_hike' in types, has_hike)
                self.assertEqual('budget_exceeded' in types, has_budget_breach)
                self.assertEqual('low_runway' in types, has_low_runway)

        self.assertEqual(checked, 16)

        # Fault injection: converting an uncached foreign currency MUST fail closed, never silently treat as 1:1
        with self.assertRaises(ValueError):
            fx_rates.convert_to_base(Decimal('100.00'), 'JPY', 'USD', {'snapshots': {}})

    def test_managerial_accounting_gross_margin_flux_and_three_runway_scenarios(self):
        """One-time windfall must NOT hide real recurring burn; verify Gross Margin %, MoM Flux, and What-If expansion runway."""
        acct = json.loads((self.ws / 'accounts.json').read_text(encoding='utf-8'))
        acct['cashBalances']['USD'] = '12000.00'
        (self.ws / 'accounts.json').write_text(json.dumps(acct), encoding='utf-8')

        rows = [
            # Prior month (Oct): cloud_infra = 500
            {'txHash': 'o1', 'date': '2026-10-10', 'timestamp': '2026-10-10T10:00:00Z', 'direction': 'outflow', 'amount': '500.00', 'currency': 'USD', 'merchant': 'AWS', 'description': 'Infra', 'category': 'cloud_infra', 'sourceFile': 'oct.csv', 'sourceLine': 2},
            # Current month (Nov): 2000 recurring revenue + 5000 one-time grant; 1000 COGS (cloud_infra) + 3000 fixed_opex
            {'txHash': 'n1', 'date': '2026-11-05', 'timestamp': '2026-11-05T10:00:00Z', 'direction': 'inflow', 'amount': '2000.00', 'currency': 'USD', 'merchant': 'Stripe', 'description': 'MRR', 'category': 'revenue', 'costClass': 'recurring_revenue', 'sourceFile': 'nov.csv', 'sourceLine': 2},
            {'txHash': 'n2', 'date': '2026-11-06', 'timestamp': '2026-11-06T10:00:00Z', 'direction': 'inflow', 'amount': '5000.00', 'currency': 'USD', 'merchant': 'Partner', 'description': 'One-time setup', 'category': 'one_time_revenue', 'costClass': 'one_time_revenue', 'sourceFile': 'nov.csv', 'sourceLine': 3},
            {'txHash': 'n3', 'date': '2026-11-10', 'timestamp': '2026-11-10T10:00:00Z', 'direction': 'outflow', 'amount': '1000.00', 'currency': 'USD', 'merchant': 'AWS', 'description': 'Infra', 'category': 'cloud_infra', 'sourceFile': 'nov.csv', 'sourceLine': 4},
            {'txHash': 'n4', 'date': '2026-11-12', 'timestamp': '2026-11-12T10:00:00Z', 'direction': 'outflow', 'amount': '3000.00', 'currency': 'USD', 'merchant': 'Payroll', 'description': 'Team', 'category': 'payroll', 'sourceFile': 'nov.csv', 'sourceLine': 5},
        ]
        (self.ws / 'ledger.jsonl').write_text('\n'.join(json.dumps(r) for r in rows) + '\n', encoding='utf-8')

        rep = anomaly_and_runway.analyze_workspace(self.ws, month='2026-11', write_report=True, scenario_extra_burn='1000')
        # Total inflow=7000, COGS=1000 -> grossProfit=6000, grossMarginPct=85.7%
        self.assertEqual(rep['summary']['grossProfit'], '6000.00')
        self.assertEqual(rep['summary']['grossMarginPct'], '85.7')
        # Base appears CF+ because of 5000 windfall, but recurringOnly exposes 2000/mo burn -> 12000/2000 = 6.0 mo!
        self.assertIsNone(rep['scenarios']['base']['runwayMonths'])
        self.assertEqual(rep['scenarios']['recurringOnly']['monthlyNetBurn'], '2000.00')
        self.assertEqual(rep['scenarios']['recurringOnly']['runwayMonths'], '6.0')
        # Downside (-20% recurring rev -> 1600): burn = 4000 - 1600 = 2400 -> 12000/2400 = 5.0 mo
        self.assertEqual(rep['scenarios']['downsideRev20']['runwayMonths'], '5.0')
        # Proposed expansion (+1000/mo burn -> 3000/mo): 12000/3000 = 4.0 mo
        self.assertEqual(rep['scenarios']['proposedExpansion']['runwayMonths'], '4.0')
        # Flux: cloud_infra jumped +500 (+100.0%) -> material!
        cloud_flux = [f for f in rep['fluxAnalysis'] if f['category'] == 'cloud_infra'][0]
        self.assertEqual(cloud_flux['delta'], '500.00')
        self.assertEqual(cloud_flux['changePct'], '100.0')
        self.assertTrue(cloud_flux['isMaterial'])


if __name__ == '__main__':
    unittest.main()

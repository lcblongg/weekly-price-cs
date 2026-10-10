import unittest
from unittest.mock import MagicMock, patch
from common import PipelineError
from tools import update_web_local as local


class LocalWebTests(unittest.TestCase):
    def test_idle_returns_without_starting_or_waiting(self):
        with patch.object(local, 'expire_jobs'), patch.object(local, 'active_jobs', return_value=[]), patch.object(local, 'running_workers', return_value={}):
            sleep = MagicMock()
            local.wait_for_idle(MagicMock(), ['fpt'], 0, sleep=sleep)
            sleep.assert_not_called()

    def test_live_remote_job_or_selected_cli_worker_blocks(self):
        for jobs, workers in [([{'id': 'live', 'status': 'running'}], {}), ([], {'fpt': [123]})]:
            with patch.object(local, 'expire_jobs'), patch.object(local, 'active_jobs', return_value=jobs), patch.object(local, 'running_workers', return_value=workers):
                with self.assertRaises(PipelineError):
                    local.wait_for_idle(MagicMock(), ['fpt'], 0, clock=lambda: 10)

    def test_waits_for_existing_job_then_continues(self):
        with patch.object(local, 'expire_jobs'), patch.object(local, 'active_jobs', side_effect=[[{'id':'old'}], []]), patch.object(local, 'running_workers', return_value={}):
            sleep = MagicMock()
            local.wait_for_idle(MagicMock(), ['fpt'], 60, sleep=sleep, clock=lambda: 10)
            sleep.assert_called_once_with(10)

    def test_publication_uses_existing_job_protocol_and_never_telegram(self):
        db = MagicMock()
        job = local.create_job(db, 'daily_prices', ['fpt', 'phongvu'])
        queued = db.table.return_value.insert.call_args.args[0]
        self.assertEqual(queued['id'], job)
        self.assertEqual(queued['payload']['channels'], ['fpt', 'phongvu'])
        self.assertFalse(queued['payload']['send_report'])
        self.assertEqual(queued['payload']['source'], 'local_mac')

    def test_racing_runner_cannot_start_scraping_when_db_lock_rejects(self):
        with patch.object(local, 'wait_for_idle'), patch.object(local, 'create_job', side_effect=RuntimeError('unique conflict')), patch.object(local.subprocess, 'Popen') as process:
            with self.assertRaises(PipelineError):
                local.run_job(MagicMock(), 'daily_prices', ['fpt'], 0)
            process.assert_not_called()

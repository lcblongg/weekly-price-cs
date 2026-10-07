"""Khóa phối hợp discovery, bot giá và job Apple; không gọi mạng."""
import asyncio
import os
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch, AsyncMock
import apple_jobs
import scraper
import discover_products

class PipelineLocks(unittest.TestCase):
    def test_busy_channel_prevents_both_full_pipeline_workers(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(apple_jobs,'LOCKS',Path(folder)):
            with apple_jobs.channel_lock('cellphones'):
                with patch.object(scraper,'_scrape_one',new_callable=AsyncMock) as scrape:
                    result=asyncio.run(scraper.scrape_one('CellphoneS',Namespace(),None,None))
                    self.assertEqual(result['error_kind'],'busy');scrape.assert_not_called()
                with patch.object(discover_products,'_discover_chain',new_callable=AsyncMock) as discover:
                    result=asyncio.run(discover_products.discover_chain('CellphoneS',[],None,None,folder,Namespace(),None,False))
                    self.assertEqual(result['error_kind'],'busy');discover.assert_not_called()

    def test_inherited_worker_cannot_release_parent_publication_lock(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(apple_jobs,'LOCKS',Path(folder)):
            prefix=f"import apple_jobs;from pathlib import Path;apple_jobs.LOCKS=Path({folder!r});"
            with apple_jobs.channel_lock('fpt') as fd:
                env={**os.environ,'WPCS_CHANNEL_LOCK_SLUG':'fpt','WPCS_CHANNEL_LOCK_FD':str(fd)}
                result=subprocess.run([sys.executable,'-c',prefix+"\nwith apple_jobs.channel_lock('fpt'):pass"],env=env,pass_fds=(fd,))
                self.assertEqual(result.returncode,0)
                with self.assertRaises(apple_jobs.Busy):
                    with apple_jobs.channel_lock('fpt'):pass
            with apple_jobs.channel_lock('fpt'):pass

    def test_detects_discovery_and_full_price_cli(self):
        with patch('subprocess.run') as run:
            run.return_value.stdout='111 /x/python scraper.py --chain cps,fpt\n112 /x/python discover_products.py --chain all\n113 /bin/zsh -c python scraper.py --chain all'
            found=apple_jobs.running_workers()
        self.assertEqual(found['cellphones'],[111,112]);self.assertEqual(found['fpt'],[111,112]);self.assertEqual(found['tgdd'],[112])

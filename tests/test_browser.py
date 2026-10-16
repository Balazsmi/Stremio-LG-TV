"""Real Chromium, simulated Stremio responses. No network or TV credentials.

Run: python -m unittest discover -s tests -v
Requires the Python Playwright package and an already installed Chromium.
"""
from pathlib import Path
import unittest

from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://tv.strem.io/'
REMOTE = '<!doctype html><html><body style="background:#100820;color:white"><h1>Stremio test page</h1><button id="remote">Remote target</button></body></html>'


class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def setUp(self):
        self.context = self.browser.new_context(viewport={'width': 1920, 'height': 1080})
        self.page = self.context.new_page()
        self.page.set_default_timeout(8000)
        self.errors = []
        self.page.on('pageerror', lambda error: self.errors.append(str(error)))
        self.loads = 0

        def remote(route):
            self.loads += 1
            route.fulfill(status=200, content_type='text/html', body=REMOTE)

        self.context.route('https://tv.strem.io/**', remote)
        self.page.clock.install()

    def tearDown(self):
        self.context.close()
        self.assertEqual(self.errors, [])

    def launch(self, offline=False):
        self.context.set_offline(offline)
        self.page.goto((ROOT / 'index.html').as_uri())

    def recovery(self):
        self.launch()
        self.page.keyboard.press('ArrowRight')
        expect(self.page.locator('#recovery')).to_be_focused()
        self.page.keyboard.press('Enter')
        expect(self.page.locator('#recovery-panel')).to_be_visible()
        expect(self.page.frame_locator('#stremio-frame').locator('h1')).to_have_text('Stremio test page')

    def test_direct_launch_has_no_iframe_or_warmup_requests(self):
        self.launch()
        self.assertEqual(self.loads, 0)
        self.assertEqual(self.page.locator('iframe').count(), 0)
        self.page.clock.fast_forward(3100)
        expect(self.page).to_have_url(URL)
        self.assertEqual(self.loads, 1)
        self.assertEqual(self.page.locator('iframe').count(), 0)

    def test_remote_navigation_pauses_autostart(self):
        self.launch()
        self.page.keyboard.press('ArrowRight')
        self.page.clock.fast_forward(60000)
        expect(self.page.locator('#recovery')).to_be_focused()
        self.assertEqual(self.loads, 0)
        self.page.keyboard.press('ArrowLeft')
        expect(self.page.locator('#open')).to_be_focused()

    def test_offline_start_remains_recoverable(self):
        self.launch(offline=True)
        self.page.clock.fast_forward(60000)
        expect(self.page.locator('#status')).to_contain_text('offline')
        self.assertEqual(self.loads, 0)
        self.page.locator('#open').click()
        self.assertEqual(self.loads, 0)
        self.context.set_offline(False)
        self.page.locator('#open').click()
        expect(self.page).to_have_url(URL)

    def test_network_return_can_resume_untouched_startup(self):
        self.launch(offline=True)
        self.context.set_offline(False)
        self.page.wait_for_function('navigator.onLine')
        self.page.clock.fast_forward(3100)
        expect(self.page).to_have_url(URL)

    def test_iframe_load_does_not_claim_stremio_is_ready(self):
        self.recovery()
        expect(self.page.locator('#recovery-panel')).to_be_visible()
        expect(self.page.locator('#continue')).to_be_focused()
        expect(self.page.locator('#recovery-status')).to_contain_text('If the menus appear')
        self.page.clock.fast_forward(46000)
        expect(self.page.locator('#recovery-status')).to_contain_text('45 seconds')
        self.assertEqual(self.loads, 1)  # No destructive automatic retries.

    def test_failed_iframe_keeps_retry_controls(self):
        self.context.unroute('https://tv.strem.io/**')
        self.context.route('https://tv.strem.io/**', lambda route: route.abort())
        self.launch()
        self.page.locator('#recovery').click()
        self.page.clock.fast_forward(46000)
        expect(self.page.locator('#retry')).to_be_visible()
        expect(self.page.locator('#recovery-status')).to_contain_text('45 seconds')
        self.page.locator('#home').click()
        expect(self.page.locator('#open')).to_be_focused()

    def test_late_load_does_not_overwrite_slow_start_message(self):
        self.recovery()
        self.page.clock.fast_forward(46000)
        self.page.locator('#stremio-frame').dispatch_event('load')
        expect(self.page.locator('#recovery-status')).to_contain_text('45 seconds')
        expect(self.page.locator('#retry')).to_be_visible()
        self.assertEqual(self.loads, 1)

    def test_manual_retry_creates_new_context(self):
        self.recovery()
        self.page.frame_locator('#stremio-frame').locator('#remote').evaluate('(e) => e.dataset.marker = "old"')
        self.page.locator('#retry').click()
        expect(self.page.frame_locator('#stremio-frame').locator('#remote')).not_to_have_attribute('data-marker', 'old')
        self.assertEqual(self.loads, 2)
        self.assertEqual(self.page.locator('iframe').count(), 1)

    def test_continue_hands_real_keyboard_input_to_iframe(self):
        self.recovery()
        self.page.keyboard.press('Enter')
        expect(self.page.locator('#recovery-panel')).to_be_hidden()
        expect(self.page.locator('#stremio-frame')).to_be_focused()
        self.page.frames[1].evaluate('window.received = []; document.addEventListener("keydown", e => received.push(e.keyCode))')
        self.page.keyboard.press('ArrowDown')
        self.page.keyboard.press('Enter')
        self.assertEqual(self.page.frames[1].evaluate('received'), [40, 13])
        self.page.clock.fast_forward(60000)
        expect(self.page.locator('#recovery-panel')).to_be_hidden()
        self.assertEqual(self.loads, 1)

    def test_relaunch_recovers_remote_focus_without_reloading(self):
        self.recovery()
        self.page.locator('#continue').click()
        self.page.evaluate('document.dispatchEvent(new Event("webOSRelaunch"))')
        expect(self.page.locator('#continue')).to_be_focused()
        expect(self.page.locator('#recovery-panel')).to_be_visible()
        self.assertEqual(self.loads, 1)

    def test_visibility_return_opens_recovery_without_reloading(self):
        self.recovery()
        self.page.locator('#continue').click()
        self.page.evaluate('document.dispatchEvent(new Event("visibilitychange"))')
        expect(self.page.locator('#recovery-panel')).to_be_visible()
        self.assertEqual(self.loads, 1)

    def test_network_drop_does_not_interrupt_playback(self):
        self.recovery()
        self.page.locator('#continue').click()
        self.context.set_offline(True)
        self.page.wait_for_function('!navigator.onLine')
        expect(self.page.locator('#recovery-panel')).to_be_hidden()
        self.context.set_offline(False)
        self.page.wait_for_function('navigator.onLine')
        self.page.clock.fast_forward(60000)
        expect(self.page.locator('#recovery-panel')).to_be_hidden()
        self.assertEqual(self.loads, 1)

    def test_recovery_offline_can_return_to_launcher(self):
        self.launch(offline=True)
        self.page.locator('#recovery').click()
        expect(self.page.locator('#recovery-status')).to_contain_text('No network connection')
        self.page.locator('#continue').click()
        expect(self.page.locator('#recovery-panel')).to_be_visible()
        self.page.locator('#home').click()
        expect(self.page.locator('#launcher')).to_be_visible()

    def test_recovery_can_open_directly(self):
        self.recovery()
        self.page.locator('#direct').click()
        expect(self.page).to_have_url(URL)
        expect(self.page.locator('h1')).to_have_text('Stremio test page')
        self.assertEqual(self.page.locator('iframe').count(), 0)

    def test_back_uses_native_exit_on_launcher(self):
        self.page.add_init_script('window.webOSSystem = {platformBack: function () { window.exitCalled = true; }}')
        self.launch()
        self.page.evaluate('document.dispatchEvent(new KeyboardEvent("keydown", {keyCode: 461, bubbles: true}))')
        self.assertTrue(self.page.evaluate('window.exitCalled'))
        self.page.clock.fast_forward(10000)
        self.assertEqual(self.loads, 0)

    def test_pointer_help_does_not_destroy_frame(self):
        self.recovery()
        self.page.locator('#continue').click()
        self.page.locator('#help').click()
        expect(self.page.locator('#continue')).to_be_focused()
        self.assertEqual(self.loads, 1)

    def test_launcher_layout_at_1080p(self):
        self.launch()
        self.page.keyboard.press('ArrowUp')
        for element in self.page.locator('#launcher button').all():
            box = element.bounding_box()
            self.assertGreaterEqual(box['x'], 0)
            self.assertLessEqual(box['x'] + box['width'], 1920)
            self.assertLessEqual(box['y'] + box['height'], 1080)
        (ROOT / 'artifacts').mkdir(exist_ok=True)
        self.page.screenshot(path=str(ROOT / 'artifacts' / 'launcher.png'))


if __name__ == '__main__':
    unittest.main()

"""Real Chromium check against an isolated test ingress server and archived HiGHS inputs.

HA session discovery is mocked; the browser, HTTP handlers, archive and worker are real.
Run: PYTHONPATH=energymanager/src .venv/bin/python tools/check_gui_browser.py SNAPSHOT_ID
Requires the development-only playwright package and Chromium (system or Playwright install).
"""
import argparse
import asyncio
import shutil
from pathlib import Path

from aiohttp import web
from playwright.async_api import async_playwright

from energymanager.decision_store import DecisionStore
from energymanager.explanation_api import ExplanationAPI


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('snapshot_id')
    args = parser.parse_args()
    api = ExplanationAPI(DecisionStore(Path('.v3-evidence/archive')), trusted_peer='127.0.0.1', cooldown=0)
    source = Path('energymanager-dashboard/energymanager-timeline-card.js').read_text()
    source = source[source.index('// V3 evidence viewer:'):]
    # Own immutable test code only, not archive content, is embedded in HTML.
    html = '<html><body style="font:16px sans-serif;max-width:1300px;margin:auto"><script>' + source + '''
const card = document.createElement('energymanager-decision-details');
card.setConfig({addon:'local_energy_manager'}); document.body.appendChild(card);
card.hass = {callWS: async request => request.endpoint.endsWith('/info') ?
  {ingress_url:'/api/hassio_ingress/token'} : {session:'test-session'}};
window.card = card;
</script></body></html>'''
    app = web.Application()
    app.add_subapp('/api/hassio_ingress/token', api.app())

    async def page(request):
        return web.Response(text=html, content_type='text/html')
    app.router.add_get('/', page)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(executable_path=shutil.which('chromium'),
                                                       args=['--no-sandbox'])
            page = await browser.new_page(viewport={'width': 1440, 'height': 1100},
                                           extra_http_headers={'X-Ingress-Path': '/api/hassio_ingress/token'})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            await page.goto(f'http://127.0.0.1:{port}/')
            await page.wait_for_function('window.card?._decision')
            await page.evaluate('(id) => window.card.load(id)', args.snapshot_id)
            assert 'passed' in await page.locator('[data-quality]').inner_text()
            options = await page.locator('[data-selection] option').all_text_contents()
            assert any(text.startswith('EV session:') for text in options)
            assert any(text.startswith('Requirement:') for text in options)
            await page.locator('[data-selection]').select_option(index=0)
            await page.locator('[data-start]').select_option('0')
            await page.locator('[data-end]').select_option('4')
            await page.locator('[data-run]').click()
            await page.wait_for_function('!window.card._jobRunning', timeout=75000)
            assert 'completed' in await page.locator('[data-job]').inner_text()
            assert 'economic confidence' in await page.locator('[data-result]').inner_text()
            await page.screenshot(path='.v3-evidence/gui-browser.png', full_page=True)
            assert not errors, errors
            await browser.close()
            print('Chromium: history, selection, evidence and isolated counterfactual passed; no page errors')
    finally:
        await runner.cleanup()


if __name__ == '__main__':
    asyncio.run(main())

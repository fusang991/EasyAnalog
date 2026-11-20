const assert = require('node:assert/strict');
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    page.on('pageerror', error => console.error(error));
    await page.goto('http://127.0.0.1:8080/');
    async function ready() {
      await page.waitForFunction(() => document.getElementById('status').textContent.startsWith('ngspice 已完成'), undefined, {timeout: 60000});
    }
    const read = async id => parseFloat((await page.locator(id).textContent()).replaceAll(',', ''));
    await ready();
    assert(Math.abs(await read('#op') - 1) < 0.001);
    assert(Math.abs(await read('#ac') - Math.SQRT1_2) < 0.0002);
    assert(Math.abs(await read('#angle') + 45) < 0.03);
    console.log('ngspice cutoff cursor:', await page.locator('#cursor').textContent());
    await page.locator('#probe').selectOption('i');
    assert(Math.abs(await read('#ac') - Math.SQRT1_2) < 0.0002);
    await page.locator('#r').fill('2');
    await ready();
    await page.locator('#cutoff').click();
    await ready();
    assert(Math.abs(Number(await page.locator('#f').inputValue()) - 79.57747) < 0.001);
    assert(Math.abs(await read('#ac') - 0.35355) < 0.0001);
    await page.locator('[data-mode=phase]').click();
    assert.equal(await page.locator('[data-mode=phase]').getAttribute('aria-pressed'), 'true');
    console.log('R = 2 kΩ:', await page.locator('#ac').textContent(), await page.locator('#cursor').textContent());
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });

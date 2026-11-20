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
    async function checkWave() {
      const stats = await page.evaluate(() => {
        const {amp, dc, f, fc, R, C, duration} = settings;
        let maxError = 0;
        for (const [t, vin, vout] of result.wave) {
          const angle = 2 * Math.PI * f * t, ratio = f / fc;
          const expected = dc + amp * (Math.sin(angle) - ratio * Math.cos(angle)
            + ratio * Math.exp(-t / (R * C))) / (1 + ratio ** 2);
          maxError = Math.max(maxError, Math.abs(vout - expected), Math.abs(vin - dc - amp * Math.sin(angle)));
        }
        return {maxError, duration, start: result.wave[0][0], end: result.wave.at(-1)[0]};
      });
      assert.equal(stats.start, 0);
      assert(Math.abs(stats.end / stats.duration - 1) < 1e-7);
      assert(stats.maxError < 0.001, 'Waveform deviation: ' + stats.maxError + ' V');
      assert.equal(await page.locator('#timeChart polyline').count(), 2);
      console.log('Waveform max error (V):', stats.maxError);
    }
    await checkWave();
    await page.locator('#f').fill('420');
    await ready();
    await checkWave();
    const slider = page.locator('#timeSlider');
    await slider.focus();
    await slider.press('Home');
    assert.match(await page.locator('#timeReadout').textContent(), /t = 0 ms.*Vin = 1 V.*Vout = 1 V/);
    await slider.press('End');
    assert.match(await page.locator('#timeReadout').textContent(), /t = 7.1429 ms/);
    await page.locator('#engine').selectOption('exact');
    await checkWave();

  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });

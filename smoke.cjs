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
    const timeTab = page.getByRole('tab', { name: '时域波形' });
    const freqTab = page.getByRole('tab', { name: '频率响应' });
    assert.equal(await page.getByRole('tabpanel').count(), 1);
    assert.equal(await timeTab.getAttribute('aria-selected'), 'true');
    await freqTab.click();
    assert.equal(await page.locator('#timeChart').isVisible(), false);
    assert.equal(await page.locator('#chart').isVisible(), true);
    console.log('ngspice cutoff cursor:', await page.locator('#cursor').textContent());
    const freqSlider = page.getByRole('slider', {name:'频率游标'});
    const cursor = page.locator('#cursor');
    await freqSlider.press('End');
    assert.match(await cursor.textContent(), /15\.9 kHz.*-40 dB.*-89\.42/);
    const endReading = await cursor.textContent();
    await page.locator('[data-mode=phase]').click();
    assert.equal(await cursor.textContent(), endReading);
    await freqSlider.press('Home');
    assert.match(await cursor.textContent(), /1\.59 Hz.*-0\.57\d*°/);
    const center = await page.locator('#chart').evaluate(svg => {
      const frame = plotFrame(svg);
      return {x:(frame.left+frame.right)/2, y:(frame.top+frame.bottom)/2};
    });
    await page.locator('#chart').click({position:center});
    assert.match(await cursor.textContent(), /159 Hz.*-3\.0103 dB.*-45°/);
    assert.equal(await page.locator('#f').inputValue(), '159.155');
    await page.locator('[data-mode=mag]').click();
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
    await freqTab.focus();
    await freqTab.press('ArrowLeft');
    assert.equal(await timeTab.getAttribute('aria-selected'), 'true');
    assert.equal(await page.getByRole('tabpanel').count(), 1);
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

    async function switchCase(id) {
      await page.selectOption('#case', id);
      await page.selectOption('#engine', 'spice');
      await ready();
      assert.equal(new URL(page.url()).searchParams.get('case'), id);
      assert.equal(await page.locator('#timeChart polyline').count(), 2);
    }
    await switchCase('highpass');
    assert(Math.abs(await read('#op')) < 1e-8);
    assert(Math.abs(await read('#angle') - 45) < 0.03);
    assert(Math.abs(await read('#ac') - Math.SQRT1_2) < 0.0002);
    const highpassError = await page.evaluate(() => Math.max(...result.wave.map(([t, vin, vout]) => {
      const {f, fc, dc, amp, R, C} = settings;
      const angle = 2 * Math.PI * f * t, ratio = f / fc;
      const lowpass = dc + amp * (Math.sin(angle) - ratio * Math.cos(angle)
        + ratio * Math.exp(-t / (R * C))) / (1 + ratio ** 2);
      return Math.abs(vout - (vin - lowpass));
    })));
    assert(highpassError < 0.001);
    await page.selectOption('#engine', 'exact');
    assert(Math.abs(await read('#angle') - 45) < 0.03);
    await switchCase('common-source');
    assert(Math.abs(await read('#op') - 3.825) < 0.01);
    assert(Math.abs(await read('#ac') / 0.05 - 4.7) < 0.02);
    assert(await read('#angle') > 175);
    await page.selectOption('#probe', 'i');
    assert(Math.abs(await read('#op') - 0.25) < 0.001);
    await page.locator('#amp').fill('0.5');
    await ready();
    const swing = await page.evaluate(() => result.wave.map(row => row[2]));
    assert(Math.min(...swing) < 1.5 && Math.max(...swing) > 4.9);

    await switchCase('follower');
    const output = await read('#op');
    assert(Math.abs(output - 1.032) < 0.005);
    assert(Math.abs(await read('#ac') / 0.1 - 0.815) < 0.005);
    assert(Math.abs(await read('#angle')) < 1);
    await page.locator('[data-probe=vdd]').click();
    assert.equal(await read('#op'), 5);
    await page.locator('#dc').fill('1.9');
    await ready();
    await page.selectOption('#probe','out');
    assert(await read('#op') < output - 0.2);
    console.log('Verified high-pass, common-source amplification and source follower.');
    await page.getByRole('link', {name:'电路图册'}).click();
    await page.locator('#chapter').selectOption('第3章');
    await page.getByRole('link', {name:'电阻负载共源放大器', exact:true}).click();
    await page.waitForFunction(()=>document.querySelector('#figure').naturalWidth>0);
    assert.equal(await page.locator('#title').textContent(), '电阻负载共源放大器');
    await page.getByRole('link', {name:'打开对应仿真'}).click();
    await ready();
    assert.equal(await page.locator('#case').inputValue(),'c03-01');
    await require('./atlas-smoke.cjs')(page);

  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });

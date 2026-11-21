const assert = require('node:assert/strict');

module.exports = async function verifyExperiments(page) {
  const cases = await page.locator('#case optgroup option').evaluateAll(options => options.map(o => o.value));
  assert.equal(cases.length, 205);
  async function ready(id) {
    await page.waitForFunction(id =>
      document.querySelector('#case').value === id &&
      /ngspice 已完成|仿真未完成|加载失败/.test(document.querySelector('#status').textContent), id);
    assert.match(await page.locator('#status').textContent(), /ngspice 已完成/, id);
  }
  async function open(id) {
    await page.selectOption('#case', id);
    await ready(id);
  }
  for (const id of cases) {
    await open(id);
    const metrics = await page.evaluate(() => ({
      bias: result.dc[1],
      ac: result.points.length,
      time: result.wave.at(-1)[0],
      duration: settings.duration,
      noAC: settings.noAC,
      finite: result.wave.every(row => row.every(Number.isFinite))
    }));
    assert(metrics.finite && Number.isFinite(metrics.bias), id);
    assert(metrics.time >= metrics.duration * (1 - 1e-6), id);
    if (!metrics.noAC) assert(metrics.ac > 10, id);
    assert.equal(await page.locator('#freq-tab').isDisabled(), metrics.noAC, id);
  }
  await open('c06-01');
  await page.click('#freq-tab');
  const amplitude = () => page.evaluate(() => Math.hypot(result.volt[1].real, result.volt[1].img));
  assert(Math.abs(await amplitude() - Math.SQRT1_2) < .001);
  await page.getByLabel('R（kΩ）', {exact:true}).fill('2');
  await ready('c06-01');
  assert(Math.abs(await amplitude() - 1/Math.sqrt(5)) < .001);
  await open('c05-02');
  assert(Math.abs(await page.evaluate(() => result.dc[1])-100) < 5);
  await page.selectOption('#probe','K');
  await ready('c05-02');
  assert.equal(await page.evaluate(() => settings.outputUnit),'V');
  assert.match(await page.locator('#cursor').textContent(), /dBΩ/);
  const svg = page.frames().find(frame => frame.url().endsWith('/diagrams/c05-02.svg'));
  await svg.getByRole('button', {name:'测量 VDD', exact:true}).first().click();
  await ready('c05-02');
  assert.equal(await page.locator('#probe').inputValue(),'VDD');
  assert(Math.abs(await page.evaluate(() => result.dc[1])-5)<1e-5);
  await open('c01-04');
  await page.getByLabel('位移 / 初始间距',{exact:true}).fill('0');
  await ready('c01-04');
  assert(await amplitude() < 1e-6);
  await open('c04-13');
  assert(await page.locator('#time-panel').isVisible());
  await open('c09-56');
  assert.match(await page.locator('#net').textContent(), /PULSE/);
  assert(Math.abs(await page.evaluate(()=>result.wave.at(-1)[2])-.95)<.01);
  console.log('Verified all 205 catalog experiments, parameter changes, nodal and current probes, AC units and step response.');
};

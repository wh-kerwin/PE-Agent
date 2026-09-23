import { expect, test } from '@playwright/test'
import { DEMO_CASE_ID } from '../../src/demo/fixtures'
import { installCaseAnalysisRoutes } from './mocks'

const DEMO_CASE_BUTTON = `AI 分析 ${DEMO_CASE_ID}`

test('successful analysis shows report, evidence, and review', async ({ page }) => {
  await installCaseAnalysisRoutes(page, 'success')
  await page.goto('/')
  await page.getByRole('button', { name: DEMO_CASE_BUTTON }).click()

  await expect(page.getByRole('heading', { name: 'LOT001 良率下降分析' })).toBeVisible()
  await expect(page.getByText('腔体压力漂移可能导致良率损失')).toBeVisible()
  await page.getByText('腔体压力在 01:23 UTC 超出有效上控制限。').first().click()
  await page.getByRole('button', { name: '查看原始数据 EV-SPC-01' }).first().click()

  await page.getByText('确认分析结论').click()
  await page.getByRole('textbox', { name: '确认的假设' }).click()
  await page.locator('.arco-select-option').filter({ hasText: '腔体压力漂移可能导致良率损失' }).click()
  await page.getByRole('button', { name: '保存复核' }).click()
  await expect(page.getByText(/已保存 · Revision 1/)).toBeVisible()
  await page.getByRole('button', { name: '保存到 Case Book' }).click()
  await expect(page.getByText('已归档 Case Book')).toBeVisible()
})

test('partial result preserves report and makes data gap prominent', async ({ page }) => {
  await installCaseAnalysisRoutes(page, 'partial')
  await page.goto('/')
  await page.getByRole('button', { name: DEMO_CASE_BUTTON }).click()

  await expect(page.getByText('部分结果：可用内容已保留')).toBeVisible()
  await expect(page.getByText(/FDC 明细不可用/)).toBeVisible()
  await expect(page.getByRole('heading', { name: 'LOT001 良率下降分析' })).toBeVisible()
})

test('refresh recovers task and completes from SSE without creating a duplicate', async ({ page }) => {
  let createRequests = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && new URL(request.url()).pathname === '/api/ai/case-analysis') createRequests += 1
  })
  await installCaseAnalysisRoutes(page, 'refresh')
  await page.goto('/')
  await page.getByRole('button', { name: DEMO_CASE_BUTTON }).click()
  await expect(page.getByRole('heading', { name: 'LOT001 良率下降分析' })).toBeVisible()

  await page.reload()
  await page.getByRole('button', { name: DEMO_CASE_BUTTON }).click()
  await expect(page.getByRole('heading', { name: 'LOT001 良率下降分析' })).toBeVisible()
  expect(createRequests).toBe(0)
})

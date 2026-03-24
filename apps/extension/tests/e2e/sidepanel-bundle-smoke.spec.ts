import { test, expect } from '@playwright/test'
import { launchWithExtensionOrSkip } from "./utils/real-server"
import path from 'path'
import { launchWithExtension } from './utils/extension'

test.describe('Packaged sidepanel bundle', () => {
  test('renders a non-blank sidepanel surface from the built artifact', async () => {
    const extPath = path.resolve('build/chrome-mv3')
    const { context, openSidepanel } = (await launchWithExtensionOrSkip(test, extPath)) as any
    const page = await openSidepanel()

    await page.waitForLoadState('domcontentloaded')
    await expect
      .poll(
        async () =>
          page.evaluate(() => {
            const bodyText = document.body?.innerText?.trim() || ''
            const root = document.querySelector('#root')
            return {
              textLength: bodyText.length,
              rootChildren: root?.childElementCount ?? 0
            }
          }),
        { timeout: 10000 }
      )
      .toMatchObject({
        textLength: expect.any(Number),
        rootChildren: expect.any(Number)
      })
    await expect
      .poll(
        async () => {
          const snapshot = await page.evaluate(() => {
            const bodyText = document.body?.innerText?.trim() || ''
            const root = document.querySelector('#root')
            return {
              textLength: bodyText.length,
              rootChildren: root?.childElementCount ?? 0
            }
          })
          return snapshot.textLength > 20 || snapshot.rootChildren > 0
        },
        { timeout: 10000 }
      )
      .toBe(true)

    await context.close()
  })
})

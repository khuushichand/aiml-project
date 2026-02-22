import { test, expect } from '@playwright/test'
import { launchWithBuiltExtension } from './utils/extension-build'
import { MockTldwServer } from './utils/mock-server'
import { grantHostPermission } from './utils/permissions'
import { forceConnected, waitForConnectionStore } from './utils/connection'

const escapeRegex = (value: string) =>
  value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const TEST_API_KEY =
  process.env.TLDW_E2E_API_KEY || 'THIS-IS-A-SECURE-KEY-123-FAKE-KEY'

const normalizeServerUrl = (value: string) =>
  value.match(/^https?:\/\//) ? value : `http://${value}`

const fetchWithTimeout = async (
  url: string,
  init: RequestInit | undefined,
  timeoutMs = 15000
) => {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(url, {
      ...init,
      signal: controller.signal
    })
  } finally {
    clearTimeout(timeout)
  }
}

const requestJson = async (
  serverUrl: string,
  path: string,
  init?: RequestInit
) => {
  const response = await fetchWithTimeout(`${serverUrl}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': TEST_API_KEY,
      ...(init?.headers || {})
    }
  })
  const text = await response.text().catch(() => '')
  if (!response.ok) {
    throw new Error(
      `Request failed ${response.status} ${response.statusText}: ${text}`
    )
  }
  if (!text) return null
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

const parseListPayload = (payload: any): any[] => {
  if (Array.isArray(payload)) return payload
  if (!payload || typeof payload !== 'object') return []
  return payload.items || payload.results || payload.data || payload.characters || []
}

type CharacterSeedOverrides = Partial<{
  description: string
  greeting: string
  first_message: string
  system_prompt: string
}>

const createCharacterViaApi = async (
  serverUrl: string,
  name: string,
  overrides: CharacterSeedOverrides = {}
) => {
  const payload = {
    name,
    description: `${name} description`,
    greeting: `Hello from ${name}`,
    first_message: `Hello from ${name}`,
    system_prompt: `You are ${name}.`,
    ...overrides
  }
  const created = await requestJson(serverUrl, '/api/v1/characters/', {
    method: 'POST',
    body: JSON.stringify(payload)
  }).catch(() =>
    requestJson(serverUrl, '/api/v1/characters', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  )
  return created?.id != null ? String(created.id) : null
}

const deleteCharacterById = async (serverUrl: string, characterId: string) => {
  const details = await requestJson(
    serverUrl,
    `/api/v1/characters/${characterId}`
  ).catch(() => null)
  const expectedVersion = Number(details?.version)
  const versionSuffix =
    Number.isInteger(expectedVersion) && expectedVersion >= 0
      ? `?expected_version=${expectedVersion}`
      : ''

  await requestJson(
    serverUrl,
    `/api/v1/characters/${characterId}${versionSuffix}`,
    {
      method: 'DELETE'
    }
  ).catch(() =>
    requestJson(serverUrl, `/api/v1/characters/${characterId}`, {
      method: 'DELETE'
    }).catch(() => null)
  )
}

const listAllCharacters = async (serverUrl: string) => {
  const all: any[] = []
  const pageSize = 100
  for (let page = 0; page < 50; page += 1) {
    const offset = page * pageSize
    const path = `/api/v1/characters/?limit=${pageSize}&offset=${offset}`
    const response = await requestJson(serverUrl, path)
      .catch(() =>
        requestJson(serverUrl, path.replace('/?', '?'))
      )
      .catch(() => null)
    const items = parseListPayload(response)
    if (!items.length) break
    all.push(...items)
    if (items.length < pageSize) break
  }
  return all
}

const deleteCharactersByPrefix = async (serverUrl: string, prefix: string) => {
  const queryPath = `/api/v1/characters/query?page=1&page_size=100&query=${encodeURIComponent(prefix)}`
  const result = await requestJson(serverUrl, queryPath).catch(() => null)
  let characters = parseListPayload(result)
  if (!characters.length) {
    characters = await listAllCharacters(serverUrl).catch(() => [])
  }
  const matches = characters.filter((item: any) =>
    String(item?.name || '').startsWith(prefix)
  )
  await Promise.all(
    matches
      .map((item: any) => (item?.id != null ? String(item.id) : null))
      .filter(Boolean)
      .map((id: string) => deleteCharacterById(serverUrl, id))
  )
}

const findVisibleLocator = async (locator: any, timeoutMs = 10000) => {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const count = Math.min(await locator.count(), 20)
    for (let index = 0; index < count; index += 1) {
      const candidate = locator.nth(index)
      const visible = await candidate
        .isVisible({ timeout: 500 })
        .then(() => true)
        .catch(() => false)
      if (visible) return candidate
    }
    await new Promise((resolve) => setTimeout(resolve, 200))
  }
  return null
}

const openCharacterSelectMenu = async (page: any) => {
  const triggerLocator = page.locator(
    "button[aria-label*='Select character' i], button[aria-label*='Clear character' i]"
  )
  let trigger = await findVisibleLocator(triggerLocator)
  if (!trigger) {
    const startChat = await findVisibleLocator(
      page.getByRole('button', { name: /Start chatting/i })
    )
    if (startChat) {
      await startChat.click()
      await page.waitForTimeout(400)
    }
    trigger = await findVisibleLocator(triggerLocator)
  }
  if (!trigger) {
    throw new Error('Character select trigger not visible in current chat layout.')
  }
  await trigger.click()
  return trigger
}

const ensureConnected = async (page: any, serverUrl: string, label: string) => {
  await waitForConnectionStore(page, `${label}:wait-store`)
  await forceConnected(page, { serverUrl }, `${label}:force-connected`)
}

const seedConfig = (page: any, serverUrl: string) =>
  page.evaluate(
    (cfg) =>
      new Promise<void>((resolve) => {
        // @ts-ignore
        chrome.storage.local.set({ tldwConfig: cfg }, () => resolve())
      }),
    { serverUrl, authMode: 'single-user', apiKey: TEST_API_KEY }
  )

const setupExtensionForServer = async (server: MockTldwServer) => {
  const { context, page, extensionId, optionsUrl } =
    await launchWithBuiltExtension()

  const granted = await grantHostPermission(
    context,
    extensionId,
    `${server.url}/*`
  )
  if (!granted) {
    await context.close()
    return { granted, context: undefined, page: undefined, extensionId, optionsUrl }
  }

  await page.goto(optionsUrl)
  await seedConfig(page, server.url)

  return { granted, context, page, extensionId, optionsUrl }
}

test.describe('Characters workspace UX', () => {
  test('empty state, CRUD toasts, accessible actions, and focus handling', async () => {
    const server = new MockTldwServer()
    await server.start()
    const serverUrl = normalizeServerUrl(server.url)

    const setup = await setupExtensionForServer(server)
    if (!setup.granted || !setup.context || !setup.page || !setup.optionsUrl) {
      await server.stop()
      test.skip(true, 'Host permission not granted for mock server')
      return
    }
    const { context, page, optionsUrl } = setup

    await page.goto(`${optionsUrl}#/characters`)
    await ensureConnected(page, serverUrl, 'characters-crud')

    await expect(page.getByRole('heading', { name: /Characters/i })).toBeVisible({
      timeout: 15_000
    })

    const crudPrefix = '!!! Characters UX CRUD'
    const characterName = `${crudPrefix} ${Date.now()}`
    await deleteCharactersByPrefix(serverUrl, crudPrefix)

    // Create
    await page.getByRole('button', { name: /New character/i }).click()
    const createDialog = page.getByRole('dialog', {
      name: /New character|Create character/i
    })
    await createDialog.getByLabel(/^Name/i).fill(characterName)
    await createDialog.getByLabel(/^Description/i).fill('A helpful test persona')
    await createDialog.getByLabel(/Greeting message/i).fill('Hello from test!')
    await createDialog.getByLabel(/Behavior \/ instructions/i).fill(
      'You are a cheerful helper.'
    )
    await createDialog.getByRole('button', { name: /^Create character$/i }).click()
    await expect(
      page.getByText(/Character created/i)
    ).toBeVisible({ timeout: 10_000 })
    await expect(
      page.getByRole('button', { name: /New character/i })
    ).toBeFocused()

    const characterRow = page.locator('tr').filter({ hasText: characterName }).first()
    await expect(characterRow).toBeVisible({ timeout: 10_000 })

    // Accessible action buttons
    await expect(
      characterRow.getByText(/^Chat$/i).first()
    ).toBeVisible()
    const editBtn = characterRow.locator('button').filter({ hasText: /^Edit$/i }).first()
    await expect(editBtn).toBeVisible()
    const deleteBtn = characterRow.locator('button').filter({ hasText: /^Delete$/i }).first()
    await expect(deleteBtn).toBeVisible()

    // Edit modal open/close and focus restoration
    await editBtn.click()
    const editDialog = page.getByRole('dialog', { name: /Edit character/i })
    await expect(editDialog).toBeVisible({ timeout: 10_000 })
    const closeEditButton = editDialog.locator('.ant-modal-close').first()
    if (await closeEditButton.isVisible().catch(() => false)) {
      await closeEditButton.click()
    } else {
      await page.keyboard.press('Escape')
    }
    const discardButton = page.getByRole('button', { name: /^Discard$/i }).first()
    if (await discardButton.isVisible({ timeout: 1_000 }).catch(() => false)) {
      await discardButton.click()
    }
    await expect(editDialog).toHaveCount(0, { timeout: 15_000 })
    await expect(editBtn).toBeFocused()

    // Delete
    await deleteBtn.click()
    const confirmDeleteDialog = page
      .locator('.ant-modal-confirm, [role="dialog"]')
      .filter({ hasText: /Please confirm|Are you sure you want to delete this character/i })
      .last()
    await expect(confirmDeleteDialog).toBeVisible({ timeout: 10_000 })
    await confirmDeleteDialog.getByRole('button', { name: /^Delete$/i }).click()
    await expect(confirmDeleteDialog).toBeHidden({ timeout: 10_000 })
    await page.waitForTimeout(500)

    await context.close()
    await server.stop()
  })

  test('shows capability empty state when Characters API missing', async () => {
    test.skip(
      true,
      'Legacy mock route override no longer applies after MockTldwServer switched to real-server harness.'
    )

    const server = new MockTldwServer({
      '/openapi.json': (_req, res) => {
        res.writeHead(200, { 'content-type': 'application/json' })
        res.end(
          JSON.stringify({
            openapi: '3.0.0',
            info: { version: 'test' },
            paths: {
              '/api/v1/health': { get: {} }
            }
          })
        )
      }
    })
    await server.start()

    const setup = await setupExtensionForServer(server)
    if (!setup.granted || !setup.context || !setup.page || !setup.optionsUrl) {
      await server.stop()
      test.skip(true, 'Host permission not granted for mock server')
      return
    }
    const { context, page, optionsUrl } = setup

    await page.goto(`${optionsUrl}#/characters`)

    await expect(
      page.getByText(/Characters API not available on this server/i)
    ).toBeVisible({ timeout: 15_000 })
    await expect(
      page.getByRole('button', { name: /Health & diagnostics/i })
    ).toBeVisible()

    await context.close()
    await server.stop()
  })

  test('header character select exposes clear affordances', async () => {
    const server = new MockTldwServer()
    await server.start()
    const serverUrl = normalizeServerUrl(server.url)
    const seededName = `Header Persona ${Date.now()}`
    const seededId = await createCharacterViaApi(serverUrl, seededName)

    const setup = await setupExtensionForServer(server)
    if (!setup.granted || !setup.context || !setup.page || !setup.optionsUrl) {
      await server.stop()
      test.skip(true, 'Host permission not granted for mock server')
      return
    }
    const { context, page, optionsUrl } = setup

    await page.goto(`${optionsUrl}#/chat`)
    await ensureConnected(page, serverUrl, 'header-clear')

    // Open the header CharacterSelect and pick the seeded character.
    await openCharacterSelectMenu(page)

    await page.getByText(seededName).first().click()

    // Header trigger should now include selected character context.
    await expect(
      page.getByRole('button', { name: new RegExp(escapeRegex(seededName), 'i') }).first()
    ).toBeVisible()

    // Clear via the new "None" menu option at the top.
    await openCharacterSelectMenu(page)
    const noneOption = page.getByText(/None \(no character\)/i).first()
    await expect(noneOption).toBeVisible()
    await noneOption.click()

    await expect(page.getByRole('button', { name: /Select character/i }).first()).toBeVisible()

    if (seededId) {
      await deleteCharacterById(serverUrl, seededId)
    }
    await context.close()
    await server.stop()
  })

  test('header character select offers a Create character path', async () => {
    const server = new MockTldwServer()
    await server.start()

    const { context, page, optionsUrl, granted } =
      await setupExtensionForServer(server)
    if (!granted) {
      await server.stop()
      test.skip('host permission not granted')
      return
    }

    await page.goto(`${optionsUrl}#/chat`)
    await ensureConnected(page, normalizeServerUrl(server.url), 'header-create-path')

    await openCharacterSelectMenu(page)

    const createFromMenu = page
      .getByText(/Create a New Character\+|Create character/i)
      .first()
    await expect(createFromMenu).toBeVisible()

    // Use the menu action to navigate to the Characters workspace.
    await createFromMenu.click()

    await expect(page).toHaveURL(/#\/characters/)
    await expect(
      page.getByRole('button', { name: /New character/i })
    ).toBeVisible({ timeout: 15_000 })

    await context.close()
    await server.stop()
  })

  test('header character select scales via search/filter', async () => {
    const server = new MockTldwServer()
    await server.start()
    const serverUrl = normalizeServerUrl(server.url)
    const prefix = `Persona E2E ${Date.now()}`
    const seededNames = [
      `${prefix} Alpha`,
      `${prefix} Beta`,
      `${prefix} Gamma`,
      `${prefix} Delta`,
      `${prefix} Epsilon`,
      `${prefix} Zeta`
    ]
    const createdIds: string[] = []
    for (const name of seededNames) {
      const createdId = await createCharacterViaApi(serverUrl, name)
      if (createdId) {
        createdIds.push(createdId)
      }
    }

    const { context, page, optionsUrl, granted } =
      await setupExtensionForServer(server)
    if (!granted) {
      await server.stop()
      test.skip('host permission not granted')
      return
    }

    await page.goto(`${optionsUrl}#/chat`)
    await ensureConnected(page, serverUrl, 'header-search-filter')

    await openCharacterSelectMenu(page)

    // Search input should be visible and focusable.
    const searchInput = page.getByPlaceholder(/Search characters/i)
    await expect(searchInput).toBeVisible()

    // Type part of a name and ensure only matching entries remain.
    const targetName = seededNames[1]
    await searchInput.fill('Beta')

    await expect(
      page.getByText(targetName).first()
    ).toBeVisible()

    // "None" and "Clear character" options should remain available.
    const noneOption = page.getByText(/None \(no character\)/i).first()
    await expect(noneOption).toBeVisible()

    // Select a character so Clear becomes available.
    await page.getByText(targetName).first().click()

    await openCharacterSelectMenu(page)
    const clearOption = page.getByText(/Clear character/i).first()
    await expect(clearOption).toBeVisible()
    await clearOption.click()

    await Promise.all(
      createdIds.map((id) => deleteCharacterById(serverUrl, id))
    )
    await context.close()
    await server.stop()
  })

  test('supports compare workflow for two selected characters', async () => {
    const server = new MockTldwServer()
    await server.start()
    const serverUrl = normalizeServerUrl(server.url)
    const uniqueSuffix = Date.now()
    const comparePrefix = '!!! E2E Compare Pair'
    const alphaName = `${comparePrefix} Alpha ${uniqueSuffix}`
    const betaName = `${comparePrefix} Beta ${uniqueSuffix}`

    await deleteCharactersByPrefix(serverUrl, comparePrefix)

    const alphaId = await createCharacterViaApi(serverUrl, alphaName, {
      description: 'Alpha character description',
      greeting: 'Hi from alpha',
      first_message: 'Hi from alpha',
      system_prompt: 'Prompt alpha'
    })
    const betaId = await createCharacterViaApi(serverUrl, betaName, {
      description: 'Beta character description',
      greeting: 'Hi from beta',
      first_message: 'Hi from beta',
      system_prompt: 'Prompt beta'
    })
    if (!alphaId || !betaId) {
      throw new Error('Failed to seed compare characters via API')
    }

    const { context, page, optionsUrl, granted } =
      await setupExtensionForServer(server)
    if (!granted) {
      await server.stop()
      test.skip('host permission not granted')
      return
    }

    await page.goto(`${optionsUrl}#/characters`)
    await ensureConnected(page, serverUrl, 'characters-compare')
    const activeScope = page
      .locator('.ant-segmented-item')
      .filter({ hasText: /^Active$/i })
      .first()
    if (await activeScope.isVisible().catch(() => false)) {
      await activeScope.click()
    }

    const alphaRow = page.locator('tr').filter({ hasText: alphaName }).first()
    const betaRow = page.locator('tr').filter({ hasText: betaName }).first()
    await expect(alphaRow).toBeVisible({ timeout: 15_000 })
    await expect(betaRow).toBeVisible({ timeout: 15_000 })

    const alphaCheckbox = alphaRow.getByRole('checkbox').first()
    const betaCheckbox = betaRow.getByRole('checkbox').first()
    await alphaCheckbox.click()
    await betaCheckbox.click()

    const compareButton = page.getByRole('button', { name: /^Compare$/ })
    await expect(compareButton).toBeEnabled()
    await compareButton.click()

    const compareDialog = page.getByRole('dialog', {
      name: /Compare characters/i
    })
    await expect(compareDialog).toBeVisible({ timeout: 15_000 })
    await expect(compareDialog.getByText(/tracked fields differ/i)).toBeVisible()
    await expect(compareDialog.getByText('Prompt alpha')).toBeVisible()
    await expect(compareDialog.getByText('Prompt beta')).toBeVisible()

    await compareDialog.getByRole('button', { name: /^Close$/ }).last().click()
    await expect(compareDialog).toHaveCount(0)
    await expect(page).toHaveURL(/#\/characters/)

    await Promise.all([
      deleteCharacterById(serverUrl, alphaId),
      deleteCharacterById(serverUrl, betaId)
    ])
    await context.close()
    await server.stop()
  })
})

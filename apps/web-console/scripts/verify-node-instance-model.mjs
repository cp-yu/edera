import { spawn } from 'node:child_process'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import net from 'node:net'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const projectRoot = path.resolve(__dirname, '..')
const sourceId = '0194f7a6-7b17-7c01-b601-000000000001'
const readerId = '0194f7a6-7b17-7c01-b601-000000000003'
const sinkId = '0194f7a6-7b17-7c01-b601-000000000006'

const fixtures = {
  nodeTypes: [
    nodeType('rss-fetcher', 'function', 'source', 'Any', 'list[RawItem]', {
      handler: 'fetch-rss',
      source_names: ['sample-rss'],
    }),
    nodeType('uzi-fetch-price', 'function', 'source', 'Any', 'PriceTick', {
      handler: 'fetch-price',
    }),
    nodeType('uzi-render-chart', 'function', 'source', 'Any', 'ChartSpec', {
      handler: 'render-chart',
    }),
    nodeType('reader', 'function', 'processor', 'list[RawItem]', 'AnalysisResult', {
      skills: ['summarize'],
      model: 'hf-share/deepseek-v4-flash',
      system_prompt_file: 'prompts/reader.md',
    }),
    nodeType('advisor', 'function', 'processor', 'AnalysisResult', 'Advice', {
      model: 'hf-share/deepseek-v4-flash',
      system_prompt_file: 'prompts/advisor.md',
    }),
    nodeType('agent-reader', 'agent', 'processor', 'list[RawItem]', 'AnalysisResult', {
      model: 'hf-share/deepseek-v4-flash',
      system_prompt_file: 'prompts/agent-reader.md',
    }),
    nodeType('approval-wait', 'wait', 'processor', 'AnalysisResult', 'AnalysisResult'),
    nodeType('notifier', 'function', 'sink', 'Advice', 'Any', {
      handler: 'notify-ntfy',
    }),
  ],
  skills: [
    {
      name: 'summarize',
      description: 'Summarize text',
      handler: 'summarize',
      parameters_schema: { type: 'object' },
    },
  ],
}

fixtures.dag = {
  name: 'default',
  nodes: [
    instance(sourceId, 'rss-fetcher', 'rss-source', { source_names: ['sample-rss'] }),
    instance(readerId, 'reader', 'market-reader', {
      skills: ['summarize'],
      model: 'hf-share/deepseek-v4-flash',
      parameters: { temperature: 0.2 },
    }),
    instance(sinkId, 'notifier', 'alert-sink', {}),
  ],
  edges: [
    { from: sourceId, to: readerId, fan_in: true, fan_out: false },
    { from: readerId, to: sinkId, fan_in: false, fan_out: false },
  ],
  ui: {
    nodes: {
      [sourceId]: { x: 0, y: 40 },
      [readerId]: { x: 340, y: 40 },
      [sinkId]: { x: 680, y: 40 },
    },
    edges: {
      [`e-${sourceId}-${readerId}-0`]: { sourceHandle: 'output-0', targetHandle: 'input-0' },
      [`e-${readerId}-${sinkId}-1`]: { sourceHandle: 'output-0', targetHandle: 'input-0' },
    },
  },
}

fixtures.runtimeStatus = {
  node_statuses: {
    [readerId]: { status: 'running', error: null, run_id: 'run-browser' },
  },
}

let viteProcess
let chromeProcess
let chromeProfile
let cdpClient

async function main() {
  const baseUrl = process.env.FRONTEND_URL ?? await startVite()
  const chrome = await startChrome()
  chromeProcess = chrome.process
  chromeProfile = chrome.profile
  const target = await newPage(chrome.port)
  const cdp = new Cdp(target.webSocketDebuggerUrl)
  cdpClient = cdp
  await cdp.ready
  await cdp.send('Page.enable')
  await cdp.send('Runtime.enable')
  await cdp.send('Page.addScriptToEvaluateOnNewDocument', {
    source: `(${installFetchMock.toString()})(${JSON.stringify(fixtures)})`,
  })

  await navigate(cdp, `${baseUrl}/workbench`)
  await waitFor(cdp, `document.querySelector('.react-flow__node[data-id="${readerId}"]')`)

  await verifyGraphLogic(cdp)
  await verifyWorkbenchDom(cdp)
  await verifyCanvasSelectionHighlight(cdp)
  await verifyQuickAddAndMultiInstance(cdp)
  await verifyPaletteGrouping(cdp)
  await verifyInspector(cdp)
  await verifyNodesPage(cdp, baseUrl)
  cdp.close()
  cdpClient = undefined

  console.log('node instance browser verification passed')
}

function nodeType(name, type, role, inputType, outputType, extra = {}) {
  return {
    name,
    type,
    role,
    input_type: inputType,
    output_type: outputType,
    skills: [],
    parameters: {},
    inspector_schema: buildInspectorSchema(type, role, extra),
    ...extra,
  }
}

function instance(id, typeName, alias, config) {
  const prototype = fixtures.nodeTypes.find((item) => item.name === typeName)
  return {
    ...prototype,
    id,
    type_name: typeName,
    alias,
    config,
    skills: Array.isArray(config.skills) ? config.skills : prototype.skills,
    model: typeof config.model === 'string' ? config.model : prototype.model,
    source_names: Array.isArray(config.source_names) ? config.source_names : prototype.source_names,
    parameters: config.parameters ?? prototype.parameters,
  }
}

async function verifyGraphLogic(cdp) {
  const checks = await evaluate(cdp, `
    (async () => {
      const graph = await import('/src/features/workbench/lib/graph.ts')
      const source = ${JSON.stringify(fixtures.dag.nodes[0])}
      const reader = ${JSON.stringify(fixtures.dag.nodes[1])}
      const sink = ${JSON.stringify(fixtures.dag.nodes[2])}
      const functionTarget = {
        ...sink,
        id: 'function-target',
        role: 'processor',
        input_type: 'PriceTick',
        output_type: 'Any',
        visualKind: 'function',
        inputHandles: [],
        outputHandles: [],
      }
      const processorTarget = {
        ...reader,
        id: 'processor-target',
        input_type: 'PriceTick',
        visualKind: 'function',
        inputHandles: [],
        outputHandles: [],
      }
      const anySource = { ...source, output_type: 'Any' }
      const listToItemTarget = { ...functionTarget, input_type: 'RawItem' }
      const sourceHandles = graph.getHandleSpecs(source.id, source, [])
      const readerHandles = graph.getHandleSpecs(reader.id, reader, [])
      const sinkHandles = graph.getHandleSpecs(sink.id, sink, [])
      const handleEdges = [
        { from: 'source-a', to: 'processor-a' },
        { from: 'source-b', to: 'processor-a' },
        { from: 'processor-a', to: 'sink-a' },
        { from: 'processor-a', to: 'sink-b' },
      ]
      const processorFunction = { ...reader, id: 'processor-a', type: 'function', role: 'processor' }
      const processorAgent = { ...reader, id: 'processor-a', type: 'agent', role: 'processor' }
      const processorFunctionHandles = graph.getHandleSpecs(processorFunction.id, processorFunction, handleEdges)
      const processorAgentHandles = graph.getHandleSpecs(processorAgent.id, processorAgent, handleEdges)
      const visualKinds = {
        functionSource: graph.getNodeKind({ ...source, type: 'function', role: 'source' }),
        functionProcessor: graph.getNodeKind({ ...reader, type: 'function', role: 'processor' }),
        functionSink: graph.getNodeKind({ ...sink, type: 'function', role: 'sink' }),
        agentSource: graph.getNodeKind({ ...source, type: 'agent', role: 'source' }),
        agentProcessor: graph.getNodeKind({ ...reader, type: 'agent', role: 'processor' }),
        agentSink: graph.getNodeKind({ ...sink, type: 'agent', role: 'sink' }),
        dag: graph.getNodeKind({ ...reader, type: 'dag', role: 'processor' }),
        wait: graph.getNodeKind({ ...reader, type: 'wait', role: 'processor' }),
      }
      const search = graph.filterSearchItems(
        graph.buildSearchItems(${JSON.stringify(fixtures.nodeTypes)}, [{ ...reader, alias: 'alias-hit' }]),
        'alias-hit',
      )
      const enriched = graph.enrichNodeData(reader, [], ${JSON.stringify(fixtures.runtimeStatus)})
      const subDagDraft = graph.toDagDraft([
        {
          id: 'sub-a',
          position: { x: 0, y: 0 },
          data: {
            ...reader,
            id: 'sub-a',
            type_name: 'dag',
            dag_ref: 'common-subdag',
            input_mapping: { topic: 'payload.topic' },
            visualKind: 'dag',
            inputHandles: [],
            outputHandles: [],
          },
        },
      ], [])
      return {
        sourceRoleHandles: sourceHandles.inputHandles.length === 0 && sourceHandles.outputHandles.length === 1,
        processorHandles: readerHandles.inputHandles.length === 1 && readerHandles.outputHandles.length === 1,
        sinkRoleHandles: sinkHandles.inputHandles.length === 1 && sinkHandles.outputHandles.length === 0,
        functionKindAcrossRoles: visualKinds.functionSource === 'function'
          && visualKinds.functionProcessor === 'function'
          && visualKinds.functionSink === 'function',
        agentKindAcrossRoles: visualKinds.agentSource === 'agent'
          && visualKinds.agentProcessor === 'agent'
          && visualKinds.agentSink === 'agent',
        functionAgentVisualsDiffer: visualKinds.functionProcessor !== visualKinds.agentProcessor,
        dagKind: visualKinds.dag === 'dag',
        waitKind: visualKinds.wait === 'wait',
        functionAgentHandlesMatch: JSON.stringify(processorFunctionHandles) === JSON.stringify(processorAgentHandles),
        processorConnectivityHandles: processorFunctionHandles.inputHandles.length === 2
          && processorFunctionHandles.outputHandles.length === 2,
        rejectsInputToSource: graph.isValidConnection(reader, source) === false,
        rejectsFunctionMismatch: graph.isValidConnection(source, functionTarget) === false,
        rejectsProcessorMismatch: graph.isValidConnection(source, processorTarget) === false,
        anyOutputCompatible: graph.isValidConnection(anySource, functionTarget) === true,
        listDoesNotFlatten: graph.isValidConnection(source, listToItemTarget) === false,
        aliasSearch: search.length === 1 && search[0].name === 'reader',
        uuidRuntimeStatus: enriched.status === 'running',
        subDagDraftFields: subDagDraft.nodes[0].dag_ref === 'common-subdag'
          && subDagDraft.nodes[0].input_mapping.topic === 'payload.topic',
      }
    })()
  `)
  assertAll(checks, 'graph logic')
}

async function verifyWorkbenchDom(cdp) {
  const checks = await evaluate(cdp, `
    (() => {
      const handles = (id, side) =>
        document.querySelectorAll('.react-flow__node[data-id="' + id + '"] .react-flow__handle-' + side).length
      const readerNode = document.querySelector('.react-flow__node[data-id="${readerId}"]')
      const titleText = readerNode?.querySelector('[data-node-title]')?.textContent?.trim()
      const typeContext = readerNode?.querySelector('[data-node-type-context]')?.textContent?.trim()
      return {
        sourceHandleHidden: handles('${sourceId}', 'left') === 0 && handles('${sourceId}', 'right') === 1,
        sinkHandleHidden: handles('${sinkId}', 'left') === 1 && handles('${sinkId}', 'right') === 0,
        processorHandles: handles('${readerId}', 'left') === 1 && handles('${readerId}', 'right') === 1,
        runtimeBadge: Boolean(readerNode?.querySelector('.animate-pulse')),
        aliasPrimaryTitle: titleText === 'market-reader',
        typeContextPreserved: typeContext === 'reader',
        identityTextNotPrimaryTitle: titleText !== '${readerId}',
      }
    })()
  `)
  assertAll(checks, 'workbench dom')
}

async function verifyQuickAddAndMultiInstance(cdp) {
  const grouped = await evaluate(cdp, `
    (async () => {
      openQuickAdd()
      await tick()
      return ['Sources', 'Processors', 'Sinks'].every((label) => document.body.textContent.includes(label))
    })()
  `)
  assert(grouped, 'quick add groups by role')

  const aliasSearch = await evaluate(cdp, `
    (async () => {
      const input = quickAddInput()
      setInput(input, 'market-reader')
      await tick()
      const buttons = [...document.querySelectorAll('button')].map((button) => button.textContent.trim())
      return buttons.some((text) => text.startsWith('reader'))
    })()
  `)
  assert(aliasSearch, 'quick add search matches instance alias')

  for (let index = 0; index < 2; index += 1) {
    await evaluate(cdp, `
      (async () => {
        openQuickAdd()
        await tick()
        setInput(quickAddInput(), 'reader')
        await tick()
        quickAddButton('reader').click()
      })()
    `)
    await waitFor(cdp, `document.querySelectorAll('.react-flow__node').length >= ${4 + index}`)
  }

  const multiInstance = await evaluate(cdp, `
    (() => {
      const ids = [...document.querySelectorAll('.react-flow__node')]
        .filter((node) => node.textContent.includes('reader'))
        .map((node) => node.getAttribute('data-id'))
      return ids.length >= 3 && new Set(ids).size === ids.length
    })()
  `)
  assert(multiInstance, 'same node type can be added more than once with distinct ids')
}

async function verifyPaletteGrouping(cdp) {
  const checks = await evaluate(cdp, `
    (() => {
      const palette = document.querySelector('aside')
      const text = palette?.textContent ?? ''
      const prefixLabels = [...(palette?.querySelectorAll('[data-palette-prefix]') ?? [])]
        .map((item) => item.textContent.trim())
      const sourceRole = text.includes('Source 节点')
      const processorRole = text.includes('Processor 节点')
      const sinkRole = text.includes('Sink 节点')
      const uziFetchGroup = prefixLabels.includes('uzi-fetch')
      const uziRenderGroup = prefixLabels.includes('uzi-render')
      const dragNode = [...(palette?.querySelectorAll('[draggable="true"]') ?? [])]
        .find((item) => item.textContent.includes('uzi-fetch-price'))
      const event = new DragEvent('dragstart', { bubbles: true, cancelable: true, dataTransfer: new DataTransfer() })
      dragNode?.dispatchEvent(event)
      return {
        sourceRole,
        processorRole,
        sinkRole,
        uziFetchGroup,
        uziRenderGroup,
        dragPayloadUnchanged: event.dataTransfer.getData('application/reactflow') === 'uzi-fetch-price',
      }
    })()
  `)
  assertAll(checks, 'palette grouping')
}

async function verifyCanvasSelectionHighlight(cdp) {
  const checks = await evaluate(cdp, `
    (async () => {
      const sourceNode = document.querySelector('.react-flow__node[data-id="${sourceId}"]')
      sourceNode?.dispatchEvent(clickEvent())
      await tick()
      const connected = document.querySelector('.react-flow__edge[data-id="e-${sourceId}-${readerId}-0"]')
      const unrelated = document.querySelector('.react-flow__edge[data-id="e-${readerId}-${sinkId}-1"]')
      const connectedPath = connected?.querySelector('.react-flow__edge-path')
      const connectedStyle = connectedPath ? getComputedStyle(connectedPath) : null
      const connectedWidth = Number.parseFloat(connectedStyle?.strokeWidth ?? '0')
      const unrelatedPath = unrelated?.querySelector('.react-flow__edge-path')
      const unrelatedWidth = Number.parseFloat(unrelatedPath ? getComputedStyle(unrelatedPath).strokeWidth : '0')
      return {
        connectedEdgeHighlighted: connected?.classList.contains('selected-neighborhood-edge'),
        unrelatedEdgeNotHighlighted: !unrelated?.classList.contains('selected-neighborhood-edge'),
        runtimeStrokePreserved: connectedStyle?.stroke === 'rgb(37, 99, 235)',
        selectedWidthIncreased: connectedWidth > unrelatedWidth,
        selectedNodeStillHighlighted: sourceNode?.classList.contains('selected'),
      }
    })()
  `)
  assertAll(checks, 'canvas selection highlight')
}

async function verifyInspector(cdp) {
  await evaluate(cdp, `
    (async () => {
      document.querySelector('.react-flow__node[data-id="${readerId}"]').dispatchEvent(clickEvent())
      await tick()
    })()
  `)
  await waitFor(cdp, `(() => {
    const asides = document.querySelectorAll('aside')
    const inspector = asides[asides.length - 1]
    return inspector?.querySelector('textarea')
  })()`)
  await waitFor(cdp, `(() => {
    const asides = document.querySelectorAll('aside')
    const inspector = asides[asides.length - 1]
    return inspector?.querySelector('input[type="number"]')
  })()`)

  const nodeInspector = await evaluate(cdp, `
    (async () => {
      const asides = [...document.querySelectorAll('aside')]
      const aside = asides[asides.length - 1]
      const hasModelSelect = Boolean(aside?.querySelector('select'))
      const inputs = aside ? [...aside.querySelectorAll('input')] : []
      const buttons = aside ? [...aside.querySelectorAll('button')] : []
      const readonly = (name) => aside?.querySelector('[data-inspector-readonly="' + name + '"]')?.textContent ?? ''
      const hasNumberInput = Boolean(inputs.find((input) => input.type === 'number'))
      const hasJsonTextarea = Boolean(aside?.querySelector('textarea'))
      const hasSkillChip = buttons.some((button) => button.textContent.includes('summarize'))
      return {
        hasModelSelect,
        hasSkillChip,
        hasNumberInput,
        hasJsonTextarea,
        readonlyName: readonly('name').includes('reader'),
        readonlyType: readonly('类型').includes('reader'),
        readonlyInput: readonly('输入').includes('list[RawItem]'),
        readonlyOutput: readonly('输出').includes('AnalysisResult'),
      }
    })()
  `)
  assertAll(nodeInspector, 'inspector shows schema-driven fields')

  const configFooter = await evaluate(cdp, `
    (() => {
      const aside = [...document.querySelectorAll('aside')].at(-1)
      const footer = aside?.querySelector('[data-inspector-config-footer]')
      const saveButton = footer?.querySelector('button')
      const footerStyle = footer ? getComputedStyle(footer) : null
      return {
        footerExists: Boolean(footer),
        footerSticky: footerStyle?.position === 'sticky',
        saveButtonVisible: saveButton?.textContent.includes('保存实例'),
      }
    })()
  `)
  assertAll(configFooter, 'inspector config footer')

  await evaluate(cdp, `
    (async () => {
      const asides = [...document.querySelectorAll('aside')]
      const aside = asides[asides.length - 1]
      const select = aside?.querySelector('select')
      if (!select) throw new Error('model select not found')
      select.value = ''
      select.dispatchEvent(new Event('change', { bubbles: true }))
      await tick()
      window.__lastDagPut = undefined
      ;[...aside.querySelectorAll('button')]
        .find((button) => button.textContent.includes('保存实例'))
        ?.click()
      await tick()
    })()
  `)
  await waitFor(cdp, `(() => {
    const payload = window.__lastDagPut
    const savedReader = payload?.nodes?.find((node) => node.type === 'reader')
    return savedReader && !Object.prototype.hasOwnProperty.call(savedReader.config, 'model')
  })()`)
  const savePayload = await evaluate(cdp, `(() => window.__lastDagPut)()`)
  const savedReader = savePayload.nodes.find((node) => node.type === 'reader')
  assert(
    savedReader && !Object.prototype.hasOwnProperty.call(savedReader.config, 'model'),
    `inspector diff save drops cleared model: ${JSON.stringify(savedReader)}`,
  )

  const nonConfigFooter = await evaluate(cdp, `
    (async () => {
      const aside = [...document.querySelectorAll('aside')].at(-1)
      const clickTab = async (label) => {
        ;[...aside.querySelectorAll('button')].find((button) => button.textContent.includes(label))?.click()
        await tick()
        return Boolean(aside.querySelector('[data-inspector-config-footer]'))
      }
      const runtimeHasFooter = await clickTab('Runtime')
      const triggersHasFooter = await clickTab('Triggers')
      ;[...aside.querySelectorAll('button')].find((button) => button.textContent.includes('Config'))?.click()
      await tick()
      return {
        runtimeFooterAbsent: runtimeHasFooter === false,
        triggersFooterAbsent: triggersHasFooter === false,
      }
    })()
  `)
  assertAll(nonConfigFooter, 'inspector non-config footer')

  const edgeInspector = await evaluate(cdp, `
    (async () => {
      const edge = document.querySelector('.react-flow__edge[data-id="e-${sourceId}-${readerId}-0"]')
      edge?.dispatchEvent(clickEvent())
      await tick()
      const text = document.body.textContent
      return text.includes('fan_in') && text.includes('fan_out')
    })()
  `)
  assert(edgeInspector, 'inspector shows edge fan_in and fan_out')
}

function buildInspectorSchema(type, role, extra) {
  const properties = {
    timeout_seconds: { type: 'number', default: extra.timeout_seconds ?? null },
  }
  if (type === 'function') {
    properties.model = {
      type: 'string',
      enum: ['hf-share/deepseek-v4-flash'],
      default: extra.model ?? '',
    }
    properties.skills = {
      type: 'array',
      items: { type: 'string', enum: ['summarize'] },
      default: extra.skills ?? [],
    }
    properties['param.profile'] = {
      type: 'object',
      default: { mode: 'balanced' },
    }
  }
  if (type === 'function' && role === 'source') {
    properties.source_names = {
      type: 'array',
      items: { type: 'string', enum: ['sample-rss', 'sample-web'] },
      default: extra.source_names ?? [],
    }
  }
  return { type: 'object', properties }
}

async function verifyNodesPage(cdp, baseUrl) {
  await navigate(cdp, `${baseUrl}/nodes`)
  await waitFor(cdp, `document.body.textContent.includes('processor')`)
  await waitFor(cdp, `document.body.textContent.includes('reader')`)
  const checks = await evaluate(cdp, `
    (async () => {
      const clickTab = async (label) => {
        ;[...document.querySelectorAll('button')].find((button) => button.textContent.includes(label)).click()
        await tick()
      }
      const hasReader = document.body.textContent.includes('reader')
      const hasFunction = document.body.textContent.includes('rss-fetcher')
      await clickTab('Skills')
      const hasSkills = document.body.textContent.includes('summarize')
      const createButton = [...document.querySelectorAll('button')].find((button) => button.textContent.includes('创建'))
      const deleteButton = [...document.querySelectorAll('button')].find((button) => button.textContent.includes('删除'))
      const editorText = document.querySelector('textarea')?.value ?? ''
      return {
        hasReader,
        hasFunction,
        hasSkills,
        hasCreate: Boolean(createButton),
        hasDelete: Boolean(deleteButton),
        hasCodeEditor: editorText.includes('handler_code') || editorText.includes('handler'),
      }
    })()
  `)
  assertAll(checks, 'nodes page tabs')
}

async function startVite() {
  const port = await freePort()
  viteProcess = spawn(
    process.execPath,
    [path.join(projectRoot, 'node_modules', 'vite', 'bin', 'vite.js'), '--host', '127.0.0.1', '--port', String(port), '--strictPort'],
    { cwd: projectRoot, stdio: ['ignore', 'pipe', 'pipe'] },
  )
  viteProcess.stdout.on('data', (chunk) => {
    if (process.env.VERIFY_VERBOSE) process.stdout.write(chunk)
  })
  viteProcess.stderr.on('data', (chunk) => process.stderr.write(chunk))
  const url = `http://127.0.0.1:${port}`
  await waitForHttp(url)
  return url
}

async function startChrome() {
  const port = await freePort()
  const profile = mkdtempSync(path.join(tmpdir(), 'stockinfo-chrome-'))
  const binary = process.env.CHROME_BIN ?? 'google-chrome'
  const args = [
    '--headless=new',
    '--disable-gpu',
    '--no-sandbox',
    '--disable-dev-shm-usage',
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profile}`,
    'about:blank',
  ]
  const child = spawn(binary, args, { stdio: ['ignore', 'ignore', 'pipe'] })
  child.stderr.on('data', (chunk) => {
    if (process.env.VERIFY_VERBOSE) process.stderr.write(chunk)
  })
  await waitForHttp(`http://127.0.0.1:${port}/json/version`)
  return { process: child, port, profile }
}

async function newPage(port) {
  const response = await fetch(`http://127.0.0.1:${port}/json/new?about:blank`, { method: 'PUT' })
  if (!response.ok) throw new Error(`failed to create chrome target: ${response.status}`)
  return response.json()
}

async function navigate(cdp, url) {
  await cdp.send('Page.navigate', { url })
  await waitFor(cdp, `document.readyState === 'complete' || document.readyState === 'interactive'`)
}

async function evaluate(cdp, expression) {
  const response = await cdp.send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
    userGesture: true,
  })
  if (response.exceptionDetails) {
    const detail = response.exceptionDetails.exception?.description ?? response.exceptionDetails.text
    throw new Error(detail)
  }
  return response.result.value
}

async function waitFor(cdp, expression, timeoutMs = 10000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (await evaluate(cdp, `Boolean(${expression})`)) return
    await delay(100)
  }
  throw new Error(`timed out waiting for: ${expression}`)
}

async function waitForHttp(url, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url)
      if (response.ok) return
    } catch {
      await delay(100)
    }
  }
  throw new Error(`timed out waiting for ${url}`)
}

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      server.close(() => resolve(address.port))
    })
    server.on('error', reject)
  })
}

function installFetchMock(data) {
  const originalFetch = window.fetch.bind(window)
  let savedDag = data.dag
  const json = (body, status = 200) =>
    new Response(JSON.stringify(body), {
      status,
      headers: { 'content-type': 'application/json' },
    })

  window.tick = () => new Promise((resolve) => setTimeout(resolve, 80))
  window.clickEvent = () => new MouseEvent('click', { bubbles: true, cancelable: true, view: window })
  window.openQuickAdd = () => {
    ;[...document.querySelectorAll('button')]
      .find((button) => button.textContent.includes('Cmd/Ctrl+K'))
      ?.click()
  }
  window.quickAddInput = () =>
    [...document.querySelectorAll('input')]
      .find((input) => input.placeholder === '搜索节点并添加到画布中心')
  window.quickAddButton = (text) =>
    [...document.querySelectorAll('button')]
      .find((button) => button.closest('.absolute.left-1\\/2') && button.textContent.includes(text))
  window.setInput = (input, value) => {
    input.focus()
    input.value = value
    input.dispatchEvent(new Event('input', { bubbles: true }))
  }
  window.fetch = async (input, init = {}) => {
    const url = new URL(typeof input === 'string' ? input : input.url, window.location.origin)
    const method = (init.method ?? 'GET').toUpperCase()
    if (url.pathname === '/api/graph/nodes') return json({ prototypes: data.nodeTypes })
    if (url.pathname === '/api/graph/node-types' && method === 'GET') return json({ types: data.nodeTypes })
    if (url.pathname === '/api/graph/skills' && method === 'GET') return json({ skills: data.skills })
    if (url.pathname === '/api/graph/node-types' && method === 'POST') return json({ node: JSON.parse(init.body ?? '{}') })
    if (url.pathname.startsWith('/api/graph/node-types/') && ['PUT', 'DELETE'].includes(method)) return json({ ok: true })
    if (url.pathname === '/api/graph/skills' && method === 'POST') return json({ skill: JSON.parse(init.body ?? '{}') })
    if (url.pathname.startsWith('/api/graph/skills/') && ['PUT', 'DELETE'].includes(method)) return json({ ok: true })
    if (url.pathname === '/api/graph/dag/default' && method === 'GET') return json(savedDag)
    if (url.pathname === '/api/graph/dag/default' && method === 'PUT') {
      window.__lastDagPut = JSON.parse(init.body ?? '{}')
      savedDag = { ...savedDag, ...window.__lastDagPut }
      return json({ dag: savedDag })
    }
    if (url.pathname === '/api/dags/default/status') {
      return json({
        scheduler_running: true,
        scheduler_paused: false,
        dag_name: 'default',
        current_run_id: 'run-browser',
        recent_runs: [],
      })
    }
    if (url.pathname === '/api/graph/runtime-status') return json(data.runtimeStatus)
    if (url.pathname === '/api/node-outputs') return json({ outputs: [] })
    if (url.pathname === '/api/node-logs') {
      return json({
        logs: [
          {
            id: 1,
            run_id: 'run-browser',
            node_id: readerId,
            kind: 'summary',
            path: '/tmp/run-browser-reader-summary.json',
            digest: 'digest-summary',
            size: 128,
            created_at: '2026-01-01T00:00:00Z',
            updated_at: '2026-01-01T00:00:00Z',
          },
        ],
      })
    }
    return originalFetch(input, init)
  }
}

function assertAll(results, label) {
  for (const [name, passed] of Object.entries(results)) {
    assert(passed, `${label}: ${name}`)
  }
}

function assert(value, message) {
  if (!value) throw new Error(message)
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

class Cdp {
  constructor(url) {
    this.nextId = 1
    this.pending = new Map()
    this.socket = new WebSocket(url)
    this.ready = new Promise((resolve, reject) => {
      this.socket.addEventListener('open', resolve, { once: true })
      this.socket.addEventListener('error', reject, { once: true })
    })
    this.socket.addEventListener('message', (event) => {
      const message = JSON.parse(event.data)
      if (!message.id) return
      const pending = this.pending.get(message.id)
      if (!pending) return
      this.pending.delete(message.id)
      if (message.error) pending.reject(new Error(message.error.message))
      else pending.resolve(message.result)
    })
  }

  send(method, params = {}) {
    const id = this.nextId++
    this.socket.send(JSON.stringify({ id, method, params }))
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
    })
  }

  close() {
    this.socket.close()
  }
}

let failure
try {
  await main()
} catch (error) {
  failure = error
} finally {
  if (cdpClient) cdpClient.close()
  if (chromeProcess) chromeProcess.kill()
  if (viteProcess) viteProcess.kill()
  if (chromeProfile) {
    try {
      rmSync(chromeProfile, { recursive: true, force: true })
    } catch {
      // Chrome may still be flushing profile files after the process exits.
    }
  }
}
if (failure) throw failure

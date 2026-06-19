const avatar = document.getElementById('avatar')
const base = document.getElementById('base')
const eyes = document.getElementById('eyes')
const mouth = document.getElementById('mouth')
const status = document.getElementById('status')
const hud = document.getElementById('hud')
const micBtn = document.getElementById('micBtn')
const screenBtn = document.getElementById('screenBtn')
const listenBtn = document.getElementById('listenBtn')
const stopBtn = document.getElementById('stopBtn')
const hideHudBtn = document.getElementById('hideHudBtn')
const reloadBtn = document.getElementById('reloadBtn')
const closeBtn = document.getElementById('closeBtn')

const idlePoseKeys = ['idleDefault', 'idleShift', 'idleSoft']
const speakingMouths = ['closed', 'middle_open', 'open']

let config = null
let currentState = {}
let currentPoseKey = ''
let currentIdlePoseKey = 'idleDefault'
let currentRenderedMouth = 'closed'
let lastIdlePoseChangeAt = 0
let nextIdlePoseChangeAt = 0
let blinkLockedUntil = 0
let thinkingEyeOpenUntil = 0
let lastThinkingEyePulseAt = 0
let lastMouthChangeAt = 0
let mouthChangeTimer = null
let hudVisible = true
let commandBusy = false
let isPoseTransitioning = false

const imageCache = new Map()

function joinUrl(baseUrl, file) {
  return `${baseUrl.replace(/\/$/, '')}/${file}`
}

function poseUrl(pose, file) {
  return joinUrl(joinUrl(config.posesBaseUrl, pose.id), file)
}

function partUrl(pose, type, name) {
  return joinUrl(joinUrl(joinUrl(config.posesBaseUrl, pose.id), pose.partsDir), `${type}_${name}.png`)
}

function preloadImage(src) {
  if (!src) return Promise.resolve()
  if (imageCache.has(src)) return imageCache.get(src)

  const promise = new Promise((resolve) => {
    const img = new Image()
    img.onload = () => resolve(src)
    img.onerror = () => resolve(src)
    img.src = src
  })

  imageCache.set(src, promise)
  return promise
}

function setImage(element, next) {
  if (!next || element.dataset.src === next) return
  element.dataset.src = next
  element.src = next
}

function normalizeMode(mode) {
  const value = String(mode || 'idle').toLowerCase()
  if (['idle', 'thinking', 'listening', 'speaking', 'approach'].includes(value)) {
    return value
  }
  return 'idle'
}

function normalizeExpression(expression) {
  const value = String(expression || 'neutral').toLowerCase()
  if (['neutral', 'serious', 'happy', 'surprised'].includes(value)) {
    return value
  }
  return 'neutral'
}

function hasPart(pose, type, name) {
  const listName = type === 'eye' ? 'eyes' : 'mouths'
  return Array.isArray(pose[listName]) && pose[listName].includes(name)
}

function normalizeEye(pose, requested, mode, expression) {
  const now = Date.now()

  if (now < blinkLockedUntil && hasPart(pose, 'eye', 'closed')) {
    return 'closed'
  }

  if (mode === 'thinking') {
    if (now < thinkingEyeOpenUntil && hasPart(pose, 'eye', 'open')) {
      return 'open'
    }
    return hasPart(pose, 'eye', 'closed') ? 'closed' : 'open'
  }

  if (expression === 'happy' && hasPart(pose, 'eye', 'happy')) {
    return 'happy'
  }

  if (expression === 'serious' && hasPart(pose, 'eye', 'serious')) {
    return 'serious'
  }

  if (hasPart(pose, 'eye', requested)) {
    return requested
  }

  if (hasPart(pose, 'eye', 'open')) return 'open'
  if (hasPart(pose, 'eye', 'closed')) return 'closed'
  return pose.eyes[0]
}

function normalizeMouth(pose, requested, mode, expression) {
  if (mode === 'thinking') {
    return 'closed'
  }

  if (mode === 'speaking') {
    const mouthName = speakingMouths.includes(requested) ? requested : 'closed'
    return hasPart(pose, 'mouth', mouthName) ? mouthName : 'closed'
  }

  if (expression === 'happy' && hasPart(pose, 'mouth', 'smile')) {
    return 'smile'
  }

  if (expression === 'surprised' && hasPart(pose, 'mouth', 'surprise')) {
    return 'surprise'
  }

  if (hasPart(pose, 'mouth', requested)) {
    return requested
  }

  return 'closed'
}

function scheduleNextIdlePoseChange(minSeconds = 9, maxSeconds = 18) {
  nextIdlePoseChangeAt = Date.now() + (minSeconds + Math.random() * (maxSeconds - minSeconds)) * 1000
}

function pickIdlePose(force = false) {
  const now = Date.now()

  if (!force && now < nextIdlePoseChangeAt) {
    return currentIdlePoseKey
  }

  const options = idlePoseKeys.filter((key) => key !== currentIdlePoseKey)
  currentIdlePoseKey = options[Math.floor(Math.random() * options.length)] || 'idleDefault'
  lastIdlePoseChangeAt = now
  scheduleNextIdlePoseChange()
  return currentIdlePoseKey
}

function poseKeyForState(state, mode) {
  if (state.pose && config.poses[state.pose]) {
    return state.pose
  }

  if (mode === 'thinking') return 'thinking'
  if (mode === 'listening') return 'listening'
  if (mode === 'approach') return 'approach'

  if (mode === 'speaking') {
    return currentIdlePoseKey || 'idleDefault'
  }

  return pickIdlePose(false)
}

function cloneCurrentAvatar() {
  if (!base.dataset.src) return

  const ghost = document.createElement('div')
  ghost.className = 'avatar-ghost'

  ;[base, eyes, mouth].forEach((layer) => {
    if (!layer.dataset.src) return
    const clone = layer.cloneNode(false)
    clone.removeAttribute('id')
    clone.classList.add('ghost-layer')
    ghost.appendChild(clone)
  })

  avatar.appendChild(ghost)
  requestAnimationFrame(() => ghost.classList.add('fade-out'))
  setTimeout(() => ghost.remove(), 360)
}

function setMouthImageSmooth(url, mouthName, mode, force = false) {
  if (mouthChangeTimer) {
    clearTimeout(mouthChangeTimer)
    mouthChangeTimer = null
  }

  if (force || mode !== 'speaking') {
    currentRenderedMouth = mouthName
    lastMouthChangeAt = Date.now()
    setImage(mouth, url)
    return
  }

  if (currentRenderedMouth === mouthName) return

  const now = Date.now()
  const minimumDelay = mouthName === 'closed' ? 62 : 86
  const elapsed = now - lastMouthChangeAt

  const commit = () => {
    currentRenderedMouth = mouthName
    lastMouthChangeAt = Date.now()
    mouth.classList.add('mouth-pop')
    setImage(mouth, url)
    setTimeout(() => mouth.classList.remove('mouth-pop'), 110)
  }

  if (elapsed >= minimumDelay) {
    commit()
  } else {
    mouthChangeTimer = setTimeout(commit, minimumDelay - elapsed)
  }
}

async function renderAvatar(poseKey, pose, eyeName, mouthName, mode, expression) {
  const nextBase = poseUrl(pose, pose.baseImage)
  const nextEye = partUrl(pose, 'eye', eyeName)
  const nextMouth = partUrl(pose, 'mouth', mouthName)
  const poseChanged = poseKey !== currentPoseKey

  await Promise.all([
    preloadImage(nextBase),
    preloadImage(nextEye),
    preloadImage(nextMouth)
  ])

  if (poseChanged) {
    cloneCurrentAvatar()
    isPoseTransitioning = true
    avatar.classList.add('pose-enter')
    currentPoseKey = poseKey
  }

  avatar.className = `avatar ${mode} ${expression} pose-${pose.id}${poseChanged ? ' pose-enter' : ''}`

  setImage(base, nextBase)
  setImage(eyes, nextEye)
  setMouthImageSmooth(nextMouth, mouthName, mode, poseChanged)

  if (poseChanged) {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        avatar.classList.remove('pose-enter')
        isPoseTransitioning = false
      })
    })
  }
}

function updateThinkingPulse(mode) {
  if (mode !== 'thinking') return

  const now = Date.now()
  if (now - lastThinkingEyePulseAt > 2800 + Math.random() * 2600) {
    thinkingEyeOpenUntil = now + 210
    lastThinkingEyePulseAt = now
  }
}

function updateHudFromState(state) {
  const controls = state.controls || {}
  micBtn.classList.toggle('active', Boolean(controls.microphone))
  screenBtn.classList.toggle('active', Boolean(controls.screen))
  listenBtn.classList.toggle('active', Boolean(controls.listening) || normalizeMode(state.mode) === 'listening')

  micBtn.title = controls.microphone ? 'Microphone flag enabled' : 'Microphone flag disabled'
  screenBtn.title = controls.screen ? 'Screen flag enabled' : 'Screen flag disabled'
  listenBtn.title = controls.listening ? 'Listening state enabled' : 'Listening state disabled'
}

function applyState(state) {
  if (!state || !config) return

  currentState = state
  const mode = normalizeMode(state.mode)
  const expression = normalizeExpression(state.expression)

  updateThinkingPulse(mode)

  const poseKey = poseKeyForState(state, mode)
  const pose = config.poses[poseKey] || config.poses.idleDefault

  const requestedEye = String(state.eye || 'open').replace(/^eye_/, '')
  const requestedMouth = String(state.mouth || 'closed').replace(/^mouth_/, '')

  const eyeName = normalizeEye(pose, requestedEye, mode, expression)
  const mouthName = normalizeMouth(pose, requestedMouth, mode, expression)

  renderAvatar(poseKey, pose, eyeName, mouthName, mode, expression)
  updateHudFromState(state)
}

async function pollState() {
  try {
    const state = await window.lyraAvatar.readState()
    applyState(state)
  } catch (error) {
    showStatus('State read failed')
  }
}

function runBlinkSequence(sequence) {
  if (!config || !currentState) return
  const mode = normalizeMode(currentState.mode)
  if (mode === 'thinking' || isPoseTransitioning) return

  const pose = config.poses[currentPoseKey] || config.poses.idleDefault
  if (!hasPart(pose, 'eye', 'closed')) return

  let delay = 0
  sequence.forEach((step) => {
    delay += step.after
    setTimeout(() => {
      if (normalizeMode(currentState.mode) === 'thinking' || isPoseTransitioning) return
      blinkLockedUntil = step.closed ? Date.now() + step.duration : 0
      if (step.closed) {
        setImage(eyes, partUrl(pose, 'eye', 'closed'))
      } else {
        applyState(currentState)
      }
    }, delay)
  })
}

function startBlinkLoop() {
  const tick = () => {
    const mode = normalizeMode(currentState.mode)
    const speaking = mode === 'speaking' || currentState.speaking
    const thinking = mode === 'thinking'

    const delay = thinking
      ? 4500 + Math.random() * 3600
      : speaking
        ? 2400 + Math.random() * 2600
        : 2800 + Math.random() * 4200

    setTimeout(() => {
      const doubleBlink = !speaking && Math.random() < 0.16

      if (doubleBlink) {
        runBlinkSequence([
          { closed: true, after: 0, duration: 110 },
          { closed: false, after: 115, duration: 0 },
          { closed: true, after: 90, duration: 95 },
          { closed: false, after: 105, duration: 0 }
        ])
      } else {
        runBlinkSequence([
          { closed: true, after: 0, duration: 120 + Math.random() * 35 },
          { closed: false, after: 135 + Math.random() * 35, duration: 0 }
        ])
      }

      tick()
    }, delay)
  }

  tick()
}

function showStatus(text) {
  status.textContent = text
  status.classList.add('visible')
  setTimeout(() => status.classList.remove('visible'), 1700)
}

function setHudVisible(visible) {
  hudVisible = Boolean(visible)
  document.body.classList.toggle('hud-hidden', !hudVisible)
  showStatus(hudVisible ? 'HUD visible' : 'HUD hidden. Ctrl+Shift+H to show')
}

async function sendCommand(command, label = command) {
  if (commandBusy) return

  commandBusy = true
  try {
    await window.lyraAvatar.writeCommand(command)
    showStatus(label)
  } catch (error) {
    showStatus('Command failed')
  } finally {
    commandBusy = false
  }
}

function bindHud() {
  document.querySelectorAll('[data-command]').forEach((button) => {
    button.addEventListener('click', async () => {
      const command = button.dataset.command
      const label = button.textContent.trim()
      await sendCommand(command, label)
    })
  })

  hideHudBtn.addEventListener('click', () => setHudVisible(false))

  reloadBtn.addEventListener('click', async () => {
    await window.lyraAvatar.writeCommand('reload_avatar')
    await window.lyraAvatar.reloadWindow()
  })

  closeBtn.addEventListener('click', async () => {
    await window.lyraAvatar.closeWindow()
  })
}

async function init() {
  config = await window.lyraAvatar.getConfig()

  currentIdlePoseKey = 'idleDefault'
  currentPoseKey = ''
  lastIdlePoseChangeAt = Date.now()
  scheduleNextIdlePoseChange(6, 10)

  bindHud()

  applyState({
    mode: 'idle',
    eye: 'open',
    mouth: 'closed',
    expression: 'neutral',
    speaking: false,
    controls: {
      microphone: false,
      screen: false,
      listening: false
    }
  })

  setInterval(pollState, 75)
  startBlinkLoop()

  window.lyraAvatar.onClickThroughChanged((enabled) => {
    showStatus(enabled ? 'Click-through enabled' : 'Click-through disabled')
  })

  window.lyraAvatar.onToggleHud(() => {
    setHudVisible(!hudVisible)
  })

  window.lyraAvatar.onAvatarCommandSent((command) => {
    if (command === 'stop_activity') {
      showStatus('Stop requested')
    }
  })
}

init()

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
let currentPoseKey = 'idleDefault'
let currentIdlePoseKey = 'idleDefault'
let lastIdlePoseChangeAt = 0
let blinkLockedUntil = 0
let thinkingEyeOpenUntil = 0
let lastThinkingEyePulseAt = 0
let hudVisible = true
let commandBusy = false

function joinUrl(baseUrl, file) {
  return `${baseUrl.replace(/\/$/, '')}/${file}`
}

function poseUrl(pose, file) {
  return joinUrl(joinUrl(config.posesBaseUrl, pose.id), file)
}

function partUrl(pose, type, name) {
  return joinUrl(joinUrl(joinUrl(config.posesBaseUrl, pose.id), pose.partsDir), `${type}_${name}.png`)
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

function pickIdlePose(force = false) {
  const now = Date.now()
  const interval = 13000 + Math.random() * 9000

  if (!force && now - lastIdlePoseChangeAt < interval) {
    return currentIdlePoseKey
  }

  const currentIndex = idlePoseKeys.indexOf(currentIdlePoseKey)
  const nextIndex = currentIndex < 0 ? 0 : (currentIndex + 1 + Math.floor(Math.random() * 2)) % idlePoseKeys.length
  currentIdlePoseKey = idlePoseKeys[nextIndex]
  lastIdlePoseChangeAt = now
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

function applyPose(poseKey) {
  if (poseKey === currentPoseKey) return

  currentPoseKey = poseKey
  const pose = config.poses[poseKey]
  setImage(base, poseUrl(pose, pose.baseImage))
}

function updateThinkingPulse(mode) {
  if (mode !== 'thinking') return

  const now = Date.now()
  if (now - lastThinkingEyePulseAt > 2600 + Math.random() * 2400) {
    thinkingEyeOpenUntil = now + 220
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

  applyPose(poseKey)

  const requestedEye = String(state.eye || 'open').replace(/^eye_/, '')
  const requestedMouth = String(state.mouth || 'closed').replace(/^mouth_/, '')

  const eyeName = normalizeEye(pose, requestedEye, mode, expression)
  const mouthName = normalizeMouth(pose, requestedMouth, mode, expression)

  avatar.className = `avatar ${mode} ${expression} pose-${pose.id}`
  setImage(eyes, partUrl(pose, 'eye', eyeName))
  setImage(mouth, partUrl(pose, 'mouth', mouthName))
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

function startBlinkLoop() {
  const tick = () => {
    const mode = normalizeMode(currentState.mode)
    const speaking = mode === 'speaking' || currentState.speaking
    const thinking = mode === 'thinking'

    const delay = thinking
      ? 4200 + Math.random() * 3200
      : speaking
        ? 2600 + Math.random() * 2200
        : 3200 + Math.random() * 3600

    setTimeout(() => {
      if (normalizeMode(currentState.mode) !== 'thinking') {
        blinkLockedUntil = Date.now() + 140
        const pose = config.poses[currentPoseKey] || config.poses.idleDefault
        if (hasPart(pose, 'eye', 'closed')) {
          setImage(eyes, partUrl(pose, 'eye', 'closed'))
        }
        setTimeout(() => applyState(currentState), 150)
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

  setInterval(pollState, 65)
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

const avatar = document.getElementById('avatar')
const base = document.getElementById('base')
const eyes = document.getElementById('eyes')
const mouth = document.getElementById('mouth')
const status = document.getElementById('status')

const availableEyes = ['open', 'closed', 'serious', 'happy']
const availableMouths = ['closed', 'middle_open', 'open', 'surprise', 'smile']

let poseBaseUrl = ''
let partsBaseUrl = ''
let baseImage = '01_idle_default.png'
let current = {}
let blinkLockedUntil = 0

function joinUrl(baseUrl, file) {
  return `${baseUrl.replace(/\/$/, '')}/${file}`
}

function poseAssetUrl(file) {
  return joinUrl(poseBaseUrl, file)
}

function partAssetUrl(name) {
  return joinUrl(partsBaseUrl, `${name}.png`)
}

function setImage(element, next) {
  if (element.dataset.src === next) return
  element.dataset.src = next
  element.src = next
}

function normalizeEye(value) {
  return availableEyes.includes(value) ? value : 'open'
}

function normalizeMouth(value) {
  return availableMouths.includes(value) ? value : 'closed'
}

function applyState(state) {
  if (!state) return

  current = state
  const mode = state.mode || 'idle'
  const expression = state.expression || 'neutral'
  const now = Date.now()
  const eye = now < blinkLockedUntil ? 'closed' : normalizeEye(state.eye)
  const mouthName = normalizeMouth(state.mouth)

  avatar.className = `avatar ${mode} ${expression}`
  setImage(eyes, partAssetUrl(`eye_${eye}`))
  setImage(mouth, partAssetUrl(`mouth_${mouthName}`))
}

async function pollState() {
  const state = await window.lyraAvatar.readState()
  applyState(state)
}

function startBlinkLoop() {
  const tick = () => {
    const speaking = current && current.speaking
    const delay = speaking ? 2600 + Math.random() * 2200 : 3200 + Math.random() * 3600

    setTimeout(() => {
      blinkLockedUntil = Date.now() + 140
      setImage(eyes, partAssetUrl('eye_closed'))
      setTimeout(() => applyState(current), 150)
      tick()
    }, delay)
  }

  tick()
}

function showStatus(text) {
  status.textContent = text
  status.classList.add('visible')
  setTimeout(() => status.classList.remove('visible'), 1600)
}

async function init() {
  const config = await window.lyraAvatar.getConfig()
  poseBaseUrl = config.poseBaseUrl
  partsBaseUrl = config.partsBaseUrl
  baseImage = config.baseImage || baseImage

  setImage(base, poseAssetUrl(baseImage))
  setImage(eyes, partAssetUrl('eye_open'))
  setImage(mouth, partAssetUrl('mouth_closed'))

  setInterval(pollState, 65)
  startBlinkLoop()

  window.lyraAvatar.onClickThroughChanged((enabled) => {
    showStatus(enabled ? 'Click-through ligado' : 'Click-through desligado')
  })
}

init()

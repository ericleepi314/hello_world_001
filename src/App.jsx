import { useCallback, useEffect, useRef, useState } from 'react'
import { GRID_SIZE, createGame, tick, tickInterval, turn } from './snake.js'

const CELL = 20
const BOARD = GRID_SIZE * CELL
const HIGH_SCORE_KEY = 'snake-high-score'

const KEY_DIRECTIONS = {
  ArrowUp: 'up',
  ArrowDown: 'down',
  ArrowLeft: 'left',
  ArrowRight: 'right',
  w: 'up',
  s: 'down',
  a: 'left',
  d: 'right',
}

function readHighScore() {
  try {
    return Number(localStorage.getItem(HIGH_SCORE_KEY)) || 0
  } catch {
    return 0
  }
}

function saveHighScore(score) {
  try {
    localStorage.setItem(HIGH_SCORE_KEY, String(score))
  } catch {
    // Storage can be unavailable (private mode); the high score just won't persist.
  }
}

export default function App() {
  const [game, setGame] = useState(() => createGame())
  const [highScore, setHighScore] = useState(readHighScore)
  const canvasRef = useRef(null)
  const touchStart = useRef(null)

  const steer = useCallback((direction) => {
    setGame((g) => {
      if (g.status === 'over' || g.status === 'won') return g
      const turned = turn(g, direction)
      return g.status === 'ready' ? { ...turned, status: 'playing' } : turned
    })
  }, [])

  // Space / Enter / the main button: start, pause, resume, or restart.
  const toggle = useCallback(() => {
    setGame((g) => {
      switch (g.status) {
        case 'ready':
        case 'paused':
          return { ...g, status: 'playing' }
        case 'playing':
          return { ...g, status: 'paused' }
        default:
          return { ...createGame(), status: 'playing' }
      }
    })
  }, [])

  // Game loop; speeds up as the score climbs.
  useEffect(() => {
    if (game.status !== 'playing') return
    const id = setInterval(() => setGame((g) => tick(g)), tickInterval(game.score))
    return () => clearInterval(id)
  }, [game.status, game.score])

  useEffect(() => {
    if (game.score > highScore) {
      setHighScore(game.score)
      saveHighScore(game.score)
    }
  }, [game.score, highScore])

  useEffect(() => {
    const onKey = (e) => {
      const direction = KEY_DIRECTIONS[e.key] ?? KEY_DIRECTIONS[e.key.toLowerCase()]
      if (direction) {
        e.preventDefault()
        steer(direction)
      } else if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault()
        toggle()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [steer, toggle])

  // Pause automatically when the tab is hidden.
  useEffect(() => {
    const onVisibility = () => {
      if (document.hidden) {
        setGame((g) => (g.status === 'playing' ? { ...g, status: 'paused' } : g))
      }
    }
    document.addEventListener('visibilitychange', onVisibility)
    return () => document.removeEventListener('visibilitychange', onVisibility)
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    const css = getComputedStyle(canvas)
    const color = (name) => css.getPropertyValue(name).trim()

    ctx.fillStyle = color('--board')
    ctx.fillRect(0, 0, BOARD, BOARD)

    ctx.fillStyle = color('--grid')
    for (let y = 0; y < GRID_SIZE; y++) {
      for (let x = (y % 2); x < GRID_SIZE; x += 2) {
        ctx.fillRect(x * CELL, y * CELL, CELL, CELL)
      }
    }

    if (game.food) {
      ctx.fillStyle = color('--food')
      ctx.beginPath()
      ctx.arc(
        game.food.x * CELL + CELL / 2,
        game.food.y * CELL + CELL / 2,
        CELL / 2 - 3,
        0,
        Math.PI * 2,
      )
      ctx.fill()
    }

    game.snake.forEach((p, i) => {
      ctx.fillStyle = color(i === 0 ? '--snake-head' : '--snake')
      ctx.beginPath()
      ctx.roundRect(p.x * CELL + 1, p.y * CELL + 1, CELL - 2, CELL - 2, 5)
      ctx.fill()
    })
  }, [game])

  const onTouchStart = (e) => {
    const t = e.touches[0]
    touchStart.current = { x: t.clientX, y: t.clientY }
  }

  const onTouchEnd = (e) => {
    const start = touchStart.current
    touchStart.current = null
    if (!start) return
    const t = e.changedTouches[0]
    const dx = t.clientX - start.x
    const dy = t.clientY - start.y
    if (Math.max(Math.abs(dx), Math.abs(dy)) < 20) return toggle()
    if (Math.abs(dx) > Math.abs(dy)) steer(dx > 0 ? 'right' : 'left')
    else steer(dy > 0 ? 'down' : 'up')
  }

  const overlay = {
    ready: { title: 'Snake', hint: 'Press an arrow key or Space to start' },
    paused: { title: 'Paused', hint: 'Press Space to resume' },
    over: { title: 'Game over', hint: `Score ${game.score} · press Space to play again` },
    won: { title: 'You win!', hint: 'The board is full · press Space to play again' },
  }[game.status]

  const buttonLabel = {
    ready: 'Start',
    playing: 'Pause',
    paused: 'Resume',
    over: 'Play again',
    won: 'Play again',
  }[game.status]

  return (
    <main className="app">
      <header className="scoreboard">
        <span>Score <strong>{game.score}</strong></span>
        <span>Best <strong>{highScore}</strong></span>
      </header>

      <div className="board" onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}>
        <canvas ref={canvasRef} width={BOARD} height={BOARD} aria-label="Snake game board" />
        {overlay && (
          <div className="overlay">
            <h1>{overlay.title}</h1>
            <p>{overlay.hint}</p>
          </div>
        )}
      </div>

      <button
        className="primary"
        onClick={(e) => {
          // Drop focus so a later Space/Enter doesn't also "click" the button.
          e.currentTarget.blur()
          toggle()
        }}
      >
        {buttonLabel}
      </button>

      <div className="dpad" aria-label="Direction controls">
        <button aria-label="Up" className="up" onClick={() => steer('up')}>▲</button>
        <button aria-label="Left" className="left" onClick={() => steer('left')}>◀</button>
        <button aria-label="Right" className="right" onClick={() => steer('right')}>▶</button>
        <button aria-label="Down" className="down" onClick={() => steer('down')}>▼</button>
      </div>

      <p className="help">Arrow keys or WASD to move · Space to pause · swipe on touch screens</p>
    </main>
  )
}

// Pure game logic for Snake. No DOM or React here, so it is easy to reason about.

export const GRID_SIZE = 20

export const DIRECTIONS = {
  up: { x: 0, y: -1 },
  down: { x: 0, y: 1 },
  left: { x: -1, y: 0 },
  right: { x: 1, y: 0 },
}

const OPPOSITE = { up: 'down', down: 'up', left: 'right', right: 'left' }

// Cap on buffered turns, so a fast double-tap (e.g. up then left) registers
// across two ticks instead of being dropped or reversing into the snake.
const MAX_QUEUED_TURNS = 2

export function createGame(random = Math.random) {
  const mid = Math.floor(GRID_SIZE / 2)
  const snake = [
    { x: mid, y: mid },
    { x: mid - 1, y: mid },
    { x: mid - 2, y: mid },
  ]
  return {
    snake,
    direction: 'right',
    queue: [],
    food: placeFood(snake, random),
    score: 0,
    status: 'ready', // ready | playing | paused | over | won
  }
}

export function turn(game, next) {
  if (!DIRECTIONS[next] || game.queue.length >= MAX_QUEUED_TURNS) return game
  const last = game.queue.at(-1) ?? game.direction
  if (next === last || next === OPPOSITE[last]) return game
  return { ...game, queue: [...game.queue, next] }
}

export function tick(game, random = Math.random) {
  if (game.status !== 'playing') return game

  const [direction = game.direction, ...queue] = game.queue
  const { x: dx, y: dy } = DIRECTIONS[direction]
  const head = { x: game.snake[0].x + dx, y: game.snake[0].y + dy }
  const eats = head.x === game.food?.x && head.y === game.food?.y

  // The tail moves out of the way this tick unless the snake is growing.
  const body = eats ? game.snake : game.snake.slice(0, -1)
  const hitsWall =
    head.x < 0 || head.y < 0 || head.x >= GRID_SIZE || head.y >= GRID_SIZE
  const hitsSelf = body.some((p) => p.x === head.x && p.y === head.y)
  if (hitsWall || hitsSelf) {
    return { ...game, direction, queue, status: 'over' }
  }

  const snake = [head, ...body]
  if (!eats) return { ...game, snake, direction, queue }

  const food = placeFood(snake, random)
  return {
    ...game,
    snake,
    direction,
    queue,
    food,
    score: game.score + 1,
    status: food ? 'playing' : 'won',
  }
}

function placeFood(snake, random) {
  const taken = new Set(snake.map((p) => `${p.x},${p.y}`))
  const free = []
  for (let y = 0; y < GRID_SIZE; y++) {
    for (let x = 0; x < GRID_SIZE; x++) {
      if (!taken.has(`${x},${y}`)) free.push({ x, y })
    }
  }
  return free.length ? free[Math.floor(random() * free.length)] : null
}

// Starts at 140ms per step and speeds up with each point, down to 60ms.
export function tickInterval(score) {
  return Math.max(60, 140 - score * 4)
}

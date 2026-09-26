# hello_world_001

A simple Snake game built with React and Vite.

## How to play

- **Arrow keys** or **WASD** to steer (on touch screens, swipe or use the on-screen pad)
- **Space** / **Enter** to start, pause, resume, or play again
- Eat the red food to grow and score; the snake speeds up as your score climbs
- Hitting a wall or yourself ends the game. Your best score is saved in the browser

## Requirements

- Node.js 20.19+ or 22.12+ (Vite 8 requirement)

## Getting started

```bash
npm install
npm run dev
```

Then open the URL printed in the terminal (default http://localhost:5173).

## Scripts

| Command | Description |
| --- | --- |
| `npm run dev` | Start the dev server with hot reload |
| `npm run build` | Build for production into `dist/` |
| `npm run preview` | Serve the production build locally |

## Project structure

```
index.html        Entry HTML, mounts #root
src/main.jsx      React root, renders <App />
src/App.jsx       Game UI: canvas rendering, input, game loop, scores
src/snake.js      Pure game logic (movement, collisions, food)
src/index.css     Styles, light + dark
vite.config.js    Vite + React plugin config
```

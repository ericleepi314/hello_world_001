# hello_world_001

A minimal "Hello, World!" app built with React and Vite.

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
src/App.jsx       The Hello World component (with a click counter)
src/index.css     Styles, light + dark
vite.config.js    Vite + React plugin config
```

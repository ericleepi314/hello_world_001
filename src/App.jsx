import { useState } from 'react'

export default function App() {
  const [count, setCount] = useState(0)

  return (
    <main className="app">
      <h1>Hello, World!</h1>
      <p>A minimal React app built with Vite.</p>
      <button onClick={() => setCount(count + 1)}>
        You clicked {count} {count === 1 ? 'time' : 'times'}
      </button>
    </main>
  )
}

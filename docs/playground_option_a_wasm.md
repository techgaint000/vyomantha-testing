# Client-Side WASM (Pyodide) Playground Architecture

This document details the architecture for **Option A: Client-Side WebAssembly (WASM) Execution**, utilizing Pyodide, CodeMirror 6, and Xterm.js.

---

## 1. Technological Stack

*   **Editor**: `@uiw/react-codemirror` (CodeMirror 6)
    *   *Why*: Extremely lightweight, highly customizable, and mobile-friendly. We will use the `@codemirror/lang-python` package.
*   **Terminal**: `xterm` & `xterm-addon-fit`
    *   *Why*: Provides a hardware-accelerated terminal UI inside the browser. It displays compilation logs, errors, and prints, and can listen to keystrokes.
*   **Engine**: `pyodide`
    *   *Why*: Brings the Python 3 runtime directly into WebAssembly. It compiles Python scripts to WebAssembly instructions executed locally by the browser.

---

## 2. Multi-Threaded Architecture (Web Worker)

To prevent the browser tab from freezing when executing intensive code (or infinite loops like `while True:`), Pyodide must run inside a background **Web Worker**.

```
+-------------------------------------------------------------------------+
|                              MAIN UI THREAD                             |
|                                                                         |
|  +------------------------+                  +-----------------------+  |
|  |     CodeMirror UI      |                  |      Xterm.js UI      |  |
|  +------------------------+                  +-----------------------+  |
|               |                                          ^              |
|               | (Send Code)                              | (stdout/err) |
|               v                                          |              |
|         [postMessage]                              [postMessage]        |
+---------------|------------------------------------------|--------------+
                |                                          |
+---------------|------------------------------------------|--------------+
|               v                                          |              |
|         [onmessage]                                      |              |
|  +-------------------------------------------------------+-----------+  |
|  |                        BACKGROUND WEB WORKER                      |  |
|  |                                                                   |  |
|  |   +------------------+                   +--------------------+   |  |
|  |   | Pyodide Runtime  | =================>| sys.stdout Wrapper |   |  |
|  |   +------------------+                   +--------------------+   |  |
|  +-------------------------------------------------------------------+  |
|                                                                         |
+-------------------------------------------------------------------------+
```

### Main Thread Responsibilities:
1. Render CodeMirror and capture code updates.
2. Render the Xterm.js terminal instance.
3. Spawns the Web Worker.
4. Listens for worker events (e.g. `stdout`, `stderr`, `run-finished`) and writes them to the terminal.

### Background Worker Responsibilities:
1. Load Pyodide and fetch WASM modules asynchronously.
2. Capture the run command.
3. Redirect standard output (`sys.stdout`) and error output (`sys.stderr`) to the worker's parent thread via `postMessage()`.
4. Run the code in an isolated scope.

---

## 3. Data Flow Detailed Steps

### A. Initialization
1. The user visits a course page and clicks **Playground**.
2. The page instantiates the Web Worker (`new Worker('/pyodide.worker.js')`).
3. The Web Worker calls `loadPyodide()` from CDN or static hosting and fetches the WASM binary.
4. Once loaded, the worker fires a `READY` message to the main thread.
5. The UI displays "Playground Ready" on the terminal.

### B. Execution Flow
1. The user types python code and presses **Run**.
2. The main thread calls `worker.postMessage({ type: 'RUN', code: codeContent })`.
3. The background worker receives the code:
   * It resets the custom stdout and stderr hooks.
   * It runs the code: `pyodide.runPython(code)`.
4. While running, any `print()` or output triggers the stdout hook, calling:
   `postMessage({ type: 'STDOUT', content: text })`.
5. The main thread receives `STDOUT` and writes it to the terminal: `xterm.write(text)`.
6. When execution finishes, the worker fires `postMessage({ type: 'FINISH' })` to re-enable the UI run button.

---

## 4. Proposed File Structure

Inside the `frontend/` directory, we can structure the playground components as follows:

```
frontend/
├── public/
│   └── workers/
│       └── pyodide.worker.js     # Background worker code to load & run Pyodide
├── components/
│   ├── PlaygroundPanel.jsx       # The Split-Screen layout wrapper
│   ├── PlaygroundEditor.jsx      # CodeMirror configuration component
│   └── PlaygroundTerminal.jsx    # Xterm.js wrapper and theme setup
└── hooks/
    └── usePyodide.js             # Custom React hook to manage worker lifecycle
```

---

## 5. Next Steps & Considerations

When we implement this, we will need to address:
*   **Caching**: Pyodide's WASM files are large (~6-10MB). We need to leverage browser cache headers so it only downloads once.
*   **Infinite Loop Safety**: If the user runs `while True: pass`, the Web Worker thread will lock up. We can implement a **Stop Button** that kills the active Web Worker instance and spawns a fresh one.
*   **Package Imports**: Pyodide supports automatic package detection. We can parse `import` statements and use `pyodide.loadPackage()` to dynamically fetch libraries (like `numpy` or `sympy`) when students need them.

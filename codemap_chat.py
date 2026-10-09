"""
CodeMap Context-Aware AI Chat & Voice Assistant
Allows interactive, multi-turn AI conversation about any specific file or folder.
Includes Windows offline Text-To-Speech (SAPI/System.Speech) and a browser-based
true Voice-to-Voice assistant powered by Web Speech API + Gemini API.
"""

import os
import re
import sys
import json
import tempfile
import threading
import subprocess
import webbrowser
import posixpath
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont

import codemap_core as core


def speak_text_async(text):
    """Speaks text in the background using Windows built-in SpeechSynthesizer."""
    if sys.platform != "win32" or not text.strip():
        return
    # Clean text of markdown and quotes
    cleaned = re.sub(r"[#*_`~>\[\]\(\)]", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()[:800]

    def _speak():
        try:
            # Escape single quotes for powershell
            ps_text = cleaned.replace("'", "''")
            cmd = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{ps_text}')"
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
                           creationflags=subprocess.CREATE_NO_WINDOW, timeout=20)
        except Exception:
            pass

    threading.Thread(target=_speak, daemon=True).start()


def build_folder_context(project, rel, is_file):
    """Extracts structured files, roles, entry points, and definitions for AI prompt context."""
    if not project:
        return "No project loaded."

    if is_file:
        node = project.nodes.get(rel)
        info = project.info.get(rel, {})
        text = core.read_text(node.path) if node else ""
        lines = text.splitlines()
        code_snippet = "\n".join(lines[:120]) + ("\n... [remaining code truncated]" if len(lines) > 120 else "")
        return f"""Target File: {rel}
Language: {info.get('lang', 'Unknown')}
Role: {info.get('role', 'Code file')}
Summary: {info.get('summary', '')}
Imports: {', '.join(info.get('imports', [])) or 'None'}
Used by: {', '.join(project.imported_by.get(rel, [])) or 'None'}
External Libraries: {', '.join(info.get('external', [])) or 'None'}
Definitions: {', '.join(info.get('defines', [])) or 'None'}
Endpoints: {', '.join(info.get('endpoints', [])) or 'None'}

CODE PREVIEW:
```{info.get('lang', '').lower()}
{code_snippet}
```"""
    else:
        node = project.nodes.get(rel)
        files = project.files_under(rel) if hasattr(project, "files_under") else []
        file_details = []
        for f in files[:40]:
            inf = project.info.get(f, {})
            name = posixpath.basename(f)
            file_details.append(f"• {name} ({f}): {inf.get('role', 'Code file')}")

        st = core.project_stats(project, rel)
        fs = core.folder_summary(project, rel)

        entry_candidates = [f for f in files if any(posixpath.basename(f).lower().startswith(x) for x in
                            ("main", "index", "app", "router", "route", "server", "layout", "page"))]

        return f"""Target Folder: {rel or '(Project Root)'}
Total Files inside this folder: {len(files)}
Direct Subfolders: {fs.get('subfolders', 0)}
Key Languages: {', '.join(f'{k} ({v})' for k, v in st.get('langs', {}).items())}
Potential Interface / App Starters: {', '.join(entry_candidates[:8]) or 'None obvious'}
Folder Depends on External Modules: {', '.join(k for k, _ in fs.get('out', [])[:6]) or 'None'}
External Modules that depend on this folder: {', '.join(k for k, _ in fs.get('in', [])[:6]) or 'None'}

FILES IN THIS FOLDER:
{chr(10).join(file_details)}
{f'... and {len(files) - 40} more files' if len(files) > 40 else ''}"""


def open_browser_voice_chat(project, rel, is_file, cfg):
    """
    Generates a self-contained HTML page using the Web Speech API (Microphone + TTS)
    connected to Gemini API for real-time, free voice-to-voice communication.
    """
    # Use dedicated voice API key if configured, otherwise fall back to the general Gemini key
    api_key = (cfg.get("key_voice", "").strip()
               or cfg.get("keys", {}).get("gemini", ""))
    # Default to gemini-2.5-flash-lite for voice — much higher free-tier quota than flash
    model = (cfg.get("model_voice", "").strip()
             or cfg.get("models", {}).get("gemini")
             or "gemini-2.5-flash-lite")
    target_name = rel or (project.name if project else "Project")
    context_text = build_folder_context(project, rel, is_file)
    custom_sys = cfg.get("system_voice", "").strip()
    voice_sys_prompt = f"{custom_sys}\n\n" if custom_sys else ""
    voice_sys_prompt += f"""Here is the code context of the folder or file we are working on:
{context_text}

You are a friendly teacher and real-time voice guide explaining this codebase to a creator who does not write complex code. Always use plain conversational English or Urdu according to the user's language. Use real-world analogies and step-by-step guidance. Be direct, natural, and concise."""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>🎙️ CodeMap Voice Chat - {target_name}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    :root {{
      --bg: #0f172a;
      --card: #1e293b;
      --text: #f8fafc;
      --accent: #3b82f6;
      --accent-glow: rgba(59, 130, 246, 0.4);
      --green: #10b981;
    }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      margin: 0;
      display: flex;
      flex-direction: column;
      height: 100vh;
    }}
    header {{
      padding: 16px 24px;
      background: var(--card);
      border-bottom: 1px solid #334155;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    header h1 {{
      margin: 0;
      font-size: 1.25rem;
      display: flex;
      align-items: center;
      gap: 8px;
    }}
    .badge {{
      background: #334155;
      padding: 4px 10px;
      border-radius: 999px;
      font-size: 0.8rem;
      color: #94a3b8;
    }}
    #chat-container {{
      flex: 1;
      overflow-y: auto;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 16px;
    }}
    .msg {{
      max-width: 75%;
      padding: 14px 18px;
      border-radius: 16px;
      line-height: 1.5;
      font-size: 0.95rem;
      white-space: pre-wrap;
    }}
    .msg-user {{
      align-self: flex-end;
      background: #2563eb;
      color: #ffffff;
      border-bottom-right-radius: 4px;
    }}
    .msg-ai {{
      align-self: flex-start;
      background: var(--card);
      color: #e2e8f0;
      border: 1px solid #334155;
      border-bottom-left-radius: 4px;
    }}
    #controls {{
      padding: 18px 24px;
      background: var(--card);
      border-top: 1px solid #334155;
      display: flex;
      flex-direction: column;
      gap: 12px;
    }}
    .chip-bar {{
      display: flex;
      gap: 8px;
      overflow-x: auto;
    }}
    .chip {{
      background: #334155;
      color: #93c5fd;
      padding: 6px 12px;
      border-radius: 999px;
      font-size: 0.82rem;
      cursor: pointer;
      border: 1px solid #475569;
      white-space: nowrap;
    }}
    .chip:hover {{
      background: #475569;
    }}
    .input-row {{
      display: flex;
      gap: 12px;
      align-items: center;
    }}
    #input-text {{
      flex: 1;
      padding: 12px 16px;
      border-radius: 12px;
      background: #0f172a;
      border: 1px solid #475569;
      color: #ffffff;
      font-size: 1rem;
      outline: none;
    }}
    #input-text:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 0 2px var(--accent-glow);
    }}
    .btn {{
      padding: 12px 20px;
      border-radius: 12px;
      border: none;
      font-weight: 600;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 0.95rem;
    }}
    .btn-primary {{
      background: var(--accent);
      color: white;
    }}
    .btn-mic {{
      background: #dc2626;
      color: white;
      width: 48px;
      height: 48px;
      padding: 0;
      border-radius: 50%;
      justify-content: center;
      transition: all 0.2s;
    }}
    .btn-mic.listening {{
      background: var(--green);
      box-shadow: 0 0 16px var(--green);
      animation: pulse 1.5s infinite;
    }}
    @keyframes pulse {{
      0% {{ transform: scale(1); }}
      50% {{ transform: scale(1.08); }}
      100% {{ transform: scale(1); }}
    }}
    #voice-status {{
      font-size: 0.8rem;
      color: #94a3b8;
    }}
  </style>
</head>
<body>
  <header>
    <h1>🎙️ AI Voice Chat <span class="badge">Target: {target_name}</span></h1>
    <div style="display: flex; gap: 12px; align-items: center;">
      <select id="lang-select" style="background: #0f172a; color: #f8fafc; border: 1px solid #475569; border-radius: 6px; padding: 4px 8px; font-size: 0.85rem;">
        <option value="ur-PK" selected>🇵🇰 Urdu / اردو (Pakistan)</option>
        <option value="en-US">🇺🇸 English (US)</option>
      </select>
      <label style="font-size: 0.85rem; color: #94a3b8; display: flex; align-items: center; gap: 6px;">
        <input type="checkbox" id="tts-toggle" checked> Auto Read Responses
      </label>
    </div>
  </header>

  <div id="chat-container">
    <div class="msg msg-ai">👋 Hello! I am your AI code guide for <strong>{target_name}</strong>.<br><br>You can type your question or click the <strong>Red Microphone</strong> to speak directly. Try asking:<br>• <em>"Where does this interface start?"</em><br>• <em>"Which file should I edit to change the layout?"</em><br>• <em>"Explain what this folder does step-by-step."</em></div>
  </div>

  <div id="controls">
    <div class="chip-bar">
      <span class="chip" onclick="askChip('Where does this interface start and how do I run it?')">👉 Where does this start?</span>
      <span class="chip" onclick="askChip('Explain all files in this folder in plain English')">👉 Explain all files</span>
      <span class="chip" onclick="askChip('How do these files connect to each other?')">👉 How do files connect?</span>
      <span class="chip" onclick="askChip('What would break if this folder stopped working?')">👉 Why does this matter?</span>
    </div>

    <div class="input-row">
      <button id="mic-btn" class="btn btn-mic" title="Click to Speak" onclick="toggleVoice()">🎙️</button>
      <input type="text" id="input-text" placeholder="Ask anything or click the microphone to speak..." onkeydown="if(event.key==='Enter') sendMessage()">
      <button class="btn btn-primary" onclick="sendMessage()">Send ➔</button>
    </div>
    <div id="voice-status">Microphone ready. Click 🎙️ to start hands-free conversation.</div>
  </div>

  <script>
    const API_KEY = {json.dumps(api_key)};
    const MODEL = {json.dumps(model)};
    const VOICE_SYS = {json.dumps(voice_sys_prompt)};

    let history = [
      {{
        role: "user",
        parts: [{{ text: VOICE_SYS }}]
      }},
      {{
        role: "model",
        parts: [{{ text: "Understood! I have studied the files, structure, and system rules for this project. I am ready to guide you naturally." }}]
      }}
    ];

    const chatContainer = document.getElementById("chat-container");
    const inputEl = document.getElementById("input-text");
    const micBtn = document.getElementById("mic-btn");
    const voiceStatus = document.getElementById("voice-status");
    const ttsToggle = document.getElementById("tts-toggle");

    let recognition = null;
    let isListening = false;
    let autoRestartMic = false;   // tracks whether mic should restart after AI reply
    let isSpeaking = false;
    let retryCountdown = null;

    // ── Speech Recognition Setup ──────────────────────────────────────────
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {{
      const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognition = new SpeechRec();
      recognition.continuous = true;       // keep mic open continuously
      recognition.interimResults = false;
      recognition.lang = 'ur-PK';

      recognition.onstart = () => {{
        isListening = true;
        micBtn.classList.add("listening");
        voiceStatus.innerText = "🎙 Listening… speak anytime (بولیں، سن رہا ہوں)";
      }};

      recognition.onresult = (e) => {{
        // Grab the last final result
        for (let i = e.resultIndex; i < e.results.length; i++) {{
          if (e.results[i].isFinal) {{
            const transcript = e.results[i][0].transcript.trim();
            if (transcript) {{
              inputEl.value = transcript;
              voiceStatus.innerText = "🔊 Heard: \\"" + transcript + "\\"";
              sendMessage();
            }}
          }}
        }}
      }};

      recognition.onerror = (e) => {{
        if (e.error === 'no-speech') return;  // ignore silence — just keep going
        isListening = false;
        micBtn.classList.remove("listening");
        autoRestartMic = false;
        voiceStatus.innerText = "⚠ Voice error: " + e.error + " — Click 🎙 to retry.";
      }};

      recognition.onend = () => {{
        isListening = false;
        micBtn.classList.remove("listening");
        // Auto-restart mic if AI isn't speaking and user hasn't stopped
        if (autoRestartMic && !isSpeaking) {{
          try {{ recognition.start(); }} catch(e) {{}}
        }}
      }};
    }} else {{
      voiceStatus.innerText = "Note: Voice input is supported in Google Chrome & Microsoft Edge.";
    }}

    function toggleVoice() {{
      if (!recognition) {{
        alert("Speech Recognition is supported in Microsoft Edge or Google Chrome.");
        return;
      }}
      if (isListening || autoRestartMic) {{
        // STOP hands-free mode
        autoRestartMic = false;
        recognition.stop();
        voiceStatus.innerText = "🛑 Hands-free mode stopped. Click 🎙 to start again.";
      }} else {{
        // START hands-free mode
        autoRestartMic = true;
        window.speechSynthesis.cancel();
        const langSelect = document.getElementById("lang-select");
        if (langSelect) recognition.lang = langSelect.value;
        try {{ recognition.start(); }} catch(e) {{}}
      }}
    }}

    function speakText(text) {{
      if (!ttsToggle.checked || !('speechSynthesis' in window)) {{
        // Even if TTS off, restart mic after AI response
        if (autoRestartMic) try {{ recognition.start(); }} catch(e) {{}}
        return;
      }}
      window.speechSynthesis.cancel();
      const clean = text.replace(/[*_#`~>\\[\\]]/g, '');
      const utter = new SpeechSynthesisUtterance(clean);
      utter.rate = 1.0;

      const voices = window.speechSynthesis.getVoices();
      const langSelect = document.getElementById("lang-select");
      const currentLang = langSelect ? langSelect.value : 'ur-PK';
      utter.lang = currentLang;

      if (currentLang.startsWith("ur")) {{
        const urVoice = voices.find(v => v.lang.startsWith("ur") || v.name.toLowerCase().includes("urdu") || v.name.toLowerCase().includes("asad") || v.name.toLowerCase().includes("uzma"));
        if (urVoice) utter.voice = urVoice;
      }}

      isSpeaking = true;
      utter.onend = () => {{
        isSpeaking = false;
        // Restart mic after AI has finished speaking
        if (autoRestartMic) {{
          try {{ recognition.start(); }} catch(e) {{}}
        }}
      }};
      utter.onerror = () => {{
        isSpeaking = false;
        if (autoRestartMic) try {{ recognition.start(); }} catch(e) {{}}
      }};
      window.speechSynthesis.speak(utter);
    }}

    function appendMsg(text, isUser) {{
      const div = document.createElement("div");
      div.className = "msg " + (isUser ? "msg-user" : "msg-ai");
      div.innerText = text;
      chatContainer.appendChild(div);
      chatContainer.scrollTop = chatContainer.scrollHeight;
      return div;
    }}

    function askChip(prompt) {{
      inputEl.value = prompt;
      sendMessage();
    }}

    function startRetryCountdown(seconds, onDone) {{
      if (retryCountdown) clearInterval(retryCountdown);
      let remaining = seconds;
      voiceStatus.innerText = `⏳ Quota limit hit. Retrying in ${{remaining}}s…`;
      retryCountdown = setInterval(() => {{
        remaining--;
        if (remaining <= 0) {{
          clearInterval(retryCountdown);
          retryCountdown = null;
          voiceStatus.innerText = "🔄 Retrying…";
          onDone();
        }} else {{
          voiceStatus.innerText = `⏳ Quota limit hit. Retrying in ${{remaining}}s…`;
        }}
      }}, 1000);
    }}

    async function doApiCall() {{
      const url = `https://generativelanguage.googleapis.com/v1beta/models/${{MODEL}}:generateContent?key=${{API_KEY}}`;
      const resp = await fetch(url, {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{ contents: history }})
      }});

      if (!resp.ok) {{
        const errData = await resp.json().catch(() => ({{}}));
        const msg = errData.error?.message || "API request failed: " + resp.status;
        // Parse retry delay from quota error message
        if (resp.status === 429) {{
          const match = msg.match(/(\\d+\\.?\\d*)\\s*s/);
          const waitSec = match ? Math.ceil(parseFloat(match[1])) + 2 : 62;
          throw {{ isQuota: true, waitSec, message: msg }};
        }}
        throw new Error(msg);
      }}

      const data = await resp.json();
      return data.candidates?.[0]?.content?.parts?.[0]?.text || "No response received.";
    }}

    async function sendMessage() {{
      const q = inputEl.value.trim();
      if (!q) return;
      inputEl.value = "";
      appendMsg(q, true);

      // Pause mic while AI is thinking
      if (isListening) {{ try {{ recognition.stop(); }} catch(e) {{}} }}

      history.push({{ role: "user", parts: [{{ text: q }}] }});
      voiceStatus.innerText = "⚙ AI is thinking…";

      const attempt = async () => {{
        try {{
          const reply = await doApiCall();
          history.push({{ role: "model", parts: [{{ text: reply }}] }});
          appendMsg(reply, false);
          voiceStatus.innerText = autoRestartMic
            ? "✅ AI answered — 🎙 listening for your next question…"
            : "✅ AI answered. Click 🎙 for hands-free or type your next question.";
          speakText(reply);
        }} catch (err) {{
          if (err.isQuota) {{
            // Show retry countdown then retry automatically
            startRetryCountdown(err.waitSec, attempt);
            appendMsg(`⏳ Quota limit reached (free tier). Auto-retrying in ${{err.waitSec}}s…\\n\\n(Tip: Add a separate Voice API key in ⚙️ Settings → Specialized Models to avoid this.)`, false);
          }} else {{
            appendMsg("⚠️ Error: " + (err.message || err), false);
            voiceStatus.innerText = "Error communicating with AI.";
            if (autoRestartMic) try {{ recognition.start(); }} catch(e) {{}}
          }}
        }}
      }};

      await attempt();
    }}
  </script>
</body>
</html>"""

    fd, tmp = tempfile.mkstemp(prefix="codemap_voice_chat_", suffix=".html")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(html)
    webbrowser.open("file://" + os.path.abspath(tmp))


# ==========================================================================
# Native Tkinter Context-Aware AI Chat Dialog
# ==========================================================================
class FolderChatDialog(tk.Toplevel):
    """
    Dedicated multi-turn interactive chat dialog for asking questions about a specific
    folder or file. Features Windows offline TTS and link to Web Speech voice mode.
    """

    def __init__(self, master, app, rel, is_file):
        super().__init__(master)
        self.app = app
        self.project = app.project
        self.rel = rel
        self.is_file = is_file
        self.history = []
        self.voice_enabled = tk.BooleanVar(value=True)

        target_name = rel or (self.project.name if self.project else "Project")
        icon = "📄 File" if is_file else "📁 Folder"
        self.title(f"💬 CodeMap AI Guide - {icon}: {posixpath.basename(target_name) or target_name}")
        self.geometry("680x620")
        self.minsize(500, 450)

        self._build_ui(target_name, icon)
        self._init_conversation()

    def _build_ui(self, target_name, icon):
        # Header
        hdr = ttk.Frame(self)
        hdr.pack(fill="x", padx=12, pady=10)

        t_lbl = ttk.Label(hdr, text=f"{icon}: {posixpath.basename(target_name) or target_name}",
                          font=("Segoe UI", 11, "bold"), foreground="#1e293b")
        t_lbl.pack(side="left")

        ttk.Button(hdr, text="🌐 Full Voice Mode (Browser)", command=self._launch_browser_voice).pack(side="right", padx=(6, 0))
        ttk.Checkbutton(hdr, text="🔊 Speak replies", variable=self.voice_enabled).pack(side="right", padx=6)

        # Chat display
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=12, pady=(0, 6))

        self.chat_txt = tk.Text(body, wrap="word", font=("Segoe UI", 10), bd=0, padx=12, pady=10, bg="#f8fafc")
        ys = ttk.Scrollbar(body, orient="vertical", command=self.chat_txt.yview)
        self.chat_txt.configure(yscrollcommand=ys.set)
        self.chat_txt.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")

        self.chat_txt.tag_configure("user", foreground="#1d4ed8", font=("Segoe UI", 10, "bold"), spacing1=10, spacing3=2)
        self.chat_txt.tag_configure("ai", foreground="#0f172a", spacing1=4, spacing3=8)
        self.chat_txt.tag_configure("system", foreground="#64748b", font=("Segoe UI", 9, "italic"), spacing3=8)
        self.chat_txt.tag_configure("meta", foreground="#475569", background="#e2e8f0", font=("Segoe UI", 8))

        # Quick chips
        chips = ttk.Frame(self)
        chips.pack(fill="x", padx=12, pady=2)
        ttk.Button(chips, text="👉 Where does this start?",
                   command=lambda: self._ask_prompt("Where does this interface/code start and how do I run it?")).pack(side="left", padx=2)
        ttk.Button(chips, text="👉 Explain all files",
                   command=lambda: self._ask_prompt("Explain what each file in this folder does in plain English.")).pack(side="left", padx=2)
        ttk.Button(chips, text="👉 How do files connect?",
                   command=lambda: self._ask_prompt("How do these files connect with each other?")).pack(side="left", padx=2)

        # Input box + inline mic + send
        in_frame = ttk.Frame(self)
        in_frame.pack(fill="x", padx=12, pady=(4, 4))

        # Inline voice button (launches browser voice — most prominent placement)
        self.mic_btn = tk.Button(
            in_frame,
            text="🎙",
            font=("Segoe UI", 14),
            bg="#dc2626", fg="white",
            activebackground="#b91c1c", activeforeground="white",
            relief="flat", bd=0,
            cursor="hand2",
            width=3,
            command=self._launch_browser_voice
        )
        self.mic_btn.pack(side="left", padx=(0, 6))

        self.input_entry = ttk.Entry(in_frame, font=("Segoe UI", 10))
        self.input_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.input_entry.bind("<Return>", lambda e: self.send_message())

        self.send_btn = ttk.Button(in_frame, text="Send ➔", width=9, command=self.send_message)
        self.send_btn.pack(side="left")

        # Small status line under input
        self.chat_status = ttk.Label(self, text="🎙 Click the red mic button for hands-free voice conversation (browser opens)",
                                     font=("Segoe UI", 8), foreground="#64748b")
        self.chat_status.pack(fill="x", padx=14, pady=(0, 8))


    def _init_conversation(self):
        context = build_folder_context(self.project, self.rel, self.is_file)
        self.system_prompt = f"""You are an expert AI software architect and patient teacher helping a non-programmer understand a specific folder or file:
{context}

CRITICAL RULES:
1. Explain in plain everyday English using simple real-world analogies.
2. If asked how to run or open the interface, pinpoint exactly which file handles UI (e.g. App.tsx, index.html), which handles routes/backend (e.g. route.ts, server.js), and give step-by-step instructions.
3. Be direct, clear, and structured."""

        self.chat_txt.configure(state="normal")
        self.chat_txt.insert("end", f"✨ Context loaded for: {self.rel or 'Project Root'}\nAsk any question below or click a quick suggestion.\n\n", "system")
        self.chat_txt.configure(state="disabled")

    def _launch_browser_voice(self):
        open_browser_voice_chat(self.project, self.rel, self.is_file, self.app.cfg)

    def _ask_prompt(self, prompt_text):
        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, prompt_text)
        self.send_message()

    def send_message(self):
        q = self.input_entry.get().strip()
        if not q:
            return
        self.input_entry.delete(0, "end")

        self.chat_txt.configure(state="normal")
        self.chat_txt.insert("end", f"You: {q}\n", "user")
        self.chat_txt.configure(state="disabled")
        self.chat_txt.yview_moveto(1.0)

        self.history.append({"role": "user", "parts": [q]})
        self.send_btn.configure(state="disabled")
        if hasattr(self, "chat_status"):
            self.chat_status.configure(text="⚙ AI is thinking…", foreground="#1e40af")

        cfg = self.app.cfg
        # Use dedicated voice key for chat if configured
        voice_key = cfg.get("key_voice", "").strip()
        chat_cfg = dict(cfg)
        if voice_key and cfg.get("provider") == "gemini":
            chat_cfg = dict(cfg)
            chat_cfg["keys"] = dict(cfg.get("keys", {}))
            chat_cfg["keys"]["gemini"] = voice_key

        v_model = cfg.get("model_voice", "").strip() or None
        v_sys = cfg.get("system_voice", "").strip()
        combined_sys = f"{v_sys}\n\n{self.system_prompt}" if v_sys else self.system_prompt

        def work():
            # Combine history into full prompt for ai_generate
            dialogue = [f"SYSTEM INSTRUCTION:\n{combined_sys}\n"]
            for h in self.history:
                dialogue.append(f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['parts'][0]}")
            full_prompt = "\n\n".join(dialogue)
            return core.ai_generate(chat_cfg, full_prompt, timeout=120, max_tokens=1800,
                                    system_instruction=combined_sys, model_override=v_model)

        def done(res, err):
            self.send_btn.configure(state="normal")
            self.chat_txt.configure(state="normal")
            if err:
                self.chat_txt.insert("end", f"⚠️ Error: {err}\n\n", "ai")
                if hasattr(self, "chat_status"):
                    self.chat_status.configure(text="⚠️ Error communicating with AI.", foreground="#b91c1c")
            else:
                self.history.append({"role": "model", "parts": [res]})
                self.chat_txt.insert("end", f"AI: {res}\n\n", "ai")
                if self.voice_enabled.get():
                    speak_text_async(res)
                if hasattr(self, "chat_status"):
                    self.chat_status.configure(
                        text="🎙 Click the red mic button for hands-free voice conversation (browser opens)",
                        foreground="#64748b")
            self.chat_txt.configure(state="disabled")
            self.chat_txt.yview_moveto(1.0)

        self.app.run_bg(work, done)

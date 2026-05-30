import os
import queue
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


APP_TITLE = "Whisper - Transcricao"
WHISPER_EXE = Path.home() / "AppData" / "Local" / "Programs" / "Python" / "Python314" / "Scripts" / "whisper.exe"


class WhisperGui(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("780x560")
        self.minsize(720, 500)

        self.process = None
        self.log_queue = queue.Queue()

        self.input_path = tk.StringVar()
        self.output_dir = tk.StringVar(value=str(Path.home() / "Documents"))
        self.model = tk.StringVar(value="tiny")
        self.language = tk.StringVar(value="Portuguese")
        self.output_format = tk.StringVar(value="txt")
        self.fp16 = tk.BooleanVar(value=False)

        self._build_ui()
        self.after(120, self._drain_log_queue)

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        form = ttk.Frame(self, padding=14)
        form.grid(row=0, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Arquivo").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Entry(form, textvariable=self.input_path).grid(row=0, column=1, sticky="ew", pady=5)
        ttk.Button(form, text="Escolher", command=self._choose_input).grid(row=0, column=2, padx=(8, 0), pady=5)

        ttk.Label(form, text="Saida").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=5)
        ttk.Entry(form, textvariable=self.output_dir).grid(row=1, column=1, sticky="ew", pady=5)
        ttk.Button(form, text="Escolher", command=self._choose_output).grid(row=1, column=2, padx=(8, 0), pady=5)

        options = ttk.Frame(form)
        options.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        for i in range(8):
            options.columnconfigure(i, weight=1)

        ttk.Label(options, text="Modelo").grid(row=0, column=0, sticky="w")
        ttk.Combobox(
            options,
            textvariable=self.model,
            values=("tiny", "base", "small", "medium", "large-v3", "turbo"),
            width=12,
            state="readonly",
        ).grid(row=1, column=0, sticky="ew", padx=(0, 10))

        ttk.Label(options, text="Idioma").grid(row=0, column=1, sticky="w")
        ttk.Combobox(
            options,
            textvariable=self.language,
            values=("Portuguese", "English", "Spanish", "French", "German", "Italian", "auto"),
            width=14,
        ).grid(row=1, column=1, sticky="ew", padx=(0, 10))

        ttk.Label(options, text="Formato").grid(row=0, column=2, sticky="w")
        ttk.Combobox(
            options,
            textvariable=self.output_format,
            values=("txt", "srt", "vtt", "json", "tsv", "all"),
            width=10,
            state="readonly",
        ).grid(row=1, column=2, sticky="ew", padx=(0, 10))

        ttk.Checkbutton(options, text="FP16", variable=self.fp16).grid(row=1, column=3, sticky="w")

        buttons = ttk.Frame(form)
        buttons.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(14, 0))
        buttons.columnconfigure(2, weight=1)

        self.run_button = ttk.Button(buttons, text="Transcrever", command=self._run)
        self.run_button.grid(row=0, column=0, padx=(0, 8))
        self.cancel_button = ttk.Button(buttons, text="Cancelar", command=self._cancel, state="disabled")
        self.cancel_button.grid(row=0, column=1)
        self.progress = ttk.Progressbar(buttons, mode="indeterminate")
        self.progress.grid(row=0, column=2, sticky="ew", padx=(12, 0))

        log_frame = ttk.Frame(self, padding=(14, 0, 14, 14))
        log_frame.grid(row=1, column=0, sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log = tk.Text(log_frame, wrap="word", height=18)
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(log_frame, command=self.log.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scroll.set)

    def _choose_input(self):
        filetypes = (
            ("Audio e video", "*.mp3 *.wav *.m4a *.mp4 *.aac *.flac *.ogg *.wma *.mov *.mkv"),
            ("Todos os arquivos", "*.*"),
        )
        selected = filedialog.askopenfilename(title="Escolha o audio ou video", filetypes=filetypes)
        if selected:
            self.input_path.set(selected)
            self.output_dir.set(str(Path(selected).parent))

    def _choose_output(self):
        selected = filedialog.askdirectory(title="Escolha a pasta de saida")
        if selected:
            self.output_dir.set(selected)

    def _run(self):
        audio = Path(self.input_path.get().strip('" '))
        out_dir = Path(self.output_dir.get().strip('" '))

        if not audio.exists():
            messagebox.showerror(APP_TITLE, "Escolha um arquivo de audio ou video valido.")
            return
        if not out_dir.exists():
            messagebox.showerror(APP_TITLE, "Escolha uma pasta de saida valida.")
            return
        if not WHISPER_EXE.exists():
            messagebox.showerror(APP_TITLE, f"Nao encontrei o Whisper em:\n{WHISPER_EXE}")
            return

        command = [
            str(WHISPER_EXE),
            str(audio),
            "--model",
            self.model.get(),
            "--output_format",
            self.output_format.get(),
            "--output_dir",
            str(out_dir),
            "--fp16",
            "True" if self.fp16.get() else "False",
        ]

        language = self.language.get().strip()
        if language and language.lower() != "auto":
            command.extend(["--language", language])

        self._set_running(True)
        self._append_log("Executando:\n" + subprocess.list2cmdline(command) + "\n\n")

        worker = threading.Thread(target=self._run_process, args=(command, out_dir), daemon=True)
        worker.start()

    def _run_process(self, command, out_dir):
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
            )
            assert self.process.stdout is not None
            for line in self.process.stdout:
                self.log_queue.put(line)
            code = self.process.wait()
            if code == 0:
                self.log_queue.put(f"\nConcluido. Arquivos salvos em: {out_dir}\n")
            else:
                self.log_queue.put(f"\nFinalizado com erro. Codigo: {code}\n")
        except Exception as exc:
            self.log_queue.put(f"\nErro: {exc}\n")
        finally:
            self.process = None
            self.log_queue.put(("DONE", None))

    def _cancel(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self._append_log("\nCancelando...\n")

    def _set_running(self, running):
        self.run_button.configure(state="disabled" if running else "normal")
        self.cancel_button.configure(state="normal" if running else "disabled")
        if running:
            self.progress.start(12)
        else:
            self.progress.stop()

    def _append_log(self, text):
        self.log.insert("end", text)
        self.log.see("end")

    def _drain_log_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple) and item[0] == "DONE":
                    self._set_running(False)
                else:
                    self._append_log(item)
        except queue.Empty:
            pass
        self.after(120, self._drain_log_queue)


if __name__ == "__main__":
    app = WhisperGui()
    app.mainloop()

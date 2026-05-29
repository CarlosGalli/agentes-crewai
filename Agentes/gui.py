"""
gui.py — Interfaz gráfica con tkinter.
Se abre con: python gui.py
"""

import sys
import os
import importlib
import inspect
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

sys.path.insert(0, str(Path(__file__).parent))
from agentes.registry import AGENTES, CATEGORIAS

# ── paleta ────────────────────────────────────────────────────────────────────
PURPLE  = "#534AB7"
GREEN   = "#1D9E75"
TEAL    = "#0F6E56"
GRAY    = "#888780"
DARK    = "#2C2C2A"
BG      = "#F8F8F6"
BG2     = "#EEEDFE"
WHITE   = "#FFFFFF"
RED     = "#E24B4A"
FONT    = ("Segoe UI", 10)
FONT_B  = ("Segoe UI", 10, "bold")
FONT_T  = ("Consolas", 9)

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Agentes — Galli CBC")
        self.geometry("900x620")
        self.minsize(800, 500)
        self.configure(bg=BG)
        self.resizable(True, True)

        self._agente_key   = tk.StringVar()
        self._param_vars   = {}   # nombre → StringVar / BooleanVar
        self._param_widgets = {}  # nombre → widget

        self._build_ui()
        self._seleccionar_primero()

    # ── construcción de la UI ─────────────────────────────────────────────
    def _build_ui(self):
        # ── Encabezado ────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg=PURPLE, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="AGENTES", font=("Segoe UI", 16, "bold"),
                 bg=PURPLE, fg=WHITE).pack(side="left", padx=18, pady=10)
        tk.Label(hdr, text="Galli CBC — Sistema multi-agente",
                 font=("Segoe UI", 10), bg=PURPLE, fg="#CECBF6").pack(
                 side="left", pady=10)

        # ── Cuerpo principal ──────────────────────────────────────────────
        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=0, pady=0)

        # Panel izquierdo: lista de agentes
        left = tk.Frame(body, bg=WHITE, width=240,
                        highlightthickness=1, highlightbackground="#D3D1C7")
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        tk.Label(left, text="Agentes disponibles", font=FONT_B,
                 bg=WHITE, fg=GRAY, anchor="w").pack(fill="x", padx=12, pady=(12,4))

        self._tree = ttk.Treeview(left, show="tree", selectmode="browse")
        self._tree.pack(fill="both", expand=True, padx=6, pady=(0,6))
        self._tree.bind("<<TreeviewSelect>>", self._on_select)
        self._tree.tag_configure("cat",    font=("Segoe UI", 9, "bold"), foreground=PURPLE)
        self._tree.tag_configure("agente", font=("Segoe UI", 10),        foreground=DARK)

        style = ttk.Style()
        style.configure("Treeview", background=WHITE, fieldbackground=WHITE,
                        rowheight=26, font=("Segoe UI", 10))
        style.map("Treeview", background=[("selected", BG2)],
                  foreground=[("selected", DARK)])

        self._poblar_tree()

        # Panel derecho: detalle + parámetros + log
        right = tk.Frame(body, bg=BG)
        right.pack(side="left", fill="both", expand=True)

        # Descripción
        self._frm_desc = tk.Frame(right, bg=BG2,
                                   highlightthickness=1, highlightbackground="#AFA9EC")
        self._frm_desc.pack(fill="x", padx=12, pady=(12,6))
        self._lbl_nombre = tk.Label(self._frm_desc, text="", font=("Segoe UI", 12, "bold"),
                                     bg=BG2, fg=PURPLE, anchor="w")
        self._lbl_nombre.pack(fill="x", padx=10, pady=(8,2))
        self._lbl_desc = tk.Label(self._frm_desc, text="", font=("Segoe UI", 9),
                                   bg=BG2, fg=GRAY, anchor="w", wraplength=560, justify="left")
        self._lbl_desc.pack(fill="x", padx=10, pady=(0,8))

        # Parámetros
        tk.Label(right, text="Parámetros", font=FONT_B, bg=BG, fg=GRAY,
                 anchor="w").pack(fill="x", padx=14, pady=(4,2))
        self._frm_params = tk.Frame(right, bg=BG)
        self._frm_params.pack(fill="x", padx=12, pady=(0,8))

        # Botón ejecutar
        btn_frame = tk.Frame(right, bg=BG)
        btn_frame.pack(fill="x", padx=12, pady=(0,6))
        self._btn_run = tk.Button(btn_frame, text="▶  Ejecutar",
                                   font=("Segoe UI", 11, "bold"),
                                   bg=GREEN, fg=WHITE, activebackground=TEAL,
                                   activeforeground=WHITE, relief="flat",
                                   cursor="hand2", padx=18, pady=7,
                                   command=self._ejecutar)
        self._btn_run.pack(side="left")
        self._lbl_status = tk.Label(btn_frame, text="", font=("Segoe UI", 9),
                                     bg=BG, fg=GRAY)
        self._lbl_status.pack(side="left", padx=12)

        # Log
        tk.Label(right, text="Log", font=FONT_B, bg=BG, fg=GRAY,
                 anchor="w").pack(fill="x", padx=14, pady=(0,2))
        self._log = scrolledtext.ScrolledText(right, font=FONT_T, bg="#1E1E2E",
                                               fg="#CDD6F4", insertbackground="white",
                                               relief="flat", height=10, state="disabled")
        self._log.pack(fill="both", expand=True, padx=12, pady=(0,12))
        self._log.tag_config("ok",   foreground="#A6E3A1")
        self._log.tag_config("err",  foreground="#F38BA8")
        self._log.tag_config("info", foreground="#89B4FA")
        self._log.tag_config("dim",  foreground="#6C7086")

    def _poblar_tree(self):
        self._key_map = {}  # iid → key de agente
        for cat in CATEGORIAS:
            cat_id = self._tree.insert("", "end", text=f"  {cat}", tags=("cat",),
                                        open=True)
            for key, ag in AGENTES.items():
                if ag["categoria"] == cat:
                    iid = self._tree.insert(cat_id, "end",
                                             text=f"  {ag['nombre']}", tags=("agente",))
                    self._key_map[iid] = key

    def _seleccionar_primero(self):
        children = self._tree.get_children()
        if children:
            first_cat = children[0]
            subs = self._tree.get_children(first_cat)
            if subs:
                self._tree.selection_set(subs[0])
                self._tree.focus(subs[0])

    # ── eventos ───────────────────────────────────────────────────────────
    def _on_select(self, event):
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        key = self._key_map.get(iid)
        if not key:
            return
        self._agente_key.set(key)
        self._mostrar_agente(key)

    def _mostrar_agente(self, key: str):
        ag = AGENTES[key]
        self._lbl_nombre.config(text=ag["nombre"])
        self._lbl_desc.config(text=ag["descripcion"])
        self._construir_params(key)

    def _construir_params(self, key: str):
        # Limpiar widgets anteriores
        for w in self._frm_params.winfo_children():
            w.destroy()
        self._param_vars.clear()
        self._param_widgets.clear()

        ag = AGENTES[key]
        for row, p in enumerate(ag["parametros"]):
            nombre  = p["nombre"]
            tipo    = p["tipo"]
            label   = p["label"]
            default = p.get("default")
            req     = p.get("requerido", False)

            lbl_txt = label + (" *" if req else "")
            tk.Label(self._frm_params, text=lbl_txt, font=("Segoe UI", 9),
                     bg=BG, fg=DARK, anchor="w", width=30).grid(
                     row=row, column=0, sticky="w", pady=3, padx=(0,8))

            if tipo == "bool":
                var = tk.BooleanVar(value=default if default is not None else True)
                chk = ttk.Checkbutton(self._frm_params, variable=var)
                chk.grid(row=row, column=1, sticky="w")
                self._param_vars[nombre]    = var
                self._param_widgets[nombre] = chk

            elif tipo in ("archivo", "archivo_salida"):
                var = tk.StringVar(value="" if default is None else str(default))
                frm = tk.Frame(self._frm_params, bg=BG)
                frm.grid(row=row, column=1, sticky="ew", pady=2)
                self._frm_params.columnconfigure(1, weight=1)
                ent = tk.Entry(frm, textvariable=var, font=("Segoe UI", 9),
                               relief="solid", bd=1, width=40)
                ent.pack(side="left", fill="x", expand=True)
                ext = p.get("extensiones", [])

                def _browse(v=var, e=ext, ts=tipo):
                    if ts == "archivo_salida":
                        path = filedialog.asksaveasfilename(
                            defaultextension=".pdf",
                            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")])
                    else:
                        ftypes = [(x.upper().lstrip("."), f"*{x}") for x in e] + \
                                  [("Todos", "*.*")]
                        path = filedialog.askopenfilename(filetypes=ftypes)
                    if path:
                        v.set(path)

                tk.Button(frm, text="…", font=("Segoe UI", 9),
                          relief="flat", bg="#D3D1C7", cursor="hand2",
                          padx=6, command=_browse).pack(side="left", padx=(4,0))
                self._param_vars[nombre]    = var
                self._param_widgets[nombre] = ent

            else:
                var = tk.StringVar(value="" if default is None else str(default))
                ent = tk.Entry(self._frm_params, textvariable=var,
                               font=("Segoe UI", 9), relief="solid", bd=1, width=40)
                ent.grid(row=row, column=1, sticky="ew", pady=2)
                self._frm_params.columnconfigure(1, weight=1)
                self._param_vars[nombre]    = var
                self._param_widgets[nombre] = ent

    # ── ejecución ─────────────────────────────────────────────────────────
    def _log_write(self, texto, tag=""):
        self._log.config(state="normal")
        self._log.insert("end", texto + "\n", tag)
        self._log.see("end")
        self._log.config(state="disabled")

    def _ejecutar(self):
        key = self._agente_key.get()
        if not key:
            messagebox.showwarning("Sin selección", "Elegí un agente de la lista.")
            return

        ag = AGENTES[key]

        # Recolectar kwargs
        kwargs = {}
        for p in ag["parametros"]:
            nombre = p["nombre"]
            tipo   = p["tipo"]
            var    = self._param_vars.get(nombre)
            if var is None:
                continue
            val = var.get()
            if tipo == "bool":
                kwargs[nombre] = bool(val)
            elif tipo in ("archivo", "archivo_salida"):
                kwargs[nombre] = str(val) if val else None
            elif tipo == "entero":
                try:
                    kwargs[nombre] = int(val)
                except Exception:
                    kwargs[nombre] = None
            else:
                kwargs[nombre] = val if val else None

            # Validar requeridos
            if p.get("requerido") and not kwargs[nombre]:
                messagebox.showerror("Parámetro faltante",
                                     f"El campo '{p['label']}' es requerido.")
                return

        self._btn_run.config(state="disabled", text="Ejecutando…")
        self._lbl_status.config(text="En curso…", fg=GRAY)

        # Redirigir stdout al log
        log_ref = self._log_write

        class LogRedirect:
            def write(self, msg):
                if msg.strip():
                    tag = "err" if "Error" in msg or "error" in msg else \
                          "ok"  if "✓" in msg or "Generado" in msg else "info"
                    log_ref(msg.rstrip(), tag)
            def flush(self):
                pass

        orig_stdout = sys.stdout
        sys.stdout  = LogRedirect()

        def _run():
            try:
                modulo  = importlib.import_module(ag["modulo"])
                funcion = getattr(modulo, ag["funcion"])
                sig     = inspect.signature(funcion)
                if "verbose" in sig.parameters:
                    kwargs["verbose"] = True
                resultado = funcion(**kwargs)
                sys.stdout = orig_stdout
                self._lbl_status.config(text="Completado ✓", fg=GREEN)
                if resultado:
                    self._log_write(f"Salida: {resultado}", "ok")
            except Exception as e:
                import traceback
                sys.stdout = orig_stdout
                self._log_write(f"Error: {e}", "err")
                self._log_write(traceback.format_exc(), "err")
                self._lbl_status.config(text="Error", fg=RED)
            finally:
                sys.stdout = orig_stdout
                self._btn_run.config(state="normal", text="▶  Ejecutar")

        threading.Thread(target=_run, daemon=True).start()


# ── punto de entrada ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()

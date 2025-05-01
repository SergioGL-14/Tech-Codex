# sections/commands_section.py
# Repositorio de Comandos – filtros, CRUD y toggle Aprendido / Favorito
# Refactor 26-abr-2025
from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
    QGraphicsDropShadowEffect,
    QSizePolicy,
)

from utils import clear_layout, exec_sql, fetchall, fetchone

# ────────────────────────── Constantes ────────────────────────────
BASE_CATEGORIES: List[str] = ["Red", "Sistema", "Eventos",
                              "Servicios", "Seguridad", "Otra"]
BASE_LANGS: List[str]     = ["PowerShell", "CMD", "Bash", "Linux",
                              "Python", "Docker", "Git", "SQL", "Otro"]

# ═════════════  Diálogo CRUD  ═════════════
class ComandoDialog(QDialog):
    """Diálogo para crear / editar comandos."""

    def __init__(
        self,
        parent=None,
        *,
        titulo: str = "",
        codigo: str = "",
        categoria: str = "",
        lenguaje: str = "",
        categorias: list[str] | None = None,
        lenguajes:  list[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Comando")
        self.resize(520, 340)

        form = QFormLayout(self)

        # --- campos ---
        self.txt_titulo         = QLineEdit(titulo)
        self.txt_codigo         = QPlainTextEdit(codigo); self.txt_codigo.setMaximumHeight(150)
        self.cmb_cat:  QComboBox= QComboBox()
        self.cmb_lang: QComboBox= QComboBox()

        # categorías
        for c in BASE_CATEGORIES + sorted(set(categorias or [])):
            if self.cmb_cat.findText(c) == -1:
                self.cmb_cat.addItem(c)
        if categoria and self.cmb_cat.findText(categoria) == -1:
            self.cmb_cat.addItem(categoria)
        if categoria:
            self.cmb_cat.setCurrentText(categoria)

        # lenguajes
        for l in BASE_LANGS + sorted(set(lenguajes or [])):
            if self.cmb_lang.findText(l) == -1:
                self.cmb_lang.addItem(l)
        if lenguaje and self.cmb_lang.findText(lenguaje) == -1:
            self.cmb_lang.addItem(lenguaje)
        if lenguaje:
            self.cmb_lang.setCurrentText(lenguaje)

        # layout
        form.addRow("Texto:",            self.txt_titulo)
        form.addRow("Código de ejemplo:", self.txt_codigo)
        form.addRow("Categoría:",        self.cmb_cat)
        form.addRow("Lenguaje:",         self.cmb_lang)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addWidget(bb)

    # --- datos resultantes ---
    def data(self) -> dict[str, str]:
        return dict(
            titulo    = self.txt_titulo.text().strip(),
            codigo    = self.txt_codigo.toPlainText().strip(),
            categoria = self.cmb_cat.currentText(),
            lenguaje  = self.cmb_lang.currentText(),
        )

# ═════════════  Sección principal  ═════════════
class CommandsSection(QWidget):
    """Listado con filtros, CRUD y botones Aprendido / Favorito."""

    def __init__(self, db_path: str, parent=None) -> None:
        super().__init__(parent)
        self.db_path         = db_path
        self.current_cmd_id: Optional[int] = None
        self._build_ui()
        self._populate_filter_values()
        self._filter_cmds()

    # ─────────────────────  UI  ─────────────────────
    def _build_ui(self) -> None:
        v = QVBoxLayout(self)

        # --- barra filtros ---
        bar = QHBoxLayout()
        self.txt_bus  = QLineEdit(placeholderText="Buscar…")
        self.cmb_cat  = QComboBox(); self.cmb_cat.addItem("Todas")
        self.cmb_lang = QComboBox(); self.cmb_lang.addItem("Todos")
        self.chkP = QCheckBox("Pendientes")
        self.chkA = QCheckBox("Aprendidos")
        self.chkF = QCheckBox("Favoritos")

        for w,l in ((self.txt_bus,"Buscar:"),
                    (self.cmb_cat,"Categoría:"),
                    (self.cmb_lang,"Lenguaje:")):
            bar.addWidget(QLabel(l)); bar.addWidget(w)
        bar.addWidget(self.chkP); bar.addWidget(self.chkA); bar.addWidget(self.chkF)
        bar.addStretch()
        v.addLayout(bar)

        # --- lista + detalle ---
        h = QHBoxLayout()
        self.lst_cmds = QListWidget(minimumWidth=260)
        h.addWidget(self.lst_cmds, 1)

        self.pnl_detail = QWidget()
        self.pnl_lay    = QVBoxLayout(self.pnl_detail); self.pnl_lay.setAlignment(Qt.AlignmentFlag.AlignTop)
        h.addWidget(self.pnl_detail, 2)
        v.addLayout(h)

        # --- botones globales ---
        btn_row   = QHBoxLayout()
        self.btn_state = QPushButton("❌ Pendiente")
        self.btn_fav   = QPushButton("☆ Favorito")
        self.btn_state.clicked.connect(self._toggle_estado)
        self.btn_fav.clicked.connect(self._toggle_fav_button)
        btn_row.addWidget(self.btn_state); btn_row.addStretch(); btn_row.addWidget(self.btn_fav)
        self.pnl_lay.addLayout(btn_row)

        # --- CRUD global ---
        crud = QHBoxLayout()
        for txt, cb in (("Nuevo", self._new_cmd),
                        ("Editar", self._edit_cmd),
                        ("Eliminar", self._delete_cmd)):
            b = QPushButton(txt); b.clicked.connect(cb); crud.addWidget(b)
        v.addLayout(crud)

        # Señales de filtros / lista
        self.txt_bus.textChanged.connect(self._filter_cmds)
        self.cmb_cat.currentIndexChanged.connect(self._filter_cmds)
        self.cmb_lang.currentIndexChanged.connect(self._filter_cmds)
        self.chkP.stateChanged.connect(self._filter_cmds)
        self.chkA.stateChanged.connect(self._filter_cmds)
        self.chkF.stateChanged.connect(self._filter_cmds)
        self.lst_cmds.itemClicked.connect(self._select_cmd)

    # ───────────────────  filtros dinámicos  ──────────────────
    def _populate_filter_values(self) -> None:
        """Rellena combos con los valores presentes en BD (sin duplicados)."""
        cats  = {r["categoria_funcional"] for r in
                 fetchall("SELECT DISTINCT categoria_funcional FROM Comandos")}
        langs = {r["lenguaje"] for r in
                 fetchall("SELECT DISTINCT lenguaje FROM Comandos")}

        for c in sorted(cats):
            if c and self.cmb_cat.findText(c) == -1:
                self.cmb_cat.addItem(c)
        for l in sorted(langs):
            if l and self.cmb_lang.findText(l) == -1:
                self.cmb_lang.addItem(l)

    # ───────────────────  FILTRO / QUERY  ───────────────────
    def _filter_cmds(self) -> None:
        text = self.txt_bus.text().strip()
        cat  = self.cmb_cat.currentText()
        lang = self.cmb_lang.currentText()

        conds: List[str] = ["1=1"]
        params: List[Any] = []

        if text:
            conds.append("(texto LIKE ? OR codigo_ejemplo LIKE ?)")
            params += [f"%{text}%"] * 2
        if cat != "Todas":
            conds.append("categoria_funcional=?"); params.append(cat)
        if lang != "Todos":
            conds.append("lenguaje=?"); params.append(lang)

        estados: List[str] = []
        if self.chkP.isChecked(): estados.append("Pendiente")
        if self.chkA.isChecked(): estados.append("Aprendido")
        if estados:
            conds.append(f"estado IN ({','.join('?'*len(estados))})"); params += estados
        if self.chkF.isChecked():
            conds.append("favorito=1")

        rows = fetchall(
            f"""SELECT id,texto,categoria_funcional,lenguaje
                FROM Comandos
                WHERE {' AND '.join(conds)}
                ORDER BY id""",
            params,
        )

        # mantener selección actual si sigue visible
        keep_id   = self.current_cmd_id
        keep_index= 0
        self.lst_cmds.clear()

        for idx, r in enumerate(rows):
            it = QListWidgetItem(f"{r['texto']} ({r['categoria_funcional']} - {r['lenguaje']})")
            it.setData(Qt.ItemDataRole.UserRole, r["id"])
            self.lst_cmds.addItem(it)
            if r["id"] == keep_id:
                keep_index = idx

        if rows:
            self.lst_cmds.setCurrentRow(keep_index)
            self._select_cmd(self.lst_cmds.item(keep_index))
        else:
            # limpia la parte superior
            while self.pnl_lay.count() > 1:
                w = self.pnl_lay.takeAt(0).widget()
                if w: w.deleteLater()
            self.current_cmd_id = None
            self._update_toggle_buttons()

    # ─────────────────────  DETALLE  ─────────────────────
    def _select_cmd(self, item: QListWidgetItem) -> None:
        cmd = fetchone("SELECT * FROM Comandos WHERE id=?",
                       (item.data(Qt.ItemDataRole.UserRole),))
        if not cmd:
            return
        self.current_cmd_id = cmd["id"]

        while self.pnl_lay.count() > 1:
            w = self.pnl_lay.takeAt(0).widget()
            if w:
                w.deleteLater()

        self.pnl_lay.insertWidget(0, QLabel(f"Categoría: {cmd['categoria_funcional']}"))
        self.pnl_lay.insertWidget(1, QLabel(f"Lenguaje: {cmd['lenguaje']}"))
        self.pnl_lay.insertWidget(2, self._card("", cmd))
        self._update_toggle_buttons()

    # ═════════════  CRUD  ═════════════
    def _cmd_dialog(self, row: Optional[dict] = None) -> Optional[dict]:
        cats  = [self.cmb_cat.itemText(i)  for i in range(1, self.cmb_cat.count())]
        langs = [self.cmb_lang.itemText(i) for i in range(1, self.cmb_lang.count())]

        dlg = ComandoDialog(
            self,
            titulo    = row["texto"]            if row else "",
            codigo    = row["codigo_ejemplo"]   if row else "",
            categoria = row["categoria_funcional"] if row else "",
            lenguaje  = row["lenguaje"]         if row else "",
            categorias= cats,
            lenguajes = langs,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        d = dlg.data()
        if not d["titulo"] or not d["codigo"]:
            QMessageBox.warning(self, "Campos vacíos", "Título y código son obligatorios.")
            return None
        return d

    def _new_cmd(self) -> None:
        if d := self._cmd_dialog():
            exec_sql(
                """INSERT INTO Comandos(texto,codigo_ejemplo,estado,favorito,
                                         fecha_aprendido,categoria_funcional,lenguaje)
                   VALUES(?,?,'Pendiente',0,NULL,?,?)""",
                (d["titulo"], d["codigo"], d["categoria"], d["lenguaje"]),
            )
            self._populate_filter_values()
            self._filter_cmds()

    def _edit_cmd(self) -> None:
        if not self.current_cmd_id:
            return
        row = fetchone("SELECT * FROM Comandos WHERE id=?", (self.current_cmd_id,))
        if d := self._cmd_dialog(row):
            exec_sql(
                "UPDATE Comandos SET texto=?,codigo_ejemplo=?,categoria_funcional=?,lenguaje=? WHERE id=?",
                (d["titulo"], d["codigo"], d["categoria"], d["lenguaje"], self.current_cmd_id),
            )
            self._populate_filter_values()
            self._filter_cmds()

    def _delete_cmd(self) -> None:
        if not self.current_cmd_id:
            return
        if QMessageBox.question(self, "Eliminar",
                                "¿Eliminar comando seleccionado?") != QMessageBox.StandardButton.Yes:
            return
        exec_sql("DELETE FROM Comandos WHERE id=?", (self.current_cmd_id,))
        self._filter_cmds()

    # ═════════════  TOGGLEs  ═════════════
    def _update_toggle_buttons(self) -> None:
        if not self.current_cmd_id:
            self.btn_state.setEnabled(False); self.btn_state.setText("❌ Pendiente")
            self.btn_fav.setEnabled(False);   self.btn_fav.setText("☆ Favorito")
            return

        row = fetchone("SELECT estado,favorito FROM Comandos WHERE id=?", (self.current_cmd_id,))
        if not row:
            return
        self.btn_state.setEnabled(True)
        self.btn_fav.setEnabled(True)
        self.btn_state.setText("✔ Aprendido" if row["estado"] == "Aprendido" else "❌ Pendiente")
        self.btn_fav.setText("⭐ Favorito"    if row["favorito"] else "☆ Favorito")

    def _toggle_estado(self) -> None:
        if not self.current_cmd_id:
            return
        row = fetchone("SELECT estado FROM Comandos WHERE id=?", (self.current_cmd_id,))
        new_state = "Pendiente" if row["estado"] == "Aprendido" else "Aprendido"
        exec_sql(
            "UPDATE Comandos SET estado=?,fecha_aprendido=? WHERE id=?",
            (new_state,
             datetime.now().isoformat(timespec="seconds") if new_state == "Aprendido" else None,
             self.current_cmd_id),
        )
        self._filter_cmds()

    def _toggle_fav_button(self) -> None:
        if not self.current_cmd_id:
            return
        row = fetchone("SELECT favorito FROM Comandos WHERE id=?", (self.current_cmd_id,))
        exec_sql("UPDATE Comandos SET favorito=? WHERE id=?",
                 (0 if row["favorito"] else 1, self.current_cmd_id))
        self._filter_cmds()

    # ═════════════  Tarjeta detalle  ═════════════
    @staticmethod
    def _card(title: str, data: dict[str, Any]) -> QGroupBox:
        card = QGroupBox(title) if title else QGroupBox()
        card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        card.setGraphicsEffect(QGraphicsDropShadowEffect(blurRadius=12, xOffset=2, yOffset=2))

        lay = QVBoxLayout(card)
        txt = QLabel(data["texto"]); txt.setWordWrap(True); lay.addWidget(txt)

        code = QPlainTextEdit(data["codigo_ejemplo"])
        code.setReadOnly(True); code.setMaximumHeight(140)
        lay.addWidget(code)
        return card
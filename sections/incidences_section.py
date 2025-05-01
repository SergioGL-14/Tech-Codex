#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sections/incidences_section.py  ·  Diario de Incidencias
Refactorizado 25-abr-2025
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QPlainTextEdit, QScrollArea, QMessageBox,
    QDialog, QFormLayout, QDialogButtonBox, QGroupBox,
    QSizePolicy, QGraphicsDropShadowEffect
)

from utils import get_conn, exec_sql, fetchall, clear_layout


class IncidenciaDialog(QDialog):
    """Crear/Editar incidencia."""
    def __init__(self, parent=None, data: Optional[dict[str, Any]] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Incidencia")
        self.resize(500, 400)
        form = QFormLayout(self)
        d = data or {}

        self.txt_titulo = QLineEdit(d.get("titulo", ""))
        self.txt_desc   = QPlainTextEdit(d.get("descripcion", "")); self.txt_desc.setMaximumHeight(100)
        self.txt_sol    = QPlainTextEdit(d.get("solucion", ""));    self.txt_sol.setMaximumHeight(100)
        self.cmb_estado = QComboBox(); self.cmb_estado.addItems(["Pendiente", "Resuelto"])
        if d.get("estado"):    self.cmb_estado.setCurrentText(d["estado"])
        self.cmb_prio   = QComboBox(); self.cmb_prio.addItems(["Alta", "Media", "Baja"])
        if d.get("prioridad"): self.cmb_prio.setCurrentText(d["prioridad"])
        self.cmb_cat    = QComboBox(); self.cmb_cat.addItems(["Hardware","Software","Red","AD","Otro"])
        if d.get("categoria"): self.cmb_cat.setCurrentText(d["categoria"])

        form.addRow("Título *:",      self.txt_titulo)
        form.addRow("Descripción:",   self.txt_desc)
        form.addRow("Solución:",      self.txt_sol)
        form.addRow("Estado:",        self.cmb_estado)
        form.addRow("Prioridad:",     self.cmb_prio)
        form.addRow("Categoría:",     self.cmb_cat)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addWidget(bb)

    def data(self) -> dict[str, Any]:
        return {
            "titulo":      self.txt_titulo.text().strip(),
            "descripcion": self.txt_desc.toPlainText().strip(),
            "solucion":    self.txt_sol.toPlainText().strip(),
            "estado":      self.cmb_estado.currentText(),
            "prioridad":   self.cmb_prio.currentText(),
            "categoria":   self.cmb_cat.currentText(),
        }


class IncidenciasSection(QWidget):
    """Listado de incidencias con filtros y CRUD."""
    def __init__(self, db_path: str, parent=None) -> None:
        super().__init__(parent)
        self.db_path = db_path
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        # filtros
        bar = QHBoxLayout()
        self.txt_bus    = QLineEdit(placeholderText="Buscar…")
        self.cmb_estado = QComboBox(); self.cmb_estado.addItems(["Todos","Pendiente","Resuelto"])
        self.cmb_prio   = QComboBox(); self.cmb_prio.addItems(["Todas","Alta","Media","Baja"])
        self.cmb_cat    = QComboBox(); self.cmb_cat.addItems(["Todas","Hardware","Software","Red","AD","Otro"])
        for lbl,w in [("Buscar:",self.txt_bus),("Estado:",self.cmb_estado),
                      ("Prioridad:",self.cmb_prio),("Categoría:",self.cmb_cat)]:
            bar.addWidget(QLabel(lbl)); bar.addWidget(w)
        bar.addStretch()
        root.addLayout(bar)

        # área scroll
        scroll = QScrollArea(widgetResizable=True)
        container = QWidget()
        self.vbox = QVBoxLayout(container)
        self.vbox.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)

        # botón nuevo
        btn_new = QPushButton("➕ Nueva incidencia")
        btn_new.clicked.connect(self._new)
        root.addWidget(btn_new)

        # señales filtro
        self.txt_bus.textChanged.connect(self._refresh)
        self.cmb_estado.currentIndexChanged.connect(self._refresh)
        self.cmb_prio.currentIndexChanged.connect(self._refresh)
        self.cmb_cat.currentIndexChanged.connect(self._refresh)

        self._refresh()

    def _refresh(self) -> None:
        clear_layout(self.vbox)
        txt = self.txt_bus.text().lower().strip()
        est = self.cmb_estado.currentText()
        pr  = self.cmb_prio.currentText()
        cat = self.cmb_cat.currentText()

        # prioridad para ordenar
        order = {"Alta":0,"Media":1,"Baja":2}
        rows = sorted(fetchall("SELECT * FROM Incidencias"), 
                      key=lambda r: (r["estado"]!="Pendiente", order.get(r["prioridad"],3)))

        for inc in rows:
            if txt and txt not in inc["titulo"].lower(): continue
            if est!="Todos"    and inc["estado"]    != est: continue
            if pr !="Todas"    and inc["prioridad"] != pr:  continue
            if cat!="Todas"    and inc["categoria"] != cat: continue

            card = QGroupBox(inc["titulo"])
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            card.setGraphicsEffect(QGraphicsDropShadowEffect(blurRadius=8,xOffset=1,yOffset=1))
            h = QHBoxLayout(card)

            # detalle
            info = QWidget(); il = QVBoxLayout(info)
            fecha = datetime.fromisoformat(inc["fecha"]).strftime("%d/%m/%Y %H:%M")
            il.addWidget(QLabel(f"Fecha: {fecha}"))
            lbl_e = QLabel(f"Estado: {inc['estado']}")
            if inc["estado"]=="Resuelto": lbl_e.setStyleSheet("color:#4caf50;")
            il.addWidget(lbl_e)
            il.addWidget(QLabel(f"Prioridad: {inc['prioridad']}"))
            il.addWidget(QLabel(f"Categoría: {inc['categoria']}"))
            h.addWidget(info, 4)

            # acciones
            act = QWidget(); al = QVBoxLayout(act)
            btn_v = QPushButton("🔍 Ver / Editar")
            btn_v.clicked.connect(lambda _, i=inc: self._open(i))
            btn_d = QPushButton("🗑️ Eliminar")
            btn_d.clicked.connect(lambda _, i=inc["id"]: self._delete(i))
            al.addWidget(btn_v); al.addWidget(btn_d)
            h.addWidget(act,1)

            self.vbox.addWidget(card)

    def _new(self) -> None:
        dlg = IncidenciaDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        d = dlg.data()
        exec_sql(
            "INSERT INTO Incidencias(titulo,fecha,descripcion,solucion,estado,prioridad,categoria) "
            "VALUES(?,?,?,?,?,?,?)",
            (d["titulo"], datetime.now().isoformat(),
             d["descripcion"], d["solucion"],
             d["estado"], d["prioridad"], d["categoria"])
        )
        self._refresh()

    def _open(self, data: dict[str,Any]) -> None:
        dlg = IncidenciaDialog(self, data=data)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        d = dlg.data()
        exec_sql(
            "UPDATE Incidencias SET titulo=?,descripcion=?,solucion=?,estado=?,prioridad=?,categoria=? WHERE id=?",
            (d["titulo"], d["descripcion"], d["solucion"],
             d["estado"], d["prioridad"], d["categoria"], data["id"])
        )
        self._refresh()

    def _delete(self, inc_id: int) -> None:
        if QMessageBox.question(self, "Eliminar", "¿Eliminar esta incidencia?") \
           != QMessageBox.StandardButton.Yes:
            return
        exec_sql("DELETE FROM Incidencias WHERE id=?", (inc_id,))
        self._refresh()

import json
import os
from functools import partial
from PySide2 import QtWidgets, QtGui, QtCore

import hotbox_designer
from hotbox_designer.editor.application import HotboxEditor
from hotbox_designer.widgets import BoolCombo, Title
from hotbox_designer.templates import HOTBOX
from hotbox_designer.ressources import TEMPLATES
from hotbox_designer.utils import copy_hotbox_data


PRESS_COMMAND_TEMPLATE = """\
import hotbox_designer
from hotbox_designer import softwares
hotbox_designer.initialize(softwares.Maya())
hotbox_designer.show('{}')
"""

RELEASE_COMMAND_TEMPLATE = """\
import hotbox_designer
hotbox_designer.hide('{}')
"""


def get_new_hotbox(hotboxes):
    options = HOTBOX.copy()
    options.update({'name': get_valid_name(hotboxes)})
    return {
        'general': options,
        'shapes': []}

DEFAULT_NAME = 'MyHotbox_{}'
TRIGGERING_TYPES = 'click only', 'click or close'


def get_valid_name(hotboxes, proposal=None):
    names = [hotbox['general']['name'] for hotbox in hotboxes]
    index = 0
    name = proposal or DEFAULT_NAME.format(str(index).zfill(2))
    while name in names:
        if proposal:
            name = proposal + "_" + str(index).zfill(2)
        else:
            name = DEFAULT_NAME.format(str(index).zfill(2))
        index += 1
    return name


class HotboxManager(QtWidgets.QWidget):

    def __init__(self, context):
        parent = context.main_window
        super(HotboxManager, self).__init__(parent, QtCore.Qt.Tool)
        self.setWindowTitle('Hotbox Designer')
        self.context = context
        self.hotbox_editor = None
        hotboxes_data = hotbox_designer.load_data(self.context.file)
        self.table_model = HotboxTableModel(hotboxes_data)
        self.table_view = HotboxTableView()
        self.table_view.set_model(self.table_model)
        self.table_view.selectedRowChanged.connect(self._selected_row_changed)

        self.add_button = QtWidgets.QPushButton('create')
        self.add_button.released.connect(self._call_create)
        self.edit_button = QtWidgets.QPushButton('edit')
        self.edit_button.released.connect(self._call_edit)
        self.remove_button = QtWidgets.QPushButton('remove')
        self.remove_button.released.connect(self._call_remove)
        self.reinitialize = QtWidgets.QPushButton('reinitialize hotboxes')
        self.reinitialize.released.connect(self._call_reinitialize)

        self.export = QtWidgets.QPushButton('export')
        self.export.released.connect(self._call_export)
        self.import_ = QtWidgets.QPushButton('import')
        self.import_.released.connect(self._call_import)

        self.hbuttons = QtWidgets.QHBoxLayout()
        self.hbuttons.setContentsMargins(0, 0, 0, 0)
        self.hbuttons.addWidget(self.add_button)
        self.hbuttons.addWidget(self.edit_button)
        self.hbuttons.addWidget(self.remove_button)
        self.hbuttons2 = QtWidgets.QHBoxLayout()
        self.hbuttons2.setContentsMargins(0, 0, 0, 0)
        self.hbuttons2.addWidget(self.import_)
        self.hbuttons2.addWidget(self.export)
        self.vbuttons = QtWidgets.QVBoxLayout()
        self.vbuttons.setContentsMargins(0, 0, 0, 0)
        self.vbuttons.addLayout(self.hbuttons)
        self.vbuttons.addLayout(self.hbuttons2)
        self.vbuttons.addWidget(self.reinitialize)

        self.table_layout = QtWidgets.QVBoxLayout()
        self.table_layout.setContentsMargins(0, 0, 0, 0)
        self.table_layout.setSpacing(0)
        self.table_layout.addWidget(self.table_view)
        self.table_layout.addLayout(self.vbuttons)

        self.edit = HotboxGeneralSettingWidget()
        self.edit.optionSet.connect(self._call_option_set)
        self.edit.setEnabled(False)
        self.press_command = QtWidgets.QPushButton('show on press command')
        self.press_command.released.connect(self._call_press_command)
        self.release_command = QtWidgets.QPushButton('show on release command')
        self.release_command.released.connect(self._call_release_command)

        self.edit_layout = QtWidgets.QVBoxLayout()
        self.edit_layout.setContentsMargins(0, 0, 0, 0)
        self.edit_layout.setSpacing(0)
        self.edit_layout.addWidget(self.edit)
        self.edit_layout.addStretch(1)
        self.edit_layout.addWidget(self.press_command)
        self.edit_layout.addWidget(self.release_command)

        self.hlayout = QtWidgets.QHBoxLayout()
        self.hlayout.setContentsMargins(0, 0, 0, 0)
        self.hlayout.addLayout(self.table_layout)
        self.hlayout.addLayout(self.edit_layout)

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.addLayout(self.hlayout)

    def get_selected_hotbox(self):
        row = self.table_view.get_selected_row()
        if row is None:
            return
        return self.table_model.hotboxes[row]

    def save_hotboxes(self, *_):
        hotbox_designer.save_data(self.context.file, self.table_model.hotboxes)

    def _selected_row_changed(self):
        hotbox = self.get_selected_hotbox()
        if hotbox is not None:
            self.edit.set_hotbox_settings(hotbox['general'])
            self.edit.setEnabled(True)
        else:
            self.edit.setEnabled(False)

    def _call_edit(self):
        if self.hotbox_editor is not None:
            self.hotbox_editor.close()
        hotbox_data = self.get_selected_hotbox()
        if hotbox_data is None:
            return
        parent = self.context.main_window
        self.hotbox_editor = HotboxEditor(hotbox_data, parent=parent)
        self.hotbox_editor.set_hotbox_data(hotbox_data, reset_stacks=True)
        row = self.table_view.get_selected_row()
        method = partial(self.table_model.set_hotbox, row)
        self.hotbox_editor.hotboxDataModified.connect(method)
        self.hotbox_editor.hotboxDataModified.connect(self.save_hotboxes)
        self.hotbox_editor.show()

    def _call_create(self):
        dialog = CreateHotboxDialog(self.table_model.hotboxes, self)
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Rejected:
            return

        self.table_model.layoutAboutToBeChanged.emit()
        self.table_model.hotboxes.append(dialog.hotbox())
        self.table_model.layoutChanged.emit()
        self.save_hotboxes()

    def _call_remove(self):
        hotbox = self.get_selected_hotbox()
        if hotbox is None:
            return

        areyousure = QtWidgets.QMessageBox.question(
            self,
            'remove',
            'remove a hotbox is definitive, are you sure to continue',
            buttons=QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            defaultButton=QtWidgets.QMessageBox.No)

        if areyousure == QtWidgets.QMessageBox.No:
            return

        self.table_model.layoutAboutToBeChanged.emit()
        self.table_model.hotboxes.remove(hotbox)
        self.table_model.layoutChanged.emit()
        self.save_hotboxes()

    def _call_reinitialize(self):
        hotbox_designer.load_hotboxes(self.context)

    def _call_press_command(self):
        hotbox = self.get_selected_hotbox()
        if not hotbox:
            return
        command = PRESS_COMMAND_TEMPLATE.format(hotbox['general']['name'])
        CommandDisplayDialog(command, self).exec_()

    def _call_release_command(self):
        hotbox = self.get_selected_hotbox()
        if not hotbox:
            return
        command = RELEASE_COMMAND_TEMPLATE.format(hotbox['general']['name'])
        CommandDisplayDialog(command, self).exec_()

    def _call_option_set(self, option, value):
        self.table_model.layoutAboutToBeChanged.emit()
        hotbox = self.get_selected_hotbox()
        if option == 'name':
            value = get_valid_name(self.table_model.hotboxes, value)

        if hotbox is not None:
            hotbox['general'][option] = value
        self.table_model.layoutChanged.emit()
        self.save_hotboxes()

    def _call_export(self):
        hotbox = self.get_selected_hotbox()
        if not hotbox:
            return
        export_hotbox(hotbox)

    def _call_import(self):
        hotbox = import_hotbox()
        if not hotbox:
            pass
        hotboxes = self.table_model.hotboxes
        name = get_valid_name(hotboxes, hotbox['general']['name'])
        hotbox['general']['name'] = name

        self.table_model.layoutAboutToBeChanged.emit()
        self.table_model.hotboxes.append(hotbox)
        self.table_model.layoutChanged.emit()
        self.save_hotboxes()


def import_hotbox():
    filenames = QtWidgets.QFileDialog.getOpenFileName(
        None, caption='Import hotbox',  directory=os.path.expanduser("~"),
        filter= '*.json')
    if not filenames:
        return
    with open(filenames[0], 'r') as f:
        return json.load(f)


def export_hotbox(hotbox):
    filenames = QtWidgets.QFileDialog.getSaveFileName(
        None, caption='Import hotbox',  directory=os.path.expanduser("~"),
        filter= '*.json')
    filename = filenames[0]
    if not filename:
        return
    if not filename.lower().endswith('.json'):
        filename += '.json'
    with open(filename, 'w') as f:
        json.dump(hotbox, f)


class HotboxTableView(QtWidgets.QTableView):
    selectedRowChanged = QtCore.Signal()

    def __init__(self, parent=None):
        super(HotboxTableView, self).__init__(parent)
        self.selection_model = None
        vheader = self.verticalHeader()
        vheader.hide()
        vheader.setSectionResizeMode(vheader.ResizeToContents)
        hheader = self.horizontalHeader()
        hheader.setStretchLastSection(True)
        hheader.hide()
        self.setAlternatingRowColors(True)
        self.setWordWrap(True)
        self.setShowGrid(False)
        self.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)

    def selection_changed(self, *_):
        return self.selectedRowChanged.emit()

    def set_model(self, model):
        self.setModel(model)
        self.selection_model = self.selectionModel()
        self.selection_model.selectionChanged.connect(self.selection_changed)

    def get_selected_row(self):
        indexes = self.selection_model.selectedIndexes()
        rows = list({index.row() for index in indexes})
        if not rows:
            return None
        return rows[0]


class HotboxTableModel(QtCore.QAbstractTableModel):

    def __init__(self, hotboxes, parent=None):
        super(HotboxTableModel, self).__init__(parent=None)
        self.hotboxes = hotboxes

    def columnCount(self, _):
        return 1

    def rowCount(self, _):
        return len(self.hotboxes)

    def set_hotbox(self, row, hotbox):
        self.layoutAboutToBeChanged.emit()
        self.hotboxes[row] = hotbox

    def data(self, index, role):
        row, col = index.row(), index.column()
        hotbox = self.hotboxes[row]
        if role == QtCore.Qt.DisplayRole:
            if col == 0:
                return hotbox['general']['name']


class HotboxGeneralSettingWidget(QtWidgets.QWidget):
    optionSet = QtCore.Signal(str, object)
    applyRequested = QtCore.Signal()

    def __init__(self, parent=None):
        super(HotboxGeneralSettingWidget, self).__init__(parent)
        self.setFixedWidth(150)
        self.name = QtWidgets.QLineEdit()
        self.name.textEdited.connect(partial(self.optionSet.emit, 'name'))
        self.triggering = QtWidgets.QComboBox()
        self.triggering.addItems(TRIGGERING_TYPES)
        self.triggering.currentIndexChanged.connect(self._triggering_changed)
        self.aiming = BoolCombo(False)
        self.aiming.valueSet.connect(partial(self.optionSet.emit, 'aiming'))

        self.layout = QtWidgets.QFormLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.layout.setHorizontalSpacing(5)
        self.layout.addRow(Title('Options'))
        self.layout.addItem(QtWidgets.QSpacerItem(0, 8))
        self.layout.addRow('name', self.name)
        self.layout.addItem(QtWidgets.QSpacerItem(0, 8))
        self.layout.addRow('triggering', self.triggering)
        self.layout.addRow('aiming', self.aiming)

    def _triggering_changed(self, _):
        self.optionSet.emit('triggering', self.triggering.currentText())

    def _touch_changed(self, _):
        self.optionSet.emit('touch', self.touch.text())

    def set_hotbox_settings(self, hotbox_settings):
        self.name.setText(hotbox_settings['name'])
        self.triggering.setCurrentText(hotbox_settings['triggering'])
        self.aiming.setCurrentText(str(hotbox_settings['aiming']))


class CreateHotboxDialog(QtWidgets.QDialog):
    def __init__(self, hotboxes, parent=None):
        super(CreateHotboxDialog, self).__init__(parent)
        self.setWindowTitle("Create new hotbox")
        self.hotboxes = hotboxes

        self.new = QtWidgets.QRadioButton("empty hotbox")
        self.duplicate = QtWidgets.QRadioButton("duplicate existing hotbox")
        self.duplicate.setEnabled(bool(self.hotboxes))
        self.template = QtWidgets.QRadioButton("from template")
        self.groupbutton = QtWidgets.QButtonGroup()
        self.groupbutton.addButton(self.new, 0)
        self.groupbutton.addButton(self.duplicate, 1)
        self.groupbutton.addButton(self.template, 2)
        self.new.setChecked(True)

        self.existing = QtWidgets.QComboBox()
        self.existing.addItems([hb['general']['name'] for hb in self.hotboxes])
        self.template_combo = QtWidgets.QComboBox()
        items = [hb['general']['name'] for hb in TEMPLATES]
        self.template_combo.addItems(items)

        self.up_layout = QtWidgets.QGridLayout()
        self.up_layout.setContentsMargins(0, 0, 0, 0)
        self.up_layout.setSpacing(0)
        self.up_layout.addWidget(self.new, 0, 0)
        self.up_layout.addWidget(self.duplicate, 1, 0)
        self.up_layout.addWidget(self.existing, 1, 1)
        self.up_layout.addWidget(self.template, 2, 0)
        self.up_layout.addWidget(self.template_combo, 2, 1)

        self.ok = QtWidgets.QPushButton('ok')
        self.ok.released.connect(self.accept)
        self.cancel = QtWidgets.QPushButton('cancel')
        self.cancel.released.connect(self.reject)

        self.down_layout = QtWidgets.QHBoxLayout()
        self.down_layout.setContentsMargins(0, 0, 0, 0)
        self.down_layout.addStretch(1)
        self.down_layout.addWidget(self.ok)
        self.down_layout.addWidget(self.cancel)

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.setSpacing(12)
        self.layout.addLayout(self.up_layout)
        self.layout.addLayout(self.down_layout)

    def hotbox(self):
        if self.groupbutton.checkedId() == 0:
            return get_new_hotbox(self.hotboxes)
        elif self.groupbutton.checkedId() == 1:
            name = self.existing.currentText()
            hotboxes = self.hotboxes
        elif self.groupbutton.checkedId() == 2:
            name = self.template_combo.currentText()
            hotboxes = TEMPLATES
        hotbox = [hb for hb in hotboxes if hb['general']['name'] == name][0]
        hotbox = copy_hotbox_data(hotbox)
        name = get_valid_name(hotboxes, hotbox['general']['name'])
        hotbox['general']['name'] = name
        return hotbox


class CommandDisplayDialog(QtWidgets.QDialog):
    def __init__(self, command, parent=None):
        super(CommandDisplayDialog, self).__init__(parent)
        self.setWindowTitle("Command")
        self.text = QtWidgets.QTextEdit()
        self.text.setReadOnly(True)
        self.text.setPlainText(command)
        self.ok = QtWidgets.QPushButton('ok')
        self.ok.released.connect(self.accept)

        self.button_layout = QtWidgets.QHBoxLayout()
        self.button_layout.setContentsMargins(0, 0, 0, 0)
        self.button_layout.addStretch(1)
        self.button_layout.addWidget(self.ok)

        self.layout = QtWidgets.QVBoxLayout(self)
        self.layout.addWidget(self.text)
        self.layout.addLayout(self.button_layout)


class TouchEdit(QtWidgets.QLineEdit):
    def keyPressEvent(self, event):
        self.setText(QtGui.QKeySequence(event.key()).toString().lower())
        self.textEdited.emit(self.text())

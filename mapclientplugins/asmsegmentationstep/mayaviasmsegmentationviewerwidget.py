'''
MAP Client, a program to generate detailed musculoskeletal models for OpenSim.
    Copyright (C) 2012  University of Auckland
    
This file is part of MAP Client. (http://launchpad.net/mapclient)

    MAP Client is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    MAP Client is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with MAP Client.  If not, see <http://www.gnu.org/licenses/>..
'''
import os
os.environ['ETS_TOOLKIT'] = 'qt4'

from PySide.QtGui import QDialog, QFileDialog, QDialogButtonBox,\
                         QAbstractItemView, QTableWidgetItem,\
                         QDoubleValidator
from PySide.QtCore import Qt
from PySide.QtCore import QThread, Signal

# from mapclientplugins.asmsegmentationtep.ui_mayaviasmsegmentationviewerwidget import Ui_Dialog
from ui_mayaviasmsegmentationviewerwidget import Ui_Dialog

from traits.api import HasTraits, Instance, on_trait_change, \
    Int, Dict

from mappluginutils.mayaviviewer import MayaviViewerObjectsContainer, MayaviViewerDataPoints,\
    MayaviViewerFieldworkModel, MayaviViewerLandmark, MayaviViewerImagePlane, colours

import copy

INVALID_STYLE_SHEET = 'background-color: rgba(239, 0, 0, 50)'
DEFAULT_STYLE_SHEET = ''

class _ExecThread(QThread):
    update = Signal(tuple)

    def __init__(self, func):
        QThread.__init__(self)
        self.func = func

    def run(self):
        output = self.func()
        self.update.emit(output)

class MayaviASMSegmentationViewerWidget(QDialog):
    '''
    Configure dialog to present the user with the options to configure this step.
    '''
    defaultColor = colours['bone']
    objectTableHeaderColumns = {'visible':0}
    backgroundColour = (0.0,0.0,0.0)
    _pointCloudRenderArgs = {'mode':'point', 'scale_factor':0.5, 'color':(0,1,0)}
    _modelInitRenderArgs = {'color':(1,0,0)}
    _modelFinalRenderArgs = {'color':(1,1,0)}
    # _landmarkRenderArgs = {'mode':'sphere', 'scale_factor':5.0, 'color':(0,1,0)}
    # _imageRenderArgs = {'vmax':2000, 'vmin':-200}
    _GFD = [8,8]

    def __init__(self, step, parent=None):
        '''
        Constructor
        '''
        QDialog.__init__(self, parent)
        self._ui = Ui_Dialog()
        self._ui.setupUi(self)

        self._scene = self._ui.MayaviScene.visualisation.scene
        self._scene.background = self.backgroundColour

        self.selectedObjectName = None
        self._step = step

        self._worker = _ExecThread(self._step._segment)
        self._worker.update.connect(self._segUpdate)

        self._initViewerObjects()
        self._setupGui()
        self._initialiseSettings()
        self._makeConnections()
        self._initialiseObjectTable()
        self._refresh()

        self._previousProfileModelFile = ''

        # for k, v in self._config.items():
        #     print k+': ', v

    def _makeConnections(self):
        self._ui.tableWidget.itemClicked.connect(self._tableItemClicked)
        self._ui.tableWidget.itemChanged.connect(self._visibleBoxChanged)
        self._ui.screenshotSaveButton.clicked.connect(self._saveScreenShot)
        
        self._ui.segButton.clicked.connect(self._segButtonClicked)
        self._ui.resetButton.clicked.connect(self._reset)
        self._ui.abortButton.clicked.connect(self._abort)
        self._ui.acceptButton.clicked.connect(self._accept)

        # self._ui.pcsToFitSpinBox.valueChanged.connect(self._saveConfig)
        # self._ui.mWeightDbtSpinBox.valueChanged.connect(self._saveConfig)
        # self._ui.surfDiscSpinBox.valueChanged.connect(self._saveConfig)
        # self._ui.pExtDblSpinBox1.valueChanged.connect(self._saveConfig)
        # self._ui.pExtDblSpinBox2.valueChanged.connect(self._saveConfig)
        self._ui.profileModelLineEdit.textChanged.connect(self._profileModelFileEdited)
        self._ui.profileModelButton.clicked(self._profileModelFileClicked)
        # self._ui.searchDistSpinBox.valueChanged.connect(self._saveConfig)
        # self._ui.maxItSpinBox.valueChanged.connect(self._saveConfig)

    def _profileModelFileClicked(self):
        location = QFileDialog.getOpenFileName(self, 'Select File Location', self._previousProfileModelFile)
        if location[0]:
            self._previousProfileModelFile = location[0]
            self._ui.profileModelLineEdit.setText(location[0])

    def _profileModelFileEdited(self):
        valid = os.path.exists(self._ui.profileModelLineEdit.text())
        if valid:
            self._ui.profileModelLineEdit.setStyleSheet(DEFAULT_STYLE_SHEET)
        else:
            self._ui.profileModelLineEdit.setStyleSheet(INVALID_STYLE_SHEET)

    def _initViewerObjects(self):
        self._objects = MayaviViewerObjectsContainer()
        self._objects.addObject('image', 
                                MayaviViewerImagePlane('image',
                                                       self._step.image,
                                                       renderArgs=self._imageRenderArgs))
        self._objects.addObject('Initial Model',
                                MayaviViewerFieldworkModel('Initial Model',
                                                           self._step.modelInit,
                                                           self._GFD,
                                                           renderArgs=self._modelInitRenderArgs))
        self._objects.addObject('Segmented Model',
                                MayaviViewerFieldworkModel('Segmented Model',
                                                           self._step._modelFinal,
                                                           self._GFD,
                                                           renderArgs=self._modelFinalRenderArgs))
        # self._objects.addObject('Segmented Points',
        #                         MayaviViewerDataPoints('Segmented Points',
        #                                                    self._pointCloudFinal,
        #                                                    renderArgs=self._pointCloudRenderArgs))
        # for ln in self._landmarkNames:
        #     self._objects.addObject(ln, MayaviViewerLandmark(ln,
        #                                                      self._landmarks[ln],
        #                                                      renderArgs=self._landmarkRenderArgs
        #                                                      )
        #                             )


    def _setupGui(self):
        self._ui.pcsToFitSpinBox.setSingleStep(1)
        self._ui.mWeightDblSpinBox.setSingleStep(0.1)
        self._ui.surfDicsSpinBox.setSingleStep(1)
        self._ui.pExtDblSpinBox1.setSingleStep(0.1)
        self._ui.pExtDblSpinBox2.setSingleStep(0.1)
        self._ui.searchDistSpinBox.setSingleStep(1)
        self._ui.maxItSpinBox.setSingleStep(1)

    def _saveConfig(self):
        self._step._segParams['ASM']['shape_modes'] = self._ui.pcsToFitSpinBox.value()
        self._step._segParams['ASM']['fit_mweight'] = self._ui.mWeightDblSpinBox.value()
        self._step._segParams['ASM']['mesh_d'] = self._ui.surfDicsSpinBox.value()
        self._step._segParams['ASM']['n_lim'] = [self._ui.pExtDblSpinBox1.value(), self._ui.pExtDblSpinBox2.value()]
        self._step._segParams['data_files']['ppc_filename'] = self._ui.profileModelLineEdit.text()
        self._step._segParams['ASM']['n_pad'] = self._ui.searchDistSpinBox.value()
        self._step._segParams['ASM']['max_it'] = self._ui.maxItSpinBox.value()

    def _initialiseSettings(self):
        self._previousProfileModelFile = self._step._segParams['data_files']['ppc_filename']
        self._ui.pcsToFitSpinBox.setValue(self._step._segParams['ASM']['shape_modes'])
        self._ui.mWeightDblSpinBox.setValue(self._step._segParams['ASM']['fit_mweight'])
        self._ui.surfDicsSpinBox.setValue(self._step._segParams['ASM']['mesh_d'])
        self._ui.pExtDblSpinBox1.setValue(self._step._segParams['ASM']['n_lim'][0])
        self._ui.pExtDblSpinBox2.setValue(self._step._segParams['ASM']['n_lim'][1])
        self._ui.profileModelLineEdit.settText(self._step._segParams['data_files']['ppc_filename'])
        self._ui.searchDistSpinBox.setValue(self._step._segParams['ASM']['n_pad'])
        self._ui.maxItSpinBox.setValue(self._step._segParams['ASM']['max_it'])

    def _initialiseObjectTable(self):

        self._ui.tableWidget.setRowCount(self._objects.getNumberOfObjects())
        self._ui.tableWidget.verticalHeader().setVisible(False)
        self._ui.tableWidget.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._ui.tableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._ui.tableWidget.setSelectionMode(QAbstractItemView.SingleSelection)
        
        self._addObjectToTable(0, 'image', self._objects.getObject('image'))
        self._addObjectToTable(1, 'Initial Model', self._objects.getObject('Initial Model'))
        self._addObjectToTable(2, 'Segmented Model', self._objects.getObject('Segmented Model'), checked=False)
        self._addObjectToTable(3, 'Segmented Points', self._objects.getObject('Segmented Points'), checked=False)
        # if self._landmarks is not None:
        #     r = 3
        #     for ln in self._landmarkNames:
        #         self._addObjectToTable(r, ln, self._objects.getObject(ln))
        #         r += 1

        self._ui.tableWidget.resizeColumnToContents(self.objectTableHeaderColumns['visible'])
        
    def _addObjectToTable(self, row, name, obj, checked=True):
        typeName = obj.typeName
        # print typeName
        # print name
        tableItem = QTableWidgetItem(name)
        if checked:
            tableItem.setCheckState(Qt.Checked)
        else:
            tableItem.setCheckState(Qt.Unchecked)

        self._ui.tableWidget.setItem(row, self.objectTableHeaderColumns['visible'], tableItem)

    def _tableItemClicked(self):
        selectedRow = self._ui.tableWidget.currentRow()
        self.selectedObjectName = self._ui.tableWidget.item(selectedRow, self.objectTableHeaderColumns['visible']).text()
        # self._populateScalarsDropDown(self.selectedObjectName)
        # print selectedRow
        # print self.selectedObjectName

    def _visibleBoxChanged(self, tableItem):

        # checked changed item is actually the checkbox
        if tableItem.column()==self.objectTableHeaderColumns['visible']:
            # get visible status
            name = tableItem.text()
            visible = tableItem.checkState().name=='Checked'

            # print 'visibleboxchanged name', name
            # print 'visibleboxchanged visible', visible

            # toggle visibility
            obj = self._objects.getObject(name)
            # print obj.name
            if obj.sceneObject:
                # print 'changing existing visibility'
                obj.setVisibility(visible)
            else:
                # print 'drawing new'
                obj.draw(self._scene)

    def _getSelectedObjectName(self):
        return self.selectedObjectName

    def _getSelectedScalarName(self):
        return 'none'

    def drawObjects(self):
        for name in self._objects.getObjectNames():
            self._objects.getObject(name).draw(self._scene)

    def _segButtonClicked(self):
        self._saveConfig()
        self._objects.removeObject('Segmented Points')
        self._worker.start()
        self._segLockUI()

    def _segUpdate(self, output):
        # update error fields
        rmse = self._step._asmOutput['segRMS']
        pFrac = self._step._asmOutput['segPFrac']
        self._ui.RMSELineEdit.setText('{:6.4f}'.format(rmse))
        self._ui.pFracLineEdit.setText('{:5.2f}'.format(pFrac*100.0))

        # update fitted GF
        segObj = self._objects.getObject('Segmented Model')
        segObj.updateGeometry(self._step._model.get_field_parameters(), self._scene)
        segTableItem = self._ui.tableWidget.item(2, self.objectTableHeaderColumns['visible'])
        segTableItem.setCheckState(Qt.Checked)

        # update segmented data cloud
        # segObj = self._objects.getObject('Segmented Points')
        # segObj.updateGeometry(self._step._model.get_field_parameters(), self._scene)
        # segTableItem = self._ui.tableWidget.item(2, self.objectTableHeaderColumns['visible'])
        # segTableItem.setCheckState(Qt.Checked)

        self._objects.addObject('Segmented Points',
            MayaviViewerDataPoints('Segmented Points',
            self._pointCloudFinal,
            renderArgs=self._pointCloudRenderArgs))

        # unlock reg ui
        self._fitUnlockUI()

    def _fitLockUI(self):
        self._ui.pcsToFitSpinBox.setEnabled(False)
        self._ui.mWeightDblSpinBox.setEnabled(False)
        self._ui.surfDiscSpinBox.setEnabled(False)
        self._ui.pExtDblSpinBox1.setEnaled(False)
        self._ui.pExtDblSpinBox2.setEnaled(False)
        self._ui.profileModelButton.setEnabled(False)
        self._ui.profileModelLineEdit.setEnabled(False)
        self._ui.searchDistSpinBox.setEnabled(False)
        self._ui.maxItSpinBox.setEnabled(False)
        self._ui.segButton.setEnabled(False)
        self._ui.resetButton.setEnabled(False)
        self._ui.acceptButton.setEnabled(False)
        self._ui.abortButton.setEnabled(False)

    def _fitUnlockUI(self):
        self._ui.pcsToFitSpinBox.setEnabled(True)
        self._ui.mWeightDblSpinBox.setEnabled(True)
        self._ui.surfDiscSpinBox.setEnabled(True)
        self._ui.pExtDblSpinBox1.setEnaled(True)
        self._ui.pExtDblSpinBox2.setEnaled(True)
        self._ui.profileModelButton.setEnabled(True)
        self._ui.profileModelLineEdit.setEnabled(True)
        self._ui.searchDistSpinBox.setEnabled(True)
        self._ui.maxItSpinBox.setEnabled(True)
        self._ui.segButton.setEnabled(True)
        self._ui.resetButton.setEnabled(True)
        self._ui.acceptButton.setEnabled(True)
        self._ui.abortButton.setEnabled(True)

    def _segCallback(self, output):
        GFParamsFitted = output[1]
        segObj = self._objects.getObject('Segmented Model')
        segObj.updateGeometry(GFParamsFitted, self._scene)
        segTableItem = self._ui.tableWidget.item(2, self.objectTableHeaderColumns['visible'])
        segTableItem.setCheckState(Qt.Checked)

    def _reset(self):
        self._resetCallback()
        segObj = self._objects.getObject('Segmented Model')
        segObj.updateGeometry(self._step._modelInit.field_parameters.copy(), self._scene)
        segTableItem = self._ui.tableWidget.item(2, self.objectTableHeaderColumns['visible'])
        segTableItem.setCheckState(Qt.Unchecked)

        self._objects.removeObject('Segmented Points')

        # clear error fields
        self._ui.RMSELineEdit.clear()
        self._ui.pFracLineEdit.clear()

    def _accept(self):
        self._close()

    def _abort(self):
        self._reset()
        self._close()

    def _close(self):
        for name in self._objects.getObjectNames():
            self._objects.removeObject(name)

        self._objects == None

    def _refresh(self):
        for r in range(self._ui.tableWidget.rowCount()):
            tableItem = self._ui.tableWidget.item(r, self.objectTableHeaderColumns['visible'])
            name = tableItem.text()
            visible = tableItem.checkState().name=='Checked'
            obj = self._objects.getObject(name)
            # print obj.name
            if obj.sceneObject:
                # print 'changing existing visibility'
                obj.setVisibility(visible)
            else:
                # print 'drawing new'
                obj.draw(self._scene)

    def _saveScreenShot(self):
        filename = self._ui.screenshotFilenameLineEdit.text()
        width = int(self._ui.screenshotPixelXLineEdit.text())
        height = int(self._ui.screenshotPixelYLineEdit.text())
        self._scene.mlab.savefig( filename, size=( width, height ) )

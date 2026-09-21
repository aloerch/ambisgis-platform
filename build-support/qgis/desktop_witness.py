"""Executed by the owned qgis --code option, inside its real desktop event loop."""
import json
import os
from pathlib import Path
import time

from qgis.core import QgsProject, QgsRectangle
from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtGui import QImage
from qgis.PyQt.QtWidgets import QApplication
from qgis.utils import iface
from runtime_common import check_layers, image_witness, loaded_origins, provider_origins, require, save, sha

CONFIG = json.loads(Path(os.environ['AMBISGIS_QGIS_RUNTIME_CONFIG']).read_text())
OUTPUT = Path(CONFIG['output'])


class DesktopWitness:
    def __init__(self):
        self.report = {'result_exit_code': 1, 'display': 'Qt offscreen; real desktop event loop; no physical display acceptance',
                       'render_events': 0, 'phases': []}
        self.phase, self.started, self.last_render = 0, time.monotonic(), 0
        self.canvas = iface.mapCanvas()
        self.canvas.mapCanvasRefreshed.connect(self.rendered)
        self.timer = QTimer(); self.timer.timeout.connect(self.tick); self.timer.start(250)
        self.closed = False

    def rendered(self): self.report['render_events'] += 1

    def capture(self, name):
        path = OUTPUT / (name+'.png')
        self.canvas.saveAsImage(str(path))
        require(path.is_file(), 'desktop map canvas image missing')
        e = self.canvas.extent()
        result = image_witness(QImage(str(path)), (e.xMinimum(),e.yMinimum(),e.xMaximum(),e.yMaximum()))
        result['sha256'] = sha(path)
        self.report[name] = result
        require(iface.mainWindow().grab().save(str(OUTPUT/(name+'-window.png'))), 'desktop window capture failed')

    def finish(self, code, error=None):
        if self.closed: return
        self.closed = True; self.timer.stop()
        if error: self.report['error'] = {'type':type(error).__name__,'message':str(error)}
        self.report['result_exit_code'] = code
        try: save(OUTPUT/'desktop-result.json',self.report)
        finally:
            QgsProject.instance().setDirty(False)
            QApplication.instance().exit(code)

    def tick(self):
        try:
            require(time.monotonic()-self.started < 100, 'desktop witness deadline exceeded')
            if self.phase == 0:
                require(iface is not None and iface.mainWindow().isVisible(), 'real QGIS desktop not visible in offscreen window system')
                require(Path('/proc/self/exe').resolve() == Path(CONFIG['desktop']).resolve(), 'wrong desktop executable')
                self.report['layers_initial'] = check_layers(QgsProject.instance())
                iface.mainWindow().resize(1200,950)
                self.canvas.setExtent(QgsRectangle(0,0,4,4)); self.canvas.refresh()
                self.last_render = self.report['render_events']; self.phase = 1
            elif not self.canvas.isDrawing() and self.report['render_events'] > self.last_render:
                if self.phase == 1:
                    self.capture('desktop-initial')
                    self.original_width = self.canvas.extent().width()
                    self.canvas.zoomByFactor(.8); self.canvas.refresh(); self.phase = 2
                    self.report['phases'].append('loaded project and rendered real canvas')
                elif self.phase == 2:
                    require(self.canvas.extent().width() < self.original_width*.9, 'canvas zoom did not change extent')
                    self.report['zoom'] = {'before_width':self.original_width,'after_width':self.canvas.extent().width()}
                    self.canvas.setExtent(QgsRectangle(0,0,4,4)); self.canvas.refresh(); self.phase = 3
                    self.report['phases'].append('real canvas zoom interaction')
                elif self.phase == 3:
                    project = QgsProject.instance(); project.setFileName(str(OUTPUT/'desktop-saved.qgs')); project.setDirty(True)
                    iface.actionSaveProject().trigger()
                    require((OUTPUT/'desktop-saved.qgs').is_file() and not project.isDirty(), 'desktop save action failed')
                    require(iface.newProject(False), 'desktop new project failed')
                    require(iface.addProject(str(OUTPUT/'desktop-saved.qgs')), 'desktop project reopen failed')
                    self.report['layers_reopened'] = check_layers(QgsProject.instance())
                    self.canvas.setExtent(QgsRectangle(0,0,4,4)); self.canvas.refresh(); self.phase = 4
                    self.report['phases'].append('save action, clear desktop project, reopen saved file')
                elif self.phase == 4:
                    self.capture('desktop-reopened')
                    self.report['loaded_origins'] = loaded_origins(CONFIG)
                    self.report['provider_origins'] = provider_origins(CONFIG)
                    self.report['saved_project_sha256'] = sha(OUTPUT/'desktop-saved.qgs')
                    require(self.report['render_events'] >= 4, 'desktop event loop/canvas rendering not demonstrated')
                    self.finish(0); return
                self.last_render = self.report['render_events']
        except Exception as error: self.finish(1,error)


# Keep ownership alive after the --code module finishes.
AMBISGIS_DESKTOP_WITNESS = DesktopWitness()

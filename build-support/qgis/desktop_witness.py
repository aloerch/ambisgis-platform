"""Executed by the owned qgis --code option, inside its real desktop event loop."""
import json
import os
from pathlib import Path
import time

from qgis.core import QgsProject, QgsRectangle, QgsSettings
from qgis.PyQt.QtCore import QTimer, Qt
from qgis.PyQt.QtGui import QFontInfo, QImage, QPainter, QRawFont
from qgis.PyQt.QtWidgets import QApplication
from qgis.utils import iface
from runtime_common import check_layers, image_witness, loaded_origins, provider_origins, python_origins, require, save, sha

CONFIG = json.loads(Path(os.environ['AMBISGIS_QGIS_RUNTIME_CONFIG']).read_text())
OUTPUT = Path(CONFIG['output'])


def desktop_font_witness():
    expected = json.loads((OUTPUT/'fixture-result.json').read_text())['font']['families'][0]
    font = QApplication.font()
    require(QFontInfo(font).family() == expected, 'desktop did not select retained UI font')
    require(QFontInfo(iface.mainWindow().menuBar().font()).family() == expected,
            'desktop menu did not inherit retained UI font')
    text = 'F02-04 QGIS local_points database_points'
    raw = QRawFont.fromFont(font)
    require(raw.isValid() and all(raw.glyphIndexesForString(text)), 'desktop UI font lacks fixture glyphs')
    image = QImage(600,64,QImage.Format_ARGB32); image.fill(Qt.white)
    painter = QPainter(image); painter.setFont(font); painter.setPen(Qt.black)
    painter.drawText(10,36,text); painter.end()
    dark = sum(max(image.pixelColor(x,y).getRgb()[:3]) < 128
               for x in range(image.width()) for y in range(image.height()))
    require(dark > 100, 'desktop default font renders blank text')
    path = OUTPUT/'desktop-ui-font.png'; require(image.save(str(path)), 'desktop font capture failed')
    return {'family':QFontInfo(font).family(),'point_size':font.pointSizeF(),
            'glyphs_available':True,'dark_pixels':dark,'render_sha256':sha(path)}


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
        self.report['shutdown'] = 'native File Exit action (includes closeProject)'
        try: save(OUTPUT/'desktop-result.json',self.report)
        finally:
            QgsProject.instance().setDirty(False)
            # Native File Exit closes the project before widgets are destroyed.
            # The assertion receipt preserves failures even though File Exit returns 0.
            iface.actionExit().trigger()

    def tick(self):
        try:
            require(time.monotonic()-self.started < 100, 'desktop witness deadline exceeded')
            if self.phase == 0:
                require(iface is not None and iface.mainWindow().isVisible(), 'real QGIS desktop not visible in offscreen window system')
                require(Path('/proc/self/exe').resolve() == Path(CONFIG['desktop']).resolve(), 'wrong desktop executable')
                require(QgsSettings().value('fonts/downloadMissingFonts',True,type=bool) is False,
                        'optional font downloads were not disabled in the disposable profile')
                self.report['font_downloads_enabled'] = False
                self.report['font'] = desktop_font_witness()
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
                    self.report['startup_messages'] = [item.text() for item in iface.messageBar().items()]
                    require(not any('font installation failed' in message.lower()
                                    for message in self.report['startup_messages']),
                            'optional font download failure remained in desktop')
                    self.capture('desktop-reopened')
                    self.report['loaded_origins'] = loaded_origins(CONFIG)
                    self.report['provider_origins'] = provider_origins(CONFIG)
                    self.report['python_origins'] = python_origins(CONFIG)
                    self.report['saved_project_sha256'] = sha(OUTPUT/'desktop-saved.qgs')
                    require(self.report['render_events'] >= 4, 'desktop event loop/canvas rendering not demonstrated')
                    self.finish(0); return
                self.last_render = self.report['render_events']
        except Exception as error: self.finish(1,error)


# Keep ownership alive after the --code module finishes.
AMBISGIS_DESKTOP_WITNESS = DesktopWitness()

"""Native resource/serialized-style checks executed inside the new real desktop."""
import json
import faulthandler
import xml.etree.ElementTree as ET
from pathlib import Path
import time

from common import inventory as full_inventory
from runtime_common import require, save, sha


def run(config):
    from qgis.core import (QgsApplication, QgsCptCityArchive, QgsCptCityColorRamp, QgsCptCityBrowserModel,
        QgsGradientColorRamp, QgsProject, QgsVectorLayer, QgsRasterLayer,
        QgsGraduatedSymbolRenderer, QgsRendererRange, QgsMarkerSymbol,
        QgsRasterShader, QgsColorRampShader, QgsSingleBandPseudoColorRenderer,
        QgsMapSettings, QgsMapRendererSequentialJob, QgsRectangle)
    from qgis.gui import QgsCptCityColorRampDialog
    from qgis.PyQt import sip
    from qgis.PyQt.QtCore import QSize, QDirIterator, QFile, QIODevice
    from qgis.PyQt.QtGui import QColor
    from qgis.PyQt.QtWidgets import QApplication, QTabBar, QTreeView, QListWidget, QComboBox
    start = time.monotonic(); output = Path(config["output"])
    faulthandler.enable(all_threads=False)
    def progress(message):
        with (output/"resource-progress.jsonl").open("a") as stream:
            stream.write(json.dumps({"phase":message,"seconds":time.monotonic()-start})+"\n");stream.flush()
    def check_native_palette(ramp, expected_path):
        require(Path(ramp.fileName()) == expected_path, "retained native ramp selected wrong file")
        file=QFile(ramp.fileName());require(file.open(QIODevice.ReadOnly), "retained native ramp file cannot open");file.close()
        tree=ET.fromstring(expected_path.read_bytes())
        stops=[el for el in tree.iter() if el.tag.rsplit("}",1)[-1] == "stop"]
        require(len(stops)>=2,"expected source palette has no gradient stops")
        first=QColor(stops[0].attrib.get("stop-color","#000000"));last=QColor(stops[-1].attrib.get("stop-color","#000000"))
        require(first.isValid() and last.isValid(),"expected palette endpoint invalid")
        require(ramp.color(0).rgb() == first.rgb() and ramp.color(1).rgb() == last.rgb(), "native ramp did not parse exact SVG endpoints")
    report = {"result_exit_code":1,"scope":"Fresh native desktop palette selection and local vector/raster serialized styling"}
    try:
        prefix = Path(config["qgis_prefix"])
        manifest = Path(config["resource_manifest"])
        require(sha(manifest) == config["resource_manifest_sha256"], "variant manifest identity changed")
        require(full_inventory(prefix) == json.loads(manifest.read_text())["files"], "variant stage differs before resource witness")
        selection = json.loads(Path(config["resource_selection"]).read_text())
        require(sha(config["resource_selection"]) == config["resource_selection_sha256"], "resource selection changed")
        base = prefix/"share/qgis/resources/cpt-city-qgis-min"
        require(Path(QgsApplication.prefixPath()).resolve() == prefix.resolve(), "wrong resource runtime prefix")
        require(Path(QgsApplication.pkgDataPath()).resolve() == (prefix/"share/qgis").resolve(), "old stage supplies package resources")
        require(Path(QgsCptCityArchive.defaultBaseDir()).resolve() == base.resolve(), "old or user palette archive selected")
        report["paths"]={"prefix":QgsApplication.prefixPath(),"package":QgsApplication.pkgDataPath(),"palette_archive":QgsCptCityArchive.defaultBaseDir()}
        omitted_roots = [p.removeprefix("share/qgis/resources/cpt-city-qgis-min/") for p in selection["omitted_collection_roots"]]
        progress("new resource paths and complete stage verified")
        excluded = 0
        for name in selection["exclusions"]:
            rel = name.removeprefix("share/qgis/resources/cpt-city-qgis-min/")
            ramp = QgsCptCityColorRamp(rel.removesuffix(".svg"), "")
            require(Path(ramp.fileName()) == base/rel and not QFile(ramp.fileName()).open(QIODevice.ReadOnly), "omitted named ramp file still opens: "+rel)
            excluded += 1
        require(excluded == 1129, "incorrect excluded native ramp count")
        progress("1129 excluded native QFile opens failed")
        for row in selection["colorbrewer"]:
            rel = row["path"].removeprefix("share/qgis/resources/cpt-city-qgis-min/")
            ramp = QgsCptCityColorRamp(rel.removesuffix(".svg"), "")
            check_native_palette(ramp,base/rel)
            require(sha(prefix/row["path"]) == row["sha256"], "ColorBrewer bytes changed")
        progress("265 retained ColorBrewer palettes parsed with 530 endpoint assertions")
        QgsCptCityArchive.initDefaultArchive()
        archive = QgsCptCityArchive.defaultArchive()
        require(archive is not None and not archive.isEmpty(), "native palette collection empty")
        # Use the native QModelIndex API. The inherited SIP QVector<T*>
        # conversion creates owning wrappers for borrowed archive root items;
        # temporary Python lists can destroy those C++-owned objects.
        model=QgsCptCityBrowserModel(None,archive,QgsCptCityBrowserModel.Authors)
        require(model.rowCount()>0,"native author collection model empty")
        for root in omitted_roots:
            require(not model.findPath(root).isValid(),"omitted native collection remains")
        paths=set()
        for name in selection["exclusions"]:
            path=name.removeprefix("share/qgis/resources/cpt-city-qgis-min/").removesuffix(".svg")
            require(not model.findPath(path).isValid(),"omitted native palette still selectable")
            paths.add(path)
        require(model.findPath("cb/seq/Blues").isValid(),"retained native collection path missing")
        progress("native collection model excluded 1129 paths and retained Blues")
        resources=[]; iterator=QDirIterator(":",QDirIterator.Subdirectories)
        while iterator.hasNext():
            path=iterator.next()
            if "cpt-city" in path: resources.append(path)
        require(not resources,"compiled palette copy exposed through Qt resources")
        progress("compiled Qt resource enumeration complete")
        selected = QgsCptCityColorRamp("cb/seq/Blues", ["_03","_04","_05","_06","_07","_08","_09"], "_09")
        check_native_palette(selected,base/"cb/seq/Blues_09.svg")
        dialog = QgsCptCityColorRampDialog(selected)
        dialog.show(); QApplication.processEvents()
        tabs=dialog.findChild(QTabBar,"tabBar");tree=dialog.findChild(QTreeView,"mTreeView")
        listing=dialog.findChild(QListWidget,"mListWidget");variants=dialog.findChild(QComboBox,"cboVariantName")
        require(all(widget is not None for widget in (tabs,tree,listing,variants)),"native palette chooser controls missing")
        tabs.setCurrentIndex(1);QApplication.processEvents()
        proxy=tree.model();index=sip.cast(proxy.sourceModel(),QgsCptCityBrowserModel).findPath("cb/seq")
        require(index.isValid(),"native chooser collection missing")
        visible=proxy.mapFromSource(index);tree.setCurrentIndex(visible);tree.clicked.emit(visible)
        items=[listing.item(i) for i in range(listing.count()) if listing.item(i).toolTip().split("\n")[0] == "cb/seq/Blues"]
        require(len(items)==1,"native chooser Blues item missing/ambiguous")
        listing.setCurrentItem(items[0]);listing.itemClicked.emit(items[0])
        variant_index=variants.findData("_09");require(variant_index>=0,"native chooser variant missing")
        variants.setCurrentIndex(variant_index);QApplication.processEvents()
        chosen = dialog.ramp()
        report["ramp_dialog_observed"] = {"scheme":chosen.schemeName(),"variant":chosen.variantName(),"selected_name":dialog.selectedName()}
        require(chosen.schemeName() == selected.schemeName() and chosen.variantName() == "_09", "native ramp dialog selection failed")
        check_native_palette(chosen,base/"cb/seq/Blues_09.svg")
        require(dialog.grab().save(str(output/"palette-dialog.png")),"palette dialog capture failed")
        dialog.close(); dialog.deleteLater(); QApplication.processEvents()
        progress("native ramp dialog selected and captured")
        generic = QgsGradientColorRamp(QColor("#ff3300"),QColor("#0055ff"))
        require(generic.color(0).name() == "#ff3300" and generic.color(1).name() == "#0055ff", "generic gradient unavailable")
        colors = [chosen.color(i/3) for i in range(4)]
        vector=QgsVectorLayer(str(output/"points.geojson"),"palette_vector","ogr")
        raster=QgsRasterLayer(str(output/"known.tif"),"palette_raster","gdal")
        require(vector.isValid() and raster.isValid(),"styling fixtures unavailable")
        ranges=[QgsRendererRange(i+.5,i+1.5,QgsMarkerSymbol.createSimple({"color":colors[i].name(),"size":"5","outline_style":"no"}),str(i+1)) for i in range(3)]
        renderer=QgsGraduatedSymbolRenderer("id",ranges);renderer.setSourceColorRamp(chosen.clone());vector.setRenderer(renderer)
        shader=QgsColorRampShader(0,255);shader.setColorRampType(QgsColorRampShader.Interpolated)
        shader.setColorRampItemList([QgsColorRampShader.ColorRampItem(value,color,str(value)) for value,color in zip((40,90,150,210),colors)])
        raster_shader=QgsRasterShader(0,255);raster_shader.setRasterShaderFunction(shader)
        raster.setRenderer(QgsSingleBandPseudoColorRenderer(raster.dataProvider(),1,raster_shader))
        project=QgsProject();project.addMapLayer(vector);project.addMapLayer(raster)
        project_path=output/"palette-style.qgs";require(project.write(str(project_path)),"palette-style save failed")
        before_vector=[r.symbol().color().name() for r in vector.renderer().ranges()]
        before_raster=[i.color.name() for i in raster.renderer().shader().rasterShaderFunction().colorRampItemList()]
        reopened=QgsProject();require(reopened.read(str(project_path)),"palette-style reopen failed")
        v=reopened.mapLayersByName("palette_vector")[0];r=reopened.mapLayersByName("palette_raster")[0]
        require([i.symbol().color().name() for i in v.renderer().ranges()] == before_vector,"vector style changed on reopen")
        require([i.color.name() for i in r.renderer().shader().rasterShaderFunction().colorRampItemList()] == before_raster,"raster style changed on reopen")
        check_native_palette(v.renderer().sourceColorRamp(),base/"cb/seq/Blues_09.svg")
        progress("retained vector and raster styles saved and reopened")
        settings=QgsMapSettings();settings.setLayers([r]);settings.setExtent(QgsRectangle(0,0,4,4));settings.setOutputSize(QSize(256,256))
        job=QgsMapRendererSequentialJob(settings);job.start();job.waitForFinished();image=job.renderedImage()
        require(image.save(str(output/"palette-raster.png")),"styled raster capture failed")
        for (x,y),color in zip(((32,32),(224,32),(32,224),(224,224)),colors):
            require(max(abs(a-b) for a,b in zip(image.pixelColor(x,y).getRgb()[:3],color.getRgb()[:3])) <= 2,"styled raster sampled color wrong")
        settings.setLayers([v]);job=QgsMapRendererSequentialJob(settings);job.start();job.waitForFinished();image=job.renderedImage()
        require(image.save(str(output/"palette-vector.png")),"styled vector capture failed")
        for (x,y),color in zip(((64,192),(192,192),(128,64)),colors[:3]):
            require(max(abs(a-b) for a,b in zip(image.pixelColor(x,y).getRgb()[:3],color.getRgb()[:3])) <= 2,"styled vector sampled color wrong")
        vector_image=image
        progress("retained raster and vector rendered colors verified")
        # Serialized symbols remain explicit even when their source ramp is
        # unavailable. Synthetic colors avoid copying an omitted palette into
        # this fixture or introducing any extra palette asset.
        missing=QgsCptCityColorRamp("td/DEM_print","",False,False)
        require(not QFile(missing.fileName()).exists(),"expected omitted reference unexpectedly present")
        missing_load_status = missing.loadFile()
        v.renderer().setSourceColorRamp(missing)
        missing_path=output/"omitted-ramp-project.qgs"
        require(reopened.write(str(missing_path)),"omitted-reference project save failed")
        require("td/DEM_print" in missing_path.read_text(),"omitted reference not serialized")
        again=QgsProject();require(again.read(str(missing_path)),"omitted-reference project reopen failed")
        retained=again.mapLayersByName("palette_vector")[0]
        after_colors=[i.symbol().color().name() for i in retained.renderer().ranges()]
        require(after_colors == before_vector,"serialized style silently substituted after omitted ramp reopen")
        require(not QFile(retained.renderer().sourceColorRamp().fileName()).exists(),"missing source ramp found in alternate stage")
        settings.setLayers([retained]);job=QgsMapRendererSequentialJob(settings);job.start();job.waitForFinished()
        require(job.renderedImage() == vector_image,"omitted-reference reopened rendering changed")
        require(job.renderedImage().save(str(output/"omitted-ramp-vector.png")),"omitted-reference render capture failed")
        progress("omitted reference preserved serialized and rendered symbol colors")
        report.update(result_exit_code=0,excluded_named_ramp_files_unopenable=excluded,retained_colorbrewer_loadable=265,
                      retained_native_endpoint_assertions=530,
                      native_model_paths=len(paths),compiled_palette_resources=resources,
                      ramp_dialog={"scheme":chosen.schemeName(),"variant":chosen.variantName(),"capture_sha256":sha(output/"palette-dialog.png")},
                      generic_gradient=True,vector_colors=before_vector,raster_colors=before_raster,
                      save_reopen={"vector":True,"raster":True,"project_sha256":sha(project_path)},
                      omitted_saved_project={"reference":"td/DEM_print","serialized_colors_preserved":after_colors,"rendered_colors_preserved":True,"source_ramp_file_exists":False,"inherited_loadFile_return":missing_load_status,
                        "inherited_loadFile_limitation":"Returns true despite missing file; the witness uses native QFile failure and archive-model exclusion, never that boolean as availability.",
                        "project_sha256":sha(missing_path),"limitation":"Serialized renderer colors survive; unavailable ramp cannot support reclassification. No complete saved-project compatibility claimed."},
                      manifest_sha256=sha(manifest))
        # Explicitly destroy standalone projects while the desktop is alive.
        again.clear();reopened.clear();project.clear()
    except BaseException as error:
        report["error"]={"type":type(error).__name__,"message":str(error)}
        raise
    finally:
        report["seconds"]=round(time.monotonic()-start,3);save(output/"resource-result.json",report)
    return report

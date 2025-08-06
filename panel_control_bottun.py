

from qgis.PyQt.QtCore import QSettings
from qgis.gui import QgsMapToolPan, QgsMapToolZoom
from qgis.core import (
    QgsProject,
    QgsCoordinateReferenceSystem,
    QgsFeature,
    QgsGeometry,
    QgsCoordinateTransform,
    QgsVectorLayer,
    QgsVectorFileWriter,
    Qgis,
    QgsLayerTreeLayer,
    QgsSymbol,
    QgsSimpleLineSymbolLayer
)

from PyQt5.QtWidgets import (
    QMenu,
    QWidgetAction,
    QDoubleSpinBox,
    QCheckBox,
    QFileDialog,
    QWidget,
    QHBoxLayout,
    QLabel,
)
from PyQt5.QtGui import (
    QColor,
)
import os.path
import math

def zoom_in(self):
    """Zoom in the map canvas"""
    canvas = self.iface.mapCanvas()
    canvas.zoomIn()
    
def zoom_out(self):
    """Zoom in the map canvas"""
    canvas = self.iface.mapCanvas()
    canvas.zoomOut()

def toggle_measure_mode(self, checked):
    """距離計測ツールのON/OFF切り替え"""
    if checked:
        self.iface.actionMeasure().trigger()
    else:
        # 標準のパンツールに戻す
        self.iface.actionSelect().trigger()

def toggle_pan_mode(self, checked):
    """手のひらツールのON/OFF切り替え"""
    if checked:
        self.iface.actionPan().trigger()
    else:
        # 選択ツールに戻す
        self.iface.actionSelect().trigger()

def toggle_select_zoom_in(self, checked):
    """ズームインツールのON/OFF切り替え"""
    if checked:
        self.iface.actionZoomIn().trigger()
    else:
        # パンツールに戻す
        self.iface.actionSelect().trigger()

def toggle_select_zoom_out(self, checked):
    """ズームアウトツールのON/OFF切り替え"""
    if checked:
        self.iface.actionZoomOut().trigger()
    else:
        # パンツールに戻す
        self.iface.actionSelect().trigger()

def add_latlong_grid_layer(self):
    """現在の地図範囲に緯度経度グリッドラインの仮レイヤを追加"""

    # 現在の地図範囲とCRSを取得
    canvas = self.iface.mapCanvas()
    extent = canvas.extent()
    crs = canvas.mapSettings().destinationCrs()

    # 緯度経度（EPSG:4326）で範囲を取得
    wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
    if crs.authid() != "EPSG:4326":
        xform = QgsCoordinateTransform(crs, wgs84, QgsProject.instance())
        extent = xform.transformBoundingBox(extent)
    else:
        xform = None

    xmin, xmax = extent.xMinimum(), extent.xMaximum()
    ymin, ymax = extent.yMinimum(), extent.yMaximum()


    lon_step = getattr(self, "lon_step", 0.1)
    lat_step = getattr(self, "lat_step", 0.1)
    separate = getattr(self, "separate_latlon", False)

    if separate:
        # 緯度・経度レイヤを別々に作成
        lon_layer = QgsVectorLayer("LineString?crs=EPSG:4326", "Lon Grid", "memory")
        lat_layer = QgsVectorLayer("LineString?crs=EPSG:4326", "Lat Grid", "memory")
        for lyr in (lon_layer, lat_layer):
            pr = lyr.dataProvider()
            self.create_field_attributes(pr)
            lyr.updateFields()
        # 経度ライン
        lon = math.floor(xmin / lon_step) * lon_step
        while lon <= xmax:
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPolylineXY([
                QgsGeometry.fromWkt(f"POINT({lon} {ymin})").asPoint(),
                QgsGeometry.fromWkt(f"POINT({lon} {ymax})").asPoint()
            ]))
            feat.setAttributes(["lon", round(lon, 8)])
            lon_layer.dataProvider().addFeatures([feat])
            lon += lon_step
        # 緯度ライン
        lat = math.floor(ymin / lat_step) * lat_step
        while lat <= ymax:
            feat = QgsFeature()
            feat.setGeometry(QgsGeometry.fromPolylineXY([
                QgsGeometry.fromWkt(f"POINT({xmin} {lat})").asPoint(),
                QgsGeometry.fromWkt(f"POINT({xmax} {lat})").asPoint()
            ]))
            feat.setAttributes(["lat", round(lat, 8)])
            lat_layer.dataProvider().addFeatures([feat])
            lat += lat_step
        lon_layer.updateExtents()
        lat_layer.updateExtents()

        # ファイル保存
        if getattr(self, "save_to_file", False):
            # 経度
            path_lon, _ = QFileDialog.getSaveFileName(
                self.iface.mainWindow(),
                self.tr("経度ラインの保存先ファイル名"),
                "",
                "GeoPackage (*.gpkg);;Shapefile (*.shp)"
            )
            if path_lon:
                file_format = "GPKG" if path_lon.endswith(".gpkg") else "ESRI Shapefile"
                QgsVectorFileWriter.writeAsVectorFormat(lon_layer, path_lon, "utf-8", lon_layer.crs(), file_format)
                layer_name = os.path.splitext(os.path.basename(path_lon))[0]
                saved_layer = QgsVectorLayer(path_lon, layer_name, "ogr")
                if saved_layer.isValid():
                    QgsProject.instance().addMapLayer(saved_layer, addToLegend=False)
                    root = QgsProject.instance().layerTreeRoot()
                    root.insertChildNode(0, QgsLayerTreeLayer(saved_layer))
            # 緯度
            path_lat, _ = QFileDialog.getSaveFileName(
                self.iface.mainWindow(),
                self.tr("緯度ラインの保存先ファイル名"),
                "",
                "GeoPackage (*.gpkg);;Shapefile (*.shp)"
            )
            if path_lat:
                file_format = "GPKG" if path_lat.endswith(".gpkg") else "ESRI Shapefile"
                QgsVectorFileWriter.writeAsVectorFormat(lat_layer, path_lat, "utf-8", lat_layer.crs(), file_format)
                layer_name = os.path.splitext(os.path.basename(path_lat))[0]
                saved_layer = QgsVectorLayer(path_lat, layer_name, "ogr")
                if saved_layer.isValid():
                    QgsProject.instance().addMapLayer(saved_layer, addToLegend=False)
                    root = QgsProject.instance().layerTreeRoot()
                    root.insertChildNode(0, QgsLayerTreeLayer(saved_layer))
            return

        # 経度レイヤのスタイル設定
        lon_symbol = QgsSymbol.defaultSymbol(lon_layer.geometryType())
        if lon_symbol is not None:
            lon_line_layer = QgsSimpleLineSymbolLayer(color=QColor("blue"), width=0.5)
            lon_symbol.changeSymbolLayer(0, lon_line_layer)
            lon_layer.renderer().setSymbol(lon_symbol)

        # 緯度レイヤのスタイル設定
        lat_symbol = QgsSymbol.defaultSymbol(lat_layer.geometryType())
        if lat_symbol is not None:
            lat_line_layer = QgsSimpleLineSymbolLayer(color=QColor("green"), width=0.5)
            lat_symbol.changeSymbolLayer(0, lat_line_layer)
            lat_layer.renderer().setSymbol(lat_symbol)

        # 仮レイヤとして追加
        root = QgsProject.instance().layerTreeRoot()
        root.insertChildNode(0, QgsLayerTreeLayer(lon_layer))
        QgsProject.instance().addMapLayer(lon_layer, addToLegend=False)
        root.insertChildNode(0, QgsLayerTreeLayer(lat_layer))
        QgsProject.instance().addMapLayer(lat_layer, addToLegend=False)
        return

    # 仮レイヤ作成（フィールド追加）
    layer = QgsVectorLayer("LineString?crs=EPSG:4326", "LatLon Grid", "memory")
    pr = layer.dataProvider()
    self.create_field_attributes(pr)
    layer.updateFields()

    # 経度ライン
    lon = math.floor(xmin / lon_step) * lon_step
    while lon <= xmax:
        feat = QgsFeature()
        feat.setGeometry(QgsGeometry.fromPolylineXY([
            QgsGeometry.fromWkt(f"POINT({lon} {ymin})").asPoint(),
            QgsGeometry.fromWkt(f"POINT({lon} {ymax})").asPoint()
        ]))
        feat.setAttributes(["lon", round(lon, 8)])
        pr.addFeatures([feat])
        lon += lon_step

    # 緯度ライン
    lat = math.floor(ymin / lat_step) * lat_step
    while lat <= ymax:
        feat = QgsFeature()
        feat.setGeometry(QgsGeometry.fromPolylineXY([
            QgsGeometry.fromWkt(f"POINT({xmin} {lat})").asPoint(),
            QgsGeometry.fromWkt(f"POINT({xmax} {lat})").asPoint()
        ]))
        feat.setAttributes(["lat", round(lat, 8)])
        pr.addFeatures([feat])
        lat += lat_step

    layer.updateExtents()

    # ファイル保存オプション
    if getattr(self, "save_to_file", False):
        path, _ = QFileDialog.getSaveFileName(
            self.iface.mainWindow(),
            self.tr("保存先ファイル名"),
            "",
            "GeoPackage (*.gpkg);;Shapefile (*.shp)"
        )
        if path:
            file_format = "GPKG" if path.endswith(".gpkg") else "ESRI Shapefile"
            _ = QgsVectorFileWriter.writeAsVectorFormat(layer, path, "utf-8", layer.crs(), file_format)
            self.iface.messageBar().pushMessage(self.tr("保存しました"), path)
            # ファイル名（拡張子なし）をレイヤ名に
            layer_name = os.path.splitext(os.path.basename(path))[0]
            saved_layer = QgsVectorLayer(path, layer_name, "ogr")
            if saved_layer.isValid():
                QgsProject.instance().addMapLayer(saved_layer, addToLegend=False)
                root = QgsProject.instance().layerTreeRoot()
                root.insertChildNode(0, QgsLayerTreeLayer(saved_layer))
            else:
                self.iface.messageBar().pushWarning(self.tr("レイヤ追加失敗"), self.tr("保存したファイルのレイヤ追加に失敗しました"))
        return

    # ラインスタイルを設定
    symbol = QgsSymbol.defaultSymbol(layer.geometryType())
    if symbol is not None:
        line_layer = QgsSimpleLineSymbolLayer(color=QColor("red"), width=0.5)
        symbol.changeSymbolLayer(0, line_layer)
        layer.renderer().setSymbol(symbol)

    # チェックなしの場合は仮レイヤをグループ外（ルート直下の一番上）に追加
    root = QgsProject.instance().layerTreeRoot()
    layer_node = QgsLayerTreeLayer(layer)
    root.insertChildNode(0, layer_node)
    QgsProject.instance().addMapLayer(layer, addToLegend=False)

def show_latlong_menu(self, pos):
    menu = QMenu()
    # 緯度ラベル
    lat_label = QLabel(self.tr("緯度の間隔:"))
    lat_label_widget = QWidget()
    lat_label_layout = QHBoxLayout(lat_label_widget)
    lat_label_layout.setContentsMargins(10, 0, 10, 0)
    lat_label_layout.addWidget(lat_label)
    lat_label_action = QWidgetAction(menu)
    lat_label_action.setDefaultWidget(lat_label_widget)
    menu.addAction(lat_label_action)

    # 緯度スピンボックス
    lat_spin = QDoubleSpinBox()
    lat_spin.setDecimals(4)
    lat_spin.setRange(0.001, 10)
    lat_spin.setValue(self.lat_step)
    lat_spin.setSingleStep(0.01)
    lat_widget = QWidget()
    lat_layout = QHBoxLayout(lat_widget)
    lat_layout.setContentsMargins(10, 0, 10, 0)
    lat_layout.addWidget(lat_spin)
    lat_action = QWidgetAction(menu)
    lat_action.setDefaultWidget(lat_widget)
    menu.addAction(lat_action)

    # 経度ラベル
    lon_label = QLabel(self.tr("経度の間隔:"))
    lon_label_widget = QWidget()
    lon_label_layout = QHBoxLayout(lon_label_widget)
    lon_label_layout.setContentsMargins(10, 0, 10, 0)
    lon_label_layout.addWidget(lon_label)
    lon_label_action = QWidgetAction(menu)
    lon_label_action.setDefaultWidget(lon_label_widget)
    menu.addAction(lon_label_action)

    # 経度スピンボックス
    lon_spin = QDoubleSpinBox()
    lon_spin.setDecimals(4)
    lon_spin.setRange(0.001, 10)
    lon_spin.setValue(self.lon_step)
    lon_spin.setSingleStep(0.01)
    lon_widget = QWidget()
    lon_layout = QHBoxLayout(lon_widget)
    lon_layout.setContentsMargins(10, 0, 10, 0)
    lon_layout.addWidget(lon_spin)
    lon_action = QWidgetAction(menu)
    lon_action.setDefaultWidget(lon_widget)
    menu.addAction(lon_action)

    # ファイル保存
    save_check = QCheckBox(self.tr("ファイルとして保存する"))
    save_check.setChecked(self.save_to_file)
    save_check.setStyleSheet("QCheckBox { padding-left: 10px; padding-right: 10px; }") 
    save_action = QWidgetAction(menu)
    save_action.setDefaultWidget(save_check)
    menu.addAction(save_action)

    # 緯度と経度を別ファイルで作成
    separate_check = QCheckBox(self.tr("緯度と経度を別ファイルで作成する"))
    separate_check.setChecked(getattr(self, "separate_latlon", False))
    separate_check.setStyleSheet("QCheckBox { padding-left: 10px; padding-right: 10px; }") 
    separate_action = QWidgetAction(menu)
    separate_action.setDefaultWidget(separate_check)
    menu.addAction(separate_action)

    # OKボタン
    def apply_settings():
        self.lat_step = lat_spin.value()
        self.lon_step = lon_spin.value()
        self.save_to_file = save_check.isChecked()
        self.separate_latlon = separate_check.isChecked()
        save_settings(self)  # ←ここで保存
    menu.addSeparator()
    menu.addAction(self.tr("OK")).triggered.connect(apply_settings)

    # ボタンのグローバル座標にメニュー表示
    menu.exec_(self.dlg.tbLatLongLine.mapToGlobal(pos))

def save_settings(self):
    settings = QSettings()
    settings.setValue("QGuidePanel/lat_step", self.lat_step)
    settings.setValue("QGuidePanel/lon_step", self.lon_step)
    settings.setValue("QGuidePanel/save_to_file", self.save_to_file)
    settings.setValue("QGuidePanel/separate_latlon", self.separate_latlon)

def set_map_scale_from_widget(self, scale):
    """QgsScaleWidget の値変更時に地図の縮尺を更新"""
    try:
        self.canvas.zoomScale(scale)  # QgsMapCanvas の縮尺を変更
    except Exception as e:
        self.iface.messageBar().pushMessage(
            self.tr("Error"),
            self.tr("縮尺変更に失敗しました: {error}").format(error=e),
            level=Qgis.Critical
        )

def update_scale_widget(self):
    """地図の縮尺が変更されたときに QgsScaleWidget を更新"""
    self.dlg.mScaleWidget.setScale(self.canvas.scale())
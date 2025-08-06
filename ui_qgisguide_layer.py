
import sys
import subprocess
import os

from qgis.PyQt import uic
from qgis.PyQt import QtWidgets
from PyQt5 import uic
from PyQt5.QtWidgets import QWidget, QDockWidget, QMenu, QWidgetAction, QCheckBox
from PyQt5.QtGui import QStandardItemModel, QStandardItem
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt, QTimer
from qgis.core import QgsProject, QgsMapLayer, QgsVectorLayer, QgsRasterLayer, QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsCoordinateTransform, QgsWkbTypes
from qgis.gui import QgsQueryBuilder

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui_qgisguide_layer.ui'))

class LayerPanelDialog(QWidget, FORM_CLASS):
    def __init__(self, iface, parent=None):
        super(LayerPanelDialog, self).__init__(parent)
        self.iface = iface
        self.parent_plugin = None
        self.setupUi(self)
        self.iface.currentLayerChanged.connect(self._on_layer_selection_changed)
        self._saved_table_width = None  # wdTableの幅を保存する変数
        self.wdTable.setVisible(False)  # 起動時は非表示
        self.stackedWidget.setCurrentWidget(self.none)
        self.pbTableView.toggled.connect(self.update_pbTableView_text)
        self.pbTableView.toggled.connect(self.toggle_layer_table)
        self.tbTableOpen.clicked.connect(self.open_qgis_attribute_table) 
        self.tbLayerFolderOpen.clicked.connect(self.open_layer_folder)
        self.leLayerName.setReadOnly(True)  # 初期状態は編集不可
        self.tbEditMode.toggled.connect(self.toggle_edit_mode)  # 編集モード切り替え
        self.pbLayerView.toggled.connect(self.update_pbLayerView_text)
        self.pbLayerView.toggled.connect(self.toggle_only_selected_layer)
        self._layer_visibility_backup = {}
        self._group_visibility_backup = {} 
        self.tbEditMode.setEnabled(False)
        self.leLayerName.setStyleSheet("background-color: transparent;")
        self.tbLayerFolderOpen.setEnabled(False)
        self.pbLayerView.setEnabled(False)
        self.pbLayerZoom.setEnabled(False)
        self.pbCallProperty.setEnabled(False)
        self.pbCallStyle.setEnabled(False)
        self.pbCallExport.setEnabled(False)
        self.tbTableOpen.setEnabled(False)
        self.setFixedWidth(280)  # 初期状態で横幅600px
        self._show_all_features = False  # 全件表示フラグ
        self.pbAllItems.setVisible(False)  # ボタンは初期非表示
        self.pbAllItems.clicked.connect(self.show_all_features_clicked)  # シグナル接続
        self.lblAllItems.setVisible(False)  # ボタンは初期非表示
        self._sync_active_layer = False
        self.pbCallStyle.clicked.connect(self.toggle_layer_style_panel)
        self.pbCallFiltering.clicked.connect(self.open_query_builder)
        self.pbCallExport.clicked.connect(self.open_export_dialog)
        self.pbCallLabel.toggled.connect(self.toggle_layer_label)        
        self.pbCallLabel.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pbCallLabel.customContextMenuRequested.connect(self.show_label_menu)
        self.pbCallProperty.clicked.connect(self.open_layer_properties)
        self.pbLayerZoom.clicked.connect(self.zoom_to_layer)
        self.pbCallFieldCalculator.clicked.connect(self.open_field_calculator)
        self.pbRasterCalculator.clicked.connect(self.open_raster_calculator)
        self.pbLayerView.setContextMenuPolicy(Qt.CustomContextMenu)
        self.pbLayerView.customContextMenuRequested.connect(self.show_view_layer_menu)
        self._always_visible_layer_ids = set()

    def _on_layer_tree_selection_changed(self, selected, deselected):
        indexes = self.qgis_layer_tree_view.selectedIndexes()
        if not indexes:
            # 何も選択されていない（空白部分クリックなど）
            self._on_layer_selection_changed(None)

    def _truncate_text(self, text, max_visual_width=28, preserve_extension=False):
        """テキストを視覚的な幅に基づいて省略"""
        if preserve_extension:
            # 拡張子を保持する場合
            name, ext = os.path.splitext(text)
            
            # まず全体の幅をチェック
            total_width = sum(2.0 if ord(c) > 127 else 1.5 if c.isupper() else 1.2 if c.isdigit() else 1.2 for c in text)
            
            # 全体が規定幅以下なら省略しない
            if total_width <= max_visual_width:
                return text
            
            # 省略が必要な場合のみ処理
            ext_width = sum(2.0 if ord(c) > 127 else 1.5 if c.isupper() else 1.2 if c.isdigit() else 1.2 for c in ext)
            ellipsis_width = 0.0  # "..."の幅（1.2 * 3）
            max_name_width = max_visual_width - ext_width - ellipsis_width
            
            if max_name_width > 0:
                truncated_name = self._truncate_text(name, max_visual_width=max_name_width, preserve_extension=False)
                if truncated_name.endswith("..."):
                    truncated_name = truncated_name[:-3]
                return truncated_name + ".." + ext
            else:
                return text  # 拡張子が長すぎる場合はそのまま
        
        # 通常の省略処理
        visual_width = 0
        truncated_text = ""
        
        for char in text:
            if ord(char) > 127:  # 全角文字
                char_width = 2.0
            elif char.isupper():  # 大文字
                char_width = 1.5
            elif char.isdigit():  # 数字
                char_width = 1.2
            else:  # その他の半角文字
                char_width = 1.2
            
            if visual_width + char_width > max_visual_width:
                truncated_text += "..."
                break
            
            truncated_text += char
            visual_width += char_width
        
        return truncated_text

    def _on_layer_selection_changed(self, layer):
        # レイヤ名・ファイル名・属性テーブル等の更新
        if isinstance(layer, QgsMapLayer):
            # 改良された省略処理を使用
            name = self._truncate_text(layer.name())
            self.leLayerName.setText(name)
            # 編集モードがONの場合はOFFにする
            if self.tbEditMode.isChecked():
                self.tbEditMode.setChecked(False)
            self.tbEditMode.setEnabled(True)
            # self.gbLayerInfo.setTitle(layer.name())
            
            # レイヤタイプの表示処理を追加
            if isinstance(layer, QgsVectorLayer):
                # ベクタレイヤの場合、ジオメトリタイプを取得
                geom_type = layer.geometryType()
                if geom_type == QgsWkbTypes.PointGeometry:
                    layer_type_text = self.tr("ベクタ (ポイント)")
                elif geom_type == QgsWkbTypes.LineGeometry:
                    layer_type_text = self.tr("ベクタ (ライン)")
                elif geom_type == QgsWkbTypes.PolygonGeometry:
                    layer_type_text = self.tr("ベクタ (ポリゴン)")
                else:
                    layer_type_text = self.tr("ベクタ")
            elif isinstance(layer, QgsRasterLayer):
                layer_type_text = self.tr("ラスタ")
            else:
                layer_type_text = ""
            self.lblLayerType.setText(layer_type_text)
            
            # レイヤCRSの表示処理を追加
            crs = layer.crs()
            if crs.isValid():
                # EPSG番号と名称を表示
                auth_id = crs.authid()
                description = crs.description()
                crs_text = f"- {auth_id}"
            else:
                crs_text = self.tr("不明なCRS")
            self.lblLayerCRS.setText(crs_text)

            if hasattr(layer, "source"):
                file_path = layer.source().split('|')[0]
                if os.path.isfile(file_path):
                    file_name = os.path.basename(file_path)
                    # 視覚的な幅で短縮（拡張子を保持）
                    short_name = self._truncate_text(file_name, preserve_extension=True)
                    self.lblLayerFile.setText(short_name)
                    self.tbLayerFolderOpen.setEnabled(True)   # ファイルがあるレイヤのみ有効
                else:
                    if file_path.startswith("http"):
                        self.lblLayerFile.setText(self.tr("（XYZタイル/URL）"))
                    elif file_path.startswith("dbname="):
                        self.lblLayerFile.setText(self.tr("（データベース）"))
                    else:
                        self.lblLayerFile.setText(self.tr("（ファイルなし）"))
                    self.tbLayerFolderOpen.setEnabled(False)  # ファイルが無いレイヤは無効
                self.pbLayerView.setEnabled(True)
                self.pbLayerZoom.setEnabled(True)
                self.pbCallProperty.setEnabled(True)
                self.pbCallStyle.setEnabled(True)
                self.pbCallExport.setEnabled(True)
                self.tbTableOpen.setEnabled(True)
            else:
                self.lblLayerFile.setText(self.tr("（ファイルなし）"))
                self.tbLayerFolderOpen.setEnabled(False)
                self.pbLayerView.setEnabled(True)
                self.pbLayerZoom.setEnabled(True)
                self.pbCallProperty.setEnabled(True)
                self.pbCallStyle.setEnabled(True)
                self.pbCallExport.setEnabled(True)
                self.tbTableOpen.setEnabled(True)
        else:
            # レイヤが選択されていない（グループや何も選択されていない場合）
            self.leLayerName.setText("")
            # 編集モードがONの場合はOFFにする
            if self.tbEditMode.isChecked():
                self.tbEditMode.setChecked(False)
            self.lblLayerFile.setText("")
            self.lblLayerType.setText("") 
            self.lblLayerCRS.setText("") 
            self.tbEditMode.setEnabled(False)
            self.tbLayerFolderOpen.setEnabled(False)
            self.pbLayerView.setEnabled(False)
            self.pbLayerZoom.setEnabled(False)
            self.pbCallProperty.setEnabled(False)
            self.pbCallStyle.setEnabled(False)
            self.pbCallExport.setEnabled(False)
            self.tbTableOpen.setEnabled(False)
        # wdTableが表示されているときのみ属性テーブルを表示
        self._show_all_features = False  # レイヤ切替時はフラグリセット
        if self.wdTable.isVisible() and isinstance(layer, QgsVectorLayer):
            self._show_attribute_table(layer)
        else:
            self.tbwTable.setModel(QStandardItemModel())
            self.pbAllItems.setVisible(False)  # テーブル非表示時はボタンも非表示
            self.lblAllItems.setVisible(False)  # テーブル非表示時はボタンも非表示

        if self._sync_active_layer and isinstance(layer, QgsMapLayer):
            self.iface.setActiveLayer(layer)

        if isinstance(layer, QgsVectorLayer):
            feature_count = layer.featureCount()
            # self.lblFeature.setText(f"地物数: {feature_count}")
            self.lblFeature.setText(f"{feature_count}")
            #self.wdLayerCommon.setVisible(True)
            self.pbCallLabel.setEnabled(True)
            self.pbCallLabel.setChecked(layer.labelsEnabled())
            self.stackedWidget.setCurrentWidget(self.vector)
            # pbTableViewがチェック状態でwdTableが非表示なら表示する
            if self.pbTableView.isChecked() and not self.wdTable.isVisible():
                self.wdTable.setVisible(True)
                self.setMinimumWidth(900)
                self.setMaximumWidth(16777215)
                # 保存された幅があれば復元（QTimerを使用して遅延実行）
                if self._saved_table_width is not None:
                    QTimer.singleShot(10, lambda: self._restore_table_width())
                self._show_all_features = False
                self._show_attribute_table(layer)
        elif isinstance(layer, QgsRasterLayer):
            self.stackedWidget.setCurrentWidget(self.rastor)
            # ラスタレイヤ選択時もwdTableを閉じる
            if self.wdTable.isVisible():
                # wdTableの幅を保存してから非表示にする
                self._saved_table_width = self.wdTable.width()
                self.wdTable.setVisible(False)
                self.setFixedWidth(280)
                #self.pbTableView.setChecked(False)
        else:
            self.lblFeature.setText("")
            #self.wdLayerCommon.setVisible(False) 
            self.pbCallLabel.setEnabled(False)
            self.pbCallLabel.setChecked(False)
            self.stackedWidget.setCurrentWidget(self.none)
            # レイヤ以外のときwdTableを閉じて幅を戻す
            if self.wdTable.isVisible():
                # wdTableの幅を保存してから非表示にする
                self._saved_table_width = self.wdTable.width()
                self.wdTable.setVisible(False)
                self.setFixedWidth(280)
                #self.pbTableView.setChecked(False)

        if self.pbLayerView.isChecked():
            # バックアップは上書きせず、表示切り替えだけ行う
            self.toggle_only_selected_layer(True, update_only=True)

    def toggle_edit_mode(self, checked):
        """編集モードの切り替え"""
        if checked:
            # 編集モードON：完全なレイヤ名を表示
            layer = self.iface.activeLayer()
            if isinstance(layer, QgsMapLayer):
                # 省略されていない完全なレイヤ名を設定
                self.leLayerName.setText(layer.name())
            
            self.leLayerName.setReadOnly(False)
            # 編集可能時は通常の白い背景
            self.leLayerName.setStyleSheet("")
            self.leLayerName.setFocus()
            self.leLayerName.selectAll()  # テキストを全選択
        else:
            # 編集モードOFF → まずレイヤ名を変更してから表示を更新
            layer = self.iface.activeLayer()
            if isinstance(layer, QgsMapLayer):
                new_name = self.leLayerName.text()
                if new_name and new_name != layer.name():
                    layer.setName(new_name)
            
            # その後で省略表示に戻す
            if isinstance(layer, QgsMapLayer):
                # 改良された省略処理を使用（変更後の名前で）
                name = self._truncate_text(layer.name())
                self.leLayerName.setText(name)
            
            self.leLayerName.setReadOnly(True)
            # 読み取り専用時はグレーの背景
            self.leLayerName.setStyleSheet("background-color: transparent;")
            self.leLayerName.clearFocus()

    def _on_show_table(self):
        layer = self.iface.activeLayer() 

        if isinstance(layer, QgsVectorLayer):
            self._show_attribute_table(layer)

    def update_pbTableView_text(self, checked):
        """pbTableViewの文字列をチェック状態に応じて変更"""
        if checked:
            self.pbTableView.setText(self.tr("属性テーブルを閉じる◀"))
        else:
            self.pbTableView.setText(self.tr("属性テーブルを開く▶"))

    def update_pbLayerView_text(self, checked):
        """pbTableViewの文字列をチェック状態に応じて変更"""
        if checked:
            self.pbLayerView.setText(self.tr("元の表示状態に戻す︙"))
        else:
            self.pbLayerView.setText(self.tr("選択レイヤのみを表示する︙"))

    def _show_attribute_table(self, layer, limit=500):
        model = QStandardItemModel()
        fields = layer.fields()
        model.setHorizontalHeaderLabels([f.name() for f in fields])

        feature_count = layer.featureCount()
        show_all = getattr(self, "_show_all_features", False)
        max_rows = feature_count if show_all else limit

        for i, feat in enumerate(layer.getFeatures()):
            if i >= max_rows:
                break
            row = [QStandardItem(str(feat[f.name()])) for f in fields]
            model.appendRow(row)
        self.tbwTable.setModel(model)
        self.tbwTable.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers) 

        # 500件超の場合のみボタン表示
        if not show_all and feature_count > limit:
            self.pbAllItems.setVisible(True)
            self.lblAllItems.setVisible(True)
        else:
            self.pbAllItems.setVisible(False)
            self.lblAllItems.setVisible(False)

    def show_all_features_clicked(self):
        """全件表示ボタン押下時の処理"""
        self._show_all_features = True
        layer = self.iface.activeLayer() 
        if isinstance(layer, QgsVectorLayer):
            self._show_attribute_table(layer)

    def toggle_layer_table(self, checked):
        self.wdTable.setVisible(checked)
        if checked:
            self.setMinimumWidth(900)
            self.setMaximumWidth(16777215)
            if self._saved_table_width is not None:
                QTimer.singleShot(10, lambda: self._restore_table_width())
            layer = self.iface.activeLayer()
            self._show_all_features = False  # テーブル表示時もリセット
            if isinstance(layer, QgsVectorLayer):
                self._show_attribute_table(layer)
            else:
                self.tbwTable.setModel(QStandardItemModel())
                self.pbAllItems.setVisible(False)
                self.lblAllItems.setVisible(False)
        else:
            # wdTableの幅を保存してから非表示にする
            self._saved_table_width = self.wdTable.width()
            self.setFixedWidth(280)
            self.pbAllItems.setVisible(False)
            self.lblAllItems.setVisible(False)

    def _restore_table_width(self):
        """wdTableの幅を復元する専用メソッド"""
        if self._saved_table_width is not None and self.wdTable.isVisible():
            # まずwdTableのサイズを設定
            current_height = self.wdTable.height()
            self.wdTable.resize(self._saved_table_width, current_height)
            
            # 親ウィジェット全体の幅も調整
            current_widget_width = self.width()
            if current_widget_width < self._saved_table_width + 280:  # 280は基本パネル幅
                new_width = self._saved_table_width + 280
                self.resize(new_width, self.height())

    def open_qgis_attribute_table(self):
        layer = self.iface.activeLayer() 
        if isinstance(layer, QgsVectorLayer):
            self.iface.showAttributeTable(layer)

    def open_layer_folder(self):
        layer = self.iface.activeLayer() 
        if isinstance(layer, QgsMapLayer) and hasattr(layer, "source"):
            file_path = layer.source().split('|')[0]
            folder_path = os.path.dirname(file_path)
            if os.path.exists(folder_path):
                if sys.platform == "darwin":
                    subprocess.Popen(["open", folder_path])
                elif sys.platform == "win32":
                    os.startfile(folder_path) 
                elif sys.platform.startswith("linux"):
                    subprocess.Popen(["xdg-open", folder_path])

    def toggle_only_selected_layer(self, checked, update_only=False):
        root = QgsProject.instance().layerTreeRoot()
        selected_layer = self.iface.activeLayer() 

        if checked:
            if not update_only:
                # レイヤとグループ両方の可視状態を保存（最初のON時のみ）
                self._layer_visibility_backup = {}
                for child in root.findLayers():
                    layer = child.layer()
                    if layer:
                        # itemVisibilityChecked()を使用して正確なチェック状態を保存
                        self._layer_visibility_backup[layer.id()] = child.itemVisibilityChecked()
                self._group_visibility_backup = {}
                def save_group_visibility(group):
                    self._group_visibility_backup[group.name()] = group.itemVisibilityChecked()
                    for child in group.children():
                        if child.nodeType() == 0:  # 0: Group
                            save_group_visibility(child)
                save_group_visibility(root)
            # レイヤの表示切り替え（毎回実行）
            for child in root.findLayers():
                layer = child.layer()
                if layer:
                    # 選択レイヤまたは「常に表示」レイヤのみ可視
                    visible = (layer == selected_layer) or (layer.id() in self._always_visible_layer_ids)
                    child.setItemVisibilityChecked(visible)
            # 対象レイヤの親グループもすべて可視化
            if selected_layer:
                node = root.findLayer(selected_layer.id())
                parent = node.parent() if node else None
                while parent and parent != root:
                    parent.setItemVisibilityChecked(True)
                    parent = parent.parent()
            # 「常に表示」レイヤの親グループも可視化
            for layer_id in self._always_visible_layer_ids:
                node = root.findLayer(layer_id)
                parent = node.parent() if node else None
                while parent and parent != root:
                    parent.setItemVisibilityChecked(True)
                    parent = parent.parent()
        else:
            # レイヤの可視状態を元に戻す
            for child in root.findLayers():
                layer = child.layer()
                if layer and layer.id() in self._layer_visibility_backup:
                    child.setItemVisibilityChecked(self._layer_visibility_backup[layer.id()])
            # グループの可視状態を元に戻す
            def restore_group_visibility(group):
                if group.name() in self._group_visibility_backup:
                    group.setItemVisibilityChecked(self._group_visibility_backup[group.name()])
                for child in group.children():
                    if child.nodeType() == 0:
                        restore_group_visibility(child)
            restore_group_visibility(root)
            self._layer_visibility_backup = {}
            self._group_visibility_backup = {}

    def _toggle_always_visible_layer(self, layer_id, checked):
        if checked:
            self._always_visible_layer_ids.add(layer_id)
        else:
            self._always_visible_layer_ids.discard(layer_id)
        # 「選択レイヤのみ表示」モード中なら即時反映
        if self.pbLayerView.isChecked():
            self.toggle_only_selected_layer(True, update_only=True)

    def showEvent(self, event):
        """パネルが表示されたときに呼ばれる"""
        super().showEvent(event)
        #self.visibilityChanged.emit(True)
        self.layerPanel = True  # レイヤーパネルの状態を管理するフラグ
        self._saved_table_width = None  # レイヤーパネルの幅を管理するフラグ

        # 親プラグインのボタン状態を更新
        if self.parent_plugin:
            self.parent_plugin.update_layer_panel_button(True)
    
    def hideEvent(self, event):
        """パネルが非表示になったときに呼ばれる"""
        super().hideEvent(event)
        #self.visibilityChanged.emit(False)
        self.layerPanel = False  # レイヤーパネルの状態を管理するフラグ
    
        # 親プラグインのボタン状態を更新
        if self.parent_plugin:
            self.parent_plugin.update_layer_panel_button(False)

    def closeEvent(self, event):
        # 「選択レイヤのみ表示」ボタンがONならOFFにして元に戻す
        if self.pbLayerView.isChecked():
            self.pbLayerView.setChecked(False)  # これでtoggle_only_selected_layer(False)が呼ばれ元に戻る
        super().closeEvent(event)

        self.layerPanel = False  # レイヤーパネルの状態を管理するフラグ
    
        # 親プラグインのボタン状態を更新
        if self.parent_plugin:
            self.parent_plugin.update_layer_panel_button(False)

    def show_view_layer_menu(self, pos):
        menu = QMenu()
        menu.addSection(self.tr("非表示にしないレイヤを選択"))

        root = QgsProject.instance().layerTreeRoot()
        layer_items = []
        for child in root.findLayers():
            layer = child.layer()
            if layer:
                # チェックボックスをQWidgetActionで追加
                cb = QCheckBox(layer.name())
                cb.setChecked(layer.id() in self._always_visible_layer_ids)
                cb.setStyleSheet("QCheckBox { padding-left: 10px; padding-right: 10px; }")
                cb.stateChanged.connect(lambda state, lid=layer.id(): self._toggle_always_visible_layer(lid, state == Qt.Checked))
                action = QWidgetAction(menu)
                action.setDefaultWidget(cb)
                menu.addAction(action)
                layer_items.append(cb)

        menu.addSeparator()
        ok_action = menu.addAction("OK")

        # OKボタンでのみメニューを閉じる
        def close_menu():
            menu.close()
        ok_action.triggered.connect(close_menu)

        # ボタンのグローバル座標にメニュー表示
        menu.exec_(self.pbLayerView.mapToGlobal(pos))

    def toggle_layer_style_panel(self):
        """レイヤスタイルパネルの表示/非表示を切り替え、選択中レイヤを反映"""
        style_panel = self.iface.mainWindow().findChild(QDockWidget, "LayerStyling")

        # 選択中レイヤをアクティブにする
        layer = self.iface.activeLayer() 
        if isinstance(layer, QgsMapLayer):
            self.iface.setActiveLayer(layer)

        if style_panel is not None:
            visible = style_panel.isVisible()
            style_panel.setVisible(not visible)
            self._sync_active_layer = not visible  # ← パネル表示時のみ同期ON
        else:
            print(self.tr("LayerStylingパネルが見つかりませんでした"))

    def open_query_builder(self):
        """選択中レイヤのフィルタ設定ウインドウ（クエリビルダ）を開く"""
        layer = self.iface.activeLayer() 
        if isinstance(layer, QgsVectorLayer):
            dlg = QgsQueryBuilder(layer, self)
            if dlg.exec_():
                subset = dlg.sql()
                layer.setSubsetString(subset)
        else:
            QtWidgets.QMessageBox.warning(self, self.tr("フィルタ"), self.tr("ベクタレイヤを選択してください"))

    def open_export_dialog(self):
        """選択中レイヤのエクスポート（新規ファイルに地物を保存）ダイアログを開く"""
        layer = self.iface.activeLayer() 
        if isinstance(layer, QgsMapLayer):
            self.iface.setActiveLayer(layer)
            # QGIS標準の「新規ファイルに地物を保存」アクションをトリガー
            action = self.iface.mainWindow().findChild(QtWidgets.QAction, "mActionLayerSaveAs")
            if action:
                action.trigger()
            else:
                QtWidgets.QMessageBox.warning(self, self.tr("エクスポート"), self.tr("エクスポートアクションが見つかりませんでした"))
        else:
            QtWidgets.QMessageBox.warning(self, self.tr("エクスポート"), self.tr("ベクタレイヤを選択してください"))

    def toggle_layer_label(self, checked):
        """ラベル表示のON/OFF切り替え。未設定なら最初のフィールドで自動設定"""
        layer = self.iface.activeLayer() 
        if not isinstance(layer, QgsVectorLayer):
            return

        if checked:
            # 既にラベル設定があるか確認
            if not layer.labeling():
                fields = layer.fields()
                if fields:
                    field_name = fields[0].name()
                    settings = QgsPalLayerSettings()
                    settings.fieldName = field_name
                    settings.enabled = True
                    # ラインの場合はplacementを明示的に設定
                    if QgsWkbTypes.geometryType(layer.wkbType()) == QgsWkbTypes.LineGeometry:
                        settings.placement = QgsPalLayerSettings.Line
                    labeling = QgsVectorLayerSimpleLabeling(settings)
                    layer.setLabeling(labeling)
            layer.setLabelsEnabled(True)
        else:
            layer.setLabelsEnabled(False)
        layer.triggerRepaint()

    def show_label_menu(self, pos):
        layer = self.iface.activeLayer() 
        menu = QMenu()

        if isinstance(layer, QgsVectorLayer):
            # ルールベースラベリングかチェック
            existing_labeling = layer.labeling()
            if existing_labeling and not isinstance(existing_labeling, QgsVectorLayerSimpleLabeling):
                # ルールベースラベリングの場合は操作不可
                menu.addAction(self.tr("ルールベース定義のため変更できません")).setEnabled(False)
                menu.addAction(self.tr("レイヤプロパティから設定してください")).setEnabled(False)
            else:
                # 単一定義の場合はフィールド一覧を表示
                fields = layer.fields()
                for field in fields:
                    action = menu.addAction(field.name())
                    action.triggered.connect(lambda checked, fname=field.name(): self.set_label_field(layer, fname))
        else:
            menu.addAction(self.tr("ベクタレイヤを選択してください")).setEnabled(False)

        menu.exec_(self.pbCallLabel.mapToGlobal(pos))

    def set_label_field(self, layer, field_name):
        """指定フィールドでラベル設定（既存スタイルを保持）"""
        if not isinstance(layer, QgsVectorLayer):
            return
        
        # 既存のラベル設定を取得
        existing_labeling = layer.labeling()
        if existing_labeling and isinstance(existing_labeling, QgsVectorLayerSimpleLabeling):
            # 既存の設定をコピー（clone()の代わりにコピーコンストラクタを使用）
            existing_settings = existing_labeling.settings()
            settings = QgsPalLayerSettings(existing_settings)
        else:
            # 新規作成（従来通り）
            settings = QgsPalLayerSettings()
            settings.enabled = True
            # ラインの場合はplacementを明示的に設定
            if QgsWkbTypes.geometryType(layer.wkbType()) == QgsWkbTypes.LineGeometry:
                settings.placement = QgsPalLayerSettings.Line
        
        # フィールド名のみ変更
        settings.fieldName = field_name
        
        # 新しいラベリングを設定
        labeling = QgsVectorLayerSimpleLabeling(settings)
        layer.setLabeling(labeling)
        layer.setLabelsEnabled(True)
        layer.triggerRepaint()
        # ボタンのチェック状態もONにする
        self.pbCallLabel.setChecked(True)

    def open_layer_properties(self):
        """選択中レイヤのレイヤプロパティウインドウを開く"""
        layer = self.iface.activeLayer() 
        if isinstance(layer, QgsMapLayer):
            self.iface.showLayerProperties(layer)
        else:
            QtWidgets.QMessageBox.warning(self, self.tr("レイヤプロパティ"), self.tr("レイヤを選択してください"))

    def zoom_to_layer(self):
        """選択中レイヤの全体範囲にズーム（CRS変換対応）"""
        layer = self.iface.activeLayer() 
        if isinstance(layer, QgsMapLayer):
            extent = layer.extent()
            if extent.isEmpty():
                QtWidgets.QMessageBox.warning(self, self.tr("ズーム"), self.tr("レイヤに地物がありません"))
                return

            # レイヤCRS→プロジェクトCRSへ変換
            layer_crs = layer.crs()
            project_crs = self.iface.mapCanvas().mapSettings().destinationCrs()
            if layer_crs != project_crs:
                transform = QgsCoordinateTransform(layer_crs, project_crs, QgsProject.instance())
                extent = transform.transformBoundingBox(extent)

            self.iface.mapCanvas().setExtent(extent)
            self.iface.mapCanvas().refresh()
        else:
            QtWidgets.QMessageBox.warning(self, self.tr("ズーム"), self.tr("レイヤを選択してください"))

    def open_field_calculator(self):
        """選択中レイヤのフィールド計算機ダイアログを開く（標準アクション利用）"""
        layer = self.iface.activeLayer() 
        if isinstance(layer, QgsVectorLayer):
            self.iface.setActiveLayer(layer)
            # 利用可能なアクション名を順に試す
            action_names = ["mActionFieldCalculator", "mActionOpenFieldCalc"]
            action = None
            for name in action_names:
                action = self.iface.mainWindow().findChild(QtWidgets.QAction, name)
                if action:
                    break
            if action:
                action.trigger()
            else:
                QtWidgets.QMessageBox.warning(self, self.tr("フィールド計算機"), self.tr("フィールド計算機アクションが見つかりませんでした"))
        else:
            QtWidgets.QMessageBox.warning(self, self.tr("フィールド計算機"), self.tr("ベクタレイヤを選択してください"))

    def open_raster_calculator(self):
        """選択中レイヤのフィールド計算機ダイアログを開く（標準アクション利用）"""
        layer = self.iface.activeLayer() 
        if isinstance(layer, QgsRasterLayer):
            self.iface.setActiveLayer(layer)
            # 利用可能なアクション名を順に試す
            action_names = ["mActionShowRasterCalculator"]
            action = None
            for name in action_names:
                action = self.iface.mainWindow().findChild(QtWidgets.QAction, name)
                if action:
                    break
            if action:
                action.trigger()
            else:
                QtWidgets.QMessageBox.warning(self, self.tr("ラスタ計算機"), self.tr("ラスタ計算機アクションが見つかりませんでした"))
        else:
            QtWidgets.QMessageBox.warning(self, self.tr("ラスタ計算機"), self.tr("ラスタレイヤを選択してください"))
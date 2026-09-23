"""
Overlay trong suốt cho nhiều màn hình.

Mỗi QScreen có một cửa sổ riêng vì Windows/Qt không thể ánh xạ chính xác một
cửa sổ duy nhất qua các màn hình có DPI khác nhau. Overlay nhận physical screen
pixels từ Excel/Win32, chọn đúng màn hình rồi đổi sang logical local pixels của
riêng màn hình đó.
"""

from PyQt6.QtCore import Qt, QRect, QRectF, QSize
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPen,
    QFont,
    QFontMetrics,
    QPixmap,
    QPainterPath,
)
from PyQt6.QtWidgets import QApplication, QWidget

from src.gui.mascot_assets import mascot_asset_path, mascot_style


def calculate_callout_rect(target_rect, overlay_width: int, overlay_height: int):
    """Đặt callout ngoài vùng bôi và giữ nó hoàn toàn trong màn hình."""
    x, y, width, height = target_rect
    callout_width = min(258, max(220, overlay_width - 16))
    callout_height = 140
    margin = 8
    gap = 12

    if y >= callout_height + gap + margin:
        callout_y = y - callout_height - gap
    elif overlay_height - (y + height) >= callout_height + gap + margin:
        callout_y = y + height + gap
    else:
        callout_y = max(margin, min(y, overlay_height - callout_height - margin))

    callout_x = max(margin, min(x, overlay_width - callout_width - margin))
    return QRect(callout_x, callout_y, callout_width, callout_height)


class _ScreenOverlay(QWidget):
    """Một surface click-through phủ đúng một QScreen."""

    def __init__(self, screen):
        super().__init__(None)
        self.screen = screen
        self.target_rect = None
        self.badge_text = "👉 THAO TÁC Ở ĐÂY"
        self.visual_state = "teaching"
        self.show_callout = True
        self._pose_cache = {}
        self._scaled_pose_cache = {}

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)

        # Tạo native handle trước để buộc cửa sổ thuộc đúng QScreen/DPI context.
        self.winId()
        handle = self.windowHandle()
        if handle:
            handle.setScreen(screen)
        self.sync_geometry()
        screen.geometryChanged.connect(self.sync_geometry)

    def sync_geometry(self, *_args):
        self.setGeometry(self.screen.geometry())

    def physical_geometry(self):
        """Native/physical rectangle tương ứng với QScreen này."""
        geometry = self.screen.geometry()
        dpr = max(1.0, float(self.screen.devicePixelRatio() or 1.0))
        left = int(geometry.x())
        top = int(geometry.y())
        return (
            left,
            top,
            left + int(round(geometry.width() * dpr)),
            top + int(round(geometry.height() * dpr)),
        )

    def set_physical_target(
        self, rect, badge_text: str, visual_state: str, show_callout: bool = True
    ):
        left, top, _, _ = self.physical_geometry()
        logical_rect = OverlayWindow.physical_to_local_rect(
            rect,
            self.screen.devicePixelRatio(),
            (left, top),
        )
        self.set_local_target(logical_rect, badge_text, visual_state, show_callout)

    def set_local_target(
        self,
        rect,
        badge_text: str,
        visual_state: str = "teaching",
        show_callout: bool = True,
    ):
        changed = False
        if badge_text:
            changed = changed or self.badge_text != badge_text
            self.badge_text = badge_text
        if visual_state:
            changed = changed or self.visual_state != visual_state
            self.visual_state = visual_state
        changed = changed or self.show_callout != bool(show_callout)
        self.show_callout = bool(show_callout)
        normalized = tuple(int(round(value)) for value in rect)
        if self.target_rect != normalized:
            self.target_rect = normalized
            changed = True
        if changed:
            self.update()

    def clear_target(self):
        if self.target_rect is not None:
            self.target_rect = None
            self.update()

    def paintEvent(self, event):
        if not self.target_rect:
            return

        x, y, w, h = self.target_rect
        if w <= 0 or h <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        style = mascot_style(self.visual_state)
        accent = QColor(style.accent)
        dpr = max(1.0, float(self.devicePixelRatioF()))
        half_pixel = 0.5 / dpr
        range_rect = QRectF(
            x + half_pixel,
            y + half_pixel,
            max(0.0, w - 2 * half_pixel),
            max(0.0, h - 2 * half_pixel),
        )

        # Một nét đỏ mảnh, tĩnh và sắc: không glow, không góc dày, không phủ màu
        # lên dữ liệu bên trong vùng cần thao tác.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen = QPen(QColor("#F43F5E"), 1, Qt.PenStyle.SolidLine)
        pen.setCosmetic(True)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawRoundedRect(range_rect, 4, 4)

        if self.show_callout:
            self._draw_callout(painter, range_rect, style, accent)

    def _draw_callout(self, painter, range_rect, style, accent):
        callout = calculate_callout_rect(
            self.target_rect,
            self.width(),
            self.height(),
        )
        bubble = QRect(callout.x(), callout.y(), callout.width(), 56)
        mascot_box = QRect(
            callout.center().x() - 52,
            callout.y() + 38,
            104,
            102,
        )

        milk_tea = QColor("#F2D2AA")
        milk_tea_border = QColor("#C99B68")

        cloud = self._cloud_path(bubble)
        shadow = self._cloud_path(bubble.translated(0, 3))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(77, 47, 27, 48))
        painter.drawPath(shadow)
        painter.setBrush(milk_tea)
        painter.setPen(QPen(milk_tea_border, 1.5))
        painter.drawPath(cloud)

        # Hai hạt mây nối trực tiếp từ đám mây xuống phía trên đầu mascot.
        head_x = callout.center().x() + 28
        painter.setBrush(milk_tea)
        painter.setPen(QPen(milk_tea_border, 1))
        painter.drawEllipse(QRect(head_x, callout.y() + 50, 12, 12))
        painter.drawEllipse(QRect(head_x - 5, callout.y() + 64, 7, 7))

        pixmap = self._pose_cache.get(style.key)
        if pixmap is None:
            pixmap = QPixmap(str(mascot_asset_path(style.key)))
            self._pose_cache[style.key] = pixmap
        if not pixmap.isNull():
            dpr = max(1.0, float(self.devicePixelRatioF()))
            cache_key = (style.key, mascot_box.width(), mascot_box.height(), round(dpr, 2))
            scaled = self._scaled_pose_cache.get(cache_key)
            if scaled is None:
                physical_size = QSize(
                    int(round(mascot_box.width() * dpr)),
                    int(round(mascot_box.height() * dpr)),
                )
                scaled = pixmap.scaled(
                    physical_size,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
                scaled.setDevicePixelRatio(dpr)
                self._scaled_pose_cache[cache_key] = scaled
            logical_width = scaled.width() / scaled.devicePixelRatio()
            logical_height = scaled.height() / scaled.devicePixelRatio()
            pose_x = int(round(mascot_box.center().x() - logical_width / 2))
            pose_y = int(round(mascot_box.bottom() - logical_height))
            painter.drawPixmap(pose_x, pose_y, scaled)

        text_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        text_rect = bubble.adjusted(25, 10, -17, -8)
        painter.setFont(text_font)
        metrics = QFontMetrics(text_font)
        message = metrics.elidedText(
            self.badge_text,
            Qt.TextElideMode.ElideRight,
            text_rect.width(),
        )
        dot = QColor(accent)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot)
        painter.drawEllipse(QRect(text_rect.x() - 12, text_rect.center().y() - 3, 6, 6))
        painter.setPen(QColor("#4A3025"))
        painter.drawText(
            text_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            message,
        )

    @staticmethod
    def _cloud_path(rect):
        """Tạo bong bóng đám mây gọn, mềm và không cần ảnh nền phụ."""
        path = QPainterPath()
        body = QRectF(rect.x() + 7, rect.y() + 12, rect.width() - 12, rect.height() - 17)
        path.addRoundedRect(body, 18, 18)
        for lobe in (
            QRectF(rect.x() + 19, rect.y() + 5, 42, 34),
            QRectF(rect.x() + 49, rect.y(), 54, 42),
            QRectF(rect.x() + 91, rect.y() + 4, 48, 36),
            QRectF(rect.right() - 51, rect.y() + 8, 42, 32),
        ):
            ellipse = QPainterPath()
            ellipse.addEllipse(lobe)
            path = path.united(ellipse)
        return path


class OverlayWindow(QWidget):
    """Bộ điều phối overlay qua toàn bộ desktop nhiều màn hình."""

    def __init__(self):
        # QWidget quản lý này luôn ẩn; các _ScreenOverlay mới là cửa sổ hiển thị.
        super().__init__(None)
        self._surfaces = []
        self._visible_requested = False
        self.target_rect = None  # physical global rect
        self.badge_text = "👉 THAO TÁC Ở ĐÂY"
        self.visual_state = "teaching"

        app = QApplication.instance()
        if app:
            for screen in app.screens():
                self._add_screen(screen)
            app.screenAdded.connect(self._add_screen)
            app.screenRemoved.connect(self._remove_screen)

    def _add_screen(self, screen):
        if any(surface.screen is screen for surface in self._surfaces):
            return
        surface = _ScreenOverlay(screen)
        self._surfaces.append(surface)
        if self._visible_requested:
            surface.show()
        if self.target_rect:
            self._route_physical_target(self.target_rect)

    def _remove_screen(self, screen):
        for surface in list(self._surfaces):
            if surface.screen is screen:
                surface.close()
                self._surfaces.remove(surface)

    def show(self):
        self._visible_requested = True
        for surface in self._surfaces:
            surface.show()

    def close(self):
        for surface in list(self._surfaces):
            surface.close()
        self._surfaces.clear()
        return super().close()

    def set_target_rect(
        self,
        rect,
        is_physical_pixels: bool = True,
        badge_text: str = "",
        visual_state: str = "teaching",
    ):
        if badge_text:
            self.badge_text = badge_text
        if visual_state:
            self.visual_state = visual_state
        if not rect:
            self.clear_target()
            return

        self.target_rect = tuple(rect)
        if is_physical_pixels:
            self._route_physical_target(self.target_rect)
        else:
            self._route_logical_target(self.target_rect)

    def _route_physical_target(self, rect):
        selected = self.surface_for_physical_rect(rect, self._surfaces)
        for surface in self._surfaces:
            left, top, right, bottom = surface.physical_geometry()
            x, y, width, height = rect
            intersect_left = max(x, left)
            intersect_top = max(y, top)
            intersect_right = min(x + width, right)
            intersect_bottom = min(y + height, bottom)
            if intersect_right <= intersect_left or intersect_bottom <= intersect_top:
                surface.clear_target()
                continue
            visible_piece = (
                intersect_left,
                intersect_top,
                intersect_right - intersect_left,
                intersect_bottom - intersect_top,
            )
            surface.set_physical_target(
                visible_piece,
                self.badge_text,
                self.visual_state,
                show_callout=surface is selected,
            )

    def _route_logical_target(self, rect):
        x, y, w, h = rect
        center_x = x + w / 2
        center_y = y + h / 2
        selected = None
        for surface in self._surfaces:
            geometry = surface.screen.geometry()
            if geometry.contains(int(center_x), int(center_y)):
                selected = surface
                local = (x - geometry.x(), y - geometry.y(), w, h)
                surface.set_local_target(local, self.badge_text, self.visual_state)
            else:
                surface.clear_target()
        if selected is None:
            self.clear_target()

    @staticmethod
    def surface_for_physical_rect(rect, surfaces):
        """Chọn monitor chứa tâm ô; fallback sang monitor giao nhau nhiều nhất."""
        x, y, w, h = rect
        center_x = x + w / 2
        center_y = y + h / 2
        best_surface = None
        best_area = 0

        for surface in surfaces:
            left, top, right, bottom = surface.physical_geometry()
            if left <= center_x < right and top <= center_y < bottom:
                return surface

            overlap_w = max(0, min(x + w, right) - max(x, left))
            overlap_h = max(0, min(y + h, bottom) - max(y, top))
            area = overlap_w * overlap_h
            if area > best_area:
                best_area = area
                best_surface = surface
        return best_surface

    @staticmethod
    def physical_to_local_rect(
        rect, dpr: float, physical_origin=(0, 0), overlay_origin=None
    ):
        """Đổi global physical pixels sang local logical pixels của một monitor."""
        # overlay_origin là tên tham số của bản cũ; giữ tương thích với caller/test.
        if overlay_origin is not None:
            physical_origin = overlay_origin
        x, y, w, h = rect
        scale = max(1.0, float(dpr or 1.0))
        origin_x, origin_y = physical_origin
        left = int(round((x - origin_x) / scale))
        top = int(round((y - origin_y) / scale))
        right = int(round((x + w - origin_x) / scale))
        bottom = int(round((y + h - origin_y) / scale))
        return (
            left,
            top,
            max(0, right - left),
            max(0, bottom - top),
        )

    def clear_target(self):
        self.target_rect = None
        for surface in self._surfaces:
            surface.clear_target()

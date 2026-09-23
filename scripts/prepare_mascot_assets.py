"""Tách 5 pose mascot từ ảnh nguồn thành PNG nền trong suốt.

Ảnh nguồn có nền trắng và các nhãn mô tả rời khỏi nhân vật. Script giữ lại
component của nhân vật (cùng các hiệu ứng như bóng đèn/tia sáng), tạo alpha từ
độ lệch màu so với nền trắng rồi cắt sát nội dung. Nhờ vậy asset dùng trong Qt
không mang theo nhãn chữ của ảnh tham chiếu.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage


POSES = {
    "welcome": {
        "crop": (0, 0, 520, 520),
        "extra": lambda area, x, y, w, h, cx, cy: False,
    },
    "thinking": {
        "crop": (520, 0, 1020, 540),
        # Bóng đèn và các tia sáng nằm rời khỏi component chính.
        "extra": lambda area, x, y, w, h, cx, cy: area >= 85 and cy < 140,
    },
    "teaching": {
        "crop": (980, 0, 1536, 540),
        "extra": lambda area, x, y, w, h, cx, cy: False,
    },
    "success": {
        "crop": (230, 470, 860, 1024),
        # Giữ các tia vàng quanh pose hoàn thành.
        "extra": lambda area, x, y, w, h, cx, cy: area >= 180 and 80 < cy < 235,
    },
    "warning": {
        "crop": (800, 470, 1400, 1024),
        "extra": lambda area, x, y, w, h, cx, cy: False,
    },
}


def _extract_pose(source_bgr: np.ndarray, spec: dict) -> Image.Image:
    x1, y1, x2, y2 = spec["crop"]
    crop = source_bgr[y1:y2, x1:x2]

    # Nền ảnh gần trắng. Ngưỡng 28 loại banding/nhiễu sáng của nền nhưng vẫn
    # nối đủ thân nhân vật nhờ các vùng da, kính và quần áo có tương phản cao.
    white_distance = 255 - crop.min(axis=2)
    seed = (white_distance > 28).astype(np.uint8)
    count, labels, stats, centers = cv2.connectedComponentsWithStats(seed, 8)
    if count <= 1:
        raise RuntimeError("Không tìm thấy nhân vật trong vùng cắt.")

    main_label = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    selected = labels == main_label
    for label in range(1, count):
        if label == main_label:
            continue
        x, y, w, h, area = (int(v) for v in stats[label])
        cx, cy = (float(v) for v in centers[label])
        if spec["extra"](area, x, y, w, h, cx, cy):
            selected |= labels == label

    # Bỏ các vệt nền mảnh, sau đó lấp vùng sáng nằm bên trong silhouette (lòng
    # mắt, giày trắng). Nếu chỉ suy alpha từ màu, các chi tiết trắng sẽ bị thủng
    # khi hiển thị trên thẻ tối.
    selected = cv2.morphologyEx(
        selected.astype(np.uint8),
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
    )
    padded = cv2.copyMakeBorder(selected, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    flood = padded.copy()
    cv2.floodFill(flood, None, (0, 0), 1)
    holes = (flood[1:-1, 1:-1] == 0).astype(np.uint8)
    solid = np.maximum(selected, holes)
    alpha = cv2.GaussianBlur(solid * 255, (5, 5), 0.72)

    ys, xs = np.where(alpha > 2)
    if not len(xs):
        raise RuntimeError("Alpha rỗng sau khi tách nền.")
    pad = 10
    left = max(0, int(xs.min()) - pad)
    top = max(0, int(ys.min()) - pad)
    right = min(crop.shape[1], int(xs.max()) + pad + 1)
    bottom = min(crop.shape[0], int(ys.max()) + pad + 1)

    rgba = cv2.cvtColor(crop, cv2.COLOR_BGR2RGBA)
    # Lan màu biên từ foreground ra vùng alpha mềm để không xuất hiện viền
    # trắng khi QPixmap thu nhỏ asset trên nền tối.
    _, nearest = ndimage.distance_transform_edt(solid == 0, return_indices=True)
    edge = (solid == 0) & (alpha > 0)
    rgba[edge, :3] = rgba[nearest[0][edge], nearest[1][edge], :3]
    rgba[:, :, 3] = alpha
    rgba = rgba[top:bottom, left:right]
    return Image.fromarray(rgba, "RGBA")


def prepare(source: Path, output_dir: Path) -> list[Path]:
    source_bgr = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if source_bgr is None:
        raise FileNotFoundError(source)

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for name, spec in POSES.items():
        image = _extract_pose(source_bgr, spec)
        output = output_dir / f"pose-{name}.png"
        image.save(output, optimize=True)
        outputs.append(output)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    for output in prepare(args.source, args.output_dir):
        print(output)


if __name__ == "__main__":
    main()

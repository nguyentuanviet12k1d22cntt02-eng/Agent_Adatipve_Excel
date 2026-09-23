# Realtime Agentic Excel Teaching Model

## Mục tiêu

Teaching Agent quan sát trạng thái Excel theo thời gian thực, suy luận bước học
hiện tại, chọn mức hỗ trợ phù hợp và kiểm chứng kết quả sau mỗi thao tác. Agent
không tự ghi đáp án vào workbook trong chế độ học tập.

## Vòng lặp tác nhân

```text
Excel COM + chuột
        ↓
OBSERVE: workbook, sheet, active cell, selection, value, format
        ↓
INTERPRET: đối chiếu LessonStep và xác định lỗi/tiến độ
        ↓
DECIDE: im lặng, định hướng, chỉ công cụ hay khoanh vùng
        ↓
ACT: cập nhật CompanionWidget và OverlayWindow
        ↓
VERIFY: đọc lại vùng mục tiêu và chỉ xác nhận khi điều kiện đạt
```

Vòng poll của ứng dụng chạy mỗi 300 ms. Nhánh realtime chỉ dùng dữ liệu có cấu
trúc và quy tắc xác định, không gọi LLM. LLM chỉ được dùng khi chấm câu trả lời
giải thích của học viên.

## Thành phần

- `ExcelMonitor`: cảm biến Excel COM và tọa độ vùng chọn.
- `MouseSpeedTracker`: tín hiệu ngập ngừng/bối rối.
- `LessonPlan` / `LessonStep` / `ProcedureAction`: giáo án dữ liệu và các vi-bước,
  tách khỏi logic agent.
- `RealtimeTeachingAgent`: state machine và chính sách sư phạm.
- `AITutorMCPAgent`: adapter gọi các MCP tools.
- `CompanionWidget`: tiến độ, yêu cầu, phản hồi và điều khiển bài học.
- `OverlayWindow`: khoanh chính xác mục tiêu của thao tác hiện tại và hiển thị mascot.

## Trạng thái phiên học

```text
IDLE
  → WAITING_FOR_EXCEL
  → WAITING_FOR_WORKBOOK
  → WAITING_FOR_SHEET
  → OBSERVING
  → STEP_CORRECT
  → OBSERVING (bước kế tiếp)
  → COMPLETED

Bất kỳ trạng thái đang học nào ↔ PAUSED
```

## Chính sách trợ giúp

- Mỗi bước được tách thành chuỗi `SELECT_RANGE → MANUAL → VERIFY_RESULT` khi
  thao tác có nhiều công đoạn.
- `SELECT_RANGE` chỉ hoàn thành khi địa chỉ A1 và số Area khớp tuyệt đối; vùng
  thiếu/thừa ô hoặc vùng rời rạc đều bị từ chối.
- Mức 1: câu hỏi định hướng và nhắc mục tiêu.
- Mức 2: chỉ rõ công cụ/thao tác khi ngập ngừng hoặc sai lặp lại.
- Mức 3: bổ sung gợi ý chi tiết; khung đỏ luôn bám mục tiêu của vi-bước hiện tại.
- Có tiến bộ: giảm trợ giúp về mức 1.
- Làm đúng: xác nhận ngắn rồi tự chuyển bước sau 1,2 giây; bước có câu hỏi củng
  cố vẫn chờ học viên bấm Tiếp tục.
- Agent có quyền im lặng khi học viên đang tiến triển đúng.

### Ví dụ quy trình định dạng Text

1. Chọn đúng chính xác `F7:F10`; agent xác minh Selection realtime.
2. Mở thẻ **Home**; agent đọc trạng thái `Selected` của tab qua Microsoft
   Active Accessibility và tự chuyển sau hai mẫu quan sát liên tiếp.
3. Mở danh sách **Number Format**; agent theo dõi trạng thái focus/expanded của
   control, đồng thời luôn giữ nút xác nhận thủ công làm phương án dự phòng.
4. Chọn **Text**; agent tự đọc `NumberFormat` của cả bốn ô và chỉ hoàn thành khi
   tất cả đều là `@`.

Tên Home và Number Format được lấy qua `GetLabelMso`, nên observer không phụ
thuộc ngôn ngữ hiển thị Office. Popup Number Format có thể tồn tại rất ngắn hoặc
không phát đầy đủ trạng thái Accessibility ở một số bản Office; vì vậy thao tác
này có nút xác nhận dự phòng rõ ràng. Vùng chọn và kết quả cuối luôn được kiểm
chứng tự động qua Excel COM. Nếu agent bỏ lỡ popup nhưng kết quả Text đã đúng,
checklist ghi **Đạt theo kết quả**; đây là suy luận outcome-first, không phải lời
khẳng định rằng agent đã quan sát được chính xác từng cú nhấp chuột.

## Độ chính xác khung vùng

- Chỉ đo trên sheet đang active và chỉ vẽ phần range đang nhìn thấy.
- Tọa độ Excel được giữ ở physical pixel; `EXCEL7` được đọc trong DPI context
  Per-Monitor V2 để tránh Windows DPI virtualization.
- Sai số công thức được loại bằng `RangeFromPoint`: đo bốn biên và xác minh bốn
  góc trong cùng của range thay vì chỉ kiểm tra tâm.
- Làm tròn theo hai cạnh trái/phải, trên/dưới; overlay dùng nét đỏ cosmetic 1
  physical pixel, không padding và hỗ trợ vùng đi qua nhiều màn hình.
- Probe tích hợp trên workbook Bài 08 kiểm tra zoom 55/85/100/125%, cuộn hai
  trục và frozen panes; mỗi case chỉ đạt khi bốn góc map đúng ô biên.

## Giáo án thử nghiệm

### Bài 07 — 7 bước

1. Địa chỉ B8.
2. Cột, dòng và giá trị của B8.
3. Hoàn thiện C9:F9.
4. Địa chỉ D12:E12.
5. Tên cột.
6. Số dòng.
7. Giá trị ô.

### Bài 08 — 10 bước

1. Quan sát hiện tượng mất số 0.
2. Định dạng F7:F10 thành Text.
3. Nhập số điện thoại.
4. Định dạng H7:H10 thành Text.
5. Nhập CCCD.
6. Kiểm tra dấu thập phân.
7. Kiểm tra dữ liệu Date.
8. Định dạng Mã NV ở bảng tổng hợp.
9. Định dạng SĐT và CCCD ở bảng tổng hợp.
10. Hoàn thiện bảng và đối chiếu đáp án mẫu.

## Ràng buộc an toàn

- Không gọi tool ghi dữ liệu trong vòng lặp dạy học.
- Không chuyển bước chỉ vì học viên bấm nút; phải kiểm chứng Excel trước.
- Không suy luận từ màu/căn lề màn hình nếu có thể đọc kiểu dữ liệu qua COM.
- Khi Excel bận hoặc không đọc được, chờ và thử lại thay vì báo sai.
- Ảnh màn hình/UI Automation là lớp mở rộng, không thay thế dữ liệu COM.

## Giai đoạn kế tiếp

1. Mở rộng observer Accessibility cho menu/hộp thoại Ribbon ngoài Number Format.
2. Lưu tiến độ phiên học và thống kê lỗi thường gặp.
3. Thêm screenshot/Vision fallback cho thao tác ngoài vùng bảng tính.
4. Cho giáo viên tạo LessonPlan mới mà không sửa code agent.

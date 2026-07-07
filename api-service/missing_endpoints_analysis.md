# 🔍 Phân tích toàn bộ Endpoints còn thiếu — api-service

## Tổng quan hiện trạng

### ✅ Modules ĐÃ HOÀN THÀNH (có controller + service)

| Module | Controller | Service | Endpoints | Ghi chú |
|---|---|---|---|---|
| **Auth** | 106 lines | 388 lines | 7 endpoints | Login, Refresh, Logout, Me, Change PW, Reset PW (OTP flow) |
| **Users** | 94 lines | 133 lines | 5 endpoints | List, Get, Update, Change PW, Assign Role, Deactivate |
| **Employees** | 70 lines | 421 lines | 6 endpoints | Get by ID/Code, List, Update, Delete, Activate |
| **Departments** | 80 lines | 139 lines | 7 endpoints | CRUD + Get by Code + Deactivate |
| **Positions** | 77 lines | 128 lines | 7 endpoints | CRUD + Get by Code + Deactivate |
| **Work Shifts** | 191 lines | 446 lines | 13 endpoints | CRUD + Activate/Deactivate + Assignment CRUD + Current Shift + Change Shift |
| **Attendance** | 52 lines | 344 lines | 3 endpoints | Create Event (AI), List Events, Get Event |
| **Face Profiles** | 62 lines | 158 lines | 5 endpoints | Get by Employee/ID, List, Update, Revoke |
| **Documents** | 63 lines | 217 lines | 4 endpoints | Upload, List, Get, Delete |
| **Chat** | 130 lines | 482 lines | 7 endpoints | Create/List/Delete Conversation, List/Send Message, New Message, Stream |
| **Onboarding** | 83 lines | 415 lines | 4 endpoints | Start Session, Upload Images, Commit, Cancel |
| **Upload Avatar** | 60 lines | inline | 2 endpoints | Upload Avatar, Upload Image |

**Tổng: 70 endpoints đã hoạt động**

---

### ❌ Modules CÓ MODEL + SCHEMA nhưng CHƯA CÓ LOGIC (controller trống, service 0 lines)

| Module | Model | Schema | Controller | Service | Status |
|---|---|---|---|---|---|
| **Leaves** | ✅ 233 lines | ✅ 173 lines | ❌ trống | ❌ 0 lines | **Chưa có gì** |
| **Corrections** | ✅ 192 lines | ✅ 139 lines | ❌ trống | ❌ 0 lines | **Chưa có gì** |
| **Notifications** | ✅ 86 lines | ✅ 79 lines | ❌ trống | ❌ 0 lines | **Chưa có gì** |
| **Audit** | ✅ 83 lines | ✅ 51 lines | ❌ trống | ❌ 0 lines | **Chưa có gì** |
| **System Settings** | ✅ 66 lines | ✅ 76 lines | ❌ trống | ❌ 0 lines | **Chưa có gì** |
| **Reports** | ❌ không có | ❌ trống | ❌ trống | ❌ 0 lines | **Chưa có gì** |

---

### ⚠️ Modules đã có nhưng THIẾU endpoint

| Module | Endpoint thiếu | Mô tả |
|---|---|---|
| **Attendance** | `GET /records`, `GET /records/{id}`, `PATCH /records/{id}` | Bảng công chính thức — hiện chỉ có Events, chưa expose Records |
| **Attendance** | `DELETE /events/{id}` | Xóa event (admin) |
| **Employees** | `GET /employees/{id}/subordinates` | Danh sách nhân viên dưới quyền |
| **Departments** | `GET /departments/{id}/managers` | Danh sách manager của phòng ban |
| **Documents** | `PATCH /documents/{id}` | Cập nhật title/allowed_roles |

---

## 📋 DANH SÁCH TOÀN BỘ ENDPOINTS CẦN XÂY DỰNG

### 1. 🔥 Attendance Records (bổ sung vào module attendance hiện có)

> [!IMPORTANT]
> Đây là module quan trọng nhất — "sổ công" chính thức mà cả dashboard lẫn agent đều cần.

| # | Method | Path | Auth | Mô tả |
|---|---|---|---|---|
| 1 | `GET` | `/attendance/records` | admin, hr, manager, employee* | List records (filter: employee_id, work_date, status, source) |
| 2 | `GET` | `/attendance/records/{record_id}` | admin, hr, manager | Get chi tiết 1 record |
| 3 | `PATCH` | `/attendance/records/{record_id}` | admin, hr | Sửa record (manual edit) |
| 4 | `GET` | `/attendance/records/summary` | admin, hr, manager | Tổng hợp: tổng ngày present/late/absent trong khoảng |

> *employee chỉ xem record của chính mình

**Schemas đã có sẵn:** `AttendanceRecordRead`, `AttendanceRecordUpdate`, `AttendanceRecordListQuery`

---

### 2. 🔥 Leave Management

| # | Method | Path | Auth | Mô tả |
|---|---|---|---|---|
| 5 | `POST` | `/leaves/requests` | employee | Tạo đơn xin nghỉ phép |
| 6 | `GET` | `/leaves/requests` | admin, hr, manager, employee* | List đơn nghỉ phép |
| 7 | `GET` | `/leaves/requests/{request_id}` | admin, hr, manager, owner | Chi tiết đơn |
| 8 | `PATCH` | `/leaves/requests/{request_id}` | owner (status=pending) | Sửa đơn khi chưa duyệt |
| 9 | `POST` | `/leaves/requests/{request_id}/cancel` | owner | Hủy đơn |
| 10 | `POST` | `/leaves/requests/{request_id}/review` | manager, hr, admin | Duyệt/từ chối đơn |
| 11 | `GET` | `/leaves/requests/{request_id}/logs` | admin, hr, manager, owner | Timeline duyệt đơn |
| 12 | `GET` | `/leaves/types` | all authenticated | Danh sách loại nghỉ phép |
| 13 | `POST` | `/leaves/types` | admin, hr | Tạo loại nghỉ phép mới |
| 14 | `PATCH` | `/leaves/types/{id}` | admin, hr | Sửa loại nghỉ phép |
| 15 | `GET` | `/leaves/balance/{employee_id}` | hr, manager, owner | Số ngày phép còn lại |

**Schemas đã có:** `LeaveRequestCreate`, `LeaveRequestRead`, `LeaveRequestUpdate`, `LeaveRequestListQuery`, `LeaveTypeCreate`, `LeaveTypeRead`, `LeaveTypeUpdate`, `ReviewLeaveRequest`, `LeaveApprovalLogRead`

---

### 3. 🔥 Attendance Corrections

| # | Method | Path | Auth | Mô tả |
|---|---|---|---|---|
| 16 | `POST` | `/corrections/requests` | employee | Tạo đơn sửa công |
| 17 | `GET` | `/corrections/requests` | admin, hr, manager, employee* | List đơn sửa công |
| 18 | `GET` | `/corrections/requests/{request_id}` | admin, hr, manager, owner | Chi tiết đơn |
| 19 | `PATCH` | `/corrections/requests/{request_id}` | owner (status=pending) | Sửa đơn |
| 20 | `POST` | `/corrections/requests/{request_id}/cancel` | owner | Hủy đơn |
| 21 | `POST` | `/corrections/requests/{request_id}/review` | manager, hr, admin | Duyệt/từ chối + apply vào attendance_record |
| 22 | `GET` | `/corrections/requests/{request_id}/logs` | admin, hr, manager, owner | Timeline duyệt |

**Schemas đã có:** `AttendanceCorrectionRequestCreate`, `AttendanceCorrectionRequestRead`, `CorrectionListQuery`, `ReviewCorrectionRequest`, `AttendanceCorrectionLogRead`

---

### 4. ⚡ Notifications

| # | Method | Path | Auth | Mô tả |
|---|---|---|---|---|
| 23 | `GET` | `/notifications` | authenticated user | List thông báo của user hiện tại |
| 24 | `GET` | `/notifications/{id}` | owner | Chi tiết thông báo |
| 25 | `PATCH` | `/notifications/{id}/read` | owner | Đánh dấu đã đọc |
| 26 | `POST` | `/notifications/read-all` | owner | Đánh dấu tất cả đã đọc |
| 27 | `GET` | `/notifications/unread-count` | owner | Số thông báo chưa đọc (cho badge UI) |
| 28 | `DELETE` | `/notifications/{id}` | owner | Xóa thông báo |
| 29 | `POST` | `/notifications` | system/admin | Tạo thông báo (internal) |

**Schemas đã có:** `NotificationCreate`, `NotificationRead`, `NotificationUpdate`, `MarkNotificationReadRequest`, `NotificationListQuery`

---

### 5. ⚡ Audit Logs

| # | Method | Path | Auth | Mô tả |
|---|---|---|---|---|
| 30 | `GET` | `/audit-logs` | admin | List audit logs (filter: user, action, object_type, date) |
| 31 | `GET` | `/audit-logs/{log_id}` | admin | Chi tiết 1 log entry |
| 32 | `POST` | `/audit-logs` | internal/system | Ghi audit log (helper cho các service khác gọi) |

**Schemas đã có:** `AuditLogCreate`, `AuditLogRead`, `AuditLogListQuery`

---

### 6. ⚡ System Settings

| # | Method | Path | Auth | Mô tả |
|---|---|---|---|---|
| 33 | `GET` | `/system/settings` | admin | List tất cả settings |
| 34 | `GET` | `/system/settings/{key}` | admin | Get setting by key |
| 35 | `POST` | `/system/settings` | admin | Tạo setting mới |
| 36 | `PATCH` | `/system/settings/{key}` | admin | Cập nhật setting |
| 37 | `DELETE` | `/system/settings/{key}` | admin | Xóa setting |
| 38 | `POST` | `/system/settings/bulk` | admin | Bulk upsert settings |

**Schemas đã có:** `SystemSettingCreate`, `SystemSettingRead`, `SystemSettingUpdate`, `SystemSettingBulkUpsertRequest`, `SystemSettingListQuery`

---

### 7. ⚡ Holidays

| # | Method | Path | Auth | Mô tả |
|---|---|---|---|---|
| 39 | `GET` | `/holidays` | all authenticated | List ngày lễ (filter: year, date_from, date_to) |
| 40 | `GET` | `/holidays/{id}` | all authenticated | Chi tiết ngày lễ |
| 41 | `POST` | `/holidays` | admin | Tạo ngày lễ mới |
| 42 | `PATCH` | `/holidays/{id}` | admin | Sửa ngày lễ |
| 43 | `DELETE` | `/holidays/{id}` | admin | Xóa ngày lễ |

**Schemas cần tạo:** `HolidayCreate`, `HolidayRead`, `HolidayUpdate`, `HolidayListQuery`

---

### 8. 📊 Reports (Schema + Model chưa có)

| # | Method | Path | Auth | Mô tả |
|---|---|---|---|---|
| 44 | `GET` | `/reports/attendance-summary` | admin, hr, manager | Tổng hợp chấm công theo phòng ban/tháng |
| 45 | `GET` | `/reports/leave-summary` | admin, hr | Tổng hợp nghỉ phép theo phòng ban |
| 46 | `GET` | `/reports/late-ranking` | admin, hr, manager | Bảng xếp hạng đi trễ |
| 47 | `GET` | `/reports/monthly/{employee_id}` | admin, hr, manager, owner | Báo cáo công tháng cá nhân |

**Schemas cần tạo mới hoàn toàn** — response là dữ liệu tổng hợp (aggregate), không phải CRUD đơn thuần.

---

### 9. Bổ sung cho modules hiện có

| # | Method | Path | Module | Auth | Mô tả |
|---|---|---|---|---|---|
| 48 | `GET` | `/employees/{id}/subordinates` | Employees | manager, hr, admin | Danh sách nhân viên cấp dưới |
| 49 | `GET` | `/departments/{id}/managers` | Departments | hr, admin | Managers của phòng ban |
| 50 | `PATCH` | `/documents/{id}` | Documents | admin | Cập nhật metadata document |

---

## 📊 Tổng kết

| Nhóm | Số endpoints mới | Schemas sẵn? | Effort |
|---|---|---|---|
| **Attendance Records** | 4 | ✅ Có đầy đủ | 🟢 Thấp |
| **Leaves** | 11 | ✅ Có đầy đủ | 🟡 Trung bình |
| **Corrections** | 7 | ✅ Có đầy đủ | 🟡 Trung bình |
| **Notifications** | 7 | ✅ Có đầy đủ | 🟢 Thấp-TB |
| **Audit Logs** | 3 | ✅ Có đầy đủ | 🟢 Thấp |
| **System Settings** | 6 | ✅ Có đầy đủ | 🟢 Thấp |
| **Holidays** | 5 | ❌ Cần tạo | 🟢 Thấp |
| **Reports** | 4 | ❌ Cần tạo | 🔴 Cao |
| **Bổ sung modules cũ** | 3 | Partial | 🟢 Thấp |
| **TỔNG** | **~50 endpoints** | | |

> [!TIP]
> **Thứ tự ưu tiên implement:**
> 1. **Attendance Records** (4 endpoints) — dashboard cần nhất, effort thấp
> 2. **Leaves** (11 endpoints) — nghiệp vụ cốt lõi HR
> 3. **Corrections** (7 endpoints) — phụ thuộc Attendance Records
> 4. **Holidays** (5 endpoints) — Leaves cần holiday để tính ngày nghỉ thực
> 5. **Notifications** (7 endpoints) — UX quan trọng cho mobile/web
> 6. **System Settings** (6 endpoints) — admin config
> 7. **Audit Logs** (3 endpoints) — compliance/security
> 8. **Reports** (4 endpoints) — aggregate queries phức tạp, làm sau cùng

> [!IMPORTANT]
> **Lưu ý**: Tất cả 6 module trống đều đã có sẵn đầy đủ **Models** (ORM) + **Schemas** (Pydantic) + **Enums**. Công việc chính là viết **Service** (business logic + DB queries) và **Controller** (FastAPI routes), sau đó register vào `routers.py`.
